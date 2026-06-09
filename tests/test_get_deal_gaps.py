from __future__ import annotations

import asyncio
import json
from copy import deepcopy

import pytest

from deal_intel import _context, mcp_server
from deal_intel.errors import ErrorCode, MCPError
from deal_intel.tools import get_deal_gaps


class FakeMongo:
    def __init__(self, deals: list[dict]) -> None:
        self.deals = deepcopy(deals)
        self.read_count = 0
        self.write_count = 0

    def list_deals_for_metrics(self) -> list[dict]:
        self.read_count += 1
        return deepcopy(self.deals)

    def upsert_deal(self, deal: dict) -> None:
        self.write_count += 1
        raise AssertionError("get_deal_gaps must be read-only")

    def _get_db(self) -> None:
        raise AssertionError("get_deal_gaps should use the metrics read path")


class FailingMongo:
    def list_deals_for_metrics(self) -> list[dict]:
        raise RuntimeError("mongo unavailable")

    def _get_db(self) -> None:
        raise AssertionError("should not use raw DB access")


class PreflightFailingMongo:
    def list_deals_for_metrics(self) -> list[dict]:
        raise AssertionError("preflight should fail before storage access")

    def _get_db(self) -> None:
        raise AssertionError("preflight should fail before storage access")


def _deal(deal_id: str, *, stage: str = "discovery") -> dict:
    return {
        "deal_id": deal_id,
        "company": f"Company {deal_id}",
        "industry": "IT",
        "deal_stage": stage,
        "deal_size_krw": None,
        "deal_size_status": "unknown",
        "expected_close_date": "2026-06-30",
        "expected_close_date_source": "user_provided",
        "stage_history": [{"stage": stage, "entered_at": "2026-06-01T00:00:00+00:00"}],
        "meetings": [{"date": "2026-06-01", "raw_notes": "secret"}],
        "contacts": [{"name": "secret"}],
        "summary_embedding": [0.1, 0.2],
        "meddpicc_latest": {"filled_count": 1, "health_pct": 80, "gaps": []},
    }


def test_get_deal_gaps_valid_filters_return_shape_and_exclude_sensitive_fields() -> None:
    mongo = FakeMongo([_deal("deal-1"), _deal("deal-2", stage="proposal")])

    result = get_deal_gaps.handle(
        mongo=mongo,
        cfg={},
        as_of="2026-06-09",
        stage="discovery",
        industry="IT",
        min_priority="low",
        limit=5,
    )

    assert result["ok"] is True
    assert result["as_of"] == "2026-06-09"
    assert result["filters"] == {
        "stage": "discovery",
        "industry": "IT",
        "deal_id": None,
        "min_priority": "low",
        "limit": 5,
    }
    assert result["summary"]["deal_count"] == 1
    assert result["summary"]["returned_deal_count"] == 1
    assert result["deals"][0]["deal_id"] == "deal-1"
    serialized = json.dumps(result, ensure_ascii=False)
    assert "raw_notes" not in serialized
    assert "contacts" not in serialized
    assert "summary_embedding" not in serialized
    assert mongo.read_count == 1
    assert mongo.write_count == 0


def test_get_deal_gaps_mcp_wrapper_forwards_defaults(monkeypatch) -> None:
    mongo = FakeMongo([_deal("deal-1")])
    monkeypatch.setattr(_context, "mongo", lambda: mongo)
    monkeypatch.setattr(_context, "config", lambda: {})

    result = mcp_server.get_deal_gaps(as_of="2026-06-09", min_priority="low")

    assert result["ok"] is True
    assert result["filters"]["min_priority"] == "low"
    assert result["summary"]["deal_count"] == 1


def test_get_deal_gaps_rejects_invalid_inputs_before_storage() -> None:
    with pytest.raises(MCPError) as invalid_stage:
        get_deal_gaps.handle(
            mongo=PreflightFailingMongo(),
            cfg={},
            as_of="2026-06-09",
            stage="bad",
        )
    with pytest.raises(MCPError) as invalid_as_of:
        get_deal_gaps.handle(
            mongo=PreflightFailingMongo(),
            cfg={},
            as_of="not-a-date",
        )
    with pytest.raises(MCPError) as invalid_priority:
        get_deal_gaps.handle(
            mongo=PreflightFailingMongo(),
            cfg={},
            as_of="2026-06-09",
            min_priority="urgent",
        )
    with pytest.raises(MCPError) as invalid_limit:
        get_deal_gaps.handle(
            mongo=PreflightFailingMongo(),
            cfg={},
            as_of="2026-06-09",
            limit=0,
        )

    assert invalid_stage.value.error_code == ErrorCode.INVALID_INPUT
    assert invalid_as_of.value.error_code == ErrorCode.INVALID_INPUT
    assert invalid_priority.value.hint == {"valid_priorities": ["low", "medium", "high"]}
    assert invalid_limit.value.error_code == ErrorCode.INVALID_INPUT


def test_get_deal_gaps_storage_failure_is_structured() -> None:
    with pytest.raises(MCPError) as exc_info:
        get_deal_gaps.handle(
            mongo=FailingMongo(),
            cfg={},
            as_of="2026-06-09",
        )

    assert exc_info.value.error_code == ErrorCode.STORAGE_ERROR
    assert exc_info.value.stage == "storage"
    assert exc_info.value.retryable is True


def test_mcp_runtime_registers_get_deal_gaps() -> None:
    tools = asyncio.run(mcp_server.app.list_tools())
    names = sorted(tool.name for tool in tools)

    assert len(names) == 18
    assert "get_deal_gaps" in names
