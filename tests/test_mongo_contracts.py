from __future__ import annotations

import json

from typer.testing import CliRunner

from deal_intel import _env
from deal_intel.cli import app
from deal_intel.mongo_contracts import (
    build_deals_schema_command,
    compare_mongo_indexes,
    deals_schema_contract_summary,
    expected_mongo_indexes,
)
from deal_intel.mongo_doctor import build_mongo_doctor_report
from deal_intel.storage import mongodb as storage_mongodb
from deal_intel.storage.mongodb import MongoDBClient


def _full_cfg() -> dict:
    return {
        "storage": {"backend": "mongo"},
        "mongodb": {
            "database": "deal_intel",
            "vector_search": "python_cosine",
        },
        "llm": {"provider": "chatgpt_oauth"},
    }


def test_expected_mongo_indexes_are_named_and_grouped() -> None:
    indexes = expected_mongo_indexes()

    assert set(indexes) == {"deals", "delete_audit_logs", "analytics_snapshots"}
    assert indexes["deals"][0].name == "deal_id_unique"
    assert indexes["deals"][0].unique is True
    assert indexes["analytics_snapshots"][0].name == "analytics_snapshot_event_id_unique"


def test_compare_mongo_indexes_detects_key_mismatch() -> None:
    report = compare_mongo_indexes(
        {
            "deals": [
                {
                    "name": "deal_id_unique",
                    "key": {"deal_id": -1},
                    "unique": True,
                }
            ]
        }
    )

    assert report["ok"] is False
    assert report["mismatch_count"] == 1
    assert report["collections"]["deals"][0]["status"] == "mismatched"


def test_deals_schema_command_is_warn_moderate_and_permissive() -> None:
    command = build_deals_schema_command()
    summary = deals_schema_contract_summary()

    assert command["collMod"] == "deals"
    assert command["validationAction"] == "warn"
    assert command["validationLevel"] == "moderate"
    assert summary["required_fields"] == ["deal_id", "company", "deal_stage"]
    assert command["validator"]["$jsonSchema"]["additionalProperties"] is True


class FakeSchemaDB:
    def __init__(self, *, options: dict | None = None) -> None:
        self.options = options or {}

    def command(self, name: str | dict, **kwargs):
        if name == "listCollections":
            assert kwargs == {"filter": {"name": "deals"}}
            return {
                "cursor": {
                    "firstBatch": [
                        {
                            "name": "deals",
                            "options": self.options,
                        }
                    ]
                }
            }
        return {"ok": 1}


def test_check_deals_schema_validation_reports_match() -> None:
    command = build_deals_schema_command()
    db = FakeSchemaDB(
        options={
            "validator": command["validator"],
            "validationAction": command["validationAction"],
            "validationLevel": command["validationLevel"],
        }
    )
    client = MongoDBClient(uri="mongodb://example.invalid")
    client._db = db

    report = client.check_deals_schema_validation()

    assert report["ok"] is True
    assert report["status"] == "ok"


def test_mongo_doctor_offline_skips_live_checks(monkeypatch) -> None:
    monkeypatch.setenv("MONGODB_URI", "configured-mongodb-uri-sentinel")

    report = build_mongo_doctor_report(_full_cfg(), offline=True)

    assert report["ok"] is True
    assert _status(report, "mongodb_uri") == "pass"
    assert _status(report, "storage_ping") == "skipped"
    assert "configured-mongodb-uri-sentinel" not in json.dumps(report)


def test_mongo_doctor_missing_uri_fails(monkeypatch) -> None:
    monkeypatch.delenv("MONGODB_URI", raising=False)

    report = build_mongo_doctor_report(_full_cfg(), offline=True)

    assert report["ok"] is False
    assert _status(report, "mongodb_uri") == "fail"
    assert _status(report, "mongo_indexes") == "skipped"


def test_mongo_cli_apply_schema_dry_run_does_not_require_mongodb_uri(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(_env, "_USER_CONFIG_PATH", tmp_path / "missing.yaml")
    monkeypatch.delenv("MONGODB_URI", raising=False)

    result = CliRunner().invoke(app, ["mongo", "apply-schema", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["dry_run"] is True
    assert payload["collection"] == "deals"
    assert payload["validation_action"] == "warn"


def test_mongo_cli_doctor_json_is_secret_safe(monkeypatch, tmp_path) -> None:
    user_config = tmp_path / "config.yaml"
    user_config.write_text(
        "storage:\n"
        "  backend: mongo\n"
        "mongodb:\n"
        "  database: deal_intel\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(_env, "_USER_CONFIG_PATH", user_config)
    monkeypatch.setenv("MONGODB_URI", "configured-mongodb-uri-sentinel")

    result = CliRunner().invoke(app, ["mongo", "doctor", "--offline", "--json"])

    assert result.exit_code == 0
    assert "configured-mongodb-uri-sentinel" not in result.stdout
    payload = json.loads(result.stdout)
    assert payload["summary"]["storage_backend"] == "mongo"
    assert _status(payload, "mongo_indexes") == "skipped"


def test_mongo_cli_apply_schema_json_handles_mongo_timestamp_response(
    monkeypatch,
    tmp_path,
) -> None:
    class FakeTimestamp:
        def __str__(self) -> str:
            return "Timestamp(1, 2)"

    class FakeMongoDBClient:
        def __init__(self, *, database: str) -> None:
            self.database = database

        def apply_deals_schema_validation(self) -> dict:
            return {
                "ok": 1.0,
                "operationTime": FakeTimestamp(),
                "$clusterTime": {
                    "signature": {
                        "hash": "internal-hash",
                        "keyId": 123,
                    }
                },
            }

    user_config = tmp_path / "config.yaml"
    user_config.write_text(
        "storage:\n"
        "  backend: mongo\n"
        "mongodb:\n"
        "  database: deal_intel\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(_env, "_USER_CONFIG_PATH", user_config)
    monkeypatch.setattr(storage_mongodb, "MongoDBClient", FakeMongoDBClient)

    result = CliRunner().invoke(app, ["mongo", "apply-schema", "--apply", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["dry_run"] is False
    assert payload["result"]["operationTime"] == "Timestamp(1, 2)"
    assert "$clusterTime" not in payload["result"]
    assert "internal-hash" not in result.stdout


def test_mongo_cli_apply_vector_index_dry_run(monkeypatch, tmp_path) -> None:
    user_config = tmp_path / "config.yaml"
    user_config.write_text(
        "storage:\n"
        "  backend: mongo\n"
        "mongodb:\n"
        "  database: deal_intel\n"
        "  vector_search: atlas\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(_env, "_USER_CONFIG_PATH", user_config)

    result = CliRunner().invoke(app, ["mongo", "apply-vector-index", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["dry_run"] is True
    assert payload["index_name"] == "deal_summary_vector"
    assert payload["minimum_cluster_tier"] == "M10"
    assert payload["command"]["createSearchIndexes"] == "deals"
    assert "silently fall back" in payload["policy"]


def test_ensure_vector_index_reports_duplicate_as_ok() -> None:
    class DuplicateVectorDB:
        def command(self, _command: dict) -> dict:
            raise RuntimeError("index already exists")

    client = MongoDBClient(uri="mongodb://example.invalid")
    client._db = DuplicateVectorDB()

    result = client.ensure_vector_index()

    assert result["ok"] is True
    assert result["status"] == "already_exists"


def _status(report: dict, check_id: str) -> str:
    return next(check for check in report["checks"] if check["id"] == check_id)[
        "status"
    ]
