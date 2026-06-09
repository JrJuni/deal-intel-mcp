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
    archive_reason: str,
    confirmed_by_user: bool = False,
) -> dict:
    require_confirmation(
        confirmed_by_user=confirmed_by_user,
        action="archive_deal",
    )
    reason = clean_required_text(archive_reason, "archive_reason")
    deal = get_deal_or_raise(mongo, deal_id)
    validate_expected_company(deal, expected_company)

    old_summary = lifecycle_summary(deal)
    if deal.get("archived") is True:
        return {
            "ok": True,
            "deal_id": deal_id,
            "company": deal.get("company"),
            "already_archived": True,
            "old_deal": old_summary,
            "new_deal": old_summary,
            "storage_written": False,
        }

    now = datetime.now(UTC).isoformat()
    event = {
        "action": "archive",
        "at": now,
        "reason": reason,
        "source": "archive_deal",
    }
    deal["archived"] = True
    deal["archived_at"] = now
    deal["archived_reason"] = reason
    deal["archived_by"] = "user_confirmed"
    deal["updated_at"] = now
    deal.setdefault("archive_history", []).append(event)

    write_deal_or_raise(mongo, deal)

    return {
        "ok": True,
        "deal_id": deal_id,
        "company": deal.get("company"),
        "already_archived": False,
        "old_deal": old_summary,
        "new_deal": lifecycle_summary(deal),
        "storage_written": True,
    }
