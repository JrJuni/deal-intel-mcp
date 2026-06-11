from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from datetime import date, datetime
from typing import Any

from deal_intel.schema.metrics import (
    ACTIVE_STAGES,
    OPEN_STAGES,
    STALLED_STAGES,
    TERMINAL_STAGES,
    VALID_STAGES,
    CloseDateStatus,
    HealthBand,
    HealthBandThresholds,
    PipelineTimingSettings,
    WinRateSettings,
    assess_pipeline_timing,
    build_attention_reasons,
    classify_health,
    is_health_assessed,
    summarize_data_quality,
    summarize_pipeline_value,
    summarize_win_rate,
)

CANONICAL_STAGE_ORDER = (
    "discovery",
    "qualification",
    "proposal",
    "negotiation",
    "stalled",
    "won",
    "lost",
)


def build_pipeline_health_summary(
    deals: Iterable[dict],
    *,
    as_of: date,
    health_thresholds: HealthBandThresholds | None = None,
    timing_settings: PipelineTimingSettings | None = None,
    win_rate_settings: WinRateSettings | None = None,
    stage: str | None = None,
    industry: str | None = None,
) -> dict:
    """Build the shared pipeline-health metric surface.

    This module is intentionally pure: callers provide already-fetched deal
    documents and all metric settings. It does not touch MongoDB, embeddings,
    or LLM providers.
    """
    if not isinstance(as_of, date) or isinstance(as_of, datetime):
        raise ValueError("as_of must be a date")
    if stage not in (None, "") and stage not in VALID_STAGES:
        raise ValueError(f"stage {stage!r} is not valid")

    health_thresholds = health_thresholds or HealthBandThresholds()
    timing_settings = timing_settings or PipelineTimingSettings()
    win_rate_settings = win_rate_settings or WinRateSettings()

    filtered = _filter_deals(deals, stage=stage or None, industry=industry or None)
    health = _health_summary(filtered, health_thresholds)
    active = [deal for deal in filtered if deal.get("deal_stage") in ACTIVE_STAGES]
    stalled = [deal for deal in filtered if deal.get("deal_stage") in STALLED_STAGES]
    open_deals = [deal for deal in filtered if deal.get("deal_stage") in OPEN_STAGES]
    terminal = [
        deal for deal in filtered if deal.get("deal_stage") in TERMINAL_STAGES
    ]

    active_health = _health_summary(active, health_thresholds)
    timing_rows = _timing_rows(
        filtered,
        as_of=as_of,
        health_thresholds=health_thresholds,
        timing_settings=timing_settings,
    )
    attention = _attention_summary(timing_rows)
    pipeline_values = {
        "active": summarize_pipeline_value(filtered, stages=ACTIVE_STAGES),
        "stalled": summarize_pipeline_value(filtered, stages=STALLED_STAGES),
        "open": summarize_pipeline_value(filtered, stages=OPEN_STAGES),
    }
    win_rate = summarize_win_rate(filtered, settings=win_rate_settings)
    data_quality = summarize_data_quality(filtered)
    stage_breakdown = [
        _stage_row(
            filtered,
            timing_rows,
            stage_name=stage_name,
            health_thresholds=health_thresholds,
        )
        for stage_name in CANONICAL_STAGE_ORDER
    ]

    stuck_count = sum(row["timing"].is_stuck is True for row in timing_rows)
    overdue_count = sum(row["timing"].is_overdue is True for row in timing_rows)

    return {
        "filters": {"stage": stage or None, "industry": industry or None},
        "kpis": {
            "deal_count": len(filtered),
            "active_deal_count": len(active),
            "open_deal_count": len(open_deals),
            "stalled_deal_count": len(stalled),
            "terminal_deal_count": len(terminal),
            "pipeline_value_currency": pipeline_values["open"]["currency"],
            "pipeline_value_currencies": pipeline_values["open"]["currencies"],
            "mixed_pipeline_value_currency": pipeline_values["open"][
                "mixed_currency"
            ],
            "active_pipeline_value_amount": pipeline_values["active"][
                "pipeline_value_amount"
            ],
            "open_pipeline_value_amount": pipeline_values["open"][
                "pipeline_value_amount"
            ],
            "avg_health_pct": active_health["avg_health_pct"],
            "health_coverage_pct": active_health["health_coverage_pct"],
            "health_assessed_count": active_health["assessed_count"],
            "health_unassessed_count": active_health["unassessed_count"],
            "stuck_deal_count": stuck_count,
            "overdue_deal_count": overdue_count,
            "attention_deal_count": attention["unique_deal_count"],
            "win_rate_pct": win_rate["win_rate_pct"],
            "data_quality_coverage_pct": data_quality["complete_deal_pct"],
            "confirmed_data_quality_coverage_pct": data_quality[
                "confirmed_complete_deal_pct"
            ],
        },
        "stage_breakdown": stage_breakdown,
        "health_bands": health["band_counts"],
        "attention_reasons": attention,
        "pipeline_values": pipeline_values,
        "win_rate": win_rate,
        "data_quality": data_quality,
        "warnings": _warnings(
            health=active_health,
            pipeline_values=pipeline_values,
            win_rate=win_rate,
            data_quality=data_quality,
            timing_rows=timing_rows,
        ),
    }


def _filter_deals(
    deals: Iterable[dict],
    *,
    stage: str | None,
    industry: str | None,
) -> list[dict]:
    filtered = []
    for deal in deals:
        if stage is not None and deal.get("deal_stage") != stage:
            continue
        if industry is not None and deal.get("industry") != industry:
            continue
        filtered.append(deal)
    return filtered


def _health_summary(deals: list[dict], thresholds: HealthBandThresholds) -> dict:
    assessed_scores = [
        float((deal.get("meddpicc_latest") or {})["health_pct"])
        for deal in deals
        if is_health_assessed(deal.get("meddpicc_latest"))
    ]
    band_counts = _empty_band_counts()
    for deal in deals:
        band = classify_health(deal.get("meddpicc_latest"), thresholds)
        band_counts[band.value] += 1

    deal_count = len(deals)
    assessed_count = len(assessed_scores)
    return {
        "avg_health_pct": (
            round(sum(assessed_scores) / assessed_count, 1)
            if assessed_count
            else None
        ),
        "health_coverage_pct": (
            round(assessed_count / deal_count * 100, 1) if deal_count else None
        ),
        "assessed_count": assessed_count,
        "unassessed_count": deal_count - assessed_count,
        "band_counts": band_counts,
    }


def _empty_band_counts() -> dict[str, int]:
    return {band.value: 0 for band in HealthBand}


def _timing_rows(
    deals: list[dict],
    *,
    as_of: date,
    health_thresholds: HealthBandThresholds,
    timing_settings: PipelineTimingSettings,
) -> list[dict[str, Any]]:
    rows = []
    for deal in deals:
        stage = deal.get("deal_stage")
        band = classify_health(deal.get("meddpicc_latest"), health_thresholds)
        timing = assess_pipeline_timing(
            deal,
            as_of=as_of,
            settings=timing_settings,
        )
        rows.append(
            {
                "deal": deal,
                "stage": stage,
                "health_band": band,
                "timing": timing,
                "attention_reasons": build_attention_reasons(
                    stage=stage,
                    health_band=band,
                    timing=timing,
                ),
            }
        )
    return rows


def _attention_summary(rows: list[dict[str, Any]]) -> dict:
    counts = Counter(
        reason for row in rows for reason in row["attention_reasons"]
    )
    unique_count = sum(bool(row["attention_reasons"]) for row in rows)
    return {
        "stalled_count": counts["stalled"],
        "overdue_count": counts["overdue"],
        "stuck_count": counts["stuck"],
        "at_risk_count": counts["at_risk"],
        "unique_deal_count": unique_count,
        "attention_deal_count": unique_count,
    }


def _stage_row(
    deals: list[dict],
    timing_rows: list[dict[str, Any]],
    *,
    stage_name: str,
    health_thresholds: HealthBandThresholds,
) -> dict:
    stage_deals = [
        deal for deal in deals if deal.get("deal_stage") == stage_name
    ]
    health = _health_summary(stage_deals, health_thresholds)
    stage_timing = [
        row for row in timing_rows if row["stage"] == stage_name
    ]
    stage_value = summarize_pipeline_value(
        stage_deals,
        stages={stage_name} if stage_name in OPEN_STAGES else frozenset(),
    )
    return {
        "stage": stage_name,
        "count": len(stage_deals),
        "avg_health_pct": health["avg_health_pct"],
        "health_coverage_pct": health["health_coverage_pct"],
        "health_assessed_count": health["assessed_count"],
        "health_unassessed_count": health["unassessed_count"],
        "health_bands": health["band_counts"],
        "pipeline_value_amount": stage_value["pipeline_value_amount"],
        "pipeline_value_currency": stage_value["currency"],
        "mixed_pipeline_value_currency": stage_value["mixed_currency"],
        "amount_coverage_pct": stage_value["amount_coverage_pct"],
        "stuck_count": sum(row["timing"].is_stuck is True for row in stage_timing),
        "overdue_count": sum(
            row["timing"].is_overdue is True for row in stage_timing
        ),
    }


def _warnings(
    *,
    health: dict,
    pipeline_values: dict,
    win_rate: dict,
    data_quality: dict,
    timing_rows: list[dict[str, Any]],
) -> list[str]:
    warnings = list(win_rate["warnings"])
    open_value = pipeline_values["open"]
    if health["unassessed_count"]:
        warnings.append("unassessed_health")
    if open_value["missing_amount_count"]:
        warnings.append("missing_amount")
    if open_value["invalid_amount_count"]:
        warnings.append("invalid_amount")
    if open_value["unclassified_amount_count"]:
        warnings.append("unclassified_amount")
    if open_value["mixed_currency"]:
        warnings.append("mixed_currency")

    open_timing = [
        row["timing"]
        for row in timing_rows
        if row["deal"].get("deal_stage") in OPEN_STAGES
    ]
    if any(item.close_date_status == CloseDateStatus.MISSING for item in open_timing):
        warnings.append("missing_expected_close_date")
    if any(item.close_date_status == CloseDateStatus.INVALID for item in open_timing):
        warnings.append("invalid_expected_close_date")
    if data_quality["complete_deal_count"] < data_quality["deal_count"]:
        warnings.append("incomplete_data_quality")
    return _dedupe(warnings)


def _dedupe(items: list[str]) -> list[str]:
    seen = set()
    unique = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        unique.append(item)
    return unique
