from __future__ import annotations

import math

import pytest

from deal_intel.schema.metrics import (
    ACTIVE_STAGES,
    OPEN_STAGES,
    STALLED_STAGES,
    TERMINAL_STAGES,
    DealValueStatus,
    HealthBand,
    HealthBandThresholds,
    assess_deal_value,
    classify_health,
    is_active_stage,
    is_health_assessed,
    is_open_stage,
    summarize_pipeline_value,
)


def test_pipeline_stage_populations_are_disjoint_and_complete() -> None:
    assert ACTIVE_STAGES == {
        "discovery",
        "qualification",
        "proposal",
        "negotiation",
    }
    assert STALLED_STAGES == {"stalled"}
    assert OPEN_STAGES == ACTIVE_STAGES | STALLED_STAGES
    assert TERMINAL_STAGES == {"won", "lost"}
    assert OPEN_STAGES.isdisjoint(TERMINAL_STAGES)

    assert is_active_stage("proposal") is True
    assert is_active_stage("stalled") is False
    assert is_open_stage("stalled") is True
    assert is_open_stage("won") is False


def test_health_band_uses_default_boundaries_inclusively() -> None:
    thresholds = HealthBandThresholds.from_config({})

    assert classify_health({"filled_count": 1, "health_pct": 70}, thresholds) == "healthy"
    assert classify_health({"filled_count": 1, "health_pct": 69.9}, thresholds) == "watch"
    assert classify_health({"filled_count": 1, "health_pct": 40}, thresholds) == "watch"
    assert classify_health({"filled_count": 1, "health_pct": 39.9}, thresholds) == "at_risk"


def test_health_band_thresholds_are_configurable() -> None:
    thresholds = HealthBandThresholds.from_config(
        {
            "metrics": {
                "health_bands": {
                    "healthy_min": 80,
                    "watch_min": 55,
                }
            }
        }
    )

    assert thresholds == HealthBandThresholds(healthy_min=80, watch_min=55)
    assert classify_health({"filled_count": 2, "health_pct": 75}, thresholds) == HealthBand.WATCH
    assert (
        classify_health({"filled_count": 2, "health_pct": 54.9}, thresholds)
        == HealthBand.AT_RISK
    )


@pytest.mark.parametrize(
    "snapshot",
    [
        None,
        {},
        {"filled_count": 0, "health_pct": 0},
        {"filled_count": None, "health_pct": 80},
        {"filled_count": 1, "health_pct": None},
        {"filled_count": 1, "health_pct": math.nan},
    ],
)
def test_unassessed_health_is_separate_from_at_risk(snapshot: dict | None) -> None:
    thresholds = HealthBandThresholds.from_config({})

    assert is_health_assessed(snapshot) is False
    assert classify_health(snapshot, thresholds) == HealthBand.UNASSESSED


@pytest.mark.parametrize(
    ("healthy_min", "watch_min"),
    [
        (70, 70),
        (60, 70),
        (101, 40),
        (70, -1),
        ("70", 40),
        (70, True),
        (math.inf, 40),
        (70, math.nan),
    ],
)
def test_invalid_health_band_config_fails_explicitly(
    healthy_min: object,
    watch_min: object,
) -> None:
    with pytest.raises(ValueError, match="health band|health_bands"):
        HealthBandThresholds.from_config(
            {
                "metrics": {
                    "health_bands": {
                        "healthy_min": healthy_min,
                        "watch_min": watch_min,
                    }
                }
            }
        )


@pytest.mark.parametrize(
    ("deal", "status", "known", "classified", "validated", "strategic_zero"),
    [
        ({}, None, False, False, False, False),
        (
            {"deal_size_status": "unknown"},
            DealValueStatus.UNKNOWN,
            False,
            True,
            False,
            False,
        ),
        (
            {"deal_size_amount": 30_000_000},
            None,
            True,
            False,
            False,
            False,
        ),
        (
            {
                "deal_size_amount": 40_000_000,
                "deal_size_low_amount": 30_000_000,
                "deal_size_high_amount": 50_000_000,
                "deal_size_status": "rough_estimate",
            },
            DealValueStatus.ROUGH_ESTIMATE,
            True,
            True,
            False,
            False,
        ),
        (
            {
                "deal_size_amount": 40_000_000,
                "deal_size_status": "customer_budget",
            },
            DealValueStatus.CUSTOMER_BUDGET,
            True,
            True,
            True,
            False,
        ),
        (
            {"deal_size_amount": 0, "deal_size_status": "strategic_zero"},
            DealValueStatus.STRATEGIC_ZERO,
            True,
            True,
            False,
            True,
        ),
    ],
)
def test_deal_value_classifications(
    deal: dict,
    status: DealValueStatus | None,
    known: bool,
    classified: bool,
    validated: bool,
    strategic_zero: bool,
) -> None:
    result = assess_deal_value(deal)

    assert result.is_valid is True
    assert result.status == status
    assert result.is_known is known
    assert result.is_classified is classified
    assert result.is_validated is validated
    assert result.is_strategic_zero is strategic_zero


@pytest.mark.parametrize(
    ("deal", "issue"),
    [
        ({"deal_size_amount": 0}, "non_positive_amount_requires_strategic_zero"),
        ({"deal_size_amount": -1}, "non_positive_amount_requires_strategic_zero"),
        (
            {"deal_size_amount": 1, "deal_size_status": "unknown"},
            "unknown_status_must_not_have_amount",
        ),
        (
            {"deal_size_amount": None, "deal_size_status": "quoted"},
            "known_status_requires_positive_amount",
        ),
        (
            {"deal_size_amount": 1, "deal_size_status": "strategic_zero"},
            "strategic_zero_requires_zero_amount",
        ),
        (
            {
                "deal_size_amount": 40,
                "deal_size_low_amount": 50,
                "deal_size_high_amount": 60,
                "deal_size_status": "rough_estimate",
            },
            "estimated_range_must_include_amount",
        ),
        (
            {"deal_size_amount": 1.5, "deal_size_status": "rough_estimate"},
            "invalid_amount_type",
        ),
        (
            {"deal_size_amount": 1, "deal_size_status": "guess"},
            "invalid_status",
        ),
    ],
)
def test_invalid_deal_value_combinations_are_not_counted(
    deal: dict,
    issue: str,
) -> None:
    result = assess_deal_value(deal)

    assert result.is_valid is False
    assert result.is_known is False
    assert result.issue == issue


def test_pipeline_value_keeps_missing_zero_and_legacy_amounts_distinct() -> None:
    deals = [
        {
            "deal_stage": "discovery",
            "deal_size_amount": 40_000_000,
            "deal_size_low_amount": 30_000_000,
            "deal_size_high_amount": 50_000_000,
            "deal_size_status": "rough_estimate",
        },
        {
            "deal_stage": "proposal",
            "deal_size_amount": 20_000_000,
            "deal_size_status": "customer_budget",
        },
        {
            "deal_stage": "negotiation",
            "deal_size_amount": 25_000_000,
            "deal_size_status": "quoted",
        },
        {
            "deal_stage": "discovery",
            "deal_size_status": "unknown",
        },
        {
            "deal_stage": "qualification",
            "deal_size_amount": 0,
            "deal_size_status": "strategic_zero",
        },
        {
            "deal_stage": "proposal",
            "deal_size_amount": 10_000_000,
        },
        {
            "deal_stage": "discovery",
            "deal_size_amount": 0,
        },
        {
            "deal_stage": "won",
            "deal_size_amount": 100_000_000,
            "deal_size_status": "quoted",
        },
    ]

    result = summarize_pipeline_value(deals, stages=ACTIVE_STAGES)

    assert result == {
        "deal_count": 7,
        "pipeline_value_amount": 95_000_000,
        "pipeline_value_low_amount": 85_000_000,
        "pipeline_value_high_amount": 105_000_000,
        "validated_pipeline_value_amount": 45_000_000,
        "currency": "KRW",
        "currencies": ["KRW"],
        "mixed_currency": False,
        "amount_by_currency": {
            "KRW": {
                "pipeline_value_amount": 95_000_000,
                "pipeline_value_low_amount": 85_000_000,
                "pipeline_value_high_amount": 105_000_000,
                "validated_pipeline_value_amount": 45_000_000,
                "known_amount_count": 5,
            }
        },
        "known_amount_count": 5,
        "missing_amount_count": 1,
        "invalid_amount_count": 1,
        "unclassified_amount_count": 1,
        "strategic_zero_count": 1,
        "amount_coverage_pct": 71.4,
        "status_counts": {
            "unknown": 1,
            "rough_estimate": 1,
            "customer_budget": 1,
            "quoted": 1,
            "strategic_zero": 1,
        },
    }


def test_empty_pipeline_value_has_no_misleading_coverage_percentage() -> None:
    result = summarize_pipeline_value([], stages=ACTIVE_STAGES)

    assert result["deal_count"] == 0
    assert result["pipeline_value_amount"] == 0
    assert result["amount_coverage_pct"] is None
