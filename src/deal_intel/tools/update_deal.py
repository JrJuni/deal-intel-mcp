from __future__ import annotations

from datetime import UTC, datetime

from deal_intel.errors import ErrorCode, MCPError, Stage
from deal_intel.schema.metrics import DealValueStatus, assess_deal_value
from deal_intel.storage.mongodb import MongoDBClient


def handle(
    mongo: MongoDBClient,
    *,
    deal_id: str,
    deal_size_status: str,
    deal_size_note: str,
    confirmed_by_user: bool = False,
    deal_size_krw: int | None = None,
    deal_size_low_krw: int | None = None,
    deal_size_high_krw: int | None = None,
) -> dict:
    """Update an existing deal's value classification only.

    This first update_deal surface is deliberately narrow. It exists to repair
    and maintain BI value fields without letting assistants mutate arbitrary
    deal state.
    """
    if not confirmed_by_user:
        raise MCPError(
            error_code=ErrorCode.INVALID_INPUT,
            stage=Stage.PREFLIGHT,
            message="update_deal requires explicit user confirmation",
            hint={
                "ask_user": (
                    "이 기존 딜의 금액/status를 저장해도 되는지 확인해 주세요."
                )
            },
            retryable=False,
        )

    status = _parse_status(deal_size_status)
    note = _clean_required_note(deal_size_note)
    deal = mongo.get_deal(deal_id)
    if deal is None:
        raise MCPError(
            error_code=ErrorCode.NOT_FOUND,
            stage=Stage.STORAGE,
            message=f"deal_id {deal_id!r} not found",
            retryable=False,
        )

    old_value = _deal_value_snapshot(deal)
    new_value = _build_updated_value(
        old_value,
        status=status,
        note=note,
        deal_size_krw=deal_size_krw,
        deal_size_low_krw=deal_size_low_krw,
        deal_size_high_krw=deal_size_high_krw,
    )
    assessment = assess_deal_value(new_value)
    if not assessment.is_valid:
        raise MCPError(
            error_code=ErrorCode.INVALID_INPUT,
            stage=Stage.PREFLIGHT,
            message=f"invalid deal value: {assessment.issue}",
            hint={
                "valid_statuses": [item.value for item in DealValueStatus],
                "issue": assessment.issue,
            },
            retryable=False,
        )

    now = datetime.now(UTC).isoformat()
    deal.update(new_value)
    deal["updated_at"] = now
    deal.setdefault("deal_value_history", []).append(
        {
            "updated_at": now,
            "source": "update_deal",
            **new_value,
        }
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

    return {
        "ok": True,
        "deal_id": deal_id,
        "company": deal.get("company"),
        "old_deal_value": old_value,
        "new_deal_value": new_value,
        "changed_fields": _changed_fields(old_value, new_value),
    }


def _parse_status(value: str) -> DealValueStatus:
    cleaned = (value or "").strip()
    if not cleaned:
        raise MCPError(
            error_code=ErrorCode.INVALID_INPUT,
            stage=Stage.PREFLIGHT,
            message="deal_size_status is required",
            hint={"valid_statuses": [item.value for item in DealValueStatus]},
            retryable=False,
        )
    try:
        return DealValueStatus(cleaned)
    except ValueError as exc:
        raise MCPError(
            error_code=ErrorCode.INVALID_INPUT,
            stage=Stage.PREFLIGHT,
            message=f"deal_size_status {cleaned!r} is not valid",
            hint={"valid_statuses": [item.value for item in DealValueStatus]},
            retryable=False,
        ) from exc


def _clean_required_note(value: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        raise MCPError(
            error_code=ErrorCode.INVALID_INPUT,
            stage=Stage.PREFLIGHT,
            message="deal_size_note is required for update_deal",
            hint="Include the user-approved rationale or meeting evidence.",
            retryable=False,
        )
    return cleaned


def _deal_value_snapshot(deal: dict) -> dict:
    return {
        "deal_size_krw": deal.get("deal_size_krw"),
        "deal_size_low_krw": deal.get("deal_size_low_krw"),
        "deal_size_high_krw": deal.get("deal_size_high_krw"),
        "deal_size_status": deal.get("deal_size_status"),
        "deal_size_note": deal.get("deal_size_note"),
    }


def _build_updated_value(
    current: dict,
    *,
    status: DealValueStatus,
    note: str,
    deal_size_krw: int | None,
    deal_size_low_krw: int | None,
    deal_size_high_krw: int | None,
) -> dict:
    if status == DealValueStatus.UNKNOWN:
        return {
            "deal_size_krw": None,
            "deal_size_low_krw": None,
            "deal_size_high_krw": None,
            "deal_size_status": status.value,
            "deal_size_note": note,
        }
    if status == DealValueStatus.STRATEGIC_ZERO:
        return {
            "deal_size_krw": 0,
            "deal_size_low_krw": 0 if deal_size_low_krw == 0 else None,
            "deal_size_high_krw": 0 if deal_size_high_krw == 0 else None,
            "deal_size_status": status.value,
            "deal_size_note": note,
        }
    return {
        "deal_size_krw": (
            deal_size_krw
            if deal_size_krw is not None
            else current.get("deal_size_krw")
        ),
        "deal_size_low_krw": (
            deal_size_low_krw
            if deal_size_low_krw is not None
            else current.get("deal_size_low_krw")
        ),
        "deal_size_high_krw": (
            deal_size_high_krw
            if deal_size_high_krw is not None
            else current.get("deal_size_high_krw")
        ),
        "deal_size_status": status.value,
        "deal_size_note": note,
    }


def _changed_fields(old: dict, new: dict) -> list[str]:
    return [field for field in new if old.get(field) != new.get(field)]
