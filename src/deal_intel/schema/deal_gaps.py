from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from datetime import date, datetime

from deal_intel.schema.gap_actionability import (
    CTA_POLICY_ALLOWED,
    annotate_gap_actionability,
)
from deal_intel.schema.metrics import (
    ACTIVE_STAGES,
    OPEN_STAGES,
    VALID_STAGES,
    DataQualityStatus,
    DealValueStatus,
    HealthBand,
    HealthBandThresholds,
    PipelineTimingAssessment,
    PipelineTimingSettings,
    assess_deal_data_quality,
    assess_deal_value,
    assess_pipeline_timing,
    build_attention_reasons,
    classify_health,
)
from deal_intel.schema.qualification_read import (
    MEDDPICC_FIELD_LABELS,
    QUESTION_BY_MEDDPICC_GAP,
    QualificationReadSnapshot,
    dimension_label,
    dimension_question,
    qualification_summary,
    select_qualification_snapshot,
)

__all__ = (
    "MEDDPICC_FIELD_LABELS",
    "QUESTION_BY_MEDDPICC_GAP",
    "build_deal_gaps_summary",
)

PRIORITY_BANDS = ("low", "medium", "high")
PRIORITY_RANK = {"low": 0, "medium": 1, "high": 2}
DEFAULT_LIMIT = 10
MAX_LIMIT = 50

FIELD_HINTS = {
    "company": {
        "impact_area": "sales_action",
        "reason": "Company name is missing or invalid.",
        "suggested_question": "이 딜의 공식 고객사명은 무엇인가요?",
        "recommended_action": "update_company",
    },
    "industry": {
        "impact_area": "sales_action",
        "reason": "Industry is missing or invalid.",
        "suggested_question": "이 고객은 어떤 업종으로 분류하면 되나요?",
        "recommended_action": "update_industry",
    },
    "deal_stage": {
        "impact_area": "sales_action",
        "reason": "Pipeline stage is missing or invalid.",
        "suggested_question": "현재 이 딜은 어느 pipeline stage에 있나요?",
        "recommended_action": "update_stage",
    },
    "stage_history": {
        "impact_area": "forecast_trust",
        "reason": "Stage history is missing or inconsistent with the current stage.",
        "suggested_question": "이 딜이 현재 stage에 언제 들어왔는지 확인할 수 있나요?",
        "recommended_action": "repair_stage_history",
    },
    "expected_close_date": {
        "impact_area": "forecast_trust",
        "reason": "Expected close date is missing, invalid, or still config-estimated.",
        "suggested_question": "고객 기준으로 현실적인 예상 계약일은 언제인가요?",
        "recommended_action": "confirm_expected_close_date",
    },
    "deal_value": {
        "impact_area": "forecast_trust",
        "reason": "Deal value is missing, invalid, unknown, or still a rough estimate.",
        "suggested_question": "고객 예산, 견적, 또는 내부 추정 중 어떤 근거로 금액을 잡을까요?",
        "recommended_action": "confirm_deal_value",
    },
    "meetings": {
        "impact_area": "sales_action",
        "reason": "Qualified-or-later deal has no structured meeting evidence.",
        "suggested_question": (
            "최근 미팅에서 확인된 pain, decision criteria, next step은 무엇인가요?"
        ),
        "recommended_action": "add_interaction_evidence",
    },
    "health_assessment": {
        "impact_area": "sales_action",
        "reason": "Qualified-or-later deal has no usable qualification health assessment.",
        "suggested_question": "현재 qualification 기준으로 아직 확인하지 못한 항목은 무엇인가요?",
        "recommended_action": "add_or_refresh_interaction_evidence",
    },
    "actual_close_date": {
        "impact_area": "postmortem",
        "reason": "Closed deal is missing the actual close date.",
        "suggested_question": "실제 won/lost 처리된 날짜는 언제인가요?",
        "recommended_action": "update_actual_close_date",
    },
    "close_reason": {
        "impact_area": "postmortem",
        "reason": "Lost deal is missing the reason for loss.",
        "suggested_question": "이 딜을 잃은 결정적 이유는 무엇이었나요?",
        "recommended_action": "update_close_reason",
    },
}


def build_deal_gaps_summary(
    deals: Iterable[dict],
    *,
    as_of: date,
    health_thresholds: HealthBandThresholds | None = None,
    timing_settings: PipelineTimingSettings | None = None,
    stage: str | None = None,
    industry: str | None = None,
    deal_id: str | None = None,
    min_priority: str = "medium",
    limit: int = DEFAULT_LIMIT,
) -> dict:
    """Return user-facing deal gaps without touching storage or LLM providers."""
    if not isinstance(as_of, date) or isinstance(as_of, datetime):
        raise ValueError("as_of must be a date")
    if stage not in (None, "") and stage not in VALID_STAGES:
        raise ValueError(f"stage {stage!r} is not valid")
    if min_priority not in PRIORITY_BANDS:
        raise ValueError(f"min_priority {min_priority!r} is not valid")
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1 or limit > MAX_LIMIT:
        raise ValueError(f"limit must be between 1 and {MAX_LIMIT}")

    health_thresholds = health_thresholds or HealthBandThresholds()
    timing_settings = timing_settings or PipelineTimingSettings()
    rows = [
        _build_deal_gap_row(
            deal,
            as_of=as_of,
            health_thresholds=health_thresholds,
            timing_settings=timing_settings,
        )
        for deal in _filter_deals(
            deals,
            stage=stage or None,
            industry=industry or None,
            deal_id=deal_id or None,
        )
    ]
    rows.sort(
        key=lambda row: (
            -row["priority_score"],
            -len(row["attention_reasons"]),
            -(row["deal_size_amount"] or 0),
            str(row["company"] or ""),
        )
    )

    if deal_id:
        selected = rows
    else:
        selected = [
            row
            for row in rows
            if row["gaps"]
            and PRIORITY_RANK[row["priority_band"]] >= PRIORITY_RANK[min_priority]
        ][:limit]

    return {
        "filters": {
            "stage": stage or None,
            "industry": industry or None,
            "deal_id": deal_id or None,
            "min_priority": min_priority,
            "limit": limit,
        },
        "summary": _summary(rows, selected),
        "deals": selected,
        "warnings": _warnings(rows, selected, deal_id=deal_id or None, limit=limit),
    }


def _filter_deals(
    deals: Iterable[dict],
    *,
    stage: str | None,
    industry: str | None,
    deal_id: str | None,
) -> list[dict]:
    filtered = []
    for deal in deals:
        if stage is not None and deal.get("deal_stage") != stage:
            continue
        if industry is not None and deal.get("industry") != industry:
            continue
        if deal_id is not None and deal.get("deal_id") != deal_id:
            continue
        filtered.append(deal)
    return filtered


def _build_deal_gap_row(
    deal: dict,
    *,
    as_of: date,
    health_thresholds: HealthBandThresholds,
    timing_settings: PipelineTimingSettings,
) -> dict:
    stage = str(deal.get("deal_stage") or "")
    qualification = select_qualification_snapshot(deal)
    health_band = classify_health(qualification.snapshot, health_thresholds)
    timing = assess_pipeline_timing(deal, as_of=as_of, settings=timing_settings)
    attention_reasons = build_attention_reasons(
        stage=stage,
        health_band=health_band,
        timing=timing,
    )
    data_quality = assess_deal_data_quality(deal)
    value = assess_deal_value(deal)

    gaps = []
    gaps.extend(
        _data_quality_gaps(
            deal,
            data_quality.field_statuses,
            value_status=value.status,
            attention_reasons=attention_reasons,
        )
    )
    gaps.extend(
        _unknown_value_gaps(
            deal,
            value_status=value.status,
            is_known=value.is_known,
            attention_reasons=attention_reasons,
        )
    )
    gaps.extend(
        _qualification_gaps(
            deal,
            qualification=qualification,
            attention_reasons=attention_reasons,
        )
    )
    gaps.extend(
        _attention_gaps(
            deal,
            qualification=qualification,
            timing=timing,
            attention_reasons=attention_reasons,
        )
    )
    gaps = _dedupe_gaps(gaps)
    priority_score = max((gap.pop("_score") for gap in gaps), default=0)
    gaps = [annotate_gap_actionability(gap) for gap in gaps]
    actionable_gaps = [
        gap for gap in gaps if gap.get("cta_policy") == CTA_POLICY_ALLOWED
    ]
    gap_observations = [
        gap for gap in gaps if gap.get("cta_policy") != CTA_POLICY_ALLOWED
    ]

    return {
        "deal_id": deal.get("deal_id"),
        "company": deal.get("company"),
        "industry": deal.get("industry"),
        "customer_segment": deal.get("customer_segment"),
        "deal_stage": deal.get("deal_stage"),
        "deal_size_amount": deal.get("deal_size_amount"),
        "deal_size_currency": deal.get("deal_size_currency") or "KRW",
        "deal_size_status": deal.get("deal_size_status"),
        "expected_close_date": deal.get("expected_close_date"),
        "qualification": qualification_summary(qualification),
        "qualification_framework": qualification.framework_key,
        "qualification_framework_display_name": qualification.framework_display_name,
        "qualification_source_field": qualification.source_field,
        "qualification_health_pct": qualification.snapshot.get("health_pct"),
        "qualification_quality_pct": qualification.quality_pct,
        "qualification_coverage_pct": qualification.coverage_pct,
        "qualification_filled_count": qualification.filled_count,
        "qualification_total_count": qualification.total_count,
        "qualification_gaps": qualification.gaps,
        "health_pct": qualification.snapshot.get("health_pct"),
        "health_band": health_band.value,
        "attention_reasons": attention_reasons,
        "priority_score": priority_score,
        "priority_band": _priority_band(priority_score),
        "gaps": gaps,
        "actionable_gaps": actionable_gaps,
        "gap_observations": gap_observations,
    }


def _data_quality_gaps(
    deal: dict,
    statuses: dict[str, DataQualityStatus],
    *,
    value_status: DealValueStatus | None,
    attention_reasons: list[str],
) -> list[dict]:
    gaps = []
    for field, status in statuses.items():
        if status not in {
            DataQualityStatus.MISSING,
            DataQualityStatus.INVALID,
            DataQualityStatus.ESTIMATED,
        }:
            continue
        if field == "deal_value" and value_status == DealValueStatus.UNKNOWN:
            continue
        gaps.append(
            _gap(
                deal,
                gap_id=f"{field}:{status.value}",
                field=field,
                status=_gap_status(status),
                impact_area=_field_hint(field, "impact_area"),
                reason=_field_hint(field, "reason"),
                suggested_question=_field_hint(field, "suggested_question"),
                recommended_action=_field_hint(field, "recommended_action"),
                base_score=_field_base_score(deal, field, status),
                attention_reasons=attention_reasons,
            )
        )
    return gaps


def _unknown_value_gaps(
    deal: dict,
    *,
    value_status: DealValueStatus | None,
    is_known: bool,
    attention_reasons: list[str],
) -> list[dict]:
    if deal.get("deal_stage") not in OPEN_STAGES or is_known:
        return []
    if value_status not in {None, DealValueStatus.UNKNOWN}:
        return []
    stage = deal.get("deal_stage")
    return [
        _gap(
            deal,
            gap_id="deal_value:unknown",
            field="deal_value",
            status="missing",
            impact_area="forecast_trust",
            reason=(
                "Deal value is explicitly unknown. This is expected in early "
                "discovery, but becomes more important as the deal advances."
            ),
            suggested_question=(
                "이번 미팅 기준으로 예산 범위, 견적 필요성, 또는 무료 전략딜 "
                "여부를 확인할 수 있나요?"
            ),
            recommended_action="confirm_deal_value",
            base_score=15 if stage == "discovery" else 35,
            attention_reasons=attention_reasons,
        )
    ]


def _qualification_gaps(
    deal: dict,
    *,
    qualification: QualificationReadSnapshot,
    attention_reasons: list[str],
) -> list[dict]:
    if deal.get("deal_stage") not in ACTIVE_STAGES | {"stalled"}:
        return []
    gaps = qualification.gaps
    if not isinstance(gaps, list):
        return []
    rows = []
    for raw_gap in gaps:
        gap_name = str(raw_gap)
        label = dimension_label(qualification, gap_name)
        stage = deal.get("deal_stage")
        gap_id = f"{qualification.field_prefix}:{gap_name}"
        field = f"{qualification.field_prefix}.{gap_name}"
        rows.append(
            _gap(
                deal,
                gap_id=gap_id,
                field=field,
                status="missing",
                impact_area="sales_action",
                severity="high" if stage in {"proposal", "negotiation"} else None,
                reason=(
                    f"{qualification.framework_display_name} qualification gap "
                    f"remains open: {label}."
                ),
                suggested_question=dimension_question(qualification, gap_name),
                recommended_action=(
                    "ask_in_next_meeting"
                    if qualification.is_meddpicc
                    else "ask_in_next_interaction"
                ),
                base_score=55 if stage == "negotiation" else 50,
                attention_reasons=attention_reasons,
            )
        )
    return rows


def _attention_gaps(
    deal: dict,
    *,
    qualification: QualificationReadSnapshot,
    timing: PipelineTimingAssessment,
    attention_reasons: list[str],
) -> list[dict]:
    rows = []
    if "overdue" in attention_reasons:
        overdue_days = timing.overdue_days or 0
        rows.append(
            _gap(
                deal,
                gap_id="attention:overdue",
                field="expected_close_date",
                status="attention",
                impact_area="sales_action",
                reason=f"Expected close date is overdue by {overdue_days} day(s).",
                suggested_question=(
                    "예상 계약일이 지났는데, 실제 blocker와 다음 close plan은 "
                    "무엇인가요?"
                ),
                recommended_action="review_close_plan",
                base_score=45,
                attention_reasons=attention_reasons,
            )
        )
    if "stuck" in attention_reasons:
        rows.append(
            _gap(
                deal,
                gap_id="attention:stuck",
                field="deal_stage",
                status="attention",
                impact_area="sales_action",
                reason="Deal has stayed in the current active stage past the stuck threshold.",
                suggested_question=(
                    "이 stage에서 멈춘 이유와 다음 단계로 넘기기 위한 조건은 "
                    "무엇인가요?"
                ),
                recommended_action="review_next_step",
                base_score=40,
                attention_reasons=attention_reasons,
            )
        )
    if "stalled" in attention_reasons:
        rows.append(
            _gap(
                deal,
                gap_id="attention:stalled",
                field="deal_stage",
                status="attention",
                impact_area="sales_action",
                reason="Deal is explicitly marked stalled.",
                suggested_question=(
                    "이 딜을 재개하려면 고객 또는 내부에서 어떤 조건이 풀려야 "
                    "하나요?"
                ),
                recommended_action="review_reactivation_path",
                base_score=35,
                attention_reasons=attention_reasons,
            )
        )
    if "at_risk" in attention_reasons:
        rows.append(
            _gap(
                deal,
                gap_id="attention:at_risk",
                field="health_assessment",
                status="weak_signal",
                impact_area="sales_action",
                reason=f"{qualification.framework_display_name} health is at risk.",
                suggested_question=(
                    f"가장 큰 {qualification.framework_display_name} 약점과 "
                    "이를 보완할 다음 액션은 무엇인가요?"
                ),
                recommended_action=(
                    "review_meddpicc_gap_plan"
                    if qualification.is_meddpicc
                    else "review_qualification_gap_plan"
                ),
                base_score=45,
                attention_reasons=attention_reasons,
            )
        )
    return rows


def _gap(
    deal: dict,
    *,
    gap_id: str,
    field: str,
    status: str,
    impact_area: str,
    reason: str,
    suggested_question: str,
    recommended_action: str,
    base_score: int,
    attention_reasons: list[str],
    severity: str | None = None,
) -> dict:
    score = _priority_score(deal, base_score, attention_reasons)
    return {
        "gap_id": gap_id,
        "field": field,
        "status": status,
        "impact_area": impact_area,
        "severity": severity or _severity(score),
        "reason": reason,
        "suggested_question": suggested_question,
        "recommended_action": recommended_action,
        "_score": score,
    }


def _field_base_score(deal: dict, field: str, status: DataQualityStatus) -> int:
    stage = deal.get("deal_stage")
    if status == DataQualityStatus.INVALID:
        return 60
    if field == "deal_value":
        if status == DataQualityStatus.MISSING:
            return 15 if stage == "discovery" else 35
        if status == DataQualityStatus.ESTIMATED:
            return 40 if stage in {"proposal", "negotiation"} else 25
    if field == "expected_close_date":
        if status == DataQualityStatus.ESTIMATED:
            return 35 if stage in {"proposal", "negotiation"} else 25
        return 45
    if field in {"actual_close_date", "close_reason"}:
        return 65
    if field in {"meetings", "health_assessment"} and stage in {"proposal", "negotiation"}:
        return 55
    if status == DataQualityStatus.ESTIMATED:
        return 25
    return 40


def _priority_score(deal: dict, base_score: int, attention_reasons: list[str]) -> int:
    stage_bonus = {
        "discovery": 0,
        "qualification": 5,
        "proposal": 15,
        "negotiation": 20,
        "stalled": 10,
        "won": 15,
        "lost": 15,
    }.get(str(deal.get("deal_stage") or ""), 0)
    value = deal.get("deal_size_amount")
    value_bonus = 0
    if isinstance(value, int) and not isinstance(value, bool):
        if value >= 100_000_000:
            value_bonus = 10
        elif value >= 50_000_000:
            value_bonus = 5
    attention_bonus = 10 if attention_reasons else 0
    return min(100, base_score + stage_bonus + value_bonus + attention_bonus)


def _priority_band(score: int) -> str:
    if score >= 75:
        return "high"
    if score >= 45:
        return "medium"
    return "low"


def _severity(score: int) -> str:
    return _priority_band(score)


def _gap_status(status: DataQualityStatus) -> str:
    if status == DataQualityStatus.ESTIMATED:
        return "estimated"
    if status == DataQualityStatus.INVALID:
        return "invalid"
    return "missing"


def _field_hint(field: str, key: str) -> str:
    return str(FIELD_HINTS.get(field, FIELD_HINTS["health_assessment"])[key])


def _dedupe_gaps(gaps: list[dict]) -> list[dict]:
    seen = set()
    result = []
    for gap in gaps:
        key = gap["gap_id"]
        if key in seen:
            continue
        seen.add(key)
        result.append(gap)
    return result


def _summary(rows: list[dict], selected: list[dict]) -> dict:
    rows_with_gaps = [row for row in rows if row["gaps"]]
    priority_counts = {band: 0 for band in PRIORITY_BANDS}
    for row in rows_with_gaps:
        priority_counts[row["priority_band"]] += 1

    gaps = [gap for row in rows for gap in row["gaps"]]
    status_counts = Counter(gap["status"] for gap in gaps)
    impact_counts = Counter(gap["impact_area"] for gap in gaps)
    field_counts = Counter(gap["field"] for gap in gaps)
    return {
        "deal_count": len(rows),
        "gap_deal_count": len(rows_with_gaps),
        "returned_deal_count": len(selected),
        "gap_count": len(gaps),
        "priority_counts": priority_counts,
        "gap_status_counts": {status: status_counts[status] for status in _gap_status_order()},
        "impact_area_counts": {
            area: impact_counts[area]
            for area in ("sales_action", "forecast_trust", "postmortem")
        },
        "field_counts": dict(sorted(field_counts.items())),
    }


def _gap_status_order() -> tuple[str, ...]:
    return ("missing", "estimated", "invalid", "weak_signal", "attention")


def _warnings(
    rows: list[dict],
    selected: list[dict],
    *,
    deal_id: str | None,
    limit: int,
) -> list[str]:
    warnings = []
    if not rows:
        warnings.append("no_matching_deals")
    elif not any(row["gaps"] for row in rows):
        warnings.append("no_deal_gaps")
    if deal_id and rows and not selected[0]["gaps"]:
        warnings.append("deal_has_no_gaps")
    if not deal_id and len([row for row in rows if row["gaps"]]) > limit:
        warnings.append("limit_applied")
    if any(row["health_band"] == HealthBand.UNASSESSED.value for row in rows):
        warnings.append("unassessed_health")
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
