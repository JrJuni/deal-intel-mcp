from __future__ import annotations

import uuid
from datetime import UTC, datetime

from deal_intel.errors import ErrorCode, MCPError, Stage
from deal_intel.schema.metrics import (
    DealValueStatus,
    ExpectedCloseSettings,
    ReportingContext,
    assess_deal_value,
    resolve_expected_close_date,
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
    company: str,
    industry: str | None,
    deal_size_krw: int | None,
    deal_size_status: str | None = None,
    deal_size_low_krw: int | None = None,
    deal_size_high_krw: int | None = None,
    deal_size_note: str | None = None,
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
        reporting = ReportingContext.from_config(cfg, generated_at=now_dt)
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
            created_on=reporting.as_of,
            settings=expected_close_settings,
        )
    except ValueError as exc:
        raise MCPError(
            error_code=ErrorCode.INVALID_INPUT,
            stage=Stage.PREFLIGHT,
            message=str(exc),
            retryable=False,
        ) from exc
    deal_value = _build_deal_value(
        deal_size_krw=deal_size_krw,
        deal_size_status=deal_size_status,
        deal_size_low_krw=deal_size_low_krw,
        deal_size_high_krw=deal_size_high_krw,
        deal_size_note=deal_size_note,
    )
    deal = {
        "deal_id": str(uuid.uuid4()),
        "company": company.strip(),
        "industry": industry,
        **deal_value,
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

    analytics_snapshot = record_analytics_snapshot(
        mongo=mongo,
        cfg=cfg,
        event_type="create_deal",
        event_id=snapshot_event_id(
            "create_deal",
            deal_id=deal["deal_id"],
            event_key="created",
        ),
        deal=deal,
        occurred_at=now_dt,
    )

    result = {
        "ok": True,
        "deal_id": deal["deal_id"],
        "company": deal["company"],
        "deal_size_krw": deal["deal_size_krw"],
        "deal_size_status": deal["deal_size_status"],
        "deal_size_low_krw": deal["deal_size_low_krw"],
        "deal_size_high_krw": deal["deal_size_high_krw"],
        "deal_size_note": deal["deal_size_note"],
        "expected_close_date": resolved_close_date,
        "expected_close_date_source": close_date_source,
    }
    if analytics_snapshot is not None:
        result["analytics_snapshot"] = analytics_snapshot
    return result


def _build_deal_value(
    *,
    deal_size_krw: int | None,
    deal_size_status: str | None,
    deal_size_low_krw: int | None,
    deal_size_high_krw: int | None,
    deal_size_note: str | None,
) -> dict:
    cleaned_status = _clean_optional_text(deal_size_status)
    cleaned_note = _clean_optional_text(deal_size_note)
    if deal_size_krw == 0 and cleaned_status is None:
        _raise_zero_amount_confirmation()
    if deal_size_krw is not None and deal_size_krw > 0 and cleaned_status is None:
        _raise_positive_amount_status_confirmation()
    if cleaned_status == DealValueStatus.UNKNOWN.value and all(
        value in (None, 0)
        for value in (deal_size_krw, deal_size_low_krw, deal_size_high_krw)
    ):
        deal_size_krw = None
        deal_size_low_krw = None
        deal_size_high_krw = None

    value = {
        "deal_size_krw": deal_size_krw,
        "deal_size_low_krw": deal_size_low_krw,
        "deal_size_high_krw": deal_size_high_krw,
        "deal_size_status": cleaned_status,
        "deal_size_note": cleaned_note,
    }
    assessment = assess_deal_value(value)
    if not assessment.is_valid:
        raise MCPError(
            error_code=ErrorCode.INVALID_INPUT,
            stage=Stage.PREFLIGHT,
            message=f"invalid deal value: {assessment.issue}",
            hint={
                "valid_statuses": [status.value for status in DealValueStatus],
                "issue": assessment.issue,
            },
            retryable=False,
        )
    return value


def _raise_positive_amount_status_confirmation() -> None:
    raise MCPError(
        error_code=ErrorCode.INVALID_INPUT,
        stage=Stage.PREFLIGHT,
        message="deal_size_status is required when deal_size_krw is provided",
        hint={
            "ask_user": (
                "이 금액은 영업 추정, 고객 예산 확인, 견적 발송 중 "
                "어떤 기준으로 저장할까요?"
            ),
            "retry_options": [
                {
                    "meaning": "seller_estimate",
                    "deal_size_status": DealValueStatus.ROUGH_ESTIMATE.value,
                },
                {
                    "meaning": "customer_disclosed_budget",
                    "deal_size_status": DealValueStatus.CUSTOMER_BUDGET.value,
                },
                {
                    "meaning": "formal_quote_sent",
                    "deal_size_status": DealValueStatus.QUOTED.value,
                },
            ],
        },
        retryable=False,
    )


def _raise_zero_amount_confirmation() -> None:
    raise MCPError(
        error_code=ErrorCode.INVALID_INPUT,
        stage=Stage.PREFLIGHT,
        message="deal_size_krw=0 needs user confirmation before saving",
        hint={
            "ask_user": (
                "이 0원은 전략적 무료/레퍼런스 딜인가요, "
                "아니면 아직 금액 미정인가요?"
            ),
            "retry_options": [
                {
                    "meaning": "amount_unknown",
                    "deal_size_status": DealValueStatus.UNKNOWN.value,
                    "deal_size_krw": None,
                },
                {
                    "meaning": "strategic_zero_revenue",
                    "deal_size_status": DealValueStatus.STRATEGIC_ZERO.value,
                    "deal_size_krw": 0,
                },
            ],
        },
        retryable=False,
    )


def _clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None
