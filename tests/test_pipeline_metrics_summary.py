from __future__ import annotations

from datetime import date

import pytest

from deal_intel.schema.metrics import (
    HealthBandThresholds,
    PipelineTimingSettings,
    WinRateSettings,
)
from deal_intel.schema.pipeline_metrics import (
    CANONICAL_STAGE_ORDER,
    build_pipeline_health_summary,
)

AS_OF = date(2026, 6, 8)


def _deal(
    deal_id: str,
    *,
    stage: str = "discovery",
    industry: str = "IT",
    amount: int | None = 10_000_000,
    amount_status: str | None = "quoted",
    health_pct: float | None = 80,
    entered_at: str = "2026-06-01T00:00:00+00:00",
    expected_close_date: str | None = "2026-06-30",
    expected_close_date_source: str | None = "user_provided",
    actual_close_date: str | None = None,
    close_reason: str | None = None,
) -> dict:
    return {
        "deal_id": deal_id,
        "company": f"Company {deal_id}",
        "industry": industry,
        "deal_stage": stage,
        "deal_size_amount": amount,
        "deal_size_status": amount_status,
        "stage_history": [{"stage": stage, "entered_at": entered_at}],
        "expected_close_date": expected_close_date,
        "expected_close_date_source": expected_close_date_source,
        "actual_close_date": actual_close_date,
        "close_reason": close_reason,
        "meetings": [{"date": "2026-06-01"}],
        "meddpicc_latest": (
            {"filled_count": 1, "health_pct": health_pct}
            if health_pct is not None
            else {}
        ),
    }


def test_empty_summary_has_null_averages_and_zero_values() -> None:
    result = build_pipeline_health_summary([], as_of=AS_OF)

    assert result["filters"] == {"stage": None, "industry": None}
    assert result["kpis"]["deal_count"] == 0
    assert result["kpis"]["avg_health_pct"] is None
    assert result["kpis"]["health_coverage_pct"] is None
    assert result["pipeline_values"]["open"]["pipeline_value_amount"] == 0
    assert [row["stage"] for row in result["stage_breakdown"]] == list(
        CANONICAL_STAGE_ORDER
    )
    assert all(row["count"] == 0 for row in result["stage_breakdown"])
    assert result["health_bands"] == {
        "healthy": 0,
        "watch": 0,
        "at_risk": 0,
        "unassessed": 0,
    }


def test_summary_separates_populations_health_and_current_pipeline_value() -> None:
    deals = [
        _deal("active-known", stage="discovery", amount=100, health_pct=80),
        _deal(
            "active-unknown",
            stage="qualification",
            amount=None,
            amount_status="unknown",
            health_pct=None,
        ),
        _deal("stalled", stage="stalled", amount=50, health_pct=50),
        _deal(
            "won",
            stage="won",
            amount=999,
            health_pct=90,
            expected_close_date=None,
            actual_close_date="2026-06-01",
        ),
        _deal(
            "lost",
            stage="lost",
            amount=888,
            health_pct=30,
            expected_close_date=None,
            actual_close_date="2026-06-01",
            close_reason="price",
        ),
    ]

    result = build_pipeline_health_summary(deals, as_of=AS_OF)

    assert result["kpis"]["active_deal_count"] == 2
    assert result["kpis"]["open_deal_count"] == 3
    assert result["kpis"]["stalled_deal_count"] == 1
    assert result["kpis"]["terminal_deal_count"] == 2
    assert result["kpis"]["avg_health_pct"] == 80.0
    assert result["kpis"]["health_coverage_pct"] == 50.0
    assert result["health_bands"] == {
        "healthy": 2,
        "watch": 1,
        "at_risk": 1,
        "unassessed": 1,
    }
    assert result["pipeline_values"]["active"]["pipeline_value_amount"] == 100
    assert result["pipeline_values"]["stalled"]["pipeline_value_amount"] == 50
    assert result["pipeline_values"]["open"]["pipeline_value_amount"] == 150
    assert result["stage_breakdown"][-2]["stage"] == "won"
    assert result["stage_breakdown"][-2]["pipeline_value_amount"] == 0
    assert "missing_amount" in result["warnings"]
    assert "unassessed_health" in result["warnings"]


def test_health_band_boundaries_are_configurable() -> None:
    result = build_pipeline_health_summary(
        [
            _deal("healthy", health_pct=75),
            _deal("watch", health_pct=45),
            _deal("risk", health_pct=44.9),
            _deal("unassessed", health_pct=None),
        ],
        as_of=AS_OF,
        health_thresholds=HealthBandThresholds(healthy_min=75, watch_min=45),
    )

    assert result["health_bands"] == {
        "healthy": 1,
        "watch": 1,
        "at_risk": 1,
        "unassessed": 1,
    }


def test_pipeline_value_keeps_invalid_unknown_and_terminal_amounts_separate() -> None:
    result = build_pipeline_health_summary(
        [
            _deal("invalid-zero", amount=0, amount_status=None),
            _deal("unknown", amount=None, amount_status="unknown"),
            _deal(
                "terminal",
                stage="won",
                amount=1_000_000,
                expected_close_date=None,
                actual_close_date="2026-06-01",
            ),
        ],
        as_of=AS_OF,
    )

    open_value = result["pipeline_values"]["open"]
    assert open_value["pipeline_value_amount"] == 0
    assert open_value["invalid_amount_count"] == 1
    assert open_value["missing_amount_count"] == 1
    assert result["pipeline_values"]["open"]["deal_count"] == 2
    assert result["pipeline_values"]["active"]["deal_count"] == 2
    assert "invalid_amount" in result["warnings"]


def test_attention_reason_counts_can_overlap_but_unique_count_does_not() -> None:
    result = build_pipeline_health_summary(
        [
            _deal(
                "active-risk",
                health_pct=30,
                entered_at="2026-05-01T00:00:00+00:00",
                expected_close_date="2026-05-30",
            ),
            _deal(
                "stalled-risk",
                stage="stalled",
                health_pct=30,
                expected_close_date="2026-05-30",
            ),
        ],
        as_of=AS_OF,
        timing_settings=PipelineTimingSettings(stuck_default_days=14),
    )

    assert result["attention_reasons"] == {
        "stalled_count": 1,
        "overdue_count": 2,
        "stuck_count": 1,
        "at_risk_count": 2,
        "unique_deal_count": 2,
        "attention_deal_count": 2,
    }
    assert result["kpis"]["attention_deal_count"] == 2
    assert result["kpis"]["stuck_deal_count"] == 1
    assert result["kpis"]["overdue_deal_count"] == 2


def test_win_rate_uses_terminal_deals_and_preserves_small_sample_warning() -> None:
    result = build_pipeline_health_summary(
        [
            _deal("won-1", stage="won", expected_close_date=None),
            _deal("won-2", stage="won", expected_close_date=None),
            _deal(
                "lost",
                stage="lost",
                expected_close_date=None,
                close_reason="price",
            ),
            _deal("open", stage="proposal"),
        ],
        as_of=AS_OF,
        win_rate_settings=WinRateSettings(minimum_closed_sample=10),
    )

    assert result["win_rate"]["win_rate_pct"] == 66.7
    assert result["win_rate"]["closed_count"] == 3
    assert result["kpis"]["win_rate_pct"] == 66.7
    assert "insufficient_closed_sample" in result["warnings"]


def test_data_quality_summary_exposes_usable_and_confirmed_coverage() -> None:
    result = build_pipeline_health_summary(
        [
            _deal(
                "estimated",
                amount_status="rough_estimate",
                expected_close_date_source="config_default",
            )
        ],
        as_of=AS_OF,
    )

    assert result["data_quality"]["complete_deal_pct"] == 100.0
    assert result["data_quality"]["confirmed_complete_deal_pct"] == 0.0
    assert result["kpis"]["data_quality_coverage_pct"] == 100.0
    assert result["kpis"]["confirmed_data_quality_coverage_pct"] == 0.0
    assert result["data_quality"]["field_coverage"]["deal_value"]["estimated"] == 1
    assert (
        result["data_quality"]["field_coverage"]["expected_close_date"][
            "estimated"
        ]
        == 1
    )


def test_stage_and_industry_filters_apply_before_calculation() -> None:
    result = build_pipeline_health_summary(
        [
            _deal("it-discovery", stage="discovery", industry="IT", amount=100),
            _deal(
                "finance-discovery",
                stage="discovery",
                industry="Finance",
                amount=200,
            ),
            _deal("it-proposal", stage="proposal", industry="IT", amount=300),
        ],
        as_of=AS_OF,
        stage="discovery",
        industry="IT",
    )

    assert result["filters"] == {"stage": "discovery", "industry": "IT"}
    assert result["kpis"]["deal_count"] == 1
    assert result["pipeline_values"]["open"]["pipeline_value_amount"] == 100

    with pytest.raises(ValueError, match="stage"):
        build_pipeline_health_summary([], as_of=AS_OF, stage="not-a-stage")
