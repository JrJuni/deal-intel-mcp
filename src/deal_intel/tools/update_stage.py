from __future__ import annotations

from datetime import UTC, date, datetime

from deal_intel.errors import ErrorCode, MCPError, Stage
from deal_intel.schema.meddpicc import VALID_STAGES, compute_meddpicc_latest
from deal_intel.schema.metrics import (
    ACTIVE_STAGES,
    PipelineTimingSettings,
    ReportingContext,
)
from deal_intel.storage.mongodb import MongoDBClient
from deal_intel.tools.analytics_snapshot import (
    record_analytics_snapshot,
    snapshot_event_id,
)


def handle(
    mongo: MongoDBClient,
    cfg: dict,
    *,
    deal_id: str,
    new_stage: str,
    actual_close_date: str | None = None,
) -> dict:
    if new_stage not in VALID_STAGES:
        raise MCPError(
            error_code=ErrorCode.INVALID_INPUT,
            stage=Stage.PREFLIGHT,
            message=f"stage {new_stage!r} is not valid",
            hint={"valid_stages": sorted(VALID_STAGES)},
            retryable=False,
        )

    now_dt = datetime.now(UTC)
    now = now_dt.isoformat()
    try:
        timing_settings = PipelineTimingSettings.from_config(cfg)
        reporting = ReportingContext.from_config(cfg, generated_at=now_dt)
    except ValueError as exc:
        raise MCPError(
            error_code=ErrorCode.CONFIG_ERROR,
            stage=Stage.PREFLIGHT,
            message=str(exc),
            retryable=False,
        ) from exc

    parsed_close_date = None
    if actual_close_date is not None:
        if new_stage not in {"won", "lost"}:
            raise MCPError(
                error_code=ErrorCode.INVALID_INPUT,
                stage=Stage.PREFLIGHT,
                message="actual_close_date is only valid for won or lost stages",
                retryable=False,
            )
        try:
            parsed_close_date = date.fromisoformat(actual_close_date).isoformat()
        except (TypeError, ValueError) as exc:
            raise MCPError(
                error_code=ErrorCode.INVALID_INPUT,
                stage=Stage.PREFLIGHT,
                message="actual_close_date must use ISO format YYYY-MM-DD",
                retryable=False,
            ) from exc

    deal = mongo.get_deal(deal_id)
    if deal is None:
        raise MCPError(
            error_code=ErrorCode.NOT_FOUND,
            stage=Stage.STORAGE,
            message=f"deal_id {deal_id!r} not found",
            retryable=False,
        )

    old_stage = deal.get("deal_stage", "discovery")

    deal["deal_stage"] = new_stage
    if new_stage in {"won", "lost"}:
        deal["actual_close_date"] = parsed_close_date or reporting.as_of.isoformat()
    else:
        deal["actual_close_date"] = None
    deal["updated_at"] = now
    deal.setdefault("stage_history", []).append({
        "stage": new_stage,
        "entered_at": now,
    })

    # Recompute meddpicc_latest with the new stage so gap classification
    # reflects the updated stage context (e.g., won → gaps cleared).
    if deal.get("meetings"):
        meddpicc_cfg = cfg.get("meddpicc", {})
        deal["meddpicc_latest"] = compute_meddpicc_latest(
            deal["meetings"],
            weights=meddpicc_cfg.get("weights", {}),
            gap_threshold=int(meddpicc_cfg.get("gap_threshold", 2)),
            deal_stage=new_stage,
        )

    try:
        mongo.upsert_deal(deal)
    except Exception as exc:
        raise MCPError(
            error_code=ErrorCode.STORAGE_ERROR,
            stage=Stage.STORAGE,
            message=str(exc),
            retryable=True,
        ) from exc

    # Compute days spent in previous stage from stage_history.
    history = deal.get("stage_history", [])
    days_in_prev: float | None = None
    if len(history) >= 2:
        prev_entry = history[-2]
        try:
            from datetime import datetime as _dt
            prev_ts = _dt.fromisoformat(prev_entry["entered_at"])
            curr_ts = _dt.fromisoformat(now)
            days_in_prev = round((curr_ts - prev_ts).total_seconds() / 86400, 1)
        except Exception:
            pass

    threshold = (
        timing_settings.stuck_threshold_for(new_stage)
        if new_stage in ACTIVE_STAGES
        else None
    )

    analytics_snapshot = record_analytics_snapshot(
        mongo=mongo,
        cfg=cfg,
        event_type="update_stage",
        event_id=snapshot_event_id(
            "update_stage",
            deal_id=deal_id,
            event_key=f"{new_stage}:{now}",
        ),
        deal=deal,
        occurred_at=now_dt,
    )

    result = {
        "ok": True,
        "deal_id": deal_id,
        "old_stage": old_stage,
        "new_stage": new_stage,
        "actual_close_date": deal["actual_close_date"],
        "days_in_previous_stage": days_in_prev,
        "stuck_threshold_days": threshold,
    }
    if analytics_snapshot is not None:
        result["analytics_snapshot"] = analytics_snapshot
    return result
