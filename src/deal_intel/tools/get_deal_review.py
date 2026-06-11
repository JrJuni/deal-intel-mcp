from __future__ import annotations

from deal_intel.errors import ErrorCode, MCPError, Stage
from deal_intel.schema.deal_review import DealReviewSettings, build_deal_review
from deal_intel.schema.metrics import (
    HealthBandThresholds,
    PipelineTimingSettings,
    ReportingContext,
)
from deal_intel.storage.mongodb import MongoDBClient


def handle(
    mongo: MongoDBClient,
    cfg: dict,
    *,
    deal_id: str,
    as_of: str | None = None,
) -> dict:
    if not isinstance(deal_id, str) or not deal_id.strip():
        raise MCPError(
            error_code=ErrorCode.INVALID_INPUT,
            stage=Stage.PREFLIGHT,
            message="deal_id is required",
            retryable=False,
        )
    deal_id = deal_id.strip()

    try:
        reporting = ReportingContext.from_config(cfg, as_of=as_of)
        health_thresholds = HealthBandThresholds.from_config(cfg)
        timing_settings = PipelineTimingSettings.from_config(cfg)
        review_settings = DealReviewSettings.from_config(cfg)
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

    deal = next((item for item in deals if item.get("deal_id") == deal_id), None)
    if deal is None:
        raise MCPError(
            error_code=ErrorCode.NOT_FOUND,
            stage=Stage.STORAGE,
            message=f"deal_id {deal_id!r} not found",
            retryable=False,
        )

    review = build_deal_review(
        deal,
        as_of=reporting.as_of,
        health_thresholds=health_thresholds,
        timing_settings=timing_settings,
        review_settings=review_settings,
    )
    return {
        "ok": True,
        **reporting.to_dict(),
        "review": review,
    }
