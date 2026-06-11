from __future__ import annotations

from copy import deepcopy
from datetime import date

import pytest

from deal_intel.schema.deal_gaps import build_deal_gaps_summary
from deal_intel.schema.metrics import HealthBandThresholds, PipelineTimingSettings

AS_OF = date(2026, 6, 9)


def _deal(
    deal_id: str,
    *,
    stage: str = "discovery",
    amount: int | None = 10_000_000,
    amount_status: str | None = "quoted",
    expected_close_date: str | None = "2026-06-30",
    expected_close_date_source: str | None = "user_provided",
    actual_close_date: str | None = None,
    close_reason: str | None = None,
    health_pct: float | None = 82,
    gaps: list[str] | None = None,
    entered_at: str = "2026-06-01T00:00:00+00:00",
    industry: str = "IT",
) -> dict:
    return {
        "deal_id": deal_id,
        "company": f"Company {deal_id}",
        "industry": industry,
        "deal_stage": stage,
        "deal_size_krw": amount,
        "deal_size_status": amount_status,
        "expected_close_date": expected_close_date,
        "expected_close_date_source": expected_close_date_source,
        "actual_close_date": actual_close_date,
        "close_reason": close_reason,
        "stage_history": [{"stage": stage, "entered_at": entered_at}],
        "meetings": [{"date": "2026-06-01"}],
        "meddpicc_latest": (
            {"filled_count": 1, "health_pct": health_pct, "gaps": gaps or []}
            if health_pct is not None
            else {}
        ),
    }


def _first_gap(row: dict, field: str) -> dict:
    for gap in row["gaps"]:
        if gap["field"] == field:
            return gap
    raise AssertionError(f"gap for {field!r} not found")


def test_discovery_unknown_amount_is_low_priority_by_default() -> None:
    result = build_deal_gaps_summary(
        [_deal("early", amount=None, amount_status="unknown")],
        as_of=AS_OF,
        min_priority="low",
    )

    row = result["deals"][0]
    assert row["priority_band"] == "low"
    assert _first_gap(row, "deal_value")["status"] == "missing"
    assert result["summary"]["priority_counts"]["low"] == 1


def test_proposal_rough_estimate_amount_is_forecast_trust_gap() -> None:
    result = build_deal_gaps_summary(
        [
            _deal(
                "proposal",
                stage="proposal",
                amount=80_000_000,
                amount_status="rough_estimate",
            )
        ],
        as_of=AS_OF,
    )

    row = result["deals"][0]
    gap = _first_gap(row, "deal_value")
    assert row["priority_band"] == "medium"
    assert gap["status"] == "estimated"
    assert gap["impact_area"] == "forecast_trust"
    assert gap["recommended_action"] == "confirm_deal_value"


def test_negotiation_meddpicc_gap_is_high_priority() -> None:
    result = build_deal_gaps_summary(
        [
            _deal(
                "negotiation",
                stage="negotiation",
                amount=120_000_000,
                gaps=["champion"],
            )
        ],
        as_of=AS_OF,
        min_priority="high",
    )

    row = result["deals"][0]
    gap = _first_gap(row, "meddpicc.champion")
    assert row["priority_band"] == "high"
    assert gap["severity"] == "high"
    assert gap["recommended_action"] == "ask_in_next_meeting"
    assert gap["actionability"] == "needs_human_judgment"
    assert gap["cta_policy"] == "observation_only"
    assert row["actionable_gaps"] == []
    assert row["gap_observations"][0]["gap_id"] == "meddpicc:champion"


def test_overdue_deal_includes_suggested_question() -> None:
    result = build_deal_gaps_summary(
        [
            _deal(
                "overdue",
                stage="proposal",
                expected_close_date="2026-06-01",
            )
        ],
        as_of=AS_OF,
    )

    row = result["deals"][0]
    gap = next(gap for gap in row["gaps"] if gap["gap_id"] == "attention:overdue")
    assert "overdue" in row["attention_reasons"]
    assert gap["suggested_question"]
    assert gap["recommended_action"] == "review_close_plan"
    assert gap["actionability"] == "cta_allowed"
    assert gap["cta_policy"] == "cta_allowed"
    assert row["actionable_gaps"][0]["gap_id"] == "attention:overdue"


def test_terminal_deals_require_postmortem_fields() -> None:
    result = build_deal_gaps_summary(
        [
            _deal(
                "won",
                stage="won",
                expected_close_date=None,
                actual_close_date=None,
            ),
            _deal(
                "lost",
                stage="lost",
                expected_close_date=None,
                actual_close_date="2026-06-01",
                close_reason=None,
            ),
        ],
        as_of=AS_OF,
        min_priority="high",
    )

    by_id = {row["deal_id"]: row for row in result["deals"]}
    assert by_id["won"]["priority_band"] == "high"
    assert _first_gap(by_id["won"], "actual_close_date")["impact_area"] == "postmortem"
    assert by_id["lost"]["priority_band"] == "high"
    assert _first_gap(by_id["lost"], "close_reason")["impact_area"] == "postmortem"


def test_deal_id_filter_returns_low_priority_deal_even_when_min_priority_is_high() -> None:
    result = build_deal_gaps_summary(
        [
            _deal("other", stage="negotiation", gaps=["champion"]),
            _deal("target", amount=None, amount_status="unknown"),
        ],
        as_of=AS_OF,
        deal_id="target",
        min_priority="high",
    )

    assert [row["deal_id"] for row in result["deals"]] == ["target"]
    assert result["deals"][0]["priority_band"] == "low"
    assert result["summary"]["deal_count"] == 1


def test_min_priority_high_excludes_medium_and_low() -> None:
    result = build_deal_gaps_summary(
        [
            _deal("low", amount=None, amount_status="unknown"),
            _deal(
                "medium",
                stage="proposal",
                amount=80_000_000,
                amount_status="rough_estimate",
            ),
            _deal("high", stage="negotiation", amount=120_000_000, gaps=["champion"]),
        ],
        as_of=AS_OF,
        min_priority="high",
    )

    assert [row["deal_id"] for row in result["deals"]] == ["high"]
    assert result["summary"]["priority_counts"] == {
        "low": 1,
        "medium": 1,
        "high": 1,
    }


def test_filters_apply_before_gap_scoring_and_invalid_inputs_fail() -> None:
    deals = [
        _deal("it", industry="IT", amount=None, amount_status="unknown"),
        _deal("finance", industry="Finance", amount=None, amount_status="unknown"),
    ]

    result = build_deal_gaps_summary(
        deepcopy(deals),
        as_of=AS_OF,
        industry="IT",
        min_priority="low",
    )

    assert result["summary"]["deal_count"] == 1
    assert result["deals"][0]["deal_id"] == "it"
    with pytest.raises(ValueError, match="stage"):
        build_deal_gaps_summary([], as_of=AS_OF, stage="bad")
    with pytest.raises(ValueError, match="min_priority"):
        build_deal_gaps_summary([], as_of=AS_OF, min_priority="urgent")
    with pytest.raises(ValueError, match="limit"):
        build_deal_gaps_summary([], as_of=AS_OF, limit=51)


def test_configurable_health_thresholds_feed_attention_reason() -> None:
    result = build_deal_gaps_summary(
        [_deal("risk", health_pct=64)],
        as_of=AS_OF,
        health_thresholds=HealthBandThresholds(healthy_min=80, watch_min=65),
        timing_settings=PipelineTimingSettings(stuck_default_days=30),
    )

    assert result["deals"][0]["health_band"] == "at_risk"
    assert "at_risk" in result["deals"][0]["attention_reasons"]
    assert result["deals"][0]["actionable_gaps"] == []
    assert result["deals"][0]["gap_observations"][0]["gap_id"] == "attention:at_risk"
    assert (
        result["deals"][0]["gap_observations"][0]["actionability"]
        == "needs_human_judgment"
    )
