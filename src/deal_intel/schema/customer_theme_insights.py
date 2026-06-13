from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import date
from typing import Any

from deal_intel.schema.customer_themes import THEME_DIMENSIONS, THEME_TAXONOMY
from deal_intel.schema.evidence_sources import evidence_source_label
from deal_intel.schema.interactions import (
    DEFAULT_INTERACTION_TYPES,
    VALID_SOURCE_CONFIDENCE,
)
from deal_intel.schema.meddpicc import VALID_STAGES

TERMINAL_STAGES = frozenset({"won", "lost"})
VALID_STAGE_FILTERS = VALID_STAGES | {"active", "all"}
VALID_DIMENSION_FILTERS = THEME_DIMENSIONS | {"all"}
VALID_SOURCE_CONFIDENCE_FILTERS = VALID_SOURCE_CONFIDENCE | {"all"}
VALID_GROUP_BY = frozenset({"stage", "industry", "dimension"})
MAX_TOP_K = 20
MAX_EVIDENCE_LIMIT = 50

DIMENSION_ORDER = {
    "identify_pain": 0,
    "decision_criteria": 1,
    "metrics": 2,
}
STAGE_ORDER = {
    "discovery": 0,
    "qualification": 1,
    "proposal": 2,
    "negotiation": 3,
    "stalled": 4,
    "won": 5,
    "lost": 6,
}


def validate_breakdown_inputs(
    *,
    dimension: str,
    stage: str,
    group_by: str,
    top_k: int,
) -> None:
    _validate_dimension(dimension)
    _validate_stage(stage)
    if group_by not in VALID_GROUP_BY:
        raise ValueError(f"group_by {group_by!r} is not valid")
    _validate_int_range("top_k", top_k, minimum=1, maximum=MAX_TOP_K)


def validate_evidence_inputs(
    *,
    theme_key: str,
    dimension: str,
    stage: str,
    limit: int,
    min_importance: int,
    interaction_type: str = "all",
    source_confidence: str = "all",
    valid_interaction_types: Iterable[str] | None = None,
) -> None:
    if theme_key not in THEME_TAXONOMY:
        raise ValueError(f"theme_key {theme_key!r} is not valid")
    _validate_dimension(dimension)
    _validate_stage(stage)
    _validate_int_range("limit", limit, minimum=1, maximum=MAX_EVIDENCE_LIMIT)
    _validate_int_range("min_importance", min_importance, minimum=1, maximum=5)
    _validate_interaction_type_filter(
        interaction_type,
        valid_interaction_types=valid_interaction_types,
    )
    _validate_source_confidence_filter(source_confidence)


def build_customer_theme_breakdown(
    deals: Iterable[dict],
    *,
    dimension: str = "all",
    stage: str = "active",
    industry: str | None = None,
    group_by: str = "stage",
    top_k: int = 5,
) -> dict:
    """Build a read-only theme comparison surface from deal documents."""
    validate_breakdown_inputs(
        dimension=dimension,
        stage=stage,
        group_by=group_by,
        top_k=top_k,
    )
    scoped_deals = _filter_deals(deals, stage=stage, industry=industry)
    scoped_deal_ids = {str(deal.get("deal_id") or "") for deal in scoped_deals}
    scoped_deal_ids.discard("")
    evidenced_deal_ids = {
        str(deal.get("deal_id") or "")
        for deal in scoped_deals
        if _theme_records(deal, dimension=dimension)
    }
    evidenced_deal_ids.discard("")

    group_deal_ids: dict[str, set[str]] = defaultdict(set)
    group_evidenced_deal_ids: dict[str, set[str]] = defaultdict(set)
    per_deal_theme_importance: dict[tuple[str, str, str], int] = {}
    group_labels: dict[str, str] = {}

    for deal in scoped_deals:
        deal_id = str(deal.get("deal_id") or "")
        records = _theme_records(deal, dimension=dimension)
        group_values = _group_values(deal, records, group_by=group_by)
        for group_value in group_values:
            group_deal_ids[group_value].add(deal_id)
            group_labels[group_value] = group_value
        if not records:
            continue
        for record in records:
            record_group_values = (
                [record["dimension"]]
                if group_by == "dimension"
                else group_values
            )
            for group_value in record_group_values:
                group_evidenced_deal_ids[group_value].add(deal_id)
                key = (group_value, record["theme_key"], deal_id)
                per_deal_theme_importance[key] = max(
                    per_deal_theme_importance.get(key, 0),
                    record["importance"],
                )

    groups = []
    for group_value in sorted(group_deal_ids, key=_group_sort_key(group_by)):
        deal_ids = group_deal_ids[group_value]
        evidenced_ids = group_evidenced_deal_ids.get(group_value, set())
        themes = _theme_summaries(
            group_value=group_value,
            per_deal_theme_importance=per_deal_theme_importance,
            deals_with_evidence=len(evidenced_ids),
            total_deals=len(deal_ids),
            top_k=top_k,
        )
        groups.append(
            {
                "group_by": group_by,
                "group_value": group_value,
                "label": group_labels.get(group_value, group_value),
                "deal_count": len(deal_ids),
                "deals_with_evidence": len(evidenced_ids),
                "coverage_pct": _pct(len(evidenced_ids), len(deal_ids)),
                "themes": themes,
            }
        )

    return {
        "filters": {
            "dimension": dimension,
            "stage": stage,
            "industry": industry,
            "group_by": group_by,
            "top_k": top_k,
        },
        "summary": {
            "deals_analyzed": len(scoped_deal_ids),
            "deals_with_evidence": len(evidenced_deal_ids),
            "coverage_pct": _pct(len(evidenced_deal_ids), len(scoped_deal_ids)),
            "group_count": len(groups),
        },
        "groups": groups,
        "warnings": _warnings(
            deals_analyzed=len(scoped_deal_ids),
            deals_with_evidence=len(evidenced_deal_ids),
        ),
    }


def build_customer_theme_evidence(
    deals: Iterable[dict],
    *,
    theme_key: str,
    dimension: str = "all",
    stage: str = "active",
    industry: str | None = None,
    limit: int = 10,
    min_importance: int = 1,
    interaction_type: str = "all",
    source_confidence: str = "all",
    valid_interaction_types: Iterable[str] | None = None,
) -> dict:
    """Return curated theme evidence without raw meeting notes."""
    validate_evidence_inputs(
        theme_key=theme_key,
        dimension=dimension,
        stage=stage,
        limit=limit,
        min_importance=min_importance,
        interaction_type=interaction_type,
        source_confidence=source_confidence,
        valid_interaction_types=valid_interaction_types,
    )
    scoped_deals = _filter_deals(deals, stage=stage, industry=industry)
    scoped_deal_ids = {str(deal.get("deal_id") or "") for deal in scoped_deals}
    scoped_deal_ids.discard("")

    rows = []
    seen: set[tuple[str, str, str, str]] = set()
    for deal in scoped_deals:
        for record in _theme_records(
            deal,
            dimension=dimension,
            interaction_type=interaction_type,
            source_confidence=source_confidence,
        ):
            if record["theme_key"] != theme_key:
                continue
            if record["importance"] < min_importance:
                continue
            identity = (
                str(deal.get("deal_id") or ""),
                record["dimension"],
                record["evidence"],
                str(record.get("interaction_id") or record.get("meeting_id") or ""),
            )
            if identity in seen:
                continue
            seen.add(identity)
            rows.append(
                {
                    "deal_id": deal.get("deal_id"),
                    "company": deal.get("company"),
                    "industry": deal.get("industry"),
                    "customer_segment": deal.get("customer_segment"),
                    "deal_stage": deal.get("deal_stage"),
                    "theme_key": record["theme_key"],
                    "label": record["label"],
                    "dimension": record["dimension"],
                    "evidence": record["evidence"],
                    "importance": record["importance"],
                    "meeting_id": record.get("meeting_id"),
                    "meeting_date": record.get("meeting_date"),
                    "interaction_id": record.get("interaction_id"),
                    "interaction_date": record.get("interaction_date"),
                    "interaction_type": record.get("interaction_type"),
                    "source_confidence": record.get("source_confidence"),
                    "source_label": evidence_source_label(record),
                    "subject": record.get("subject"),
                }
            )

    rows.sort(
        key=lambda row: (
            -int(row.get("importance") or 0),
            -_date_ordinal(row.get("interaction_date") or row.get("meeting_date")),
            str(row.get("company") or ""),
            str(row.get("evidence") or ""),
        )
    )
    limited_rows = rows[:limit]
    unique_deals = {str(row.get("deal_id") or "") for row in rows}
    unique_deals.discard("")

    return {
        "filters": {
            "theme_key": theme_key,
            "label": THEME_TAXONOMY[theme_key],
            "dimension": dimension,
            "stage": stage,
            "industry": industry,
            "limit": limit,
            "min_importance": min_importance,
            "interaction_type": interaction_type,
            "source_confidence": source_confidence,
        },
        "summary": {
            "deals_analyzed": len(scoped_deal_ids),
            "unique_deal_count": len(unique_deals),
            "evidence_count": len(rows),
            "returned_count": len(limited_rows),
        },
        "evidence": limited_rows,
        "warnings": _warnings(
            deals_analyzed=len(scoped_deal_ids),
            deals_with_evidence=len(unique_deals),
        ),
    }


def _validate_dimension(dimension: str) -> None:
    if dimension not in VALID_DIMENSION_FILTERS:
        raise ValueError(f"dimension {dimension!r} is not valid")


def _validate_stage(stage: str) -> None:
    if stage not in VALID_STAGE_FILTERS:
        raise ValueError(f"stage {stage!r} is not valid")


def _validate_int_range(name: str, value: int, *, minimum: int, maximum: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    if value < minimum or value > maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")


def _validate_interaction_type_filter(
    interaction_type: str,
    *,
    valid_interaction_types: Iterable[str] | None,
) -> None:
    normalized = str(interaction_type or "").strip().lower()
    if normalized == "all":
        return
    valid_values = {
        str(value or "").strip().lower()
        for value in (valid_interaction_types or DEFAULT_INTERACTION_TYPES)
    }
    valid_values.discard("")
    if normalized not in valid_values:
        expected = ", ".join(sorted(valid_values | {"all"}))
        raise ValueError(f"interaction_type must be one of: {expected}")


def _validate_source_confidence_filter(source_confidence: str) -> None:
    normalized = str(source_confidence or "").strip().lower()
    if normalized not in VALID_SOURCE_CONFIDENCE_FILTERS:
        expected = ", ".join(sorted(VALID_SOURCE_CONFIDENCE_FILTERS))
        raise ValueError(f"source_confidence must be one of: {expected}")


def _filter_deals(
    deals: Iterable[dict],
    *,
    stage: str,
    industry: str | None,
) -> list[dict]:
    filtered = []
    for deal in deals:
        deal_stage = deal.get("deal_stage")
        if stage == "active":
            if deal_stage in TERMINAL_STAGES:
                continue
        elif stage != "all" and deal_stage != stage:
            continue
        if industry is not None and deal.get("industry") != industry:
            continue
        filtered.append(deal)
    return filtered


def _theme_records(
    deal: dict,
    *,
    dimension: str,
    interaction_type: str = "all",
    source_confidence: str = "all",
) -> list[dict]:
    themes = deal.get("customer_themes")
    if not isinstance(themes, list):
        return []
    records = []
    for theme in themes:
        if not isinstance(theme, dict):
            continue
        record = _coerce_theme(theme)
        if record is None:
            continue
        if dimension != "all" and record["dimension"] != dimension:
            continue
        if interaction_type != "all" and record["interaction_type"] != interaction_type:
            continue
        if (
            source_confidence != "all"
            and record["source_confidence"] != source_confidence
        ):
            continue
        records.append(record)
    return records


def _coerce_theme(theme: dict) -> dict | None:
    theme_key = str(theme.get("theme_key") or "").strip().lower()
    if theme_key not in THEME_TAXONOMY:
        theme_key = "other"
    dimension = str(theme.get("dimension") or "").strip()
    if dimension not in THEME_DIMENSIONS:
        return None
    evidence = str(theme.get("evidence") or "").strip()
    if not evidence:
        return None
    try:
        importance = int(round(float(theme.get("importance", 3))))
    except (TypeError, ValueError):
        importance = 3
    importance = max(1, min(importance, 5))
    interaction_type = _optional_text(theme.get("interaction_type"))
    if interaction_type is None:
        interaction_type = "meeting" if theme.get("meeting_id") else "unknown"
    source_confidence = _optional_text(theme.get("source_confidence")) or "unknown"
    return {
        "theme_key": theme_key,
        "label": str(theme.get("label") or THEME_TAXONOMY[theme_key]),
        "dimension": dimension,
        "evidence": evidence[:500],
        "importance": importance,
        "meeting_id": theme.get("meeting_id"),
        "meeting_date": theme.get("meeting_date"),
        "interaction_id": _optional_text(theme.get("interaction_id")),
        "interaction_date": _optional_text(theme.get("interaction_date")),
        "interaction_type": interaction_type,
        "source_confidence": source_confidence,
        "subject": _optional_text(theme.get("subject")),
    }


def _group_values(deal: dict, records: list[dict], *, group_by: str) -> list[str]:
    if group_by == "stage":
        return [str(deal.get("deal_stage") or "unknown")]
    if group_by == "industry":
        return [str(deal.get("industry") or "unknown")]
    values = sorted({record["dimension"] for record in records}, key=_dimension_sort_key)
    return values


def _theme_summaries(
    *,
    group_value: str,
    per_deal_theme_importance: dict[tuple[str, str, str], int],
    deals_with_evidence: int,
    total_deals: int,
    top_k: int,
) -> list[dict]:
    by_theme: dict[str, list[int]] = defaultdict(list)
    for (candidate_group, theme_key, _deal_id), importance in (
        per_deal_theme_importance.items()
    ):
        if candidate_group == group_value:
            by_theme[theme_key].append(importance)
    themes = [
        {
            "theme_key": theme_key,
            "label": THEME_TAXONOMY[theme_key],
            "deal_count": len(importances),
            "avg_importance": round(sum(importances) / len(importances), 1),
            "share_of_group_evidenced_pct": _pct(len(importances), deals_with_evidence),
            "share_of_group_deals_pct": _pct(len(importances), total_deals),
        }
        for theme_key, importances in by_theme.items()
    ]
    themes.sort(
        key=lambda item: (
            -int(item["deal_count"]),
            -float(item["avg_importance"]),
            str(item["theme_key"]),
        )
    )
    return themes[:top_k]


def _pct(numerator: int, denominator: int) -> float:
    return round(numerator / denominator * 100, 1) if denominator else 0.0


def _warnings(*, deals_analyzed: int, deals_with_evidence: int) -> list[str]:
    warnings = []
    if deals_analyzed == 0:
        warnings.append("no_deals_in_scope")
    elif deals_with_evidence == 0:
        warnings.append("no_customer_theme_evidence")
    return warnings


def _group_sort_key(group_by: str):
    if group_by == "stage":
        return lambda value: (STAGE_ORDER.get(value, 99), value)
    if group_by == "dimension":
        return lambda value: (_dimension_sort_key(value), value)
    return lambda value: str(value)


def _dimension_sort_key(value: str) -> int:
    return DIMENSION_ORDER.get(value, 99)


def _date_ordinal(value: Any) -> int:
    if not isinstance(value, str) or not value:
        return 0
    try:
        return date.fromisoformat(value).toordinal()
    except ValueError:
        return 0


def _optional_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None
