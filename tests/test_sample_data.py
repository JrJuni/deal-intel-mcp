from __future__ import annotations

import asyncio
from copy import deepcopy

import pytest

from deal_intel import _context, mcp_server
from deal_intel.errors import ErrorCode, MCPError
from deal_intel.tools import create_sample_data, delete_sample_data
from deal_intel.tools.sample_dataset import SAMPLE_BATCH_ID


class FakeMongo:
    def __init__(self, *, database_name: str = "deal_intel_demo") -> None:
        self.database_name = database_name
        self.deals: list[dict] = []
        self.upsert_calls = 0
        self.delete_calls = 0

    def count_deals(self, query: dict) -> int:
        return len(_matching(self.deals, query))

    def upsert_deals(self, deals: list[dict]) -> int:
        self.upsert_calls += 1
        for deal in deepcopy(deals):
            self.deals = [item for item in self.deals if item["deal_id"] != deal["deal_id"]]
            self.deals.append(deal)
        return len(deals)

    def list_sample_deals(self, sample_batch_id: str) -> list[dict]:
        return [
            {
                "deal_id": deal["deal_id"],
                "company": deal["company"],
                "deal_stage": deal["deal_stage"],
            }
            for deal in self.deals
            if deal.get("is_sample") is True
            and deal.get("sample_batch_id") == sample_batch_id
        ]

    def delete_sample_deals(self, sample_batch_id: str) -> int:
        self.delete_calls += 1
        before = len(self.deals)
        self.deals = [
            deal
            for deal in self.deals
            if not (
                deal.get("is_sample") is True
                and deal.get("sample_batch_id") == sample_batch_id
            )
        ]
        return before - len(self.deals)


def _cfg(**mongodb_overrides) -> dict:
    mongodb = {
        "database": "deal_intel",
        "demo_database": "deal_intel_demo",
    }
    mongodb.update(mongodb_overrides)
    return {"mongodb": mongodb}


def _matching(deals: list[dict], query: dict) -> list[dict]:
    return [
        deal
        for deal in deals
        if all(deal.get(key) == value for key, value in query.items())
    ]


def test_create_sample_data_dry_run_previews_without_writing() -> None:
    mongo = FakeMongo()

    result = create_sample_data.handle(
        mongo=mongo,
        cfg=_cfg(),
    )

    assert result["ok"] is True
    assert result["dry_run"] is True
    assert result["storage_written"] is False
    assert result["primary_database"] == "deal_intel"
    assert result["demo_database"] == "deal_intel_demo"
    assert result["deal_count"] == 10
    assert len(result["preview"]) == 3
    assert mongo.upsert_calls == 0


def test_sample_data_rejects_primary_database_and_wrong_client() -> None:
    with pytest.raises(MCPError) as same_database:
        create_sample_data.handle(
            mongo=FakeMongo(database_name="deal_intel"),
            cfg=_cfg(demo_database="deal_intel"),
        )
    with pytest.raises(MCPError) as wrong_client:
        create_sample_data.handle(
            mongo=FakeMongo(database_name="deal_intel"),
            cfg=_cfg(),
        )

    assert same_database.value.error_code == ErrorCode.INVALID_INPUT
    assert "different from the primary" in same_database.value.message
    assert wrong_client.value.error_code == ErrorCode.INVALID_INPUT
    assert wrong_client.value.hint["expected_demo_database"] == "deal_intel_demo"


def test_create_sample_data_requires_confirmation_for_actual_write() -> None:
    mongo = FakeMongo()

    with pytest.raises(MCPError) as exc_info:
        create_sample_data.handle(
            mongo=mongo,
            cfg=_cfg(),
            dry_run=False,
        )

    assert exc_info.value.error_code == ErrorCode.INVALID_INPUT
    assert "confirmation" in exc_info.value.message
    assert mongo.upsert_calls == 0


def test_create_sample_data_writes_marked_demo_records() -> None:
    mongo = FakeMongo()

    result = create_sample_data.handle(
        mongo=mongo,
        cfg=_cfg(),
        dry_run=False,
        confirmed_by_user=True,
    )

    assert result["storage_written"] is True
    assert result["created_or_replaced_count"] == 10
    assert len(mongo.deals) == 10
    assert all(deal["is_sample"] is True for deal in mongo.deals)
    assert {deal["sample_batch_id"] for deal in mongo.deals} == {SAMPLE_BATCH_ID}
    assert mongo.delete_calls == 0


def test_create_sample_data_blocks_existing_batch_without_overwrite() -> None:
    mongo = FakeMongo()
    create_sample_data.handle(
        mongo=mongo,
        cfg=_cfg(),
        dry_run=False,
        confirmed_by_user=True,
    )

    with pytest.raises(MCPError) as exc_info:
        create_sample_data.handle(
            mongo=mongo,
            cfg=_cfg(),
            dry_run=False,
            confirmed_by_user=True,
        )

    assert exc_info.value.error_code == ErrorCode.INVALID_INPUT
    assert exc_info.value.hint["fix"] == "Set overwrite=true to replace this sample batch."


def test_create_sample_data_overwrite_replaces_existing_batch() -> None:
    mongo = FakeMongo()
    create_sample_data.handle(
        mongo=mongo,
        cfg=_cfg(),
        dry_run=False,
        confirmed_by_user=True,
    )

    result = create_sample_data.handle(
        mongo=mongo,
        cfg=_cfg(),
        dry_run=False,
        overwrite=True,
        confirmed_by_user=True,
    )

    assert result["deleted_existing_count"] == 10
    assert result["created_or_replaced_count"] == 10
    assert len(mongo.deals) == 10
    assert mongo.delete_calls == 1


def test_delete_sample_data_dry_run_and_actual_delete() -> None:
    mongo = FakeMongo()
    create_sample_data.handle(
        mongo=mongo,
        cfg=_cfg(),
        dry_run=False,
        confirmed_by_user=True,
    )

    dry_run = delete_sample_data.handle(mongo=mongo, cfg=_cfg())
    assert dry_run["dry_run"] is True
    assert dry_run["would_delete_count"] == 10
    assert dry_run["storage_written"] is False
    assert len(mongo.deals) == 10

    with pytest.raises(MCPError) as missing_confirmation:
        delete_sample_data.handle(mongo=mongo, cfg=_cfg(), dry_run=False)

    actual = delete_sample_data.handle(
        mongo=mongo,
        cfg=_cfg(),
        dry_run=False,
        confirmed_by_user=True,
    )

    assert missing_confirmation.value.error_code == ErrorCode.INVALID_INPUT
    assert actual["deleted_count"] == 10
    assert actual["storage_written"] is True
    assert mongo.deals == []


def test_mcp_sample_data_wrappers_use_demo_database(monkeypatch) -> None:
    created_clients: list[FakeMongo] = []

    class FakeMongoFactory(FakeMongo):
        def __init__(self, *, database: str) -> None:
            super().__init__(database_name=database)
            created_clients.append(self)

    import deal_intel.storage.mongodb as mongodb_module

    monkeypatch.setattr(
        _context,
        "config",
        lambda: {**_cfg(), "tools": {"surface": "developer"}},
    )
    monkeypatch.setattr(mongodb_module, "MongoDBClient", FakeMongoFactory)

    result = mcp_server.create_sample_data()
    tools = asyncio.run(mcp_server.app.list_tools())
    names = sorted(tool.name for tool in tools)

    assert result["ok"] is True
    assert result["dry_run"] is True
    assert created_clients[0].database_name == "deal_intel_demo"
    assert len(names) == 22
    assert {"create_sample_data", "delete_sample_data"}.issubset(names)
