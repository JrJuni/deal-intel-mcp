from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from deal_intel.reports.weekly_pipeline import REPORT_TYPE
from deal_intel.schema.metrics import (
    DEFAULT_DEAL_CURRENCY,
    HealthBand,
    assess_deal_value,
)

SUPPORTED_REPORT_LANGUAGES = frozenset({"en", "ko"})

TEXT = {
    "en": {
        "all": "all",
        "none": "none",
        "na": "N/A",
        "unknown_source": "Unknown source",
        "title": "Weekly Pipeline Report",
        "generated_at": "Generated at",
        "filters": "Filters",
        "executive_summary": "Executive Summary",
        "meeting_agenda": "Meeting Agenda",
        "kpi": "1. Core KPIs",
        "stage_breakdown": "3. Stage Breakdown",
        "meeting_flow": "5. Next Week Actions",
        "risk_deals": "2. Key Deal Watchlist",
        "issues_to_watch": "4. Issues To Watch",
        "objective_actions": "Objective Action Items",
        "gap_observations": "Gap Observations",
        "customer_evidence": "Appendix A. Customer Evidence",
        "data_quality": "Appendix B. Data Quality",
        "metric": "Metric",
        "value": "Value",
        "open_deals": "Open deals",
        "pipeline_value": "Pipeline value",
        "known_amount_coverage": "Known amount coverage",
        "average_health": "Average health",
        "health_coverage": "Health coverage",
        "attention_deals": "Attention deals",
        "objective_action_items": "Objective action items",
        "overdue": "Overdue",
        "stuck": "Stuck",
        "at_risk": "At risk",
        "stage": "Stage",
        "deals": "Deals",
        "avg_health": "Avg health",
        "company": "Company",
        "amount": "Amount",
        "expected_close": "Expected close",
        "health": "Health",
        "reasons": "Reasons",
        "objective_actions_short": "Objective actions",
        "trigger": "Trigger",
        "recommended_action": "Recommended action",
        "reason": "Reason",
        "gap": "Gap",
        "actionability": "Actionability",
        "primary_pain": "Primary pain",
        "pain_source": "Pain source",
        "decision_criteria": "Decision criteria",
        "dc_source": "DC source",
        "issue": "Issue",
        "count": "Count",
        "unassessed_health": "Unassessed health",
        "missing_expected_close_date": "Missing expected close date",
        "invalid_expected_close_date": "Invalid expected close date",
        "missing_last_meeting_date": "Missing last meeting date",
        "missing_primary_pain": "Missing primary pain",
        "missing_primary_decision_criteria": "Missing primary decision criteria",
        "incomplete_data_quality": "Incomplete data quality",
        "no_risk_deals": "No risk deals.",
        "no_key_deals": "No key deals matched the selected filters.",
        "no_objective_actions": "No objective action items.",
        "no_gap_observations": "No gap observations.",
        "no_customer_evidence": "No primary customer evidence.",
        "no_stage_breakdown": "No stage breakdown available.",
        "warning_codes": "Warning codes",
        "no_open_summary_1": "- No open deals matched the selected filters.",
        "no_open_summary_2": "- Use this report again after new active pipeline data is available.",
        "summary_purpose": (
            "- Purpose: use this report to run the weekly pipeline meeting from "
            "numbers, to deal review, to concrete next actions."
        ),
        "open_pipeline_prefix": "- Open pipeline: ",
        "open_pipeline_across": " across ",
        "open_pipeline_suffix": " open deal(s).",
        "health_prefix": "- Health: ",
        "health_average": " average; ",
        "health_attention_suffix": " deal(s) need attention.",
        "data_confidence_prefix": "- Data confidence: ",
        "amount_coverage": "amount coverage",
        "first_review_candidate": "- First review candidate: ",
        "no_attention_deals": "- No attention deals were detected by the deterministic checks.",
        "issue_intro_with_actions": (
            "These are deterministic blockers or time-sensitive signals. Assign "
            "an owner before discussing judgment-based gaps."
        ),
        "issue_intro_without_actions": (
            "No deterministic blockers were found. Review observations only "
            "where they affect forecast trust or next-step quality."
        ),
        "flow_resolve_prefix": "1. Resolve ",
        "flow_resolve_suffix": (
            " objective action item(s): dates, stuck stages, and "
            "deterministic blockers first."
        ),
        "flow_no_blockers": (
            "1. Confirm there are no deterministic blockers requiring immediate action."
        ),
        "flow_review_prefix": "2. Review ",
        "flow_review_suffix": (
            " attention deal(s) and assign clear owners before lower-risk pipeline."
        ),
        "flow_normal": "2. Review normal pipeline movement by stage and close date.",
        "flow_observation_prefix": "3. Discuss ",
        "flow_observation_suffix": (
            " judgment-based gap observation(s) as discovery prompts, not "
            "automatic CTAs."
        ),
        "flow_evidence": (
            "3. Use customer evidence to confirm whether the current forecast "
            "still feels right."
        ),
        "flow_cleanup_prefix": "4. Clean up ",
        "flow_cleanup_suffix": (
            " deal(s) with incomplete data only where it affects sales action "
            "or forecast trust."
        ),
        "flow_no_cleanup": "4. No major report data-quality cleanup is required from this export.",
        "host_prompt_title": "Host-App Report Polish Prompt",
    },
    "ko": {
        "all": "전체",
        "none": "없음",
        "na": "해당 없음",
        "unknown_source": "출처 불명",
        "title": "주간 파이프라인 보고서",
        "generated_at": "생성 시각",
        "filters": "필터",
        "executive_summary": "핵심 요약",
        "meeting_agenda": "회의 진행안",
        "kpi": "1. 핵심 KPI",
        "stage_breakdown": "3. 스테이지별 현황",
        "meeting_flow": "5. 다음 주 액션",
        "risk_deals": "2. 주요 딜 현황",
        "issues_to_watch": "4. 주목할 이슈",
        "objective_actions": "즉시 액션",
        "gap_observations": "관찰 갭",
        "customer_evidence": "부록 A. 고객 근거",
        "data_quality": "부록 B. 데이터 품질",
        "metric": "지표",
        "value": "값",
        "open_deals": "오픈 딜",
        "pipeline_value": "파이프라인 금액",
        "known_amount_coverage": "금액 확인 커버리지",
        "average_health": "평균 헬스",
        "health_coverage": "헬스 커버리지",
        "attention_deals": "주의 필요 딜",
        "objective_action_items": "즉시 액션",
        "overdue": "마감일 초과",
        "stuck": "스테이지 지연",
        "at_risk": "위험 헬스",
        "stage": "스테이지",
        "deals": "딜 수",
        "avg_health": "평균 헬스",
        "company": "회사",
        "amount": "금액",
        "expected_close": "예상 마감일",
        "health": "헬스",
        "reasons": "주의 이유",
        "objective_actions_short": "즉시 액션",
        "trigger": "트리거",
        "recommended_action": "추천 액션",
        "reason": "이유",
        "gap": "갭",
        "actionability": "액션성",
        "primary_pain": "주요 Pain",
        "pain_source": "Pain 출처",
        "decision_criteria": "선정 기준",
        "dc_source": "선정 기준 출처",
        "issue": "항목",
        "count": "건수",
        "unassessed_health": "헬스 미평가",
        "missing_expected_close_date": "예상 마감일 누락",
        "invalid_expected_close_date": "예상 마감일 오류",
        "missing_last_meeting_date": "마지막 미팅일 누락",
        "missing_primary_pain": "주요 Pain 누락",
        "missing_primary_decision_criteria": "주요 선정 기준 누락",
        "incomplete_data_quality": "불완전한 데이터 품질",
        "no_risk_deals": "우선 리뷰 딜이 없습니다.",
        "no_key_deals": "선택한 필터에 해당하는 주요 딜이 없습니다.",
        "no_objective_actions": "즉시 액션이 없습니다.",
        "no_gap_observations": "관찰 갭이 없습니다.",
        "no_customer_evidence": "주요 고객 근거가 없습니다.",
        "no_stage_breakdown": "스테이지별 현황이 없습니다.",
        "warning_codes": "경고 코드",
        "no_open_summary_1": "- 선택한 필터에 해당하는 오픈 딜이 없습니다.",
        "no_open_summary_2": "- 새 활성 파이프라인 데이터가 생긴 뒤 다시 보고서를 생성하세요.",
        "summary_purpose": (
            "- 목적: 이번 주 파이프라인 회의를 숫자 확인, 주요 딜 리뷰, "
            "다음 액션 지정 순서로 진행하기 위한 보고서입니다."
        ),
        "open_pipeline_prefix": "- 오픈 파이프라인: ",
        "open_pipeline_across": ", 총 ",
        "open_pipeline_suffix": "개 오픈 딜.",
        "health_prefix": "- 헬스: 평균 ",
        "health_average": "; ",
        "health_attention_suffix": "개 딜은 주의가 필요합니다.",
        "data_confidence_prefix": "- 데이터 신뢰도: ",
        "amount_coverage": "금액 커버리지",
        "first_review_candidate": "- 먼저 볼 딜: ",
        "no_attention_deals": "- 결정적 체크 기준에서 주의 필요 딜은 감지되지 않았습니다.",
        "issue_intro_with_actions": (
            "아래 항목은 일정, 정체, 위험 헬스처럼 비교적 객관적인 신호입니다. "
            "판단 기반 갭을 논의하기 전에 담당자를 먼저 정하세요."
        ),
        "issue_intro_without_actions": (
            "객관적 블로커는 감지되지 않았습니다. 관찰 갭은 forecast 신뢰도나 "
            "다음 액션 품질에 영향을 줄 때만 논의하세요."
        ),
        "flow_resolve_prefix": "1. ",
        "flow_resolve_suffix": (
            "개의 즉시 액션을 먼저 정리합니다: 일정, 지연 스테이지, "
            "객관적 블로커를 우선 확인하세요."
        ),
        "flow_no_blockers": "1. 즉시 조치가 필요한 객관적 블로커가 없는지 확인합니다.",
        "flow_review_prefix": "2. ",
        "flow_review_suffix": "개의 주의 필요 딜에 담당자를 지정한 뒤 나머지 파이프라인을 봅니다.",
        "flow_normal": "2. 스테이지와 마감일 기준으로 일반 파이프라인 이동을 점검합니다.",
        "flow_observation_prefix": "3. ",
        "flow_observation_suffix": (
            "개의 판단 기반 관찰 갭은 자동 CTA가 아니라 다음 discovery 질문으로 "
            "다룹니다."
        ),
        "flow_evidence": "3. 고객 근거를 보며 현재 forecast가 여전히 타당한지 확인합니다.",
        "flow_cleanup_prefix": "4. ",
        "flow_cleanup_suffix": (
            "개의 데이터 품질 이슈는 영업 액션이나 forecast 신뢰도에 영향을 줄 때만 "
            "보완합니다."
        ),
        "flow_no_cleanup": "4. 이번 export 기준으로 큰 데이터 품질 정리는 필요하지 않습니다.",
        "host_prompt_title": "호스트 앱 보고서 다듬기 프롬프트",
    },
}

WARNING_LABELS = {
    "en": {
        "no_open_deals": "No open deals",
        "unassessed_health": "Unassessed health",
        "missing_expected_close_date": "Missing expected close date",
        "invalid_expected_close_date": "Invalid expected close date",
        "missing_last_meeting_date": "Missing last meeting date",
        "missing_primary_pain": "Missing primary pain",
        "missing_primary_decision_criteria": "Missing primary decision criteria",
        "incomplete_data_quality": "Incomplete data quality",
    },
    "ko": {
        "no_open_deals": "오픈 딜 없음",
        "unassessed_health": "헬스 미평가",
        "missing_expected_close_date": "예상 마감일 누락",
        "invalid_expected_close_date": "예상 마감일 오류",
        "missing_last_meeting_date": "마지막 미팅일 누락",
        "missing_primary_pain": "주요 Pain 누락",
        "missing_primary_decision_criteria": "주요 선정 기준 누락",
        "incomplete_data_quality": "불완전한 데이터 품질",
    },
}

ATTENTION_REASON_LABELS = {
    "en": {
        "overdue": "Overdue close date",
        "stuck": "Stuck in stage",
        "stalled": "Stalled stage",
        "at_risk": "At-risk health",
    },
    "ko": {
        "overdue": "마감일 초과",
        "stuck": "스테이지 장기 체류",
        "stalled": "정체 스테이지",
        "at_risk": "위험 헬스",
    },
}

RECOMMENDED_ACTION_LABELS = {
    "en": {
        "review_close_plan": "Confirm close plan and owner",
        "review_next_step": "Confirm next step",
        "review_reactivation_path": "Confirm reactivation path",
        "review_confirmed_risk_plan": "Confirm risk mitigation plan",
    },
    "ko": {
        "review_close_plan": "클로징 계획과 담당자 확인",
        "review_next_step": "다음 액션 확인",
        "review_reactivation_path": "재활성화 경로 확인",
        "review_confirmed_risk_plan": "확인된 리스크 완화 계획 수립",
    },
}

ACTIONABILITY_LABELS = {
    "en": {
        "cta_allowed": "Actionable",
        "needs_human_judgment": "Observation",
    },
    "ko": {
        "cta_allowed": "액션 가능",
        "needs_human_judgment": "관찰",
    },
}

STAGE_LABELS = {
    "en": {},
    "ko": {
        "discovery": "디스커버리",
        "qualification": "검증",
        "proposal": "제안",
        "negotiation": "협상",
        "stalled": "정체",
        "won": "수주",
        "lost": "실주",
        "unknown": "알 수 없음",
    },
}

HEALTH_BAND_LABELS = {
    "en": {
        HealthBand.HEALTHY.value: "healthy",
        HealthBand.WATCH.value: "watch",
        HealthBand.AT_RISK.value: "at_risk",
        HealthBand.UNASSESSED.value: "unassessed",
    },
    "ko": {
        HealthBand.HEALTHY.value: "양호",
        HealthBand.WATCH.value: "관찰",
        HealthBand.AT_RISK.value: "위험",
        HealthBand.UNASSESSED.value: "미평가",
    },
}

FIELD_LABELS = {
    "en": {
        "economic_buyer": "Economic Buyer",
        "champion": "Champion",
        "competition": "Competition",
        "decision_criteria": "Decision Criteria",
        "decision_process": "Decision Process",
        "identify_pain": "Identify Pain",
        "metrics": "Metrics",
        "Overdue close date": "Overdue close date",
        "Stuck in stage": "Stuck in stage",
        "Stage is stuck": "Stage is stuck",
        "Stalled stage": "Stalled stage",
        "Stage is stalled": "Stage is stalled",
        "At-risk health": "At-risk health",
    },
    "ko": {
        "economic_buyer": "경제적 구매자",
        "Economic Buyer": "경제적 구매자",
        "champion": "챔피언",
        "Champion": "챔피언",
        "competition": "경쟁 구도",
        "Competition": "경쟁 구도",
        "decision_criteria": "선정 기준",
        "Decision Criteria": "선정 기준",
        "decision_process": "의사결정 프로세스",
        "Decision Process": "의사결정 프로세스",
        "identify_pain": "고객 Pain",
        "Identify Pain": "고객 Pain",
        "metrics": "성과 지표",
        "Metrics": "성과 지표",
        "Overdue close date": "마감일 초과",
        "Stuck in stage": "스테이지 장기 체류",
        "Stage is stuck": "스테이지 장기 체류",
        "Stalled stage": "정체 스테이지",
        "Stage is stalled": "정체 스테이지",
        "At-risk health": "위험 헬스",
    },
}

SOURCE_LABELS = {
    "en": {},
    "ko": {
        "Meeting (customer-stated)": "회의 (고객 발화)",
        "Email thread (customer-stated)": "이메일 (고객 발화)",
        "User interview (customer-stated)": "사용자 인터뷰 (고객 발화)",
        "Meeting (inferred)": "회의 (추론)",
        "Email thread (inferred)": "이메일 (추론)",
        "User interview (inferred)": "사용자 인터뷰 (추론)",
    },
}


def build_weekly_pipeline_markdown(
    report: dict,
    *,
    generated_at: datetime | None = None,
    language: str = "en",
) -> dict:
    """Build an LLM-free Markdown summary from weekly pipeline report rows."""
    if report.get("report_type") != REPORT_TYPE:
        raise ValueError("report_type must be weekly_pipeline")

    report_language = validate_report_language(language)
    generated = _generated_at(generated_at)
    rows = report.get("rows") if isinstance(report.get("rows"), list) else []
    warnings = [
        str(warning)
        for warning in report.get("warnings", [])
        if warning is not None
    ]
    metrics = _summarize_rows(rows)
    briefing_sections = _build_briefing_sections(rows, metrics, language=report_language)
    markdown = _build_markdown(
        rows,
        filters=report.get("filters") if isinstance(report.get("filters"), dict) else {},
        generated_at=generated,
        metrics=metrics,
        warnings=warnings,
        language=report_language,
        briefing_sections=briefing_sections,
    )
    briefing = _build_briefing(briefing_sections)
    host_prompt = _build_host_report_prompt(
        markdown,
        metrics,
        warnings,
        briefing_sections,
        language=report_language,
    )
    return {
        "report_type": REPORT_TYPE,
        "generated_at": generated.isoformat(),
        "language": report_language,
        "metrics": metrics,
        "warnings": warnings,
        "briefing": briefing,
        "briefing_sections": briefing_sections,
        "host_report_prompt": host_prompt,
        "markdown": markdown,
    }


def validate_report_language(value: Any = "en") -> str:
    if value in (None, ""):
        return "en"
    if not isinstance(value, str):
        raise ValueError("reporting.language must be 'en' or 'ko'")
    language = value.strip().lower()
    if language not in SUPPORTED_REPORT_LANGUAGES:
        raise ValueError("reporting.language must be 'en' or 'ko'")
    return language


def _generated_at(value: datetime | None) -> datetime:
    generated = value or datetime.now(UTC)
    if generated.tzinfo is None or generated.utcoffset() is None:
        raise ValueError("generated_at must be timezone-aware")
    return generated.astimezone(UTC)


def _summarize_rows(rows: list[dict]) -> dict:
    health_values = [
        float(row["health_pct"])
        for row in rows
        if isinstance(row.get("health_pct"), (int, float))
        and not isinstance(row.get("health_pct"), bool)
    ]
    value_assessments = [assess_deal_value(row) for row in rows]
    known_value_assessments = [
        item for item in value_assessments if item.is_valid and item.is_known
    ]
    amount_by_currency = {
        currency: sum(
            assessment.amount or 0
            for assessment in known_value_assessments
            if assessment.currency == currency
        )
        for currency in sorted({item.currency for item in known_value_assessments})
    }
    currencies = sorted(amount_by_currency) or [DEFAULT_DEAL_CURRENCY]
    mixed_currency = len(amount_by_currency) > 1
    row_count = len(rows)
    attention_deal_count = sum(bool(row.get("attention_reasons")) for row in rows)
    return {
        "open_deal_count": row_count,
        "pipeline_value_amount": (
            None if mixed_currency else amount_by_currency.get(currencies[0], 0)
        ),
        "pipeline_value_currency": None if mixed_currency else currencies[0],
        "pipeline_value_currencies": currencies,
        "mixed_pipeline_value_currency": mixed_currency,
        "pipeline_value_by_currency": amount_by_currency,
        "known_amount_count": len(known_value_assessments),
        "amount_coverage_pct": _pct(len(known_value_assessments), row_count),
        "avg_health_pct": (
            round(sum(health_values) / len(health_values), 1)
            if health_values
            else None
        ),
        "assessed_health_count": len(health_values),
        "health_coverage_pct": _pct(len(health_values), row_count),
        "attention_deal_count": attention_deal_count,
        "objective_action_item_count": sum(
            len(row.get("objective_action_items") or []) for row in rows
        ),
        "gap_observation_count": sum(
            len(row.get("gap_observations") or []) for row in rows
        ),
        "overdue_count": sum(row.get("is_overdue") is True for row in rows),
        "stuck_count": sum(row.get("is_stuck") is True for row in rows),
        "stalled_count": sum(row.get("deal_stage") == "stalled" for row in rows),
        "at_risk_count": sum(
            row.get("health_band") == HealthBand.AT_RISK.value for row in rows
        ),
        "unassessed_health_count": sum(
            row.get("health_band") == HealthBand.UNASSESSED.value for row in rows
        ),
        "incomplete_data_quality_count": sum(
            not _is_complete_data_quality(row.get("data_quality")) for row in rows
        ),
        "missing_expected_close_date_count": sum(
            row.get("close_date_status") == "missing" for row in rows
        ),
        "invalid_expected_close_date_count": sum(
            row.get("close_date_status") == "invalid" for row in rows
        ),
        "missing_last_meeting_date_count": sum(
            row.get("last_meeting_date") is None for row in rows
        ),
        "missing_primary_pain_count": sum(
            row.get("primary_pain") is None for row in rows
        ),
        "missing_primary_decision_criteria_count": sum(
            row.get("primary_decision_criteria") is None for row in rows
        ),
        "stage_breakdown": _stage_breakdown(rows),
    }


def _stage_breakdown(rows: list[dict]) -> list[dict]:
    stages = []
    for stage in sorted({str(row.get("deal_stage") or "unknown") for row in rows}):
        stage_rows = [row for row in rows if str(row.get("deal_stage") or "unknown") == stage]
        health_values = [
            float(row["health_pct"])
            for row in stage_rows
            if isinstance(row.get("health_pct"), (int, float))
            and not isinstance(row.get("health_pct"), bool)
        ]
        value_by_currency: dict[str, int] = {}
        for row in stage_rows:
            assessment = assess_deal_value(row)
            if not assessment.is_valid or not assessment.is_known:
                continue
            value_by_currency[assessment.currency] = (
                value_by_currency.get(assessment.currency, 0) + (assessment.amount or 0)
            )
        stages.append(
            {
                "stage": stage,
                "deal_count": len(stage_rows),
                "pipeline_value_by_currency": value_by_currency,
                "avg_health_pct": (
                    round(sum(health_values) / len(health_values), 1)
                    if health_values
                    else None
                ),
                "attention_deal_count": sum(
                    bool(row.get("attention_reasons")) for row in stage_rows
                ),
            }
        )
    stages.sort(
        key=lambda item: (
            -int(item["attention_deal_count"]),
            -int(item["deal_count"]),
            str(item["stage"]),
        )
    )
    return stages


def _pct(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator * 100, 1) if denominator else None


def _is_complete_data_quality(value: Any) -> bool:
    return isinstance(value, dict) and value.get("is_complete") is True


def _build_markdown(
    rows: list[dict],
    *,
    filters: dict,
    generated_at: datetime,
    metrics: dict,
    warnings: list[str],
    language: str,
    briefing_sections: dict[str, list[str]],
) -> str:
    lines = [
        f"# {_text(language, 'title')}",
        "",
        f"{_text(language, 'generated_at')}: {generated_at.isoformat()}",
        f"{_text(language, 'filters')}: "
        f"stage={_filter_value(filters.get('stage'), language)}, "
        f"industry={_filter_value(filters.get('industry'), language)}",
        "",
        f"## {_text(language, 'executive_summary')}",
        "",
        *briefing_sections["executive_summary"],
        "",
        f"## {_text(language, 'meeting_agenda')}",
        "",
        *briefing_sections["meeting_agenda"],
        "",
        f"## {_text(language, 'kpi')}",
        "",
        *_table(
            [_text(language, "metric"), _text(language, "value")],
            [
                [_text(language, "open_deals"), str(metrics["open_deal_count"])],
                [
                    _text(language, "pipeline_value"),
                    _format_pipeline_value(metrics, language),
                ],
                [
                    _text(language, "known_amount_coverage"),
                    _format_ratio(
                        metrics["known_amount_count"],
                        metrics["open_deal_count"],
                        metrics["amount_coverage_pct"],
                    ),
                ],
                [
                    _text(language, "average_health"),
                    _format_pct(metrics["avg_health_pct"], language),
                ],
                [
                    _text(language, "health_coverage"),
                    _format_ratio(
                        metrics["assessed_health_count"],
                        metrics["open_deal_count"],
                        metrics["health_coverage_pct"],
                    ),
                ],
                [
                    _text(language, "attention_deals"),
                    str(metrics["attention_deal_count"]),
                ],
                [
                    _text(language, "objective_action_items"),
                    str(metrics["objective_action_item_count"]),
                ],
                [
                    _text(language, "gap_observations"),
                    str(metrics["gap_observation_count"]),
                ],
                [_text(language, "overdue"), str(metrics["overdue_count"])],
                [_text(language, "stuck"), str(metrics["stuck_count"])],
                [_text(language, "at_risk"), str(metrics["at_risk_count"])],
            ],
            align_right={1},
        ),
        "",
        f"## {_text(language, 'risk_deals')}",
        "",
        *_priority_brief_section(rows, language),
        "",
        *_key_deal_section(rows, language),
        "",
        f"## {_text(language, 'stage_breakdown')}",
        "",
        *_stage_insight_section(metrics, language),
        "",
        *_stage_breakdown_section(metrics, language),
        "",
        f"## {_text(language, 'issues_to_watch')}",
        "",
        (
            _text(language, "issue_intro_with_actions")
            if metrics["objective_action_item_count"]
            else _text(language, "issue_intro_without_actions")
        ),
        "",
        f"### {_text(language, 'objective_actions')}",
        "",
        *_objective_action_section(rows, language),
        "",
        f"### {_text(language, 'gap_observations')}",
        "",
        *_gap_observation_section(rows, language),
        "",
        f"## {_text(language, 'meeting_flow')}",
        "",
        *_meeting_flow_section(metrics, language),
        "",
        f"## {_text(language, 'customer_evidence')}",
        "",
        *_customer_evidence_section(rows, language),
        "",
        f"## {_text(language, 'data_quality')}",
        "",
        *_table(
            [_text(language, "issue"), _text(language, "count")],
            [
                [
                    _text(language, "unassessed_health"),
                    str(metrics["unassessed_health_count"]),
                ],
                [
                    _text(language, "missing_expected_close_date"),
                    str(metrics["missing_expected_close_date_count"]),
                ],
                [
                    _text(language, "invalid_expected_close_date"),
                    str(metrics["invalid_expected_close_date_count"]),
                ],
                [
                    _text(language, "missing_last_meeting_date"),
                    str(metrics["missing_last_meeting_date_count"]),
                ],
                [
                    _text(language, "missing_primary_pain"),
                    str(metrics["missing_primary_pain_count"]),
                ],
                [
                    _text(language, "missing_primary_decision_criteria"),
                    str(metrics["missing_primary_decision_criteria_count"]),
                ],
                [
                    _text(language, "incomplete_data_quality"),
                    str(metrics["incomplete_data_quality_count"]),
                ],
            ],
            align_right={1},
        ),
        "",
        _format_warning_codes(warnings, language),
        "",
    ]
    return "\n".join(lines)


def _build_briefing_sections(
    rows: list[dict],
    metrics: dict,
    *,
    language: str,
) -> dict[str, list[str]]:
    """Return assistant-facing briefing sections for MCP responses."""
    return {
        "executive_summary": _executive_summary(rows, metrics, language),
        "meeting_agenda": _meeting_agenda(metrics, language),
        "priority_deals": _priority_brief_section(rows, language)[:4],
    }


def _build_briefing(sections: dict[str, list[str]]) -> str:
    """Return a compact text briefing for MCP clients that prefer plain text."""
    lines = []
    for key in ("executive_summary", "meeting_agenda", "priority_deals"):
        lines.extend(sections.get(key) or [])
    return "\n".join(lines)


def _meeting_agenda(metrics: dict, language: str) -> list[str]:
    attention_count = metrics["attention_deal_count"]
    action_count = metrics["objective_action_item_count"]
    observation_count = metrics["gap_observation_count"]
    if language == "ko":
        return [
            "1. 핵심 KPI와 데이터 신뢰도 확인 (5분)",
            (
                f"2. 주의 필요 딜 {attention_count}건 리뷰: 일정/정체/위험 헬스처럼 "
                "객관 신호부터 봅니다 (15분)"
            ),
            (
                f"3. 즉시 액션 {action_count}건 담당자 지정: 마감일, stuck/stalled, "
                "확정 리스크를 먼저 닫습니다 (10분)"
            ),
            (
                f"4. 관찰 갭 {observation_count}건은 CTA가 아니라 다음 discovery "
                "질문 후보로만 다룹니다 (10분)"
            ),
            "5. 다음 주 액션과 데이터 보완 항목을 확정합니다 (5분)",
        ]
    return [
        "1. Review core KPIs and data confidence (5 min)",
        (
            f"2. Review {attention_count} attention deal(s), starting with "
            "objective signals such as overdue dates, stuck stages, and confirmed "
            "health risk (15 min)"
        ),
        (
            f"3. Assign owners for {action_count} objective action item(s): close "
            "dates, stuck/stalled stages, and confirmed risks first (10 min)"
        ),
        (
            f"4. Treat {observation_count} judgment-based gap observation(s) as "
            "discovery prompts, not automatic CTAs (10 min)"
        ),
        "5. Confirm next-week actions and data cleanup items (5 min)",
    ]


def _build_host_report_prompt(
    markdown: str,
    metrics: dict,
    warnings: list[str],
    sections: dict[str, list[str]],
    *,
    language: str,
) -> str:
    """Build a safe host-app prompt for polishing the deterministic report."""
    if language == "ko":
        instructions = [
            "아래 deterministic weekly pipeline data pack을 바탕으로",
            "상사 보고/팀 회의용 보고서를 자연스러운 한국어로 다듬어주세요.",
            "숫자, 회사명, stage, 금액, health, warning code는 절대 변경하지 마세요.",
            (
                "objective action item은 CTA로 써도 되지만, gap observation은 "
                "관찰/확인 질문으로만 표현하세요."
            ),
            "raw notes, raw email, contacts, embeddings가 없으면 추측해서 만들지 마세요.",
            (
                "출력은 1) 핵심 요약, 2) 주요 딜 현황, 3) 주목할 이슈, "
                "4) 다음 주 액션, 5) 부록 순서의 Markdown으로 작성하세요."
            ),
        ]
    else:
        instructions = [
            (
                "Polish the deterministic weekly pipeline data pack below into a "
                "manager/team meeting report."
            ),
            (
                "Do not change any numbers, company names, stages, amounts, "
                "health scores, or warning codes."
            ),
            (
                "Objective action items may become CTAs, but gap observations "
                "must remain observations or discovery questions."
            ),
            "Do not invent raw notes, raw emails, contacts, embeddings, or unstated facts.",
            (
                "Return Markdown in this order: 1) Executive summary, 2) Key deal "
                "status, 3) Issues to watch, 4) Next-week actions, 5) Appendix."
            ),
        ]
    payload = {
        "metrics": metrics,
        "warnings": warnings,
        "briefing_sections": sections,
    }
    return "\n".join(
        [
            f"## {_text(language, 'host_prompt_title')}",
            "",
            *[f"- {line}" for line in instructions],
            "",
            "### Data Pack JSON",
            "",
            "```json",
            _json_dumps(payload),
            "```",
            "",
            "### Deterministic Markdown Draft",
            "",
            markdown,
        ]
    )


def _key_deal_section(rows: list[dict], language: str) -> list[str]:
    key_rows = rows[:5]
    if not key_rows:
        return [_text(language, "no_key_deals")]
    return _table(
        [
            _text(language, "company"),
            _text(language, "stage"),
            _text(language, "amount"),
            _text(language, "expected_close"),
            _text(language, "health"),
            _text(language, "reasons"),
        ],
        [
            [
                row.get("company"),
                _format_stage(row.get("deal_stage"), language),
                _format_money(
                    _valid_amount(row),
                    currency=row.get("deal_size_currency") or DEFAULT_DEAL_CURRENCY,
                ),
                row.get("expected_close_date") or _text(language, "na"),
                _format_health(row, language),
                _format_attention_reasons(row.get("attention_reasons") or [], language),
            ]
            for row in key_rows
        ],
    )


def _executive_summary(rows: list[dict], metrics: dict, language: str) -> list[str]:
    if not rows:
        return [
            _text(language, "no_open_summary_1"),
            _text(language, "no_open_summary_2"),
        ]

    top_attention = _top_attention_deal(rows)
    focus_stage = _top_stage(metrics)
    amount_coverage = _format_ratio(
        metrics["known_amount_count"],
        metrics["open_deal_count"],
        metrics["amount_coverage_pct"],
    )
    health_coverage = _format_ratio(
        metrics["assessed_health_count"],
        metrics["open_deal_count"],
        metrics["health_coverage_pct"],
    )
    health_label = _text(language, "health_coverage")
    data_quality = (
        f"{_text(language, 'amount_coverage')} {amount_coverage}; "
        f"{health_label} {health_coverage}"
    )
    if language == "ko":
        lines = [
            (
                f"- 이번 주 기준 오픈 파이프라인은 "
                f"{_format_pipeline_value(metrics, language)}"
                f"이며, 총 {metrics['open_deal_count']}개 딜이 열려 있습니다. "
                f"그중 {metrics['attention_deal_count']}개는 회의 초반에 먼저 "
                "확인해야 합니다."
            ),
            (
                f"- 평균 헬스는 {_format_pct(metrics['avg_health_pct'], language)}"
                f"입니다. 헬스 커버리지는 {health_coverage}로, 점수 자체보다 "
                "주의 딜의 원인을 함께 봐야 합니다."
            ),
            f"- 데이터 신뢰도는 {data_quality}입니다.",
        ]
    else:
        lines = [
            (
                f"- Open pipeline is "
                f"{_format_pipeline_value(metrics, language)}"
                f" across {metrics['open_deal_count']} open deal(s). "
                f"Review the {metrics['attention_deal_count']} attention deal(s) "
                "before normal pipeline updates."
            ),
            (
                f"- Average health is {_format_pct(metrics['avg_health_pct'], language)}. "
                f"Health coverage is {health_coverage}; interpret the score together "
                "with the attention reasons."
            ),
            f"- Data confidence: {data_quality}.",
        ]
    if focus_stage:
        lines.append(_stage_focus_sentence(focus_stage, metrics, language))
    if top_attention:
        company = _md_inline(top_attention.get("company"))
        reasons = _format_attention_reasons(
            top_attention.get("attention_reasons") or [],
            language,
        )
        if language == "ko":
            lines.append(
                f"- 이번 회의의 첫 리뷰 후보는 {company}입니다. "
                f"주의 이유: {reasons}."
            )
        else:
            lines.append(
                f"- First review candidate: {company}. Attention reason(s): {reasons}."
            )
    else:
        lines.append(_text(language, "no_attention_deals"))
    return lines


def _top_attention_deal(rows: list[dict]) -> dict | None:
    for row in rows:
        if row.get("attention_reasons"):
            return row
    return None


def _priority_brief_section(rows: list[dict], language: str) -> list[str]:
    priority_rows = [row for row in rows if row.get("attention_reasons")][:3]
    if not priority_rows:
        return [_text(language, "no_risk_deals")]
    lines = []
    intro = (
        "다음 딜은 표를 읽기 전에 바로 의사결정해야 할 후보입니다."
        if language == "ko"
        else "Start with these deals before reading the full table."
    )
    lines.append(intro)
    for row in priority_rows:
        lines.append(_priority_deal_sentence(row, language))
    return lines


def _priority_deal_sentence(row: dict, language: str) -> str:
    company = _md_inline(row.get("company"))
    stage = _format_stage(row.get("deal_stage"), language)
    amount = _format_money(
        _valid_amount(row),
        currency=row.get("deal_size_currency") or DEFAULT_DEAL_CURRENCY,
    )
    close_date = row.get("expected_close_date") or _text(language, "na")
    health = _format_health(row, language)
    reasons = _format_attention_reasons(row.get("attention_reasons") or [], language)
    first_action = _first_recommended_action(row, language)
    primary_gap = _first_gap_label(row, language)
    if language == "ko":
        detail = (
            f"{company} ({stage} · {amount})는 마감일 {close_date}, "
            f"헬스 {health}입니다. 주의 이유는 {reasons}"
        )
        if primary_gap:
            detail += f"이고, 함께 볼 갭은 {primary_gap}"
        detail += f"입니다. 우선 액션: {first_action}."
        return f"- {detail}"
    detail = (
        f"{company} ({stage} · {amount}) has expected close {close_date}, "
        f"health {health}, and attention reason(s): {reasons}"
    )
    if primary_gap:
        detail += f"; also review gap: {primary_gap}"
    detail += f". Priority action: {first_action}."
    return f"- {detail}"


def _first_recommended_action(row: dict, language: str) -> str:
    for action in row.get("objective_action_items") or []:
        if isinstance(action, dict):
            return _format_recommended_action(action, language)
    return (
        "근거 확인 후 다음 액션 지정"
        if language == "ko"
        else "Review evidence and assign the next action"
    )


def _first_gap_label(row: dict, language: str) -> str | None:
    for observation in row.get("gap_observations") or []:
        if isinstance(observation, dict):
            return _format_field_label(
                observation.get("label") or observation.get("field"),
                language,
            )
    return None


def _stage_insight_section(metrics: dict, language: str) -> list[str]:
    stage = _top_stage(metrics)
    if not stage:
        return []
    return [_stage_focus_sentence(stage, metrics, language)]


def _top_stage(metrics: dict) -> dict | None:
    breakdown = metrics.get("stage_breakdown")
    if not isinstance(breakdown, list):
        return None
    candidates = [stage for stage in breakdown if isinstance(stage, dict)]
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda item: (
            -_currency_total(item.get("pipeline_value_by_currency")),
            -int(item.get("deal_count") or 0),
            str(item.get("stage") or ""),
        ),
    )[0]


def _stage_focus_sentence(stage: dict, metrics: dict, language: str) -> str:
    stage_name = _format_stage(stage.get("stage"), language)
    deal_count = int(stage.get("deal_count") or 0)
    value = _format_currency_breakdown(
        stage.get("pipeline_value_by_currency"),
        language,
    )
    total = _currency_total(stage.get("pipeline_value_by_currency"))
    denominator = metrics.get("pipeline_value_amount")
    share = (
        round(total / denominator * 100, 1)
        if isinstance(denominator, (int, float))
        and not isinstance(denominator, bool)
        and denominator > 0
        and total > 0
        else None
    )
    avg_health = _format_pct(stage.get("avg_health_pct"), language)
    if language == "ko":
        if share is not None:
            return (
                f"- {stage_name} 단계가 금액 기준 핵심 구간입니다. "
                f"{deal_count}개 딜, {value}로 전체 확인 금액의 {share:.1f}%를 "
                f"차지하며 평균 헬스는 {avg_health}입니다."
            )
        return (
            f"- {stage_name} 단계가 현재 가장 큰 리뷰 묶음입니다. "
            f"{deal_count}개 딜이 있고 평균 헬스는 {avg_health}입니다."
        )
    if share is not None:
        return (
            f"- {stage_name} is the main value concentration: {deal_count} deal(s), "
            f"{value}, {share:.1f}% of known pipeline value, avg health {avg_health}."
        )
    return (
        f"- {stage_name} is the largest review cluster: {deal_count} deal(s), "
        f"avg health {avg_health}."
    )


def _currency_total(value: Any) -> int:
    if not isinstance(value, dict):
        return 0
    total = 0
    for amount in value.values():
        if isinstance(amount, (int, float)) and not isinstance(amount, bool):
            total += int(amount)
    return total


def _stage_breakdown_section(metrics: dict, language: str) -> list[str]:
    breakdown = metrics.get("stage_breakdown")
    if not isinstance(breakdown, list) or not breakdown:
        return [_text(language, "no_stage_breakdown")]
    return _table(
        [
            _text(language, "stage"),
            _text(language, "deals"),
            _text(language, "pipeline_value"),
            _text(language, "avg_health"),
            _text(language, "attention_deals"),
        ],
        [
            [
                _format_stage(row.get("stage"), language),
                row.get("deal_count"),
                _format_currency_breakdown(
                    row.get("pipeline_value_by_currency"),
                    language,
                ),
                _format_pct(row.get("avg_health_pct"), language),
                row.get("attention_deal_count"),
            ]
            for row in breakdown
            if isinstance(row, dict)
        ],
        align_right={1, 4},
    )


def _meeting_flow_section(metrics: dict, language: str) -> list[str]:
    action_count = metrics["objective_action_item_count"]
    observation_count = metrics["gap_observation_count"]
    data_quality_count = metrics["incomplete_data_quality_count"]
    lines = []
    if action_count:
        lines.append(
            f"{_text(language, 'flow_resolve_prefix')}{action_count}"
            f"{_text(language, 'flow_resolve_suffix')}"
        )
    else:
        lines.append(_text(language, "flow_no_blockers"))
    if metrics["attention_deal_count"]:
        lines.append(
            f"{_text(language, 'flow_review_prefix')}"
            f"{metrics['attention_deal_count']}"
            f"{_text(language, 'flow_review_suffix')}"
        )
    else:
        lines.append(_text(language, "flow_normal"))
    if observation_count:
        lines.append(
            f"{_text(language, 'flow_observation_prefix')}{observation_count}"
            f"{_text(language, 'flow_observation_suffix')}"
        )
    else:
        lines.append(_text(language, "flow_evidence"))
    if data_quality_count:
        lines.append(
            f"{_text(language, 'flow_cleanup_prefix')}{data_quality_count}"
            f"{_text(language, 'flow_cleanup_suffix')}"
        )
    else:
        lines.append(_text(language, "flow_no_cleanup"))
    return lines


def _objective_action_section(rows: list[dict], language: str) -> list[str]:
    action_rows = [
        (row, action)
        for row in rows
        for action in row.get("objective_action_items") or []
        if isinstance(action, dict)
    ]
    if not action_rows:
        return [_text(language, "no_objective_actions")]
    return _table(
        [
            _text(language, "company"),
            _text(language, "trigger"),
            _text(language, "recommended_action"),
            _text(language, "reason"),
        ],
        [
            [
                row.get("company"),
                _format_field_label(action.get("label") or action.get("gap_id"), language),
                _format_recommended_action(action, language),
                _format_reason(action.get("reason"), language),
            ]
            for row, action in action_rows
        ],
    )


def _gap_observation_section(rows: list[dict], language: str) -> list[str]:
    observation_rows = [
        (row, observation)
        for row in rows
        for observation in row.get("gap_observations") or []
        if isinstance(observation, dict)
    ]
    if not observation_rows:
        return [_text(language, "no_gap_observations")]
    return _table(
        [
            _text(language, "company"),
            _text(language, "gap"),
            _text(language, "actionability"),
            _text(language, "reason"),
        ],
        [
            [
                row.get("company"),
                _format_field_label(
                    observation.get("label") or observation.get("field"),
                    language,
                ),
                _format_actionability(observation.get("actionability"), language),
                _format_reason(observation.get("reason"), language),
            ]
            for row, observation in observation_rows
        ],
    )


def _customer_evidence_section(rows: list[dict], language: str) -> list[str]:
    evidence_rows = [
        row
        for row in rows
        if isinstance(row.get("primary_pain"), dict)
        or isinstance(row.get("primary_decision_criteria"), dict)
    ]
    if not evidence_rows:
        return [_text(language, "no_customer_evidence")]
    return _table(
        [
            _text(language, "company"),
            _text(language, "primary_pain"),
            _text(language, "pain_source"),
            _text(language, "decision_criteria"),
            _text(language, "dc_source"),
        ],
        [
            [
                row.get("company"),
                _format_theme(row.get("primary_pain"), language),
                _format_theme_source(row.get("primary_pain"), language),
                _format_theme(row.get("primary_decision_criteria"), language),
                _format_theme_source(row.get("primary_decision_criteria"), language),
            ]
            for row in evidence_rows
        ],
    )


def _format_theme(theme: Any, language: str) -> str:
    if not isinstance(theme, dict):
        return _text(language, "na")
    evidence = str(theme.get("evidence") or "").strip()
    label = str(theme.get("label") or theme.get("theme_key") or "").strip()
    if label and evidence:
        return f"{label}: {evidence}"
    return evidence or label or _text(language, "na")


def _format_theme_source(theme: Any, language: str) -> str:
    if not isinstance(theme, dict):
        return _text(language, "na")
    source = str(theme.get("source_label") or _text(language, "unknown_source"))
    return SOURCE_LABELS.get(language, {}).get(source, source)


def _format_action_items(actions: list[dict], language: str) -> str:
    values = [
        _format_recommended_action(action, language)
        for action in actions
        if isinstance(action, dict)
    ]
    return ", ".join(values) if values else _text(language, "none")


def _format_attention_reasons(reasons: list[Any], language: str) -> str:
    values = [
        _label(ATTENTION_REASON_LABELS, str(reason), language)
        for reason in reasons
    ]
    return ", ".join(values) if values else _text(language, "none")


def _format_recommended_action(action: dict, language: str) -> str:
    raw = str(action.get("recommended_action") or action.get("gap_id") or "review")
    return _label(RECOMMENDED_ACTION_LABELS, raw, language)


def _format_actionability(value: Any, language: str) -> str:
    raw = str(value or "")
    return _label(ACTIONABILITY_LABELS, raw, language) if raw else _text(language, "na")


def _format_reason(value: Any, language: str) -> str:
    raw = str(value or "")
    if not raw:
        return _text(language, "na")
    if language != "ko":
        return raw
    overdue_prefix = "Expected close date is overdue by "
    if raw.startswith(overdue_prefix) and raw.endswith(" day(s)."):
        days = raw.removeprefix(overdue_prefix).removesuffix(" day(s).")
        return f"예상 마감일이 {days}일 지났습니다."
    if raw == "Deal is explicitly marked stalled.":
        return "딜이 명시적으로 정체 상태로 표시되어 있습니다."
    if raw == (
        "Deal has stayed in the current active stage past the stuck threshold."
    ):
        return "현재 활성 스테이지에 기준일보다 오래 머물러 있습니다."
    if raw == (
        "Qualification health is at risk; review the underlying evidence before "
        "prescribing an action."
    ):
        return "평가 헬스가 위험 구간입니다. 액션을 정하기 전에 근거를 확인하세요."
    legacy_gap_prefix = "MEDDPICC gap remains open: "
    if raw.startswith(legacy_gap_prefix) and raw.endswith("."):
        label = raw.removeprefix(legacy_gap_prefix).removesuffix(".")
        return f"평가 갭이 남아 있습니다: {_format_field_label(label, language)}."
    gap_prefix = "Qualification gap remains open: "
    if raw.startswith(gap_prefix) and raw.endswith("."):
        label = raw.removeprefix(gap_prefix).removesuffix(".")
        return f"평가 갭이 남아 있습니다: {_format_field_label(label, language)}."
    return raw


def _format_gap_observations(observations: list[dict], language: str) -> str:
    values = [
        _format_field_label(observation.get("label") or observation.get("field"), language)
        for observation in observations
        if isinstance(observation, dict)
    ]
    return ", ".join(values) if values else _text(language, "none")


def _valid_amount(row: dict) -> int:
    assessment = assess_deal_value(row)
    if assessment.is_valid and assessment.is_known:
        return assessment.amount or 0
    return 0


def _format_health(row: dict, language: str) -> str:
    health = row.get("health_pct")
    band = str(row.get("health_band") or "unknown")
    label = _label(HEALTH_BAND_LABELS, band, language)
    if not isinstance(health, (int, float)) or isinstance(health, bool):
        return label
    return f"{float(health):.1f}% ({label})"


def _table(
    headers: list[str],
    rows: list[list[Any]],
    *,
    align_right: set[int] | None = None,
) -> list[str]:
    align_right = align_right or set()
    divider = [
        "---:" if index in align_right else "---" for index, _ in enumerate(headers)
    ]
    return [
        "| " + " | ".join(_md_cell(header) for header in headers) + " |",
        "| " + " | ".join(divider) + " |",
        *[
            "| " + " | ".join(_md_cell(value) for value in row) + " |"
            for row in rows
        ],
    ]


def _md_cell(value: Any) -> str:
    text = "N/A" if value is None else str(value)
    return text.replace("\r", " ").replace("\n", " ").replace("|", r"\|")


def _md_inline(value: Any) -> str:
    return _md_cell(value).replace("*", r"\*").replace("_", r"\_")


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)


def _filter_value(value: Any, language: str) -> str:
    return str(value) if value not in (None, "") else _text(language, "all")


def _format_pipeline_value(metrics: dict, language: str = "en") -> str:
    if metrics.get("mixed_pipeline_value_currency") is True:
        return _format_currency_breakdown(
            metrics.get("pipeline_value_by_currency"),
            language,
        )
    return _format_money(
        metrics.get("pipeline_value_amount"),
        currency=metrics.get("pipeline_value_currency") or DEFAULT_DEAL_CURRENCY,
    )


def _format_currency_breakdown(value: Any, language: str = "en") -> str:
    if not isinstance(value, dict) or not value:
        return _text(language, "na")
    return ", ".join(
        _format_money(amount, currency=str(currency))
        for currency, amount in sorted(value.items())
    )


def _format_money(value: int | float | None, *, currency: str) -> str:
    if value is None:
        return "N/A"
    return f"{int(value):,} {currency}"


def _format_pct(value: float | None, language: str = "en") -> str:
    return _text(language, "na") if value is None else f"{value:.1f}%"


def _format_ratio(count: int, total: int, pct: float | None) -> str:
    if pct is None:
        return f"{count}/{total}"
    return f"{count}/{total} ({pct:.1f}%)"


def _format_warning_codes(warnings: list[str], language: str) -> str:
    if not warnings:
        return f"{_text(language, 'warning_codes')}: {_text(language, 'none')}"
    labels = [
        f"`{warning}` ({_label(WARNING_LABELS, warning, language)})"
        for warning in warnings
    ]
    return f"{_text(language, 'warning_codes')}: " + ", ".join(labels)


def _text(language: str, key: str) -> str:
    return TEXT[language][key]


def _label(labels: dict[str, dict[str, str]], key: str, language: str) -> str:
    fallback = key.replace("_", " ").title()
    return labels.get(language, {}).get(
        key,
        labels.get("en", {}).get(key, fallback),
    )


def _format_stage(value: Any, language: str) -> str:
    stage = str(value or "unknown")
    return STAGE_LABELS.get(language, {}).get(stage, stage)


def _format_field_label(value: Any, language: str) -> str:
    raw = str(value or "")
    if not raw:
        return _text(language, "na")
    return _label(FIELD_LABELS, raw, language)
