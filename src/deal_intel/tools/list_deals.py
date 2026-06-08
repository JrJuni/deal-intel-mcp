from __future__ import annotations

from deal_intel.errors import ErrorCode, MCPError, Stage
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
        current_stage = d.get("deal_stage", "")
        meddpicc_latest = d.get("meddpicc_latest") or {}
        timing = assess_pipeline_timing(
            d,
            as_of=reporting.as_of,
            settings=timing_settings,
        )
        health_band = classify_health(
            meddpicc_latest,
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
            "deal_stage": current_stage,
            "deal_size_krw": d.get("deal_size_krw"),
            "expected_close_date": d.get("expected_close_date"),
            "expected_close_date_source": d.get("expected_close_date_source"),
            "actual_close_date": d.get("actual_close_date"),
            "health_pct": meddpicc_latest.get("health_pct"),
            "health_band": health_band,
            "filled_count": meddpicc_latest.get("filled_count"),
            "gaps": meddpicc_latest.get("gaps", []),
            "meeting_count": len(d.get("meetings", [])),
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
