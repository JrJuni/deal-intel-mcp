from __future__ import annotations

import json
from datetime import date

import pytest

from deal_intel.reports.weekly_pipeline import build_weekly_pipeline_rows
from deal_intel.schema.metrics import PipelineTimingSettings

AS_OF = date(2026, 6, 10)


def _deal(
    deal_id: str,
    *,
    company: str | None = None,
    stage: str = "discovery",
    industry: str = "IT",
    amount: int | None = 10_000_000,
    amount_status: str | None = "quoted",
    health_pct: float | None = 80,
    entered_at: str = "2026-06-01T00:00:00+00:00",
    expected_close_date: str | None = "2026-06-30",
    expected_close_date_source: str | None = "user_provided",
    meetings: list[dict] | None = None,
    customer_themes: list[dict] | None = None,
    meddpicc_gaps: list[str] | None = None,
) -> dict:
    return {
        "deal_id": deal_id,
        "company": company or f"Company {deal_id}",
        "industry": industry,
        "deal_stage": stage,
        "deal_size_krw": amount,
        "deal_size_status": amount_status,
        "stage_history": [{"stage": stage, "entered_at": entered_at}],
        "expected_close_date": expected_close_date,
        "expected_close_date_source": expected_close_date_source,
        "actual_close_date": "2026-06-01" if stage in {"won", "lost"} else None,
        "close_reason": "price" if stage == "lost" else None,
        "meetings": meetings if meetings is not None else [{"date": "2026-06-01"}],
        "customer_themes": customer_themes or [],
        "contacts": [{"name": "secret contact"}],
        "summary_embedding": [0.1, 0.2],
        "meddpicc_latest": (
            {
                "filled_count": 1,
                "health_pct": health_pct,
                "gaps": meddpicc_gaps if meddpicc_gaps is not None else ["economic_buyer"],
            }
            if health_pct is not None
            else {}
        ),
    }


def _theme(
    dimension: str,
    *,
    evidence: str,
    importance: int,
    meeting_date: str = "2026-06-01",
    theme_key: str = "operational_efficiency",
    interaction_type: str | None = None,
    source_confidence: str | None = None,
    subject: str | None = None,
) -> dict:
    theme = {
        "theme_key": theme_key,
        "label": "Theme",
        "dimension": dimension,
        "evidence": evidence,
        "importance": importance,
        "meeting_id": f"meeting-{importance}",
        "meeting_date": meeting_date,
    }
    if interaction_type:
        theme["interaction_id"] = f"interaction-{importance}"
        theme["interaction_date"] = meeting_date
        theme["interaction_type"] = interaction_type
    if source_confidence:
        theme["source_confidence"] = source_confidence
    if subject:
        theme["subject"] = subject
    return theme


def test_weekly_pipeline_rows_include_open_deals_only_and_safe_fields() -> None:
    result = build_weekly_pipeline_rows(
        [
            _deal("open-1", stage="proposal"),
            _deal("won-1", stage="won", expected_close_date=None),
            _deal("lost-1", stage="lost", expected_close_date=None),
        ],
        as_of=AS_OF,
    )

    assert result["report_type"] == "weekly_pipeline"
    assert result["filters"] == {"stage": None, "industry": None}
    assert result["row_count"] == 1
    assert result["rows"][0]["deal_id"] == "open-1"
    payload = json.dumps(result, ensure_ascii=False)
    assert "raw_notes" not in payload
    assert "contacts" not in payload
    assert "summary_embedding" not in payload
    assert result["columns"] == list(result["rows"][0].keys())


def test_weekly_pipeline_sorting_prioritizes_attention_then_close_date_and_value() -> None:
    deals = [
        _deal(
            "normal",
            company="E",
            health_pct=80,
            amount=100,
            expected_close_date="2026-06-11",
        ),
        _deal(
            "at-risk",
            company="D",
            health_pct=30,
            amount=100,
            expected_close_date="2026-07-01",
        ),
        _deal(
            "stalled",
            company="C",
            stage="stalled",
            health_pct=80,
            amount=100,
            expected_close_date="2026-07-01",
        ),
        _deal(
            "stuck",
            company="B",
            health_pct=80,
            amount=100,
            entered_at="2026-05-01T00:00:00+00:00",
            expected_close_date="2026-07-01",
        ),
        _deal(
            "overdue",
            company="A",
            health_pct=80,
            amount=100,
            entered_at="2026-06-09T00:00:00+00:00",
            expected_close_date="2026-06-01",
        ),
        _deal(
            "same-date-large",
            company="F",
            health_pct=80,
            amount=200,
            expected_close_date="2026-08-01",
        ),
        _deal(
            "same-date-small",
            company="G",
            health_pct=80,
            amount=100,
            expected_close_date="2026-08-01",
        ),
    ]

    result = build_weekly_pipeline_rows(
        deals,
        as_of=AS_OF,
        timing_settings=PipelineTimingSettings(stuck_default_days=14),
    )

    assert [row["deal_id"] for row in result["rows"]] == [
        "overdue",
        "stuck",
        "stalled",
        "at-risk",
        "normal",
        "same-date-large",
        "same-date-small",
    ]
    assert result["rows"][0]["attention_reasons"] == ["overdue"]
    assert result["rows"][1]["attention_reasons"] == ["stuck"]
    assert result["rows"][2]["attention_reasons"] == ["stalled"]


def test_weekly_pipeline_rows_split_objective_actions_from_gap_observations() -> None:
    result = build_weekly_pipeline_rows(
        [
            _deal(
                "judgment-gap",
                stage="negotiation",
                health_pct=82,
                expected_close_date="2026-06-01",
                meddpicc_gaps=["competition"],
            )
        ],
        as_of=AS_OF,
    )

    row = result["rows"][0]
    assert row["meddpicc_gaps"] == ["competition"]
    assert [item["gap_id"] for item in row["objective_action_items"]] == [
        "attention:overdue"
    ]
    assert all(
        not item["field"].startswith("meddpicc.")
        for item in row["objective_action_items"]
    )

    observation = next(
        item for item in row["gap_observations"]
        if item["field"] == "meddpicc.competition"
    )
    assert observation["actionability"] == "needs_human_judgment"
    assert observation["cta_policy"] == "observation_only"


def test_stage_and_industry_filters_apply_before_row_generation() -> None:
    result = build_weekly_pipeline_rows(
        [
            _deal("it-proposal", stage="proposal", industry="IT", amount=100),
            _deal("finance-proposal", stage="proposal", industry="Finance", amount=200),
            _deal("it-discovery", stage="discovery", industry="IT", amount=300),
        ],
        as_of=AS_OF,
        stage="proposal",
        industry="IT",
    )

    assert result["filters"] == {"stage": "proposal", "industry": "IT"}
    assert result["row_count"] == 1
    assert result["rows"][0]["deal_id"] == "it-proposal"


def test_primary_pain_and_decision_criteria_choose_importance_then_latest() -> None:
    result = build_weekly_pipeline_rows(
        [
            _deal(
                "themes",
                customer_themes=[
                    _theme(
                        "identify_pain",
                        evidence="older but lower priority",
                        importance=4,
                        meeting_date="2026-06-09",
                    ),
                    _theme(
                        "identify_pain",
                        evidence="critical current pain",
                        importance=5,
                        meeting_date="2026-06-01",
                    ),
                    _theme(
                        "decision_criteria",
                        evidence="audit log is mandatory",
                        importance=5,
                        meeting_date="2026-06-01",
                        theme_key="compliance_security",
                    ),
                    _theme(
                        "decision_criteria",
                        evidence="latest same-priority criterion",
                        importance=5,
                        meeting_date="2026-06-08",
                        theme_key="integration_migration",
                    ),
                ],
            )
        ],
        as_of=AS_OF,
    )

    row = result["rows"][0]
    assert row["primary_pain"]["evidence"] == "critical current pain"
    assert row["primary_decision_criteria"]["evidence"] == (
        "latest same-priority criterion"
    )


def test_primary_theme_preserves_safe_source_label_metadata() -> None:
    result = build_weekly_pipeline_rows(
        [
            _deal(
                "source-theme",
                customer_themes=[
                    _theme(
                        "identify_pain",
                        evidence="email says manual follow-up is too slow",
                        importance=5,
                        interaction_type="email_thread",
                        source_confidence="customer_stated",
                        subject="Re: follow-up process",
                    ),
                    _theme(
                        "decision_criteria",
                        evidence="interview confirms audit export is mandatory",
                        importance=5,
                        interaction_type="user_interview",
                        source_confidence="customer_stated",
                        subject="Buyer interview",
                    ),
                ],
            )
        ],
        as_of=AS_OF,
    )

    row = result["rows"][0]
    assert row["primary_pain"]["source_label"] == "Email thread (customer-stated)"
    assert row["primary_pain"]["source_confidence"] == "customer_stated"
    assert row["primary_pain"]["subject"] == "Re: follow-up process"
    assert row["primary_decision_criteria"]["source_label"] == (
        "User interview (customer-stated)"
    )


def test_meeting_level_themes_and_last_meeting_date_are_used_when_flattened_absent() -> None:
    result = build_weekly_pipeline_rows(
        [
            _deal(
                "meeting-themes",
                meetings=[
                    {
                        "meeting_id": "m1",
                        "date": "2026-06-01",
                        "raw_notes": "do not leak",
                        "customer_themes": [
                            _theme(
                                "identify_pain",
                                evidence="manual report takes too long",
                                importance=4,
                            )
                        ],
                    },
                    {
                        "meeting_id": "m2",
                        "date": "2026-06-09",
                        "customer_themes": [
                            _theme(
                                "decision_criteria",
                                evidence="mobile access is required",
                                importance=5,
                            )
                        ],
                    },
                ],
            )
        ],
        as_of=AS_OF,
    )

    row = result["rows"][0]
    assert row["last_meeting_date"] == "2026-06-09"
    assert row["primary_pain"]["meeting_id"] == "m1"
    assert row["primary_decision_criteria"]["meeting_id"] == "m2"
    assert "do not leak" not in json.dumps(result, ensure_ascii=False)


def test_missing_data_surfaces_warnings_without_blocking_rows() -> None:
    result = build_weekly_pipeline_rows(
        [
            _deal(
                "missing",
                stage="qualification",
                amount=None,
                amount_status="unknown",
                health_pct=None,
                expected_close_date=None,
                meetings=[],
                customer_themes=[],
            )
        ],
        as_of=AS_OF,
    )

    row = result["rows"][0]
    assert row["health_pct"] is None
    assert row["health_band"] == "unassessed"
    assert row["close_date_status"] == "missing"
    assert row["last_meeting_date"] is None
    assert row["primary_pain"] is None
    assert row["primary_decision_criteria"] is None
    assert result["warnings"] == [
        "unassessed_health",
        "missing_expected_close_date",
        "missing_last_meeting_date",
        "missing_primary_pain",
        "missing_primary_decision_criteria",
        "incomplete_data_quality",
    ]


def test_empty_report_and_invalid_inputs_are_explicit() -> None:
    empty = build_weekly_pipeline_rows([], as_of=AS_OF)

    assert empty["row_count"] == 0
    assert empty["warnings"] == ["no_open_deals"]
    with pytest.raises(ValueError, match="as_of"):
        build_weekly_pipeline_rows([], as_of="2026-06-10")
    with pytest.raises(ValueError, match="stage"):
        build_weekly_pipeline_rows([], as_of=AS_OF, stage="not-a-stage")
