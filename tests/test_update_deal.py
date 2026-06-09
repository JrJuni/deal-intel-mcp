from __future__ import annotations

from copy import deepcopy

import pytest

from deal_intel import _context, mcp_server
from deal_intel.errors import ErrorCode, MCPError, Stage
from deal_intel.tools import update_deal


class FakeMongo:
    def __init__(self, deal: dict | None) -> None:
        self.deal = deepcopy(deal)
        self.saved: dict | None = None

    def get_deal(self, deal_id: str) -> dict | None:
        if self.deal is None or self.deal.get("deal_id") != deal_id:
            return None
        return deepcopy(self.deal)

    def upsert_deal(self, deal: dict) -> None:
        self.saved = deepcopy(deal)


def _deal(**overrides) -> dict:
    deal = {
        "deal_id": "deal-1",
        "company": "Test Co",
        "deal_size_krw": 18_000_000,
        "deal_size_low_krw": None,
        "deal_size_high_krw": None,
        "deal_size_status": None,
        "deal_size_note": None,
        "updated_at": "2026-06-01T00:00:00+00:00",
    }
    deal.update(overrides)
    return deal


def test_update_deal_requires_explicit_user_confirmation() -> None:
    mongo = FakeMongo(_deal())

    with pytest.raises(MCPError) as exc_info:
        update_deal.handle(
            mongo=mongo,
            deal_id="deal-1",
            deal_size_status="quoted",
            deal_size_note="contract value confirmed",
        )

    assert exc_info.value.error_code == ErrorCode.INVALID_INPUT
    assert exc_info.value.stage == Stage.PREFLIGHT
    assert "confirmation" in exc_info.value.message
    assert mongo.saved is None


def test_update_deal_requires_non_empty_note() -> None:
    mongo = FakeMongo(_deal())

    with pytest.raises(MCPError) as exc_info:
        update_deal.handle(
            mongo=mongo,
            deal_id="deal-1",
            deal_size_status="quoted",
            deal_size_note=" ",
            confirmed_by_user=True,
        )

    assert exc_info.value.error_code == ErrorCode.INVALID_INPUT
    assert "deal_size_note" in exc_info.value.message
    assert mongo.saved is None


def test_update_deal_sets_status_and_preserves_existing_amount() -> None:
    mongo = FakeMongo(_deal())

    result = update_deal.handle(
        mongo=mongo,
        deal_id="deal-1",
        deal_size_status="quoted",
        deal_size_note="signed order form confirmed by user",
        confirmed_by_user=True,
    )

    assert result["ok"] is True
    assert result["old_deal_value"]["deal_size_status"] is None
    assert result["new_deal_value"] == {
        "deal_size_krw": 18_000_000,
        "deal_size_low_krw": None,
        "deal_size_high_krw": None,
        "deal_size_status": "quoted",
        "deal_size_note": "signed order form confirmed by user",
    }
    assert result["changed_fields"] == ["deal_size_status", "deal_size_note"]
    assert mongo.saved is not None
    assert mongo.saved["deal_size_status"] == "quoted"
    assert mongo.saved["deal_value_history"][-1]["source"] == "update_deal"


def test_update_deal_updates_amount_range_and_history() -> None:
    mongo = FakeMongo(_deal(deal_size_status="rough_estimate"))

    result = update_deal.handle(
        mongo=mongo,
        deal_id="deal-1",
        deal_size_status="customer_budget",
        deal_size_krw=20_000_000,
        deal_size_low_krw=15_000_000,
        deal_size_high_krw=25_000_000,
        deal_size_note="customer disclosed budget range",
        confirmed_by_user=True,
    )

    assert result["new_deal_value"]["deal_size_krw"] == 20_000_000
    assert result["new_deal_value"]["deal_size_status"] == "customer_budget"
    assert mongo.saved is not None
    assert mongo.saved["deal_size_low_krw"] == 15_000_000
    assert mongo.saved["deal_value_history"][-1]["deal_size_high_krw"] == 25_000_000


def test_update_deal_unknown_clears_amount_fields() -> None:
    mongo = FakeMongo(_deal())

    result = update_deal.handle(
        mongo=mongo,
        deal_id="deal-1",
        deal_size_status="unknown",
        deal_size_note="user confirmed amount is still unknown",
        confirmed_by_user=True,
    )

    assert result["new_deal_value"]["deal_size_krw"] is None
    assert result["new_deal_value"]["deal_size_status"] == "unknown"
    assert mongo.saved is not None
    assert mongo.saved["deal_size_krw"] is None


def test_update_deal_rejects_invalid_value_combination_before_storage() -> None:
    mongo = FakeMongo(_deal())

    with pytest.raises(MCPError) as exc_info:
        update_deal.handle(
            mongo=mongo,
            deal_id="deal-1",
            deal_size_status="quoted",
            deal_size_krw=0,
            deal_size_note="bad value",
            confirmed_by_user=True,
        )

    assert exc_info.value.error_code == ErrorCode.INVALID_INPUT
    assert exc_info.value.hint["issue"] == "non_positive_amount_requires_strategic_zero"
    assert mongo.saved is None


def test_update_deal_returns_not_found_without_upsert() -> None:
    mongo = FakeMongo(None)

    with pytest.raises(MCPError) as exc_info:
        update_deal.handle(
            mongo=mongo,
            deal_id="missing",
            deal_size_status="quoted",
            deal_size_note="confirmed",
            confirmed_by_user=True,
        )

    assert exc_info.value.error_code == ErrorCode.NOT_FOUND
    assert mongo.saved is None


def test_mcp_update_deal_forwards_value_update(monkeypatch) -> None:
    mongo = FakeMongo(_deal())
    monkeypatch.setattr(_context, "mongo", lambda: mongo)

    result = mcp_server.update_deal(
        "deal-1",
        "quoted",
        "signed order form confirmed by user",
        confirmed_by_user=True,
    )

    assert result["ok"] is True
    assert result["new_deal_value"]["deal_size_status"] == "quoted"
    assert mongo.saved is not None
    assert mongo.saved["deal_value_history"][-1]["deal_size_status"] == "quoted"
