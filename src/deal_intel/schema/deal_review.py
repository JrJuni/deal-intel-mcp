from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime
from typing import Any

from deal_intel.schema.deal_gaps import (
    MEDDPICC_FIELD_LABELS,
    QUESTION_BY_MEDDPICC_GAP,
    build_deal_gaps_summary,
)
from deal_intel.schema.metrics import (
    DataQualityStatus,
    DealValueStatus,
    HealthBand,
    HealthBandThresholds,
    PipelineTimingSettings,
    assess_deal_data_quality,
    assess_deal_value,
    assess_pipeline_timing,
    build_attention_reasons,
    classify_health,
)

MEDDPICC_DIMENSIONS = (
    "metrics",
    "economic_buyer",
    "decision_criteria",
    "decision_process",
    "identify_pain",
    "champion",
    "competition",
)

COVERAGE_LOW_MAX = 40.0
COVERAGE_HIGH_MIN = 70.0
NEGATIVE_SIGNAL_MAX = 1.99
WEAK_SIGNAL_MAX = 2.99
STRONG_SIGNAL_MIN = 4.0


def build_deal_review(
    deal: dict,
    *,
    as_of: date,
    health_thresholds: HealthBandThresholds | None = None,
    timing_settings: PipelineTimingSettings | None = None,
) -> dict:
    """Build an evidence-aware deal review without LLM or storage access."""
    if not isinstance(as_of, date) or isinstance(as_of, datetime):
        raise ValueError("as_of must be a date")

    health_thresholds = health_thresholds or HealthBandThresholds()
    timing_settings = timing_settings or PipelineTimingSettings()

    stage = deal.get("deal_stage")
    meddpicc_latest = deal.get("meddpicc_latest") or {}
    health_band = classify_health(meddpicc_latest, health_thresholds)
    timing = assess_pipeline_timing(deal, as_of=as_of, settings=timing_settings)
    attention_reasons = build_attention_reasons(
        stage=stage,
        health_band=health_band,
        timing=timing,
    )
    data_quality = assess_deal_data_quality(deal)
    value = assess_deal_value(deal)
    coverage = _evidence_coverage(meddpicc_latest)
    scorecard = _scorecard(meddpicc_latest)
    gaps = _gap_rows(
        deal,
        as_of=as_of,
        health_thresholds=health_thresholds,
        timing_settings=timing_settings,
    )
    confirmed_risks = _confirmed_risks(
        meddpicc_latest,
        health_band=health_band,
        coverage_pct=coverage["coverage_pct"],
        attention_reasons=attention_reasons,
        value_status=value.status,
        value_valid=value.is_valid,
    )
    uncertainty_level = _uncertainty_level(
        coverage_pct=coverage["coverage_pct"],
        health_band=health_band,
        data_quality=data_quality,
    )
    review_band = _review_band(
        health_band=health_band,
        coverage_pct=coverage["coverage_pct"],
    )
    alert_level = _alert_level(
        review_band=review_band,
        attention_reasons=attention_reasons,
        confirmed_risks=confirmed_risks,
        data_quality_statuses=data_quality.field_statuses,
    )
    warnings = _warnings(
        review_band=review_band,
        health_band=health_band,
        coverage_pct=coverage["coverage_pct"],
        attention_reasons=attention_reasons,
        data_quality_statuses=data_quality.field_statuses,
        confirmed_risks=confirmed_risks,
    )

    return {
        "deal_id": deal.get("deal_id"),
        "company": deal.get("company"),
        "industry": deal.get("industry"),
        "deal_stage": stage,
        "deal_size_krw": deal.get("deal_size_krw"),
        "deal_size_status": deal.get("deal_size_status"),
        "expected_close_date": deal.get("expected_close_date"),
        "health_interpretation": {
            "legacy_health_pct": meddpicc_latest.get("health_pct"),
            "health_band": health_band.value,
            "evidence_coverage_pct": coverage["coverage_pct"],
            "evidence_coverage_level": coverage["coverage_level"],
            "filled_meddpicc_count": coverage["filled_count"],
            "total_meddpicc_count": coverage["total_count"],
            "uncertainty_level": uncertainty_level,
            "review_band": review_band,
            "alert_level": alert_level,
            "explanation": _interpretation_text(
                review_band=review_band,
                alert_level=alert_level,
            ),
        },
        "scorecard": scorecard,
        "attention_reasons": attention_reasons,
        "missing_information": _missing_information(gaps),
        "confirmed_risks": confirmed_risks,
        "known_signals": _known_signals(scorecard, value_status=value.status),
        "recommended_questions": _recommended_questions(gaps, scorecard),
        "recommended_actions": _recommended_actions(gaps, confirmed_risks),
        "data_quality": data_quality.to_dict(),
        "warnings": warnings,
    }


def _evidence_coverage(meddpicc_latest: dict) -> dict:
    filled = _filled_count(meddpicc_latest)
    total = len(MEDDPICC_DIMENSIONS)
    coverage_pct = round(filled / total * 100, 1) if total else None
    if coverage_pct is None:
        level = "unknown"
    elif coverage_pct < COVERAGE_LOW_MAX:
        level = "low"
    elif coverage_pct < COVERAGE_HIGH_MIN:
        level = "medium"
    else:
        level = "high"
    return {
        "filled_count": filled,
        "total_count": total,
        "coverage_pct": coverage_pct,
        "coverage_level": level,
    }


def _filled_count(meddpicc_latest: dict) -> int:
    filled_count = meddpicc_latest.get("filled_count")
    if isinstance(filled_count, int) and not isinstance(filled_count, bool):
        return max(0, min(filled_count, len(MEDDPICC_DIMENSIONS)))
    return sum(1 for dim in MEDDPICC_DIMENSIONS if isinstance(meddpicc_latest.get(dim), dict))


def _scorecard(meddpicc_latest: dict) -> list[dict]:
    rows = []
    gaps = _safe_str_set(meddpicc_latest.get("gaps"))
    for dim in MEDDPICC_DIMENSIONS:
        item = meddpicc_latest.get(dim)
        score = _score(item)
        status = _signal_status(score)
        rows.append(
            {
                "dimension": dim,
                "label": MEDDPICC_FIELD_LABELS.get(dim, dim),
                "status": status,
                "score": score,
                "trend": item.get("trend") if isinstance(item, dict) else None,
                "is_gap": dim in gaps or status == "unknown",
            }
        )
    return rows


def _score(item: Any) -> float | None:
    if not isinstance(item, dict):
        return None
    raw = item.get("score")
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return None
    return round(float(raw), 2)


def _signal_status(score: float | None) -> str:
    if score is None:
        return "unknown"
    if score <= NEGATIVE_SIGNAL_MAX:
        return "negative_signal"
    if score <= WEAK_SIGNAL_MAX:
        return "weak_signal"
    return "confirmed"


def _gap_rows(
    deal: dict,
    *,
    as_of: date,
    health_thresholds: HealthBandThresholds,
    timing_settings: PipelineTimingSettings,
) -> list[dict]:
    summary = build_deal_gaps_summary(
        [deal],
        as_of=as_of,
        health_thresholds=health_thresholds,
        timing_settings=timing_settings,
        deal_id=str(deal.get("deal_id") or ""),
        min_priority="low",
        limit=1,
    )
    rows = summary.get("deals") or []
    if not rows:
        return []
    gaps = rows[0].get("gaps") or []
    return [gap for gap in gaps if isinstance(gap, dict)]


def _missing_information(gaps: list[dict]) -> list[dict]:
    result = []
    for gap in gaps:
        if gap.get("status") not in {"missing", "estimated", "invalid"}:
            continue
        result.append(
            {
                "gap_id": gap.get("gap_id"),
                "field": gap.get("field"),
                "status": gap.get("status"),
                "impact_area": gap.get("impact_area"),
                "severity": gap.get("severity"),
                "reason": gap.get("reason"),
                "suggested_question": gap.get("suggested_question"),
                "recommended_action": gap.get("recommended_action"),
            }
        )
    return result


def _confirmed_risks(
    meddpicc_latest: dict,
    *,
    health_band: HealthBand,
    coverage_pct: float | None,
    attention_reasons: list[str],
    value_status: DealValueStatus | None,
    value_valid: bool,
) -> list[dict]:
    risks = []
    high_coverage = coverage_pct is not None and coverage_pct >= COVERAGE_HIGH_MIN
    medium_or_high = coverage_pct is not None and coverage_pct >= COVERAGE_LOW_MAX

    if high_coverage and health_band == HealthBand.AT_RISK:
        risks.append(
            _risk(
                "confirmed_meddpicc_risk",
                "MEDDPICC information is mostly known and the resulting health band is at risk.",
                "alert",
            )
        )
    elif high_coverage and health_band == HealthBand.WATCH:
        risks.append(
            _risk(
                "confirmed_watch_risk",
                "MEDDPICC information is mostly known and the deal is still only watch-level.",
                "watch",
            )
        )

    for dim in MEDDPICC_DIMENSIONS:
        score = _score(meddpicc_latest.get(dim))
        if score is None or score > NEGATIVE_SIGNAL_MAX or not medium_or_high:
            continue
        risks.append(
            _risk(
                f"negative_meddpicc:{dim}",
                f"{MEDDPICC_FIELD_LABELS.get(dim, dim)} has a confirmed low score ({score}/5).",
                "alert" if high_coverage else "watch",
                field=f"meddpicc.{dim}",
            )
        )

    if "overdue" in attention_reasons:
        risks.append(
            _risk(
                "timing:overdue",
                "Expected close date is overdue.",
                "watch",
                field="expected_close_date",
            )
        )
    if "stuck" in attention_reasons or "stalled" in attention_reasons:
        risks.append(
            _risk(
                "timing:stalled_or_stuck",
                "Deal is stalled or has stayed too long in the current stage.",
                "watch",
                field="deal_stage",
            )
        )
    if not value_valid:
        risks.append(
            _risk(
                "forecast:invalid_value",
                "Deal value classification is invalid, so forecast value is not trustworthy.",
                "alert",
                field="deal_value",
            )
        )
    elif value_status == DealValueStatus.ROUGH_ESTIMATE and medium_or_high:
        risks.append(
            _risk(
                "forecast:rough_estimate",
                "Deal value is still a rough estimate.",
                "watch",
                field="deal_value",
            )
        )
    return _dedupe_by_id(risks)


def _risk(
    risk_id: str,
    reason: str,
    severity: str,
    *,
    field: str | None = None,
) -> dict:
    return {
        "risk_id": risk_id,
        "field": field,
        "severity": severity,
        "reason": reason,
    }


def _known_signals(
    scorecard: list[dict],
    *,
    value_status: DealValueStatus | None,
) -> list[dict]:
    signals = [
        {
            "signal_id": f"meddpicc:{row['dimension']}",
            "field": f"meddpicc.{row['dimension']}",
            "strength": "strong" if (row.get("score") or 0) >= STRONG_SIGNAL_MIN else "confirmed",
            "reason": (
                f"{row['label']} has a confirmed score of {row['score']}/5."
            ),
        }
        for row in scorecard
        if row["status"] == "confirmed"
    ]
    if value_status in {DealValueStatus.CUSTOMER_BUDGET, DealValueStatus.QUOTED}:
        signals.append(
            {
                "signal_id": "forecast:validated_value",
                "field": "deal_value",
                "strength": "confirmed",
                "reason": f"Deal value status is {value_status.value}.",
            }
        )
    return signals


def _recommended_questions(gaps: list[dict], scorecard: list[dict]) -> list[str]:
    questions = [
        str(gap["suggested_question"])
        for gap in gaps
        if gap.get("suggested_question")
    ]
    for row in scorecard:
        if row["status"] == "unknown":
            questions.append(
                QUESTION_BY_MEDDPICC_GAP.get(
                    str(row["dimension"]),
                    f"{row['label']}에 대해 무엇을 확인해야 하나요?",
                )
            )
    return _dedupe_strings(questions)[:8]


def _recommended_actions(gaps: list[dict], risks: list[dict]) -> list[str]:
    actions = [
        str(gap["recommended_action"])
        for gap in gaps
        if gap.get("recommended_action")
    ]
    if any(risk["severity"] == "alert" for risk in risks):
        actions.append("review_confirmed_risk_plan")
    if any(str(risk["risk_id"]).startswith("timing:") for risk in risks):
        actions.append("review_timing_and_close_plan")
    return _dedupe_strings(actions)[:8]


def _uncertainty_level(
    *,
    coverage_pct: float | None,
    health_band: HealthBand,
    data_quality: Any,
) -> str:
    if coverage_pct is None or coverage_pct < COVERAGE_LOW_MAX:
        return "high"
    if health_band == HealthBand.UNASSESSED:
        return "high"
    if coverage_pct < COVERAGE_HIGH_MIN:
        return "medium"
    if data_quality.confirmed_coverage_pct is not None and data_quality.confirmed_coverage_pct < 70:
        return "medium"
    return "low"


def _review_band(*, health_band: HealthBand, coverage_pct: float | None) -> str:
    if coverage_pct is None or coverage_pct < COVERAGE_LOW_MAX:
        if health_band == HealthBand.HEALTHY:
            return "promising_but_unproven"
        return "insufficient_evidence"
    if health_band == HealthBand.UNASSESSED:
        return "insufficient_evidence"
    if health_band == HealthBand.HEALTHY:
        if coverage_pct >= COVERAGE_HIGH_MIN:
            return "verified_healthy"
        return "promising_but_unproven"
    if health_band == HealthBand.AT_RISK:
        if coverage_pct >= COVERAGE_HIGH_MIN:
            return "confirmed_risk"
        return "unclear_with_risk_signals"
    if coverage_pct >= COVERAGE_HIGH_MIN:
        return "watch_with_evidence"
    return "watch_unproven"


def _alert_level(
    *,
    review_band: str,
    attention_reasons: list[str],
    confirmed_risks: list[dict],
    data_quality_statuses: dict[str, DataQualityStatus],
) -> str:
    actionable_attention = _actionable_attention_reasons(
        review_band=review_band,
        attention_reasons=attention_reasons,
    )
    if review_band == "confirmed_risk":
        return "alert"
    if any(risk["severity"] == "alert" for risk in confirmed_risks):
        return "alert"
    if any(status == DataQualityStatus.INVALID for status in data_quality_statuses.values()):
        return "alert"
    if confirmed_risks:
        return "watch"
    if actionable_attention or review_band in {
        "promising_but_unproven",
        "unclear_with_risk_signals",
        "watch_with_evidence",
        "watch_unproven",
    }:
        return "watch"
    if review_band == "insufficient_evidence":
        return "info"
    return "none"


def _warnings(
    *,
    review_band: str,
    health_band: HealthBand,
    coverage_pct: float | None,
    attention_reasons: list[str],
    data_quality_statuses: dict[str, DataQualityStatus],
    confirmed_risks: list[dict],
) -> list[str]:
    actionable_attention = _actionable_attention_reasons(
        review_band=review_band,
        attention_reasons=attention_reasons,
    )
    warnings = ["win_probability_suppressed"]
    if coverage_pct is None or coverage_pct < COVERAGE_LOW_MAX:
        warnings.append("insufficient_evidence")
    if health_band == HealthBand.HEALTHY and (
        coverage_pct is None or coverage_pct < COVERAGE_HIGH_MIN
    ):
        warnings.append("overconfidence_warning")
    if confirmed_risks:
        warnings.append("confirmed_risk_present")
    if actionable_attention:
        warnings.append("attention_required")
    if any(status == DataQualityStatus.INVALID for status in data_quality_statuses.values()):
        warnings.append("invalid_data_quality")
    if any(status == DataQualityStatus.ESTIMATED for status in data_quality_statuses.values()):
        warnings.append("estimated_forecast_fields")
    return _dedupe_strings(warnings)


def _actionable_attention_reasons(
    *,
    review_band: str,
    attention_reasons: list[str],
) -> list[str]:
    if review_band != "insufficient_evidence":
        return attention_reasons
    return [reason for reason in attention_reasons if reason != "at_risk"]


def _interpretation_text(*, review_band: str, alert_level: str) -> str:
    messages = {
        "verified_healthy": "Evidence coverage is high and the deal is currently healthy.",
        "promising_but_unproven": (
            "The visible signals look positive, but evidence coverage is not high enough "
            "to treat this as a high-confidence healthy deal."
        ),
        "confirmed_risk": (
            "Evidence coverage is high and the known information indicates real risk."
        ),
        "unclear_with_risk_signals": (
            "Some risk signals exist, but missing information is still a major part of the problem."
        ),
        "watch_with_evidence": (
            "Evidence coverage is high and the deal needs watch-level attention."
        ),
        "watch_unproven": "The deal needs attention and still has material evidence gaps.",
        "insufficient_evidence": (
            "There is not enough evidence to make a confident deal-quality call."
        ),
    }
    message = messages.get(review_band, "Deal review is available.")
    if alert_level == "alert":
        return f"{message} Treat this as an alert, not just missing information."
    return message


def _safe_str_set(value: Any) -> set[str]:
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes, dict)):
        return set()
    return {str(item) for item in value}


def _dedupe_strings(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _dedupe_by_id(rows: list[dict]) -> list[dict]:
    seen = set()
    result = []
    for row in rows:
        row_id = row.get("risk_id")
        if row_id in seen:
            continue
        seen.add(row_id)
        result.append(row)
    return result
