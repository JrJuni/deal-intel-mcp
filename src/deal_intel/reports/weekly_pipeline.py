from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime
from typing import Any

from deal_intel.schema.deal_gaps import MEDDPICC_FIELD_LABELS
from deal_intel.schema.evidence_sources import evidence_source_label
from deal_intel.schema.gap_actionability import (
    CTA_POLICY_ALLOWED,
    annotate_gap_actionability,
)
from deal_intel.schema.interactions import iter_interactions
from deal_intel.schema.metrics import (
    OPEN_STAGES,
    VALID_STAGES,
    HealthBand,
    HealthBandThresholds,
    PipelineTimingSettings,
    assess_deal_data_quality,
    assess_deal_value,
    assess_pipeline_timing,
    build_attention_reasons,
    classify_health,
    is_health_assessed,
)

REPORT_TYPE = "weekly_pipeline"
THEME_DIMENSION_PAIN = "identify_pain"
THEME_DIMENSION_DECISION_CRITERIA = "decision_criteria"

COLUMNS = [
    "deal_id",
    "company",
    "industry",
    "deal_stage",
    "deal_size_amount",
    "deal_size_currency",
    "deal_size_status",
    "expected_close_date",
    "days_in_stage",
    "stuck_status",
    "is_stuck",
    "close_date_status",
    "is_overdue",
    "overdue_days",
    "health_pct",
    "health_band",
    "meddpicc_gaps",
    "last_meeting_date",
    "primary_pain",
    "primary_decision_criteria",
    "attention_reasons",
    "objective_action_items",
    "gap_observations",
    "data_quality",
]


def build_weekly_pipeline_rows(
    deals: Iterable[dict],
    *,
    as_of: date,
    health_thresholds: HealthBandThresholds | None = None,
    timing_settings: PipelineTimingSettings | None = None,
    stage: str | None = None,
    industry: str | None = None,
) -> dict:
    """Build weekly pipeline review rows without storage, LLM, or file IO."""
    if not isinstance(as_of, date) or isinstance(as_of, datetime):
        raise ValueError("as_of must be a date")
    if stage not in (None, "") and stage not in VALID_STAGES:
        raise ValueError(f"stage {stage!r} is not valid")

    health_thresholds = health_thresholds or HealthBandThresholds()
    timing_settings = timing_settings or PipelineTimingSettings()
    filtered = _filter_open_deals(deals, stage=stage or None, industry=industry or None)
    rows = [
        _build_row(
            deal,
            as_of=as_of,
            health_thresholds=health_thresholds,
            timing_settings=timing_settings,
        )
        for deal in filtered
    ]
    rows.sort(key=_sort_key)
    return {
        "report_type": REPORT_TYPE,
        "filters": {"stage": stage or None, "industry": industry or None},
        "columns": COLUMNS,
        "rows": rows,
        "row_count": len(rows),
        "warnings": _build_warnings(rows),
    }


def _filter_open_deals(
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
        if deal.get("deal_stage") not in OPEN_STAGES:
            continue
        filtered.append(deal)
    return filtered


def _build_row(
    deal: dict,
    *,
    as_of: date,
    health_thresholds: HealthBandThresholds,
    timing_settings: PipelineTimingSettings,
) -> dict:
    meddpicc_latest = deal.get("meddpicc_latest") or {}
    health_band = classify_health(meddpicc_latest, health_thresholds)
    timing = assess_pipeline_timing(deal, as_of=as_of, settings=timing_settings)
    attention_reasons = build_attention_reasons(
        stage=deal.get("deal_stage"),
        health_band=health_band,
        timing=timing,
    )
    meddpicc_gaps = _meddpicc_gaps(meddpicc_latest)
    attention_gaps = _attention_gap_rows(
        timing=timing,
        attention_reasons=attention_reasons,
    )
    themes = _theme_candidates(deal)
    return {
        "deal_id": deal.get("deal_id"),
        "company": deal.get("company"),
        "industry": deal.get("industry"),
        "deal_stage": deal.get("deal_stage"),
        "deal_size_amount": deal.get("deal_size_amount"),
        "deal_size_currency": deal.get("deal_size_currency") or "KRW",
        "deal_size_status": deal.get("deal_size_status"),
        "expected_close_date": deal.get("expected_close_date"),
        "days_in_stage": timing.days_in_stage,
        "stuck_status": timing.stuck_status.value,
        "is_stuck": timing.is_stuck,
        "close_date_status": timing.close_date_status.value,
        "is_overdue": timing.is_overdue,
        "overdue_days": timing.overdue_days,
        "health_pct": (
            float(meddpicc_latest["health_pct"])
            if is_health_assessed(meddpicc_latest)
            else None
        ),
        "health_band": health_band.value,
        "meddpicc_gaps": meddpicc_gaps,
        "last_meeting_date": _last_meeting_date(deal),
        "primary_pain": _select_primary_theme(themes, THEME_DIMENSION_PAIN),
        "primary_decision_criteria": _select_primary_theme(
            themes,
            THEME_DIMENSION_DECISION_CRITERIA,
        ),
        "attention_reasons": attention_reasons,
        "objective_action_items": [
            gap for gap in attention_gaps if gap["cta_policy"] == CTA_POLICY_ALLOWED
        ],
        "gap_observations": [
            *[
                gap
                for gap in attention_gaps
                if gap["cta_policy"] != CTA_POLICY_ALLOWED
            ],
            *_meddpicc_gap_observations(meddpicc_gaps),
        ],
        "data_quality": assess_deal_data_quality(deal).to_dict(),
    }


def _meddpicc_gaps(meddpicc_latest: dict) -> list[str]:
    gaps = meddpicc_latest.get("gaps", [])
    if not isinstance(gaps, list):
        return []
    return [str(item) for item in gaps]


def _meddpicc_gap_observations(gaps: list[str]) -> list[dict]:
    rows = []
    for gap_name in gaps:
        label = MEDDPICC_FIELD_LABELS.get(gap_name, gap_name)
        rows.append(
            annotate_gap_actionability(
                {
                    "gap_id": f"meddpicc:{gap_name}",
                    "field": f"meddpicc.{gap_name}",
                    "label": label,
                    "status": "missing",
                    "impact_area": "sales_action",
                    "severity": "medium",
                    "reason": f"MEDDPICC gap remains open: {label}.",
                }
            )
        )
    return rows


def _attention_gap_rows(
    *,
    timing: Any,
    attention_reasons: list[str],
) -> list[dict]:
    rows = []
    if "overdue" in attention_reasons:
        rows.append(
            annotate_gap_actionability(
                {
                    "gap_id": "attention:overdue",
                    "field": "expected_close_date",
                    "label": "Overdue close date",
                    "status": "attention",
                    "impact_area": "sales_action",
                    "severity": "high",
                    "reason": (
                        "Expected close date is overdue by "
                        f"{timing.overdue_days or 0} day(s)."
                    ),
                    "recommended_action": "review_close_plan",
                }
            )
        )
    if "stuck" in attention_reasons:
        rows.append(
            annotate_gap_actionability(
                {
                    "gap_id": "attention:stuck",
                    "field": "deal_stage",
                    "label": "Stage is stuck",
                    "status": "attention",
                    "impact_area": "sales_action",
                    "severity": "medium",
                    "reason": (
                        "Deal has stayed in the current active stage past the "
                        "stuck threshold."
                    ),
                    "recommended_action": "review_next_step",
                }
            )
        )
    if "stalled" in attention_reasons:
        rows.append(
            annotate_gap_actionability(
                {
                    "gap_id": "attention:stalled",
                    "field": "deal_stage",
                    "label": "Stage is stalled",
                    "status": "attention",
                    "impact_area": "sales_action",
                    "severity": "medium",
                    "reason": "Deal is explicitly marked stalled.",
                    "recommended_action": "review_reactivation_path",
                }
            )
        )
    if "at_risk" in attention_reasons:
        rows.append(
            annotate_gap_actionability(
                {
                    "gap_id": "attention:at_risk",
                    "field": "meddpicc.health",
                    "label": "At-risk health",
                    "status": "weak_signal",
                    "impact_area": "sales_action",
                    "severity": "high",
                    "reason": (
                        "MEDDPICC health is at risk; review the underlying "
                        "evidence before prescribing an action."
                    ),
                }
            )
        )
    return rows


def _last_meeting_date(deal: dict) -> str | None:
    dates = [
        parsed
        for parsed in (
            _parse_iso_date(interaction.get("date"))
            for interaction in iter_interactions(deal)
        )
        if parsed is not None
    ]
    return max(dates).isoformat() if dates else None


def _theme_candidates(deal: dict) -> list[dict]:
    deal_themes = deal.get("customer_themes")
    if isinstance(deal_themes, list) and deal_themes:
        return [theme for theme in deal_themes if isinstance(theme, dict)]

    themes = []
    for interaction in iter_interactions(deal):
        interaction_themes = interaction.get("customer_themes")
        if not isinstance(interaction_themes, list):
            continue
        for theme in interaction_themes:
            if not isinstance(theme, dict):
                continue
            themes.append(
                {
                    **theme,
                    "interaction_id": interaction.get("interaction_id"),
                    "interaction_date": interaction.get("date"),
                    "interaction_type": interaction.get("interaction_type"),
                    "source_confidence": interaction.get("source_confidence"),
                    "subject": interaction.get("subject"),
                    "meeting_id": interaction.get("meeting_id"),
                    "meeting_date": interaction.get("date"),
                }
            )
    return themes


def _select_primary_theme(themes: list[dict], dimension: str) -> dict | None:
    candidates = [
        theme
        for theme in themes
        if theme.get("dimension") == dimension and str(theme.get("evidence") or "")
    ]
    if not candidates:
        return None

    selected = sorted(
        candidates,
        key=lambda theme: (
            -_importance(theme),
            -_date_ordinal(theme.get("meeting_date")),
            str(theme.get("theme_key") or ""),
            str(theme.get("evidence") or ""),
        ),
    )[0]
    return {
        "theme_key": selected.get("theme_key"),
        "label": selected.get("label"),
        "evidence": selected.get("evidence"),
        "importance": _importance(selected),
        "interaction_id": selected.get("interaction_id"),
        "interaction_date": selected.get("interaction_date"),
        "interaction_type": selected.get("interaction_type"),
        "source_confidence": selected.get("source_confidence"),
        "source_label": evidence_source_label(selected),
        "subject": selected.get("subject"),
        "meeting_id": selected.get("meeting_id"),
        "meeting_date": selected.get("meeting_date"),
    }


def _importance(theme: dict) -> int:
    try:
        importance = int(theme.get("importance", 0))
    except (TypeError, ValueError):
        return 0
    return importance


def _date_ordinal(value: Any) -> int:
    parsed = _parse_iso_date(value)
    return parsed.toordinal() if parsed else 0


def _sort_key(row: dict) -> tuple:
    return (
        row["is_overdue"] is not True,
        row["is_stuck"] is not True,
        row["deal_stage"] != "stalled",
        row["health_band"] != HealthBand.AT_RISK.value,
        _expected_close_sort_value(row["expected_close_date"]),
        -_valid_amount(row),
        str(row.get("company") or ""),
    )


def _expected_close_sort_value(value: Any) -> date:
    return _parse_iso_date(value) or date.max


def _valid_amount(row: dict) -> int:
    assessment = assess_deal_value(row)
    if assessment.is_valid and assessment.is_known:
        return assessment.amount or 0
    return 0


def _parse_iso_date(value: Any) -> date | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _build_warnings(rows: list[dict]) -> list[str]:
    warnings = []
    if not rows:
        warnings.append("no_open_deals")
    if any(row["health_band"] == HealthBand.UNASSESSED.value for row in rows):
        warnings.append("unassessed_health")
    if any(row["close_date_status"] == "missing" for row in rows):
        warnings.append("missing_expected_close_date")
    if any(row["close_date_status"] == "invalid" for row in rows):
        warnings.append("invalid_expected_close_date")
    if any(row["last_meeting_date"] is None for row in rows):
        warnings.append("missing_last_meeting_date")
    if any(row["primary_pain"] is None for row in rows):
        warnings.append("missing_primary_pain")
    if any(row["primary_decision_criteria"] is None for row in rows):
        warnings.append("missing_primary_decision_criteria")
    if any(not row["data_quality"]["is_complete"] for row in rows):
        warnings.append("incomplete_data_quality")
    return warnings
