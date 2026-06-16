from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from deal_intel.schema.metrics import (
    HealthBandThresholds,
    PipelineTimingSettings,
    ReportingContext,
    assess_pipeline_timing,
    build_attention_reasons,
    classify_health,
)
from deal_intel.schema.qualification_read import select_qualification_snapshot

SNAPSHOT_SCHEMA_VERSION = 1
SNAPSHOT_SOURCE = "deal_intel_mcp"


def record_analytics_snapshot(
    *,
    mongo: Any,
    cfg: dict,
    event_type: str,
    event_id: str,
    deal: dict,
    occurred_at: datetime | None = None,
) -> dict | None:
    """Persist a lightweight BI snapshot without blocking the source mutation."""
    if not hasattr(mongo, "upsert_analytics_snapshot"):
        return None

    try:
        now = occurred_at or datetime.now(UTC)
        snapshot = build_analytics_snapshot(
            cfg=cfg,
            event_type=event_type,
            event_id=event_id,
            deal=deal,
            occurred_at=now,
        )
        inserted = bool(mongo.upsert_analytics_snapshot(snapshot))
    except Exception as exc:
        return {
            "ok": False,
            "warning": "analytics_snapshot_failed",
            "event_type": event_type,
            "event_id": event_id,
            "message": str(exc),
        }

    return {
        "ok": True,
        "event_type": event_type,
        "event_id": event_id,
        "snapshot_id": snapshot["snapshot_id"],
        "inserted": inserted,
        "duplicate": not inserted,
    }


def build_analytics_snapshot(
    *,
    cfg: dict,
    event_type: str,
    event_id: str,
    deal: dict,
    occurred_at: datetime,
) -> dict:
    if occurred_at.tzinfo is None or occurred_at.utcoffset() is None:
        raise ValueError("occurred_at must be timezone-aware")

    occurred_utc = occurred_at.astimezone(UTC)
    reporting = ReportingContext.from_config(cfg, generated_at=occurred_utc)
    health_thresholds = HealthBandThresholds.from_config(cfg)
    timing_settings = PipelineTimingSettings.from_config(cfg)

    qualification = select_qualification_snapshot(deal)
    qualification_gaps = _safe_list(qualification.gaps)
    health_band = classify_health(
        {
            "filled_count": qualification.filled_count,
            "health_pct": qualification.snapshot.get("health_pct"),
        },
        health_thresholds,
    )
    meddpicc_latest = deal.get("meddpicc_latest") or {}
    if qualification.is_meddpicc:
        meddpicc_filled_count = meddpicc_latest.get("filled_count")
        meddpicc_gaps = _safe_gap_list(meddpicc_latest)
        meddpicc_gap_count = len(meddpicc_gaps)
    else:
        meddpicc_filled_count = None
        meddpicc_gaps = []
        meddpicc_gap_count = None
    timing = assess_pipeline_timing(
        deal,
        as_of=reporting.as_of,
        settings=timing_settings,
    )
    stage = deal.get("deal_stage")
    attention_reasons = build_attention_reasons(
        stage=stage,
        health_band=health_band,
        timing=timing,
    )

    return {
        "snapshot_id": str(uuid.uuid4()),
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "source": SNAPSHOT_SOURCE,
        "event_id": event_id,
        "event_type": event_type,
        "occurred_at": occurred_utc.isoformat(),
        "created_at": datetime.now(UTC).isoformat(),
        "as_of": reporting.as_of.isoformat(),
        "timezone": reporting.timezone,
        "deal_id": deal.get("deal_id"),
        "company": deal.get("company"),
        "industry": deal.get("industry"),
        "industry_tags": _safe_string_list(deal.get("industry_tags")),
        "customer_segment": deal.get("customer_segment"),
        "deal_stage": stage,
        "deal_size_amount": deal.get("deal_size_amount"),
        "deal_size_low_amount": deal.get("deal_size_low_amount"),
        "deal_size_high_amount": deal.get("deal_size_high_amount"),
        "deal_size_currency": deal.get("deal_size_currency") or "KRW",
        "deal_size_status": deal.get("deal_size_status"),
        "expected_close_date": deal.get("expected_close_date"),
        "expected_close_date_source": deal.get("expected_close_date_source"),
        "actual_close_date": deal.get("actual_close_date"),
        "close_reason_present": bool(str(deal.get("close_reason") or "").strip()),
        "qualification_framework": qualification.framework_key,
        "qualification_framework_display_name": qualification.framework_display_name,
        "qualification_source_field": qualification.source_field,
        "qualification_health_pct": qualification.snapshot.get("health_pct"),
        "qualification_coverage_pct": qualification.coverage_pct,
        "qualification_quality_pct": qualification.quality_pct,
        "qualification_gap_count": len(qualification_gaps),
        "qualification_gaps": qualification_gaps,
        "health_pct": qualification.snapshot.get("health_pct"),
        "health_band": health_band.value,
        "meddpicc_filled_count": meddpicc_filled_count,
        "meddpicc_gap_count": meddpicc_gap_count,
        "meddpicc_gaps": meddpicc_gaps,
        "days_in_stage": timing.days_in_stage,
        "stuck_threshold_days": timing.stuck_threshold_days,
        "is_stuck": timing.is_stuck,
        "close_date_status": timing.close_date_status.value,
        "is_overdue": timing.is_overdue,
        "overdue_days": timing.overdue_days,
        "attention_reasons": attention_reasons,
    }


def snapshot_event_id(
    event_type: str,
    *,
    deal_id: str,
    event_key: str,
) -> str:
    return f"{event_type}:{deal_id}:{event_key}"


def _safe_gap_list(meddpicc_latest: dict) -> list[str]:
    gaps = meddpicc_latest.get("gaps")
    if not isinstance(gaps, list):
        return []
    return [str(gap) for gap in gaps]


def _safe_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _safe_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]
