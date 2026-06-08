from __future__ import annotations

from deal_intel.errors import ErrorCode, MCPError, Stage
from deal_intel.schema.metrics import (
    VALID_STAGES,
    HealthBandThresholds,
    PipelineTimingSettings,
    ReportingContext,
    WinRateSettings,
)
from deal_intel.schema.pipeline_metrics import build_pipeline_health_summary
from deal_intel.storage.mongodb import MongoDBClient

VALID_METRIC_TYPES = frozenset({"pipeline_health"})


def handle(
    mongo: MongoDBClient,
    cfg: dict,
    *,
    metric_type: str,
    stage: str | None = None,
    industry: str | None = None,
    as_of: str | None = None,
) -> dict:
    if metric_type not in VALID_METRIC_TYPES:
        raise MCPError(
            error_code=ErrorCode.INVALID_INPUT,
            stage=Stage.PREFLIGHT,
            message=f"metric_type {metric_type!r} is not valid",
            hint={"valid_metric_types": sorted(VALID_METRIC_TYPES)},
            retryable=False,
        )
    if stage and stage not in VALID_STAGES:
        raise MCPError(
            error_code=ErrorCode.INVALID_INPUT,
            stage=Stage.PREFLIGHT,
            message=f"stage {stage!r} is not valid",
            hint={"valid_stages": sorted(VALID_STAGES)},
            retryable=False,
        )

    try:
        reporting = ReportingContext.from_config(cfg, as_of=as_of)
        health_thresholds = HealthBandThresholds.from_config(cfg)
        timing_settings = PipelineTimingSettings.from_config(cfg)
        win_rate_settings = WinRateSettings.from_config(cfg)
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
        deals = mongo.list_deals_for_metrics()
    except Exception as exc:
        raise MCPError(
            error_code=ErrorCode.STORAGE_ERROR,
            stage=Stage.STORAGE,
            message=str(exc),
            retryable=True,
        ) from exc

    summary = build_pipeline_health_summary(
        deals,
        as_of=reporting.as_of,
        health_thresholds=health_thresholds,
        timing_settings=timing_settings,
        win_rate_settings=win_rate_settings,
        stage=stage,
        industry=industry,
    )
    return {
        "ok": True,
        "metric_type": metric_type,
        **reporting.to_dict(),
        **summary,
    }
