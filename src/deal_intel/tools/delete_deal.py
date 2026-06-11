from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from deal_intel.errors import ErrorCode, MCPError, Stage
from deal_intel.storage.mongodb import MongoDBClient
from deal_intel.tools.deal_lifecycle import (
    clean_required_text,
    get_deal_or_raise,
    lifecycle_summary,
    require_confirmation,
    safe_deal_snapshot,
    validate_expected_company,
)


def handle(
    mongo: MongoDBClient,
    *,
    deal_id: str,
    expected_company: str,
    delete_reason: str,
    confirmed_by_user: bool = False,
    dry_run: bool = True,
) -> dict:
    reason = clean_required_text(delete_reason, "delete_reason")
    deal = get_deal_or_raise(mongo, deal_id)
    validate_expected_company(deal, expected_company)

    archived = deal.get("archived") is True
    summary = lifecycle_summary(deal)
    if dry_run:
        return {
            "ok": True,
            "deal_id": deal_id,
            "company": deal.get("company"),
            "dry_run": True,
            "can_delete": archived,
            "would_delete": archived,
            "blocked_reason": None if archived else "deal_not_archived",
            "required_action": None if archived else "archive_deal first",
            "delete_reason": reason,
            "deal": summary,
            "storage_written": False,
        }

    require_confirmation(
        confirmed_by_user=confirmed_by_user,
        action="delete_deal",
    )
    if not archived:
        raise MCPError(
            error_code=ErrorCode.INVALID_INPUT,
            stage=Stage.PREFLIGHT,
            message="delete_deal requires the deal to be archived first",
            hint={"required_action": "archive_deal first"},
            retryable=False,
        )

    now = datetime.now(UTC).isoformat()
    audit_entry = {
        "audit_id": str(uuid4()),
        "deal_id": deal_id,
        "company": deal.get("company"),
        "deleted_at": now,
        "deleted_by": "user_confirmed",
        "delete_reason": reason,
        "snapshot_excluded_fields": [
            "_id",
            "contacts",
            "summary_embedding",
            "meetings.raw_notes",
            "interactions.raw_content",
        ],
        "deal_snapshot": safe_deal_snapshot(deal),
    }
    try:
        mongo.insert_delete_audit_log(audit_entry)
        deleted_count = mongo.hard_delete_deal(deal_id)
    except Exception as exc:
        raise MCPError(
            error_code=ErrorCode.STORAGE_ERROR,
            stage=Stage.STORAGE,
            message=str(exc),
            retryable=True,
        ) from exc

    if deleted_count != 1:
        raise MCPError(
            error_code=ErrorCode.STORAGE_ERROR,
            stage=Stage.STORAGE,
            message=f"expected to delete 1 deal, deleted {deleted_count}",
            retryable=True,
        )

    return {
        "ok": True,
        "deal_id": deal_id,
        "company": deal.get("company"),
        "dry_run": False,
        "deleted_count": deleted_count,
        "audit_id": audit_entry["audit_id"],
        "deleted_at": now,
        "storage_written": True,
    }
