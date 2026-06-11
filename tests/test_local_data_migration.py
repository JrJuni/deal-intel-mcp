from __future__ import annotations

import json
from copy import deepcopy

import pytest
from typer.testing import CliRunner

from deal_intel import _context, _env, mcp_server
from deal_intel.cli import app
from deal_intel.errors import ErrorCode, MCPError
from deal_intel.storage.local_personal import LocalPersonalStore
from deal_intel.tools import migrate_local_data


class FakeMongo:
    def __init__(
        self,
        *,
        database: str = "deal_intel",
        existing: dict[str, dict] | None = None,
        ping_status: str = "ok",
    ) -> None:
        self.database_name = database
        self.existing = deepcopy(existing or {})
        self.upserted: list[dict] = []
        self.ping_status = ping_status
        self.ping_count = 0

    def ping(self) -> dict:
        self.ping_count += 1
        return {"status": self.ping_status, "database": self.database_name}

    def get_deal(self, deal_id: str) -> dict | None:
        deal = self.existing.get(deal_id)
        return deepcopy(deal) if deal is not None else None

    def upsert_deal(self, deal: dict) -> None:
        self.upserted.append(deepcopy(deal))
        self.existing[deal["deal_id"]] = deepcopy(deal)


def _write_sample_config(monkeypatch, tmp_path) -> None:
    user_config = tmp_path / "config.yaml"
    local_data_dir = tmp_path / "local-data"
    user_config.write_text(
        "storage:\n"
        "  backend: local_sample\n"
        f"  local_data_dir: {json.dumps(str(local_data_dir))}\n"
        "mongodb:\n"
        "  database: deal_intel\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(_env, "_USER_CONFIG_PATH", user_config)


def _seed_store(tmp_path) -> LocalPersonalStore:
    store = LocalPersonalStore(tmp_path / "local-data")
    store.upsert_deal(
        {
            "deal_id": "local-migrate-1",
            "company": "Local Migration Co",
            "industry": "Trial",
            "deal_stage": "discovery",
            "meetings": [
                {
                    "summary": "safe meeting summary",
                    "raw_notes": "private raw note sentinel",
                }
            ],
            "contacts": [{"email": "private@example.com"}],
            "summary_embedding": [0.1, 0.2],
        }
    )
    return store


def test_migration_dry_run_classifies_creates_without_writing(tmp_path) -> None:
    store = _seed_store(tmp_path)
    mongo = FakeMongo()

    result = migrate_local_data.handle(source_store=store, target_mongo=mongo)

    payload = json.dumps(result, ensure_ascii=False)
    assert result["ok"] is True
    assert result["dry_run"] is True
    assert result["storage_written"] is False
    assert result["counts"]["would_create"] == 1
    assert result["counts"]["would_write"] == 1
    assert result["deals"][0]["action"] == "create"
    assert mongo.upserted == []
    assert "private raw note sentinel" not in payload
    assert "private@example.com" not in payload
    assert "summary_embedding" not in payload


def test_migration_dry_run_without_local_deals_skips_target_ping(tmp_path) -> None:
    store = LocalPersonalStore(tmp_path / "local-data")
    mongo = FakeMongo(ping_status="error")

    result = migrate_local_data.handle(source_store=store, target_mongo=mongo)

    assert result["ok"] is True
    assert result["dry_run"] is True
    assert result["counts"]["source_deals"] == 0
    assert result["target"]["readiness"] == "not_checked_no_source_deals"
    assert mongo.ping_count == 0
    assert {warning["code"] for warning in result["warnings"]} == {
        "no_local_personal_deals",
        "target_not_checked_no_source_deals",
    }


def test_migration_apply_requires_confirmation(tmp_path) -> None:
    store = _seed_store(tmp_path)

    with pytest.raises(MCPError) as exc_info:
        migrate_local_data.handle(
            source_store=store,
            target_mongo=FakeMongo(),
            dry_run=False,
        )

    assert exc_info.value.error_code == ErrorCode.INVALID_INPUT


def test_migration_apply_writes_local_deals_to_mongo(tmp_path) -> None:
    store = _seed_store(tmp_path)
    mongo = FakeMongo()

    result = migrate_local_data.handle(
        source_store=store,
        target_mongo=mongo,
        dry_run=False,
        confirmed_by_user=True,
    )

    assert result["storage_written"] is True
    assert result["counts"]["migrated"] == 1
    assert result["counts"]["overwritten"] == 0
    assert mongo.upserted[0]["deal_id"] == "local-migrate-1"
    assert mongo.upserted[0]["company"] == "Local Migration Co"


def test_migration_skips_existing_by_default_and_overwrites_when_enabled(
    tmp_path,
) -> None:
    store = _seed_store(tmp_path)
    existing = {"local-migrate-1": {"deal_id": "local-migrate-1", "company": "Old"}}
    skip_mongo = FakeMongo(existing=existing)
    overwrite_mongo = FakeMongo(existing=existing)

    skipped = migrate_local_data.handle(
        source_store=store,
        target_mongo=skip_mongo,
        dry_run=False,
        confirmed_by_user=True,
    )
    overwritten = migrate_local_data.handle(
        source_store=store,
        target_mongo=overwrite_mongo,
        dry_run=False,
        confirmed_by_user=True,
        overwrite=True,
    )

    assert skipped["counts"]["skipped_existing"] == 1
    assert skipped["storage_written"] is False
    assert skip_mongo.existing["local-migrate-1"]["company"] == "Old"
    assert overwritten["counts"]["overwritten"] == 1
    assert overwritten["storage_written"] is True
    assert overwrite_mongo.existing["local-migrate-1"]["company"] == (
        "Local Migration Co"
    )


def test_migration_reports_target_ping_failure(tmp_path) -> None:
    store = _seed_store(tmp_path)

    with pytest.raises(MCPError) as exc_info:
        migrate_local_data.handle(
            source_store=store,
            target_mongo=FakeMongo(ping_status="missing_uri"),
        )

    assert exc_info.value.error_code == ErrorCode.STORAGE_ERROR
    assert "Target MongoDB storage is not ready" in exc_info.value.message


def test_local_data_migrate_to_mongo_cli_dry_run_json(
    monkeypatch,
    tmp_path,
) -> None:
    _write_sample_config(monkeypatch, tmp_path)
    _seed_store(tmp_path)
    created_clients: list[FakeMongo] = []

    class FakeMongoFactory(FakeMongo):
        def __init__(self, *, database: str) -> None:
            super().__init__(database=database)
            created_clients.append(self)

    import deal_intel.storage.mongodb as mongodb_module

    monkeypatch.setattr(mongodb_module, "MongoDBClient", FakeMongoFactory)

    result = CliRunner().invoke(
        app,
        ["local-data", "migrate-to-mongo", "--json"],
    )

    payload = json.loads(result.stdout)
    assert result.exit_code == 0
    assert payload["ok"] is True
    assert payload["dry_run"] is True
    assert payload["counts"]["would_create"] == 1
    assert created_clients[0].database_name == "deal_intel"


def test_mcp_migrate_local_data_uses_configured_local_data_dir_and_target_database(
    monkeypatch,
    tmp_path,
) -> None:
    _seed_store(tmp_path)
    created_clients: list[FakeMongo] = []

    class FakeMongoFactory(FakeMongo):
        def __init__(self, *, database: str) -> None:
            super().__init__(database=database)
            created_clients.append(self)

    import deal_intel.storage.mongodb as mongodb_module

    monkeypatch.setattr(
        _context,
        "config",
        lambda: {
            "storage": {"local_data_dir": str(tmp_path / "local-data")},
            "mongodb": {"database": "configured_db"},
        },
    )
    monkeypatch.setattr(mongodb_module, "MongoDBClient", FakeMongoFactory)

    result = mcp_server.migrate_local_data(target_database="target_db")

    assert result["ok"] is True
    assert result["dry_run"] is True
    assert result["counts"]["would_create"] == 1
    assert created_clients[0].database_name == "target_db"
