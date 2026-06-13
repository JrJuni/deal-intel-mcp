from __future__ import annotations

import asyncio
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
        "industry": "IT",
        "industry_tags": ["IT"],
        "customer_segment": "startup",
        "deal_stage": "discovery",
        "deal_size_amount": 18_000_000,
        "deal_size_low_amount": None,
        "deal_size_high_amount": None,
        "deal_size_currency": "KRW",
        "deal_size_status": None,
        "deal_size_note": None,
        "expected_close_date": "2026-06-30",
        "expected_close_date_source": "config_default",
        "actual_close_date": None,
        "close_reason": None,
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
        "deal_size_amount": 18_000_000,
        "deal_size_low_amount": None,
        "deal_size_high_amount": None,
        "deal_size_currency": "KRW",
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
        deal_size_amount=20_000_000,
        deal_size_low_amount=15_000_000,
        deal_size_high_amount=25_000_000,
        deal_size_note="customer disclosed budget range",
        confirmed_by_user=True,
    )

    assert result["new_deal_value"]["deal_size_amount"] == 20_000_000
    assert result["new_deal_value"]["deal_size_status"] == "customer_budget"
    assert mongo.saved is not None
    assert mongo.saved["deal_size_low_amount"] == 15_000_000
    assert mongo.saved["deal_value_history"][-1]["deal_size_high_amount"] == 25_000_000


def test_update_deal_unknown_clears_amount_fields() -> None:
    mongo = FakeMongo(_deal())

    result = update_deal.handle(
        mongo=mongo,
        deal_id="deal-1",
        deal_size_status="unknown",
        deal_size_note="user confirmed amount is still unknown",
        confirmed_by_user=True,
    )

    assert result["new_deal_value"]["deal_size_amount"] is None
    assert result["new_deal_value"]["deal_size_status"] == "unknown"
    assert mongo.saved is not None
    assert mongo.saved["deal_size_amount"] is None


def test_update_deal_updates_metadata_with_confirmation_and_history() -> None:
    mongo = FakeMongo(_deal())

    result = update_deal.handle(
        mongo=mongo,
        deal_id="deal-1",
        industry="제조",
        customer_segment="enterprise",
        expected_close_date="2026-07-15",
        update_note="user confirmed industry, segment, and close forecast",
        confirmed_by_user=True,
    )

    assert result["ok"] is True
    assert result["changed_value_fields"] == []
    assert result["changed_metadata_fields"] == [
        "industry",
        "industry_tags",
        "customer_segment",
        "expected_close_date",
        "expected_close_date_source",
    ]
    assert result["changed_fields"] == [
        "industry",
        "industry_tags",
        "customer_segment",
        "expected_close_date",
        "expected_close_date_source",
    ]
    assert mongo.saved is not None
    assert mongo.saved["industry"] == "Manufacturing"
    assert mongo.saved["industry_tags"] == ["Manufacturing", "IT"]
    assert mongo.saved["customer_segment"] == "enterprise"
    assert mongo.saved["expected_close_date"] == "2026-07-15"
    assert mongo.saved["expected_close_date_source"] == "user_provided"
    history = mongo.saved["deal_metadata_history"][-1]
    assert history["source"] == "update_deal"
    assert history["update_note"] == "user confirmed industry, segment, and close forecast"
    assert history["old_values"]["expected_close_date"] == "2026-06-30"
    assert history["old_values"]["industry"] == "IT"
    assert history["new_values"]["industry"] == "Manufacturing"
    assert history["new_values"]["industry_tags"] == ["Manufacturing", "IT"]
    assert history["old_values"]["customer_segment"] == "startup"
    assert history["new_values"]["expected_close_date"] == "2026-07-15"
    assert history["new_values"]["customer_segment"] == "enterprise"
    assert "deal_value_history" not in mongo.saved


def test_update_deal_updates_industry_tags_without_changing_primary() -> None:
    mongo = FakeMongo(_deal(industry="Finance", industry_tags=["Finance"]))

    result = update_deal.handle(
        mongo=mongo,
        deal_id="deal-1",
        industry_tags="보험/SaaS",
        update_note="user confirmed cross-industry tags",
        confirmed_by_user=True,
    )

    assert result["changed_metadata_fields"] == ["industry_tags"]
    assert result["new_deal_metadata"]["industry"] == "Finance"
    assert result["new_deal_metadata"]["industry_tags"] == [
        "Finance",
        "Insurance",
        "SaaS",
    ]
    assert mongo.saved is not None
    assert mongo.saved["industry_tags"] == ["Finance", "Insurance", "SaaS"]


def test_update_deal_rejects_ambiguous_primary_industry_before_storage() -> None:
    mongo = FakeMongo(_deal())

    with pytest.raises(MCPError) as exc_info:
        update_deal.handle(
            mongo=mongo,
            deal_id="deal-1",
            industry="보험·금융",
            update_note="user confirmed industry",
            confirmed_by_user=True,
        )

    assert exc_info.value.error_code == ErrorCode.INVALID_INPUT
    assert exc_info.value.hint["candidates"] == ["Finance", "Insurance"]
    assert mongo.saved is None


def test_update_deal_updates_terminal_postmortem_fields() -> None:
    mongo = FakeMongo(_deal(deal_stage="lost"))

    result = update_deal.handle(
        mongo=mongo,
        deal_id="deal-1",
        actual_close_date="2026-06-05",
        close_reason="security review failed",
        update_note="user confirmed lost postmortem",
        confirmed_by_user=True,
    )

    assert result["changed_metadata_fields"] == [
        "actual_close_date",
        "close_reason",
    ]
    assert mongo.saved is not None
    assert mongo.saved["actual_close_date"] == "2026-06-05"
    assert mongo.saved["close_reason"] == "security review failed"


def test_update_deal_rejects_metadata_update_without_note() -> None:
    mongo = FakeMongo(_deal())

    with pytest.raises(MCPError) as exc_info:
        update_deal.handle(
            mongo=mongo,
            deal_id="deal-1",
            industry="Finance",
            confirmed_by_user=True,
        )

    assert exc_info.value.error_code == ErrorCode.INVALID_INPUT
    assert "update_note" in exc_info.value.message
    assert mongo.saved is None


def test_update_deal_rejects_actual_close_date_for_open_deal() -> None:
    mongo = FakeMongo(_deal(deal_stage="proposal"))

    with pytest.raises(MCPError) as exc_info:
        update_deal.handle(
            mongo=mongo,
            deal_id="deal-1",
            actual_close_date="2026-06-05",
            update_note="user confirmed date",
            confirmed_by_user=True,
        )

    assert exc_info.value.error_code == ErrorCode.INVALID_INPUT
    assert "won or lost" in exc_info.value.message
    assert exc_info.value.hint["fix"] == "Use update_stage to move the deal to won/lost first."
    assert mongo.saved is None


def test_update_deal_rejects_close_reason_for_non_lost_deal() -> None:
    mongo = FakeMongo(_deal(deal_stage="won"))

    with pytest.raises(MCPError) as exc_info:
        update_deal.handle(
            mongo=mongo,
            deal_id="deal-1",
            close_reason="not applicable",
            update_note="user confirmed reason",
            confirmed_by_user=True,
        )

    assert exc_info.value.error_code == ErrorCode.INVALID_INPUT
    assert "lost deals" in exc_info.value.message
    assert mongo.saved is None


def test_update_deal_combines_value_and_metadata_updates() -> None:
    mongo = FakeMongo(_deal(deal_stage="proposal"))

    result = update_deal.handle(
        mongo=mongo,
        deal_id="deal-1",
        deal_size_status="quoted",
        deal_size_note="quote sent and user confirmed",
        deal_size_amount=20_000_000,
        expected_close_date="2026-07-01",
        update_note="user confirmed revised close date",
        confirmed_by_user=True,
    )

    assert result["changed_value_fields"] == [
        "deal_size_amount",
        "deal_size_status",
        "deal_size_note",
    ]
    assert result["changed_metadata_fields"] == [
        "expected_close_date",
        "expected_close_date_source",
    ]
    assert mongo.saved is not None
    assert mongo.saved["deal_value_history"][-1]["deal_size_status"] == "quoted"
    assert mongo.saved["deal_metadata_history"][-1]["new_values"] == {
        "expected_close_date": "2026-07-01",
        "expected_close_date_source": "user_provided",
    }


def test_update_deal_rejects_invalid_value_combination_before_storage() -> None:
    mongo = FakeMongo(_deal())

    with pytest.raises(MCPError) as exc_info:
        update_deal.handle(
            mongo=mongo,
            deal_id="deal-1",
            deal_size_status="quoted",
            deal_size_amount=0,
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


def test_mcp_update_deal_forwards_metadata_update(monkeypatch) -> None:
    mongo = FakeMongo(_deal())
    monkeypatch.setattr(_context, "mongo", lambda: mongo)

    result = mcp_server.update_deal(
        "deal-1",
        industry="Finance",
        customer_segment="enterprise",
        expected_close_date="2026-07-20",
        update_note="user confirmed metadata",
        confirmed_by_user=True,
    )

    assert result["ok"] is True
    assert result["changed_metadata_fields"] == [
        "industry",
        "industry_tags",
        "customer_segment",
        "expected_close_date",
        "expected_close_date_source",
    ]
    assert mongo.saved is not None
    assert mongo.saved["industry"] == "Finance"
    assert mongo.saved["industry_tags"] == ["Finance", "IT"]
    assert mongo.saved["customer_segment"] == "enterprise"


def test_mcp_runtime_update_deal_exposes_metadata_params() -> None:
    tools = asyncio.run(mcp_server.app.list_tools())
    tool = next(item for item in tools if item.name == "update_deal")

    assert tool.parameters["required"] == ["deal_id"]
    assert {
        "company",
        "industry",
        "industry_tags",
        "customer_segment",
        "expected_close_date",
        "actual_close_date",
        "close_reason",
        "update_note",
    }.issubset(tool.parameters["properties"])
