from __future__ import annotations

from copy import deepcopy

from deal_intel.schema.qualification import compute_qualification_latest
from deal_intel.schema.qualification_extraction import (
    MAX_EVIDENCE_CHARS,
    build_qualification_extraction_contract,
    normalize_qualification_extraction,
    render_qualification_extraction_prompt_block,
)
from deal_intel.schema.qualification_framework import get_qualification_template
from deal_intel.tools.qualification_snapshot import rebuild_latest_snapshots


def test_extraction_contract_lists_enabled_dimensions_only() -> None:
    framework = get_qualification_template("simple_b2b").model_copy(deep=True)
    framework.dimensions["next_step"].enabled = False

    contract = build_qualification_extraction_contract(framework)

    assert contract["framework_key"] == "simple_b2b"
    assert [dimension["key"] for dimension in contract["dimensions"]] == [
        "business_need",
        "buyer_owner",
    ]
    assert "Omit missing dimensions" in " ".join(contract["rules"])


def test_prompt_block_contains_framework_dimensions_and_output_hint() -> None:
    framework = get_qualification_template("pilot_poc")

    prompt = render_qualification_extraction_prompt_block(framework)

    assert "Active qualification framework: Pilot / PoC Qualification" in prompt
    assert "Return JSON with a top-level `qualification` object." in prompt
    assert "- success_criteria:" in prompt
    assert "- conversion_path:" in prompt


def test_normalize_qualification_extraction_keeps_valid_wrapped_payload() -> None:
    framework = get_qualification_template("simple_b2b")

    result = normalize_qualification_extraction(
        {
            "qualification": {
                "business_need": {
                    "score": 5,
                    "evidence": "Customer says manual reporting blocks renewal.",
                    "reason": "Pain and urgency are explicit.",
                    "confidence": "high",
                },
                "buyer_owner": {"score": 3.0},
            }
        },
        framework=framework,
    )

    assert result == {
        "ok": True,
        "qualification": {
            "business_need": {
                "score": 5,
                "evidence": "Customer says manual reporting blocks renewal.",
                "reason": "Pain and urgency are explicit.",
                "confidence": "high",
            },
            "buyer_owner": {"score": 3},
        },
        "warnings": [],
    }


def test_normalize_qualification_extraction_accepts_direct_dimension_map() -> None:
    framework = get_qualification_template("simple_b2b")

    result = normalize_qualification_extraction(
        {"business_need": {"score": 4}, "next_step": 2},
        framework=framework,
    )

    assert result["qualification"] == {
        "business_need": {"score": 4},
        "next_step": {"score": 2},
    }


def test_normalize_drops_unknown_disabled_and_invalid_scores() -> None:
    framework = get_qualification_template("simple_b2b").model_copy(deep=True)
    framework.dimensions["next_step"].enabled = False

    result = normalize_qualification_extraction(
        {
            "qualification": {
                "business_need": {"score": 2},
                "next_step": {"score": 4},
                "made_up": {"score": 5},
                "buyer_owner": {"score": 6},
            }
        },
        framework=framework,
    )

    assert result["qualification"] == {"business_need": {"score": 2}}
    assert [warning["code"] for warning in result["warnings"]] == [
        "disabled_dimension",
        "unknown_dimension",
        "score_out_of_range",
    ]


def test_normalize_rejects_bool_fractional_and_non_numeric_scores() -> None:
    framework = get_qualification_template("simple_b2b")

    result = normalize_qualification_extraction(
        {
            "qualification": {
                "business_need": {"score": True},
                "buyer_owner": {"score": 2.5},
                "next_step": {"score": "high"},
            }
        },
        framework=framework,
    )

    assert result["qualification"] == {}
    assert [warning["code"] for warning in result["warnings"]] == [
        "invalid_score",
        "fractional_score",
        "invalid_score",
    ]


def test_normalize_redacts_secret_like_text_and_truncates_long_evidence() -> None:
    framework = get_qualification_template("simple_b2b")
    secret = "mongodb+srv://user:pass@example.mongodb.net/deal_intel"
    long_text = "A" * (MAX_EVIDENCE_CHARS + 20)

    result = normalize_qualification_extraction(
        {
            "qualification": {
                "business_need": {
                    "score": 4,
                    "evidence": long_text,
                    "reason": secret,
                }
            }
        },
        framework=framework,
    )

    dimension = result["qualification"]["business_need"]
    assert len(dimension["evidence"]) == MAX_EVIDENCE_CHARS
    assert dimension["evidence"].endswith("...")
    assert "reason" not in dimension
    assert secret not in str(result)
    assert [warning["code"] for warning in result["warnings"]] == [
        "text_truncated",
        "secret_like_text",
    ]


def test_normalized_qualification_feeds_snapshot_engine_without_neutral_scores() -> None:
    framework = get_qualification_template("simple_b2b")
    normalized = normalize_qualification_extraction(
        {"qualification": {"business_need": {"score": 5}}},
        framework=framework,
    )

    snapshot = compute_qualification_latest(
        [{"qualification": normalized["qualification"]}],
        framework=framework,
    )

    assert snapshot["filled_count"] == 1
    assert snapshot["total_count"] == 3
    assert snapshot["coverage_pct"] == 33.3
    assert snapshot["uncertainty_level"] == "high"
    assert snapshot["dimensions"]["business_need"]["score"] == 5.0
    assert "buyer_owner" in snapshot["gaps"]
    assert "next_step" in snapshot["gaps"]


def test_interaction_qualification_survives_normalization_into_latest_snapshot() -> None:
    deal = {
        "deal_stage": "discovery",
        "interactions": [
            {
                "scoring_applied": True,
                "qualification": {
                    "business_need": {"score": 5},
                    "buyer_owner": {"score": 4},
                },
            }
        ],
    }

    snapshots = rebuild_latest_snapshots(
        deal,
        {"qualification": {"active_framework": "simple_b2b"}},
    )

    latest = snapshots["qualification_latest"]
    assert latest["framework_key"] == "simple_b2b"
    assert latest["filled_count"] == 2
    assert latest["dimensions"]["business_need"]["score"] == 5.0
    assert latest["dimensions"]["buyer_owner"]["score"] == 4.0


def test_normalization_does_not_mutate_framework() -> None:
    framework = get_qualification_template("simple_b2b")
    before = deepcopy(framework.model_dump(mode="json"))

    normalize_qualification_extraction(
        {"qualification": {"business_need": {"score": 4}}},
        framework=framework,
    )

    assert framework.model_dump(mode="json") == before
