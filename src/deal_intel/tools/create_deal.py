from __future__ import annotations

import uuid
from datetime import UTC, datetime

from deal_intel.errors import ErrorCode, MCPError, Stage
from deal_intel.schema.metrics import (
    ExpectedCloseSettings,
    resolve_expected_close_date,
)
from deal_intel.storage.mongodb import MongoDBClient


def handle(
    mongo: MongoDBClient,
    cfg: dict,
    *,
    company: str,
    industry: str | None,
    deal_size_krw: int | None,
    expected_close_date: str | None = None,
) -> dict:
    if not company or not company.strip():
        raise MCPError(
            error_code=ErrorCode.INVALID_INPUT,
            stage=Stage.PREFLIGHT,
            message="company must not be empty",
            retryable=False,
        )
    now_dt = datetime.now(UTC)
    now = now_dt.isoformat()
    try:
        expected_close_settings = ExpectedCloseSettings.from_config(cfg)
    except ValueError as exc:
        raise MCPError(
            error_code=ErrorCode.CONFIG_ERROR,
            stage=Stage.PREFLIGHT,
            message=str(exc),
            retryable=False,
        ) from exc
    try:
        resolved_close_date, close_date_source = resolve_expected_close_date(
            provided=expected_close_date,
            industry=industry,
            created_on=now_dt.date(),
            settings=expected_close_settings,
        )
    except ValueError as exc:
        raise MCPError(
            error_code=ErrorCode.INVALID_INPUT,
            stage=Stage.PREFLIGHT,
            message=str(exc),
            retryable=False,
        ) from exc
    deal = {
        "deal_id": str(uuid.uuid4()),
        "company": company.strip(),
        "industry": industry,
        "deal_size_krw": deal_size_krw,
        "contacts": [],
        "meetings": [],
        "meddpicc_latest": {},
        "stage_history": [{"stage": "discovery", "entered_at": now}],
        "deal_stage": "discovery",
        "expected_close_date": resolved_close_date,
        "expected_close_date_source": close_date_source,
        "actual_close_date": None,
        "close_reason": None,
        "bd_strategy": "",
        "gtm_notes": "",
        "prospect_id": None,
        "created_at": now,
        "updated_at": now,
    }
    try:
        mongo.upsert_deal(deal)
    except Exception as exc:
        raise MCPError(
            error_code=ErrorCode.STORAGE_ERROR,
            stage=Stage.STORAGE,
            message=str(exc),
            hint="Check MONGODB_URI and Atlas cluster status",
            retryable=True,
        ) from exc
    return {
        "ok": True,
        "deal_id": deal["deal_id"],
        "company": deal["company"],
        "expected_close_date": resolved_close_date,
        "expected_close_date_source": close_date_source,
    }
