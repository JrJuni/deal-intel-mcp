from __future__ import annotations

from datetime import date

import pytest

from deal_intel.schema.pipeline_trends import build_pipeline_trend_summary

AS_OF = date(2026, 6, 9)


def _snapshot(
    event_id: str,
    deal_id: str,
    as_of: str,
    *,
    stage: str = "discovery",
    industry: str = "IT",
    amount: int | None = 10,
    health_pct: float | None = 70,
    attention_reasons: list[str] | None = None,
) -> dict:
    return {
        "event_id": event_id,
        "deal_id": deal_id,
        "as_of": as_of,
        "occurred_at": f"{as_of}T00:00:00+00:00",
        "industry": industry,
        "deal_stage": stage,
        "deal_size_krw": amount,
        "health_pct": health_pct,
        "attention_reasons": attention_reasons or [],
    }


def test_pipeline_trend_compares_window_start_and_end_kpis() -> None:
    result = build_pipeline_trend_summary(
        [
            _snapshot("e1", "deal-1", "2026-06-02", amount=10, health_pct=60),
            _snapshot("e2", "deal-1", "2026-06-09", amount=30, health_pct=80),
            _snapshot("e3", "deal-2", "2026-06-09", stage="proposal", amount=20),
        ],
        as_of=AS_OF,
        lookback_days=7,
    )

    assert result["window"] == {
        "lookback_days": 7,
        "start_date": "2026-06-02",
        "end_date": "2026-06-09",
    }
    assert result["start"]["active_deal_count"] == 1
    assert result["end"]["active_deal_count"] == 2
    assert result["delta"]["active_deal_count"] == 1.0
    assert result["start"]["open_pipeline_value_krw"] == 10
    assert result["end"]["open_pipeline_value_krw"] == 50
    assert result["delta"]["open_pipeline_value_krw"] == 40.0
    assert result["delta"]["avg_health_pct"] == 15.0
    assert result["stage_changes"]["entered"] == {"proposal": 1}


def test_pipeline_trend_tracks_stage_transitions() -> None:
    result = build_pipeline_trend_summary(
        [
            _snapshot("e1", "deal-1", "2026-06-02", stage="proposal"),
            _snapshot("e2", "deal-1", "2026-06-09", stage="won"),
            _snapshot("e3", "deal-2", "2026-06-02", stage="negotiation"),
            _snapshot("e4", "deal-2", "2026-06-09", stage="lost"),
        ],
        as_of=AS_OF,
        lookback_days=7,
    )

    assert result["stage_changes"]["transition_count"] == 2
    assert result["stage_changes"]["transitions"] == {
        "negotiation->lost": 1,
        "proposal->won": 1,
    }
    assert result["delta"]["won_deal_count"] == 1.0
    assert result["delta"]["lost_deal_count"] == 1.0


def test_pipeline_trend_dedupes_event_id() -> None:
    duplicate = _snapshot("same-event", "deal-1", "2026-06-09", amount=10)
    result = build_pipeline_trend_summary(
        [
            _snapshot("e0", "deal-1", "2026-06-02", amount=10),
            duplicate,
            {**duplicate, "deal_size_krw": 999},
        ],
        as_of=AS_OF,
        lookback_days=7,
    )

    assert result["snapshot_count"] == 2
    assert result["end"]["open_pipeline_value_krw"] == 10


def test_pipeline_trend_filters_before_calculating() -> None:
    result = build_pipeline_trend_summary(
        [
            _snapshot("e1", "deal-1", "2026-06-02", industry="IT", amount=10),
            _snapshot("e2", "deal-1", "2026-06-09", industry="IT", amount=20),
            _snapshot("e3", "deal-2", "2026-06-09", industry="Finance", amount=500),
        ],
        as_of=AS_OF,
        lookback_days=7,
        industry="IT",
    )

    assert result["filters"] == {"stage": None, "industry": "IT"}
    assert result["deal_count"] == 1
    assert result["end"]["open_pipeline_value_krw"] == 20


def test_pipeline_trend_warns_when_snapshots_are_insufficient() -> None:
    result = build_pipeline_trend_summary([], as_of=AS_OF, lookback_days=7)

    assert result["warnings"] == [
        "no_snapshots_in_window",
        "missing_start_baseline",
        "missing_end_baseline",
        "insufficient_snapshots",
    ]


@pytest.mark.parametrize("lookback_days", [0, -1, 366, True, 1.5])
def test_pipeline_trend_rejects_invalid_lookback_days(lookback_days) -> None:
    with pytest.raises(ValueError):
        build_pipeline_trend_summary(
            [],
            as_of=AS_OF,
            lookback_days=lookback_days,
        )
