from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from deal_intel import _context, _env
from deal_intel.cli import app
from deal_intel.storage.mongodb import MongoDBClient


def _reset_context(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setattr(_env, "_USER_CONFIG_PATH", tmp_path / "missing.yaml")
    monkeypatch.setattr(_context, "_config", None)
    monkeypatch.setattr(_context, "_mongo", None)


def test_mongodb_missing_uri_ping_points_to_local_sample(monkeypatch) -> None:
    monkeypatch.delenv("MONGODB_URI", raising=False)
    client = MongoDBClient(database="deal_intel")

    ping = client.ping()

    assert ping["status"] == "missing_uri"
    assert ping["storage_backend"] == "mongo"
    assert ping["database"] == "deal_intel"
    assert "MONGODB_URI" in ping["message"]
    assert "DEAL_INTEL_STORAGE_BACKEND=local_sample" in ping["message"]
    assert ping["sample_mode_hint"]["temporary_env"] == (
        "DEAL_INTEL_STORAGE_BACKEND=local_sample"
    )


def test_mongodb_missing_uri_exception_points_to_local_sample(monkeypatch) -> None:
    monkeypatch.delenv("MONGODB_URI", raising=False)
    client = MongoDBClient(database="deal_intel")

    with pytest.raises(RuntimeError) as exc_info:
        client._get_db()

    assert "MONGODB_URI" in str(exc_info.value)
    assert "DEAL_INTEL_STORAGE_BACKEND=local_sample" in str(exc_info.value)


def test_storage_status_cli_reports_missing_mongodb_uri(monkeypatch, tmp_path) -> None:
    _reset_context(monkeypatch, tmp_path)
    monkeypatch.delenv("MONGODB_URI", raising=False)
    monkeypatch.delenv("DEAL_INTEL_STORAGE_BACKEND", raising=False)

    result = CliRunner().invoke(app, ["storage-status", "--json"])

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["storage_backend"] == "mongo"
    assert payload["ping"]["status"] == "missing_uri"
    assert payload["sample_mode_hint"]["temporary_env"] == (
        "DEAL_INTEL_STORAGE_BACKEND=local_sample"
    )


def test_storage_status_cli_includes_sample_hint_on_mongo_error(monkeypatch) -> None:
    class FakeMongoStorage:
        database_name = "deal_intel"

        def ping(self) -> dict:
            return {"status": "error", "message": "network unavailable"}

    monkeypatch.setattr(_context, "storage_backend_name", lambda: "mongo")
    monkeypatch.setattr(_context, "mongo", lambda: FakeMongoStorage())

    result = CliRunner().invoke(app, ["storage-status", "--json"])

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["ping"]["status"] == "error"
    assert payload["sample_mode_hint"]["temporary_env"] == (
        "DEAL_INTEL_STORAGE_BACKEND=local_sample"
    )


def test_storage_status_cli_passes_in_local_sample_mode(monkeypatch, tmp_path) -> None:
    _reset_context(monkeypatch, tmp_path)
    monkeypatch.delenv("MONGODB_URI", raising=False)
    monkeypatch.setenv("DEAL_INTEL_STORAGE_BACKEND", "local_sample")

    result = CliRunner().invoke(app, ["storage-status", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["storage_backend"] == "local_sample"
    assert payload["ping"]["status"] == "ok"
    assert payload["ping"]["deal_count"] >= 10
    assert payload["ping"]["snapshot_count"] >= 20
