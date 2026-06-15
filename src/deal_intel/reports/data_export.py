from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import date, datetime
from typing import Any

from deal_intel.reports.weekly_pipeline import build_weekly_pipeline_rows
from deal_intel.schema.interactions import iter_interactions
from deal_intel.schema.metrics import (
    OPEN_STAGES,
    TERMINAL_STAGES,
    VALID_STAGES,
    HealthBandThresholds,
    PipelineTimingSettings,
    assess_deal_data_quality,
    assess_deal_value,
    classify_health,
    is_health_assessed,
)
from deal_intel.schema.qualification_read import select_qualification_snapshot

DATASET_OPEN_DEALS = "open_deals"
DATASET_ALL_DEALS = "all_deals"
DATASET_CLOSED_DEALS = "closed_deals"
VALID_DATASETS = frozenset({
    DATASET_OPEN_DEALS,
    DATASET_ALL_DEALS,
    DATASET_CLOSED_DEALS,
})

OPEN_DEALS_COLUMNS = [
    "deal_id",
    "company",
    "industry",
    "industry_tags",
    "customer_segment",
    "deal_stage",
    "deal_size_amount",
    "deal_size_currency",
    "deal_size_status",
    "expected_close_date",
    "days_in_stage",
    "is_stuck",
    "is_overdue",
    "overdue_days",
    "qualification_framework",
    "qualification_health_pct",
    "qualification_quality_pct",
    "qualification_coverage_pct",
    "qualification_gaps",
    "health_pct",
    "health_band",
    "attention_reasons",
    "objective_action_items",
    "gap_observations",
    "meddpicc_gaps",
    "primary_pain",
    "primary_decision_criteria",
    "last_interaction_date",
    "data_quality_flags",
    "created_at",
    "updated_at",
]

ALL_DEALS_COLUMNS = [
    "deal_id",
    "company",
    "industry",
    "industry_tags",
    "customer_segment",
    "deal_stage",
    "deal_size_amount",
    "deal_size_currency",
    "deal_size_status",
    "expected_close_date",
    "actual_close_date",
    "close_reason",
    "qualification_framework",
    "qualification_health_pct",
    "qualification_quality_pct",
    "qualification_coverage_pct",
    "qualification_gaps",
    "health_pct",
    "health_band",
    "meddpicc_gaps",
    "interaction_count",
    "last_interaction_date",
    "data_quality_flags",
    "archived",
    "created_at",
    "updated_at",
]

CLOSED_DEALS_COLUMNS = [
    "deal_id",
    "company",
    "industry",
    "industry_tags",
    "customer_segment",
    "result",
    "deal_size_amount",
    "deal_size_currency",
    "deal_size_status",
    "expected_close_date",
    "actual_close_date",
    "close_reason",
    "sales_cycle_days",
    "final_qualification_framework",
    "final_qualification_health_pct",
    "final_qualification_quality_pct",
    "final_qualification_coverage_pct",
    "final_qualification_gaps",
    "final_health_pct",
    "final_health_band",
    "final_meddpicc_gaps",
    "primary_pain",
    "primary_decision_criteria",
    "last_interaction_date",
    "created_at",
    "updated_at",
]


def build_data_export(
    deals: Iterable[dict],
    *,
    dataset: str,
    as_of: date,
    health_thresholds: HealthBandThresholds | None = None,
    timing_settings: PipelineTimingSettings | None = None,
    stage: str | None = None,
    industry: str | None = None,
) -> dict:
    """Build deterministic CSV-oriented data extracts without LLM or file IO."""
    if dataset not in VALID_DATASETS:
        raise ValueError(f"dataset {dataset!r} is not valid")
    if not isinstance(as_of, date) or isinstance(as_of, datetime):
        raise ValueError("as_of must be a date")
    if stage not in (None, "") and stage not in VALID_STAGES:
        raise ValueError(f"stage {stage!r} is not valid")

    health_thresholds = health_thresholds or HealthBandThresholds()
    timing_settings = timing_settings or PipelineTimingSettings()
    clean_stage = stage or None
    clean_industry = industry or None

    if dataset == DATASET_OPEN_DEALS:
        return _build_open_deals_export(
            deals,
            as_of=as_of,
            health_thresholds=health_thresholds,
            timing_settings=timing_settings,
            stage=clean_stage,
            industry=clean_industry,
        )

    rows = [
        _build_ledger_row(deal, health_thresholds=health_thresholds)
        for deal in _filter_deals(
            deals,
            dataset=dataset,
            stage=clean_stage,
            industry=clean_industry,
        )
    ]
    rows.sort(key=_ledger_sort_key)
    if dataset == DATASET_CLOSED_DEALS:
        rows = [_closed_row(row) for row in rows]
        columns = CLOSED_DEALS_COLUMNS
    else:
        columns = ALL_DEALS_COLUMNS

    return {
        "report_type": f"data_{dataset}",
        "dataset": dataset,
        "filters": {"stage": clean_stage, "industry": clean_industry},
        "columns": columns,
        "rows": rows,
        "row_count": len(rows),
        "warnings": _warnings(dataset, rows),
    }


def _build_open_deals_export(
    deals: Iterable[dict],
    *,
    as_of: date,
    health_thresholds: HealthBandThresholds,
    timing_settings: PipelineTimingSettings,
    stage: str | None,
    industry: str | None,
) -> dict:
    materialized = list(deals)
    source_by_id = {
        str(deal.get("deal_id")): deal
        for deal in materialized
        if deal.get("deal_id") is not None
    }
    report = build_weekly_pipeline_rows(
        materialized,
        as_of=as_of,
        health_thresholds=health_thresholds,
        timing_settings=timing_settings,
        stage=stage,
        industry=industry,
    )
    rows = [
        _open_row(row, source_by_id.get(str(row.get("deal_id"))) or {})
        for row in report["rows"]
    ]
    return {
        "report_type": f"data_{DATASET_OPEN_DEALS}",
        "dataset": DATASET_OPEN_DEALS,
        "filters": report["filters"],
        "columns": OPEN_DEALS_COLUMNS,
        "rows": rows,
        "row_count": len(rows),
        "warnings": report["warnings"],
    }


def _filter_deals(
    deals: Iterable[dict],
    *,
    dataset: str,
    stage: str | None,
    industry: str | None,
) -> list[dict]:
    filtered = []
    for deal in deals:
        deal_stage = deal.get("deal_stage")
        if stage is not None and deal_stage != stage:
            continue
        if industry is not None and deal.get("industry") != industry:
            continue
        if dataset == DATASET_OPEN_DEALS and deal_stage not in OPEN_STAGES:
            continue
        if dataset == DATASET_CLOSED_DEALS and deal_stage not in TERMINAL_STAGES:
            continue
        filtered.append(deal)
    return filtered


def _open_row(row: dict, source_deal: dict) -> dict:
    return {
        "deal_id": row.get("deal_id"),
        "company": row.get("company"),
        "industry": row.get("industry"),
        "industry_tags": source_deal.get("industry_tags") or [],
        "customer_segment": row.get("customer_segment"),
        "deal_stage": row.get("deal_stage"),
        "deal_size_amount": row.get("deal_size_amount"),
        "deal_size_currency": row.get("deal_size_currency"),
        "deal_size_status": row.get("deal_size_status"),
        "expected_close_date": row.get("expected_close_date"),
        "days_in_stage": row.get("days_in_stage"),
        "is_stuck": row.get("is_stuck"),
        "is_overdue": row.get("is_overdue"),
        "overdue_days": row.get("overdue_days"),
        "qualification_framework": row.get("qualification_framework"),
        "qualification_health_pct": row.get("qualification_health_pct"),
        "qualification_quality_pct": row.get("qualification_quality_pct"),
        "qualification_coverage_pct": row.get("qualification_coverage_pct"),
        "qualification_gaps": row.get("qualification_gaps") or [],
        "health_pct": row.get("health_pct"),
        "health_band": row.get("health_band"),
        "attention_reasons": row.get("attention_reasons") or [],
        "objective_action_items": row.get("objective_action_items") or [],
        "gap_observations": row.get("gap_observations") or [],
        "meddpicc_gaps": row.get("meddpicc_gaps") or [],
        "primary_pain": _theme_label(row.get("primary_pain")),
        "primary_decision_criteria": _theme_label(row.get("primary_decision_criteria")),
        "last_interaction_date": row.get("last_meeting_date"),
        "data_quality_flags": _data_quality_flags(row.get("data_quality") or {}),
        "created_at": source_deal.get("created_at"),
        "updated_at": source_deal.get("updated_at"),
    }


def _build_ledger_row(
    deal: dict,
    *,
    health_thresholds: HealthBandThresholds,
) -> dict:
    qualification = select_qualification_snapshot(deal)
    qualification_latest = qualification.snapshot
    health_band = classify_health(qualification_latest, health_thresholds)
    interactions = iter_interactions(deal)
    return {
        "deal_id": deal.get("deal_id"),
        "company": deal.get("company"),
        "industry": deal.get("industry"),
        "industry_tags": deal.get("industry_tags") or [],
        "customer_segment": deal.get("customer_segment"),
        "deal_stage": deal.get("deal_stage"),
        "deal_size_amount": deal.get("deal_size_amount"),
        "deal_size_currency": deal.get("deal_size_currency") or "KRW",
        "deal_size_status": deal.get("deal_size_status"),
        "expected_close_date": deal.get("expected_close_date"),
        "actual_close_date": deal.get("actual_close_date"),
        "close_reason": deal.get("close_reason"),
        "qualification_framework": qualification.framework_key,
        "qualification_health_pct": qualification_latest.get("health_pct"),
        "qualification_quality_pct": qualification.quality_pct,
        "qualification_coverage_pct": qualification.coverage_pct,
        "qualification_gaps": qualification.gaps,
        "health_pct": (
            float(qualification_latest["health_pct"])
            if is_health_assessed(qualification_latest)
            else None
        ),
        "health_band": health_band.value,
        "meddpicc_gaps": qualification.gaps if qualification.is_meddpicc else [],
        "interaction_count": len(interactions),
        "last_interaction_date": _last_interaction_date(interactions),
        "data_quality_flags": _data_quality_flags(
            assess_deal_data_quality(deal).to_dict()
        ),
        "archived": bool(deal.get("archived")),
        "created_at": deal.get("created_at"),
        "updated_at": deal.get("updated_at"),
        "_primary_pain": _theme_label(_select_theme(deal, "identify_pain")),
        "_primary_decision_criteria": _theme_label(
            _select_theme(deal, "decision_criteria")
        ),
    }


def _closed_row(row: dict) -> dict:
    return {
        "deal_id": row.get("deal_id"),
        "company": row.get("company"),
        "industry": row.get("industry"),
        "industry_tags": row.get("industry_tags") or [],
        "customer_segment": row.get("customer_segment"),
        "result": row.get("deal_stage"),
        "deal_size_amount": row.get("deal_size_amount"),
        "deal_size_currency": row.get("deal_size_currency"),
        "deal_size_status": row.get("deal_size_status"),
        "expected_close_date": row.get("expected_close_date"),
        "actual_close_date": row.get("actual_close_date"),
        "close_reason": row.get("close_reason"),
        "sales_cycle_days": _sales_cycle_days(
            row.get("created_at"),
            row.get("actual_close_date"),
        ),
        "final_qualification_framework": row.get("qualification_framework"),
        "final_qualification_health_pct": row.get("qualification_health_pct"),
        "final_qualification_quality_pct": row.get("qualification_quality_pct"),
        "final_qualification_coverage_pct": row.get("qualification_coverage_pct"),
        "final_qualification_gaps": row.get("qualification_gaps"),
        "final_health_pct": row.get("health_pct"),
        "final_health_band": row.get("health_band"),
        "final_meddpicc_gaps": row.get("meddpicc_gaps"),
        "primary_pain": row.get("_primary_pain"),
        "primary_decision_criteria": row.get("_primary_decision_criteria"),
        "last_interaction_date": row.get("last_interaction_date"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def _data_quality_flags(data_quality: dict) -> list[str]:
    statuses = data_quality.get("field_statuses")
    if not isinstance(statuses, dict):
        return []
    flags = []
    for field, status in statuses.items():
        if status in {"missing", "invalid"}:
            flags.append(f"{field}:{status}")
    return flags


def _select_theme(deal: dict, dimension: str) -> dict | None:
    themes = deal.get("customer_themes")
    if not isinstance(themes, list):
        return None
    candidates = [
        theme
        for theme in themes
        if isinstance(theme, dict)
        and theme.get("dimension") == dimension
        and str(theme.get("evidence") or "")
    ]
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda theme: (
            -_int(theme.get("importance")),
            str(theme.get("label") or ""),
        ),
    )[0]


def _theme_label(theme: Any) -> str | None:
    if not isinstance(theme, dict):
        return None
    label = str(theme.get("label") or "").strip()
    if not label:
        return None
    evidence = str(theme.get("evidence") or "").strip()
    if evidence:
        return f"{label} | {evidence}"
    return label


def _last_interaction_date(interactions: list[dict]) -> str | None:
    dates = [
        parsed
        for parsed in (_parse_date(interaction.get("date")) for interaction in interactions)
        if parsed is not None
    ]
    return max(dates).isoformat() if dates else None


def _sales_cycle_days(created_at: Any, closed_at: Any) -> int | None:
    start = _parse_date(created_at)
    end = _parse_date(closed_at)
    if start is None or end is None:
        return None
    return max((end - start).days, 0)


def _parse_date(value: Any) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if not isinstance(value, str) or not value:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _ledger_sort_key(row: dict) -> tuple:
    return (
        row.get("deal_stage") not in OPEN_STAGES,
        row.get("expected_close_date") or "9999-12-31",
        str(row.get("company") or ""),
    )


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _warnings(dataset: str, rows: list[dict]) -> list[str]:
    warnings = []
    if not rows:
        warnings.append(f"no_{dataset}")
    if any(row.get("data_quality_flags") for row in rows):
        warnings.append("incomplete_data_quality")
    if dataset == DATASET_ALL_DEALS and any(_invalid_deal_value(row) for row in rows):
        warnings.append("invalid_deal_value")
    return warnings


def _invalid_deal_value(row: dict) -> bool:
    return not assess_deal_value(row).is_valid


def preview_rows_for_response(rows: list[dict], *, limit: int = 5) -> list[dict]:
    """Return a small JSON-safe preview for MCP responses."""
    preview = []
    for row in rows[:limit]:
        item = {}
        for key, value in row.items():
            if key.startswith("_"):
                continue
            if isinstance(value, (dict, list)):
                item[key] = json.loads(json.dumps(value, ensure_ascii=False))
            else:
                item[key] = value
        preview.append(item)
    return preview
