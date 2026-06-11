from __future__ import annotations

import asyncio
import json
from copy import deepcopy

import pytest

from deal_intel import _context, mcp_server
from deal_intel.errors import ErrorCode, MCPError
from deal_intel.tools import archive_deal, delete_deal, restore_deal


class FakeMongo:
    def __init__(self, deal: dict | None) -> None:
        self.deal = deepcopy(deal)
        self.saved: dict | None = None
        self.audit_logs: list[dict] = []
        self.deleted_ids: list[str] = []

    def get_deal(self, deal_id: str) -> dict | None:
        if self.deal is None or self.deal.get("deal_id") != deal_id:
            return None
        return deepcopy(self.deal)

    def upsert_deal(self, deal: dict) -> None:
        self.saved = deepcopy(deal)
        self.deal = deepcopy(deal)

    def insert_delete_audit_log(self, entry: dict) -> None:
        self.audit_logs.append(deepcopy(entry))

    def hard_delete_deal(self, deal_id: str) -> int:
        self.deleted_ids.append(deal_id)
        if self.deal is not None and self.deal.get("deal_id") == deal_id:
            self.deal = None
            return 1
        return 0


def _deal(**overrides) -> dict:
    deal = {
        "deal_id": "deal-1",
        "company": "Test Co",
        "industry": "IT",
        "deal_stage": "discovery",
        "deal_size_krw": 10_000_000,
        "meetings": [
            {
                "meeting_id": "meeting-1",
                "date": "2026-06-01",
                "raw_notes": "secret raw notes",
                "summary": "safe summary",
            }
        ],
        "interactions": [
            {
                "interaction_id": "interaction-1",
                "date": "2026-06-02",
                "raw_content": "secret raw interaction",
                "summary": "safe interaction summary",
            }
        ],
        "contacts": [{"name": "private contact"}],
        "summary_embedding": [0.1, 0.2],
        "updated_at": "2026-06-01T00:00:00+00:00",
    }
    deal.update(overrides)
    return deal


def test_archive_deal_requires_confirmation_and_company_match() -> None:
    mongo = FakeMongo(_deal())

    with pytest.raises(MCPError) as missing_confirmation:
        archive_deal.handle(
            mongo=mongo,
            deal_id="deal-1",
            expected_company="Test Co",
            archive_reason="duplicate",
        )
    with pytest.raises(MCPError) as company_mismatch:
        archive_deal.handle(
            mongo=mongo,
            deal_id="deal-1",
            expected_company="Other Co",
            archive_reason="duplicate",
            confirmed_by_user=True,
        )

    assert missing_confirmation.value.error_code == ErrorCode.INVALID_INPUT
    assert company_mismatch.value.error_code == ErrorCode.INVALID_INPUT
    assert mongo.saved is None


def test_archive_deal_writes_archive_metadata_and_history() -> None:
    mongo = FakeMongo(_deal())

    result = archive_deal.handle(
        mongo=mongo,
        deal_id="deal-1",
        expected_company=" Test Co ",
        archive_reason="created by mistake",
        confirmed_by_user=True,
    )

    assert result["ok"] is True
    assert result["storage_written"] is True
    assert result["new_deal"]["archived"] is True
    assert mongo.saved is not None
    assert mongo.saved["archived"] is True
    assert mongo.saved["archived_reason"] == "created by mistake"
    assert mongo.saved["archive_history"][-1]["action"] == "archive"


def test_archive_and_restore_are_idempotent() -> None:
    archived = _deal(
        archived=True,
        archived_at="2026-06-09T00:00:00+00:00",
        archived_reason="old reason",
    )
    archive_mongo = FakeMongo(archived)

    archive_result = archive_deal.handle(
        mongo=archive_mongo,
        deal_id="deal-1",
        expected_company="Test Co",
        archive_reason="duplicate",
        confirmed_by_user=True,
    )

    active_mongo = FakeMongo(_deal(archived=False))
    restore_result = restore_deal.handle(
        mongo=active_mongo,
        deal_id="deal-1",
        expected_company="Test Co",
        restore_reason="undo archive",
        confirmed_by_user=True,
    )

    assert archive_result["already_archived"] is True
    assert archive_result["storage_written"] is False
    assert archive_mongo.saved is None
    assert restore_result["already_active"] is True
    assert restore_result["storage_written"] is False
    assert active_mongo.saved is None


def test_restore_deal_reactivates_archived_deal() -> None:
    mongo = FakeMongo(
        _deal(
            archived=True,
            archived_at="2026-06-09T00:00:00+00:00",
            archived_reason="duplicate",
        )
    )

    result = restore_deal.handle(
        mongo=mongo,
        deal_id="deal-1",
        expected_company="Test Co",
        restore_reason="user wants it back",
        confirmed_by_user=True,
    )

    assert result["ok"] is True
    assert result["storage_written"] is True
    assert result["new_deal"]["archived"] is False
    assert mongo.saved is not None
    assert mongo.saved["archived"] is False
    assert mongo.saved["archived_at"] is None
    assert mongo.saved["archive_history"][-1]["action"] == "restore"


def test_delete_deal_dry_run_requires_archive_first_without_writing() -> None:
    mongo = FakeMongo(_deal())

    result = delete_deal.handle(
        mongo=mongo,
        deal_id="deal-1",
        expected_company="Test Co",
        delete_reason="cleanup duplicate",
    )

    assert result["ok"] is True
    assert result["dry_run"] is True
    assert result["can_delete"] is False
    assert result["blocked_reason"] == "deal_not_archived"
    assert mongo.audit_logs == []
    assert mongo.deleted_ids == []


def test_delete_deal_hard_delete_requires_confirmation_and_archived_state() -> None:
    active_mongo = FakeMongo(_deal())
    archived_mongo = FakeMongo(_deal(archived=True))

    with pytest.raises(MCPError) as not_archived:
        delete_deal.handle(
            mongo=active_mongo,
            deal_id="deal-1",
            expected_company="Test Co",
            delete_reason="cleanup duplicate",
            confirmed_by_user=True,
            dry_run=False,
        )
    with pytest.raises(MCPError) as missing_confirmation:
        delete_deal.handle(
            mongo=archived_mongo,
            deal_id="deal-1",
            expected_company="Test Co",
            delete_reason="cleanup duplicate",
            dry_run=False,
        )

    assert not_archived.value.error_code == ErrorCode.INVALID_INPUT
    assert missing_confirmation.value.error_code == ErrorCode.INVALID_INPUT
    assert active_mongo.deleted_ids == []
    assert archived_mongo.deleted_ids == []


def test_delete_deal_writes_safe_audit_snapshot_before_delete() -> None:
    mongo = FakeMongo(_deal(archived=True))

    result = delete_deal.handle(
        mongo=mongo,
        deal_id="deal-1",
        expected_company="Test Co",
        delete_reason="cleanup duplicate",
        confirmed_by_user=True,
        dry_run=False,
    )

    assert result["ok"] is True
    assert result["deleted_count"] == 1
    assert mongo.deleted_ids == ["deal-1"]
    assert len(mongo.audit_logs) == 1
    snapshot = mongo.audit_logs[0]["deal_snapshot"]
    serialized_snapshot = json.dumps(snapshot, ensure_ascii=False)
    assert "secret raw notes" not in serialized_snapshot
    assert "secret raw interaction" not in serialized_snapshot
    assert "private contact" not in serialized_snapshot
    assert "summary_embedding" not in serialized_snapshot
    assert mongo.audit_logs[0]["deal_snapshot"]["meetings"][0]["summary"] == "safe summary"
    assert (
        mongo.audit_logs[0]["deal_snapshot"]["interactions"][0]["summary"]
        == "safe interaction summary"
    )


def test_get_deal_warns_when_archived(monkeypatch) -> None:
    mongo = FakeMongo(_deal(archived=True, archived_reason="duplicate"))
    monkeypatch.setattr(_context, "mongo", lambda: mongo)

    result = mcp_server.get_deal("deal-1")

    assert result["ok"] is True
    assert result["warnings"] == ["deal_archived"]
    assert result["archive"]["archived_reason"] == "duplicate"


def test_mcp_lifecycle_wrappers_and_registration(monkeypatch) -> None:
    mongo = FakeMongo(_deal())
    monkeypatch.setattr(_context, "mongo", lambda: mongo)

    result = mcp_server.archive_deal(
        "deal-1",
        "Test Co",
        "duplicate",
        confirmed_by_user=True,
    )
    tools = asyncio.run(mcp_server.app.list_tools())
    names = sorted(tool.name for tool in tools)

    assert result["ok"] is True
    assert {"archive_deal", "restore_deal", "delete_deal"}.issubset(names)
