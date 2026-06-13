from __future__ import annotations

from datetime import UTC, date, datetime

from deal_intel.errors import ErrorCode, MCPError, Stage
from deal_intel.schema.metrics import (
    DEFAULT_DEAL_CURRENCY,
    OPEN_STAGES,
    TERMINAL_STAGES,
    DealValueStatus,
    assess_deal_value,
)
from deal_intel.storage.mongodb import MongoDBClient


def handle(
    mongo: MongoDBClient,
    *,
    deal_id: str,
    deal_size_status: str | None = None,
    deal_size_note: str | None = None,
    confirmed_by_user: bool = False,
    deal_size_amount: int | None = None,
    deal_size_low_amount: int | None = None,
    deal_size_high_amount: int | None = None,
    deal_size_currency: str | None = None,
    company: str | None = None,
    industry: str | None = None,
    customer_segment: str | None = None,
    expected_close_date: str | None = None,
    actual_close_date: str | None = None,
    close_reason: str | None = None,
    update_note: str | None = None,
) -> dict:
    """Update confirmed deal value and selected deal metadata.

    This surface stays intentionally narrow. It repairs BI value fields and
    customer-attack metadata gaps without letting assistants mutate arbitrary
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

    value_update_requested = _value_update_requested(
        deal_size_status=deal_size_status,
        deal_size_amount=deal_size_amount,
        deal_size_low_amount=deal_size_low_amount,
        deal_size_high_amount=deal_size_high_amount,
        deal_size_currency=deal_size_currency,
    )
    metadata_update_requested = _metadata_update_requested(
        company=company,
        industry=industry,
        customer_segment=customer_segment,
        expected_close_date=expected_close_date,
        actual_close_date=actual_close_date,
        close_reason=close_reason,
    )
    if not value_update_requested and not metadata_update_requested:
        raise MCPError(
            error_code=ErrorCode.INVALID_INPUT,
            stage=Stage.PREFLIGHT,
            message="update_deal requires at least one value or metadata field to update",
            hint={
                "value_fields": [
                    "deal_size_status",
                    "deal_size_amount",
                    "deal_size_low_amount",
                    "deal_size_high_amount",
                    "deal_size_currency",
                ],
                "metadata_fields": [
                    "company",
                    "industry",
                    "customer_segment",
                    "expected_close_date",
                    "actual_close_date",
                    "close_reason",
                ],
            },
            retryable=False,
        )

    status = _parse_status(deal_size_status) if value_update_requested else None
    value_note = _clean_required_note(deal_size_note) if value_update_requested else None
    metadata_note = (
        _clean_metadata_note(update_note, fallback=deal_size_note)
        if metadata_update_requested
        else None
    )
    deal = mongo.get_deal(deal_id)
    if deal is None:
        raise MCPError(
            error_code=ErrorCode.NOT_FOUND,
            stage=Stage.STORAGE,
            message=f"deal_id {deal_id!r} not found",
            retryable=False,
        )

    old_value = _deal_value_snapshot(deal)
    old_metadata = _deal_metadata_snapshot(deal)
    new_value = old_value
    new_metadata = old_metadata
    if status is not None and value_note is not None:
        new_value = _build_updated_value(
            old_value,
            status=status,
            note=value_note,
            deal_size_amount=deal_size_amount,
            deal_size_low_amount=deal_size_low_amount,
            deal_size_high_amount=deal_size_high_amount,
            deal_size_currency=deal_size_currency,
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
    if metadata_update_requested:
        new_metadata = _build_updated_metadata(
            deal,
            current=old_metadata,
            company=company,
            industry=industry,
            customer_segment=customer_segment,
            expected_close_date=expected_close_date,
            actual_close_date=actual_close_date,
            close_reason=close_reason,
        )

    changed_value_fields = _changed_fields(old_value, new_value)
    changed_metadata_fields = _changed_fields(old_metadata, new_metadata)
    changed_fields = changed_value_fields + changed_metadata_fields
    if not changed_fields:
        return {
            "ok": True,
            "deal_id": deal_id,
            "company": deal.get("company"),
            "old_deal_value": old_value,
            "new_deal_value": new_value,
            "old_deal_metadata": old_metadata,
            "new_deal_metadata": new_metadata,
            "changed_fields": [],
            "changed_value_fields": [],
            "changed_metadata_fields": [],
            "storage_written": False,
        }

    now = datetime.now(UTC).isoformat()
    deal.update(new_value)
    deal.update(new_metadata)
    deal["updated_at"] = now
    if changed_value_fields:
        deal.setdefault("deal_value_history", []).append(
            {
                "updated_at": now,
                "source": "update_deal",
                **new_value,
            }
        )
    if changed_metadata_fields and metadata_note is not None:
        deal.setdefault("deal_metadata_history", []).append(
            {
                "updated_at": now,
                "source": "update_deal",
                "update_note": metadata_note,
                "changed_fields": changed_metadata_fields,
                "old_values": _selected_fields(old_metadata, changed_metadata_fields),
                "new_values": _selected_fields(new_metadata, changed_metadata_fields),
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
        "old_deal_metadata": old_metadata,
        "new_deal_metadata": new_metadata,
        "changed_fields": changed_fields,
        "changed_value_fields": changed_value_fields,
        "changed_metadata_fields": changed_metadata_fields,
        "storage_written": True,
    }


def _value_update_requested(
    *,
    deal_size_status: str | None,
    deal_size_amount: int | None,
    deal_size_low_amount: int | None,
    deal_size_high_amount: int | None,
    deal_size_currency: str | None,
) -> bool:
    return (
        bool((deal_size_status or "").strip())
        or bool((deal_size_currency or "").strip())
        or deal_size_amount is not None
        or deal_size_low_amount is not None
        or deal_size_high_amount is not None
    )


def _metadata_update_requested(
    *,
    company: str | None,
    industry: str | None,
    customer_segment: str | None,
    expected_close_date: str | None,
    actual_close_date: str | None,
    close_reason: str | None,
) -> bool:
    return any(
        bool((value or "").strip())
        for value in (
            company,
            industry,
            customer_segment,
            expected_close_date,
            actual_close_date,
            close_reason,
        )
    )


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


def _clean_required_note(value: str | None) -> str:
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


def _clean_metadata_note(value: str | None, *, fallback: str | None = None) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        cleaned = (fallback or "").strip()
    if not cleaned:
        raise MCPError(
            error_code=ErrorCode.INVALID_INPUT,
            stage=Stage.PREFLIGHT,
            message="update_note is required for metadata updates",
            hint="Include the user-approved reason or evidence for the metadata change.",
            retryable=False,
        )
    return cleaned


def _deal_value_snapshot(deal: dict) -> dict:
    return {
        "deal_size_amount": deal.get("deal_size_amount"),
        "deal_size_low_amount": deal.get("deal_size_low_amount"),
        "deal_size_high_amount": deal.get("deal_size_high_amount"),
        "deal_size_currency": deal.get("deal_size_currency") or DEFAULT_DEAL_CURRENCY,
        "deal_size_status": deal.get("deal_size_status"),
        "deal_size_note": deal.get("deal_size_note"),
    }


def _deal_metadata_snapshot(deal: dict) -> dict:
    return {
        "company": deal.get("company"),
        "industry": deal.get("industry"),
        "customer_segment": deal.get("customer_segment"),
        "expected_close_date": deal.get("expected_close_date"),
        "expected_close_date_source": deal.get("expected_close_date_source"),
        "actual_close_date": deal.get("actual_close_date"),
        "close_reason": deal.get("close_reason"),
    }


def _build_updated_value(
    current: dict,
    *,
    status: DealValueStatus,
    note: str,
    deal_size_amount: int | None,
    deal_size_low_amount: int | None,
    deal_size_high_amount: int | None,
    deal_size_currency: str | None,
) -> dict:
    if status == DealValueStatus.UNKNOWN:
        return {
            "deal_size_amount": None,
            "deal_size_low_amount": None,
            "deal_size_high_amount": None,
            "deal_size_currency": (
                (deal_size_currency or "").strip().upper()
                or current.get("deal_size_currency")
                or DEFAULT_DEAL_CURRENCY
            ),
            "deal_size_status": status.value,
            "deal_size_note": note,
        }
    if status == DealValueStatus.STRATEGIC_ZERO:
        return {
            "deal_size_amount": 0,
            "deal_size_low_amount": 0 if deal_size_low_amount == 0 else None,
            "deal_size_high_amount": 0 if deal_size_high_amount == 0 else None,
            "deal_size_currency": (
                (deal_size_currency or "").strip().upper()
                or current.get("deal_size_currency")
                or DEFAULT_DEAL_CURRENCY
            ),
            "deal_size_status": status.value,
            "deal_size_note": note,
        }
    return {
        "deal_size_amount": (
            deal_size_amount
            if deal_size_amount is not None
            else current.get("deal_size_amount")
        ),
        "deal_size_low_amount": (
            deal_size_low_amount
            if deal_size_low_amount is not None
            else current.get("deal_size_low_amount")
        ),
        "deal_size_high_amount": (
            deal_size_high_amount
            if deal_size_high_amount is not None
            else current.get("deal_size_high_amount")
        ),
        "deal_size_currency": (
            (deal_size_currency or "").strip().upper()
            or current.get("deal_size_currency")
            or DEFAULT_DEAL_CURRENCY
        ),
        "deal_size_status": status.value,
        "deal_size_note": note,
    }


def _build_updated_metadata(
    deal: dict,
    *,
    current: dict,
    company: str | None,
    industry: str | None,
    customer_segment: str | None,
    expected_close_date: str | None,
    actual_close_date: str | None,
    close_reason: str | None,
) -> dict:
    stage = deal.get("deal_stage")
    updated = dict(current)
    if _has_text(company):
        updated["company"] = _clean_text(company, "company")
    if _has_text(industry):
        updated["industry"] = _clean_text(industry, "industry")
    if _has_text(customer_segment):
        updated["customer_segment"] = _clean_text(
            customer_segment,
            "customer_segment",
        )
    if _has_text(expected_close_date):
        if stage not in OPEN_STAGES:
            raise MCPError(
                error_code=ErrorCode.INVALID_INPUT,
                stage=Stage.PREFLIGHT,
                message="expected_close_date can only be updated for open deals",
                hint={"open_stages": sorted(OPEN_STAGES), "current_stage": stage},
                retryable=False,
            )
        updated["expected_close_date"] = _parse_iso_date(
            expected_close_date,
            "expected_close_date",
        )
        updated["expected_close_date_source"] = "user_provided"
    if _has_text(actual_close_date):
        if stage not in TERMINAL_STAGES:
            raise MCPError(
                error_code=ErrorCode.INVALID_INPUT,
                stage=Stage.PREFLIGHT,
                message="actual_close_date can only be updated for won or lost deals",
                hint={
                    "fix": "Use update_stage to move the deal to won/lost first.",
                    "current_stage": stage,
                },
                retryable=False,
            )
        updated["actual_close_date"] = _parse_iso_date(
            actual_close_date,
            "actual_close_date",
        )
    if _has_text(close_reason):
        if stage != "lost":
            raise MCPError(
                error_code=ErrorCode.INVALID_INPUT,
                stage=Stage.PREFLIGHT,
                message="close_reason can only be updated for lost deals",
                hint={"current_stage": stage},
                retryable=False,
            )
        updated["close_reason"] = _clean_text(close_reason, "close_reason")
    return updated


def _has_text(value: str | None) -> bool:
    return bool((value or "").strip())


def _clean_text(value: str | None, field_name: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        raise MCPError(
            error_code=ErrorCode.INVALID_INPUT,
            stage=Stage.PREFLIGHT,
            message=f"{field_name} must be a non-empty string",
            retryable=False,
        )
    return cleaned


def _parse_iso_date(value: str | None, field_name: str) -> str:
    try:
        return date.fromisoformat((value or "").strip()).isoformat()
    except ValueError as exc:
        raise MCPError(
            error_code=ErrorCode.INVALID_INPUT,
            stage=Stage.PREFLIGHT,
            message=f"{field_name} must use ISO format YYYY-MM-DD",
            retryable=False,
        ) from exc


def _changed_fields(old: dict, new: dict) -> list[str]:
    return [field for field in new if old.get(field) != new.get(field)]


def _selected_fields(values: dict, fields: list[str]) -> dict:
    return {field: values.get(field) for field in fields}
