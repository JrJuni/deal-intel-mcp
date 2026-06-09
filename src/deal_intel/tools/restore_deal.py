from __future__ import annotations

from datetime import UTC, datetime

from deal_intel.storage.mongodb import MongoDBClient
from deal_intel.tools.deal_lifecycle import (
    clean_required_text,
    get_deal_or_raise,
    lifecycle_summary,
    require_confirmation,
    validate_expected_company,
    write_deal_or_raise,
)


def handle(
    mongo: MongoDBClient,
    *,
    deal_id: str,
    expected_company: str,
    restore_reason: str,
    confirmed_by_user: bool = False,
) -> dict:
    require_confirmation(
        confirmed_by_user=confirmed_by_user,
        action="restore_deal",
    )
    reason = clean_required_text(restore_reason, "restore_reason")
    deal = get_deal_or_raise(mongo, deal_id)
    validate_expected_company(deal, expected_company)

    old_summary = lifecycle_summary(deal)
    if deal.get("archived") is not True:
        return {
            "ok": True,
            "deal_id": deal_id,
            "company": deal.get("company"),
            "already_active": True,
            "old_deal": old_summary,
            "new_deal": old_summary,
            "storage_written": False,
        }

    now = datetime.now(UTC).isoformat()
    event = {
        "action": "restore",
        "at": now,
        "reason": reason,
        "source": "restore_deal",
        "previous_archived_at": deal.get("archived_at"),
        "previous_archived_reason": deal.get("archived_reason"),
    }
    deal["archived"] = False
    deal["archived_at"] = None
    deal["archived_reason"] = None
    deal["archived_by"] = None
    deal["restored_at"] = now
    deal["restored_reason"] = reason
    deal["updated_at"] = now
    deal.setdefault("archive_history", []).append(event)

    write_deal_or_raise(mongo, deal)

    return {
        "ok": True,
        "deal_id": deal_id,
        "company": deal.get("company"),
        "already_active": False,
        "old_deal": old_summary,
        "new_deal": lifecycle_summary(deal),
        "storage_written": True,
    }
