from __future__ import annotations

from deal_intel.errors import ErrorCode, MCPError, Stage
from deal_intel.schema.interactions import iter_interactions
from deal_intel.schema.meddpicc import VALID_STAGES
from deal_intel.schema.metrics import (
    HealthBandThresholds,
    PipelineTimingSettings,
    ReportingContext,
    assess_deal_data_quality,
    assess_pipeline_timing,
    build_attention_reasons,
    classify_health,
    summarize_data_quality,
)
from deal_intel.schema.qualification_read import (
    qualification_summary,
    select_qualification_snapshot,
)
from deal_intel.storage.mongodb import MongoDBClient


def handle(
    mongo: MongoDBClient,
    cfg: dict,
    *,
    stage: str | None,
    limit: int,
    as_of: str | None = None,
) -> dict:
    if stage and stage not in VALID_STAGES:
        raise MCPError(
            error_code=ErrorCode.INVALID_INPUT,
            stage=Stage.PREFLIGHT,
            message=f"stage {stage!r} is not valid",
            hint={"valid_stages": sorted(VALID_STAGES)},
            retryable=False,
        )

    try:
        timing_settings = PipelineTimingSettings.from_config(cfg)
        health_thresholds = HealthBandThresholds.from_config(cfg)
        reporting = ReportingContext.from_config(cfg, as_of=as_of)
    except ValueError as exc:
        error_code = (
            ErrorCode.INVALID_INPUT
            if str(exc).startswith("as_of")
            else ErrorCode.CONFIG_ERROR
        )
        raise MCPError(
            error_code=error_code,
            stage=Stage.PREFLIGHT,
            message=str(exc),
            retryable=False,
        ) from exc
    try:
        deals = mongo.list_deals(stage=stage, limit=limit)
    except Exception as exc:
        raise MCPError(
            error_code=ErrorCode.STORAGE_ERROR,
            stage=Stage.STORAGE,
            message=str(exc),
            retryable=True,
        ) from exc

    summaries = []
    for d in deals:
        interactions = iter_interactions(d)
        current_stage = d.get("deal_stage", "")
        qualification = select_qualification_snapshot(d)
        timing = assess_pipeline_timing(
            d,
            as_of=reporting.as_of,
            settings=timing_settings,
        )
        health_band = classify_health(
            qualification.snapshot,
            health_thresholds,
        )
        attention_reasons = build_attention_reasons(
            stage=current_stage,
            health_band=health_band,
            timing=timing,
        )
        summaries.append({
            "deal_id": d["deal_id"],
            "company": d["company"],
            "industry": d.get("industry"),
            "industry_tags": d.get("industry_tags") or [],
            "customer_segment": d.get("customer_segment"),
            "deal_stage": current_stage,
            "deal_size_amount": d.get("deal_size_amount"),
            "deal_size_currency": d.get("deal_size_currency") or "KRW",
            "expected_close_date": d.get("expected_close_date"),
            "expected_close_date_source": d.get("expected_close_date_source"),
            "actual_close_date": d.get("actual_close_date"),
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
            "health_band": health_band,
            "filled_count": qualification.filled_count,
            "gaps": qualification.gaps,
            "meeting_count": len(interactions),
            "interaction_count": len(interactions),
            "days_in_stage": timing.days_in_stage,
            "stuck_threshold_days": timing.stuck_threshold_days,
            "stuck_status": timing.stuck_status,
            "is_stuck": timing.is_stuck,
            "close_date_status": timing.close_date_status,
            "is_overdue": timing.is_overdue,
            "overdue_days": timing.overdue_days,
            "attention_reasons": attention_reasons,
            "data_quality": assess_deal_data_quality(d).to_dict(),
            "updated_at": d.get("updated_at", ""),
        })

    # Sort: stuck deals first, then by health_pct desc within each group.
    summaries.sort(key=lambda x: (not x["is_stuck"], -(x["health_pct"] or 0)))

    return {
        "ok": True,
        **reporting.to_dict(),
        "deals": summaries,
        "count": len(summaries),
        "data_quality": summarize_data_quality(deals),
    }
