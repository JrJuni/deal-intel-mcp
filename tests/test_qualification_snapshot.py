from __future__ import annotations

from copy import deepcopy

from deal_intel.schema.meddpicc import (
    compute_meddpicc_latest,
    compute_meddpicc_qualification_latest,
)
from deal_intel.schema.qualification import compute_qualification_latest
from deal_intel.schema.qualification_framework import get_qualification_template
from deal_intel.tools.qualification_snapshot import rebuild_latest_snapshots


def test_meddpicc_wrapper_preserves_legacy_shape_and_math() -> None:
    evidence = [
        {
            "meddpicc": {
                "metrics": {"score": 4},
                "identify_pain": {"score": 5},
            }
        },
        {
            "meddpicc": {
                "metrics": {"score": 2},
                "champion": {"score": 1},
            }
        },
    ]

    result = compute_meddpicc_latest(
        evidence,
        weights={"metrics": 2.0},
        gap_threshold=2,
        deal_stage="discovery",
    )

    assert result == {
        "metrics": {"score": 3.0, "trend": "down"},
        "identify_pain": {"score": 5.0, "trend": None},
        "champion": {"score": 1.0, "trend": None},
        "total_weighted_score": 12.0,
        "health_pct": 30.0,
        "filled_count": 3,
        "gaps": [
            "economic_buyer",
            "decision_criteria",
            "decision_process",
            "champion",
            "competition",
        ],
    }


def test_meddpicc_canonical_snapshot_separates_quality_and_coverage() -> None:
    result = compute_meddpicc_qualification_latest(
        [{"meddpicc": {"identify_pain": {"score": 4}}}],
        weights={},
        deal_stage="discovery",
    )

    assert result["framework_key"] == "meddpicc"
    assert result["framework_display_name"] == "MEDDPICC"
    assert result["dimensions"]["identify_pain"]["score"] == 4.0
    assert result["quality_pct"] == 80.0
    assert result["coverage_pct"] == 14.3
    assert result["uncertainty_level"] == "high"
    assert result["health_pct"] == 11.4
    assert result["filled_count"] == 1
    assert result["total_count"] == 7


def test_generic_framework_uses_qualification_evidence_field() -> None:
    framework = get_qualification_template("simple_b2b")

    result = compute_qualification_latest(
        [
            {
                "qualification": {
                    "business_need": {"score": 5},
                    "buyer_owner": {"score": 3},
                }
            }
        ],
        framework=framework,
        evidence_fields=("qualification",),
        deal_stage="discovery",
    )

    assert result["framework_key"] == "simple_b2b"
    assert result["filled_count"] == 2
    assert result["total_count"] == 3
    assert result["quality_pct"] == 80.0
    assert result["coverage_pct"] == 66.7
    assert result["uncertainty_level"] == "medium"
    assert "business_need" not in result["gaps"]
    assert "buyer_owner" not in result["gaps"]


def test_stage_rules_and_terminal_won_gap_suppression_are_preserved() -> None:
    low_pain = [{"meddpicc": {"identify_pain": {"score": 1}}}]

    discovery = compute_meddpicc_latest(
        low_pain,
        weights={},
        gap_threshold=2,
        deal_stage="discovery",
    )
    proposal = compute_meddpicc_latest(
        low_pain,
        weights={},
        gap_threshold=2,
        deal_stage="proposal",
    )
    won = compute_meddpicc_latest(
        low_pain,
        weights={},
        gap_threshold=2,
        deal_stage="won",
    )

    assert "identify_pain" in discovery["gaps"]
    assert "identify_pain" not in proposal["gaps"]
    assert won["gaps"] == []


def test_disabled_dimensions_are_excluded_from_scores_and_gaps() -> None:
    framework = get_qualification_template("pilot_poc").model_copy(deep=True)
    framework.dimensions["conversion_path"].enabled = False

    result = compute_qualification_latest(
        [{"qualification": {"success_criteria": {"score": 4}}}],
        framework=framework,
        evidence_fields=("qualification",),
    )

    assert result["total_count"] == 3
    assert "conversion_path" not in result["dimensions"]
    assert "conversion_path" not in result["gaps"]


def test_generic_snapshot_does_not_mutate_framework_template() -> None:
    framework = get_qualification_template("simple_b2b")
    before = deepcopy(framework.model_dump(mode="json"))

    compute_qualification_latest(
        [{"qualification": {"business_need": {"score": 4}}}],
        framework=framework,
    )

    assert framework.model_dump(mode="json") == before


def test_rebuild_latest_snapshots_keeps_legacy_and_canonical_meddpicc() -> None:
    deal = {
        "deal_stage": "discovery",
        "interactions": [
            {
                "scoring_applied": True,
                "meddpicc": {"champion": {"score": 5}},
            }
        ],
        "meetings": [],
    }

    snapshots = rebuild_latest_snapshots(deal, {"meddpicc": {"weights": {}}})

    assert snapshots["meddpicc_latest"]["champion"]["score"] == 5.0
    assert snapshots["qualification_latest"]["framework_key"] == "meddpicc"
    assert snapshots["qualification_latest"]["dimensions"]["champion"]["score"] == 5.0


def test_rebuild_latest_snapshots_does_not_map_meddpicc_into_other_frameworks() -> None:
    deal = {
        "deal_stage": "discovery",
        "interactions": [
            {
                "scoring_applied": True,
                "meddpicc": {"champion": {"score": 5}},
            }
        ],
        "meetings": [],
    }

    snapshots = rebuild_latest_snapshots(
        deal,
        {"qualification": {"active_framework": "simple_b2b"}},
    )

    assert snapshots["meddpicc_latest"]["champion"]["score"] == 5.0
    assert snapshots["qualification_latest"]["framework_key"] == "simple_b2b"
    assert snapshots["qualification_latest"]["filled_count"] == 0
    assert snapshots["qualification_latest"]["coverage_pct"] == 0.0
