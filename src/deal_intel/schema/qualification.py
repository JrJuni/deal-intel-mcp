from __future__ import annotations

from collections.abc import Iterable
from math import isfinite
from typing import Any

from deal_intel.schema.qualification_framework import QualificationFramework

NO_OPEN_GAP_STAGES = {"won"}


def compute_qualification_latest(
    evidence_items: Iterable[dict[str, Any]],
    *,
    framework: QualificationFramework,
    evidence_fields: tuple[str, ...] = ("qualification",),
    deal_stage: str = "discovery",
) -> dict[str, Any]:
    """Compute a framework-based qualification snapshot.

    This is the generic successor to the MEDDPICC-only aggregator. It is pure
    Python and intentionally does not read config, storage, LLMs, or embeddings.
    """
    enabled_dimensions = {
        key: dimension
        for key, dimension in framework.dimensions.items()
        if dimension.enabled
    }
    dim_scores: dict[str, list[int]] = {key: [] for key in enabled_dimensions}

    for item in evidence_items:
        signals = _first_signal_mapping(item, evidence_fields)
        if not signals:
            continue
        for key in enabled_dimensions:
            val = signals.get(key)
            if not isinstance(val, dict):
                continue
            raw_score = val.get("score")
            if _is_numeric_score(raw_score):
                dim_scores[key].append(int(raw_score))

    dimensions_out: dict[str, dict[str, Any]] = {}
    for key, scores in dim_scores.items():
        if not scores:
            continue
        avg = sum(scores) / len(scores)
        dimensions_out[key] = {
            "label": enabled_dimensions[key].label,
            "score": round(avg, 2),
            "trend": _trend(scores),
            "evidence_count": len(scores),
            "weight": enabled_dimensions[key].weight,
        }

    dimension_metadata = {
        key: {
            "label": dimension.label,
            "description": dimension.description,
            "suggested_question": dimension.suggested_question,
            "cta_policy": dimension.cta_policy,
            "weight": dimension.weight,
            "gap_threshold": dimension.gap_threshold,
        }
        for key, dimension in enabled_dimensions.items()
    }
    total_weight = sum(dimension.weight for dimension in enabled_dimensions.values())
    filled_weight = sum(enabled_dimensions[key].weight for key in dimensions_out)
    weighted_score = sum(
        dimensions_out[key]["score"] * enabled_dimensions[key].weight
        for key in dimensions_out
    )
    scale_max = float(framework.score_scale.max)
    max_possible = scale_max * total_weight
    health_pct = round(weighted_score / max_possible * 100, 1) if max_possible > 0 else 0.0
    quality_pct = (
        round(weighted_score / (scale_max * filled_weight) * 100, 1)
        if filled_weight > 0
        else None
    )
    coverage_pct = round(filled_weight / total_weight * 100, 1) if total_weight > 0 else 0.0
    gaps = _qualification_gaps(
        dimensions_out,
        enabled_dimensions=enabled_dimensions,
        deal_stage=deal_stage,
    )

    return {
        "framework_key": framework.key,
        "framework_display_name": framework.display_name,
        "score_scale": framework.score_scale.model_dump(mode="json"),
        "dimensions": dimensions_out,
        "dimension_metadata": dimension_metadata,
        "total_weighted_score": round(weighted_score, 2),
        "max_possible_score": round(max_possible, 2),
        "quality_pct": quality_pct,
        "coverage_pct": coverage_pct,
        "uncertainty_level": _uncertainty_level(coverage_pct),
        "health_pct": health_pct,
        "filled_count": len(dimensions_out),
        "total_count": len(enabled_dimensions),
        "gaps": gaps,
    }


def _first_signal_mapping(
    item: dict[str, Any],
    evidence_fields: tuple[str, ...],
) -> dict[str, Any]:
    for field in evidence_fields:
        value = item.get(field)
        if isinstance(value, dict):
            return value
    return {}


def _is_numeric_score(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if not isinstance(value, (int, float)):
        return False
    return isfinite(float(value))


def _trend(scores: list[int]) -> str | None:
    if len(scores) < 2:
        return None
    if scores[-1] > scores[-2]:
        return "up"
    if scores[-1] < scores[-2]:
        return "down"
    return "flat"


def _qualification_gaps(
    dimensions_out: dict[str, dict[str, Any]],
    *,
    enabled_dimensions: dict[str, Any],
    deal_stage: str,
) -> list[str]:
    if deal_stage in NO_OPEN_GAP_STAGES:
        return []

    gaps: list[str] = []
    for key, dimension in enabled_dimensions.items():
        if key not in dimensions_out:
            gaps.append(key)
            continue

        threshold = dimension.gap_threshold
        suppress_gap = False
        for rule in dimension.stage_rules:
            if deal_stage not in rule.stages:
                continue
            if rule.suppress_gap:
                suppress_gap = True
            if rule.gap_threshold is not None:
                threshold = rule.gap_threshold

        if not suppress_gap and dimensions_out[key]["score"] < threshold:
            gaps.append(key)
    return gaps


def _uncertainty_level(coverage_pct: float) -> str:
    if coverage_pct < 40:
        return "high"
    if coverage_pct < 70:
        return "medium"
    return "low"
