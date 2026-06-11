from __future__ import annotations

import json

from typer.testing import CliRunner

from deal_intel import _env
from deal_intel.cli import app
from deal_intel.storage.local_personal import (
    LOCAL_PERSONAL_DEALS_FILE,
    LocalPersonalStore,
)
from deal_intel.storage.local_sample import LocalSampleClient


def _write_sample_config(monkeypatch, tmp_path) -> None:
    user_config = tmp_path / "config.yaml"
    local_data_dir = tmp_path / "local-data"
    user_config.write_text(
        "storage:\n"
        "  backend: local_sample\n"
        f"  local_data_dir: {json.dumps(str(local_data_dir))}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(_env, "_USER_CONFIG_PATH", user_config)


def _seed_local_data(tmp_path) -> LocalPersonalStore:
    store = LocalPersonalStore(tmp_path / "local-data")
    store.upsert_deal(
        {
            "deal_id": "local-cli-1",
            "company": "Local CLI Co",
            "deal_stage": "discovery",
            "meetings": [
                {
                    "summary": "safe summary",
                    "raw_notes": "private raw note sentinel",
                }
            ],
            "contacts": [{"email": "private@example.com"}],
            "summary_embedding": [0.1, 0.2],
        }
    )
    store.insert_delete_audit_log(
        {
            "deal_id": "deleted-local-cli",
            "delete_reason": "test cleanup",
            "deal_snapshot": {
                "deal_id": "deleted-local-cli",
                "company": "Deleted Local CLI Co",
                "meetings": [{"raw_notes": "deleted private note sentinel"}],
                "contacts": [{"email": "deleted@example.com"}],
                "summary_embedding": [0.3],
            },
        }
    )
    return store


def test_local_data_status_cli_reports_configured_directory(
    monkeypatch,
    tmp_path,
) -> None:
    _write_sample_config(monkeypatch, tmp_path)
    _seed_local_data(tmp_path)

    result = CliRunner().invoke(app, ["local-data", "status", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["dataset"] == "local_personal"
    assert payload["deal_count"] == 1
    assert payload["delete_audit_log_count"] == 1
    assert payload["data_dir"].endswith("local-data")


def test_local_data_export_cli_writes_secret_safe_snapshot(
    monkeypatch,
    tmp_path,
) -> None:
    _write_sample_config(monkeypatch, tmp_path)
    _seed_local_data(tmp_path)
    output_path = tmp_path / "exports" / "snapshot.json"

    result = CliRunner().invoke(
        app,
        [
            "local-data",
            "export",
            "--output",
            str(output_path),
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    exported = json.loads(output_path.read_text(encoding="utf-8"))
    exported_text = json.dumps(exported, ensure_ascii=False)
    assert payload["ok"] is True
    assert payload["export_path"] == str(output_path)
    assert exported["export_type"] == "local_personal_snapshot"
    assert exported["counts"] == {"deals": 1, "delete_audit_logs": 1}
    assert "private raw note sentinel" not in exported_text
    assert "private@example.com" not in exported_text
    assert "summary_embedding" not in exported_text


def test_local_data_reset_cli_is_dry_run_by_default(
    monkeypatch,
    tmp_path,
) -> None:
    _write_sample_config(monkeypatch, tmp_path)
    store = _seed_local_data(tmp_path)

    result = CliRunner().invoke(app, ["local-data", "reset", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["dry_run"] is True
    assert payload["storage_written"] is False
    assert payload["would_delete_deal_count"] == 1
    assert len(store.load_deals()) == 1
    assert len(store.load_delete_audit_logs()) == 1


def test_local_data_reset_cli_force_clears_deals_and_preserves_audit_logs(
    monkeypatch,
    tmp_path,
) -> None:
    _write_sample_config(monkeypatch, tmp_path)
    store = _seed_local_data(tmp_path)

    result = CliRunner().invoke(
        app,
        ["local-data", "reset", "--force", "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["dry_run"] is False
    assert payload["storage_written"] is True
    assert payload["deleted_deal_count"] == 1
    assert store.load_deals() == []
    assert len(store.load_delete_audit_logs()) == 1

    raw_payload = json.loads(
        (tmp_path / "local-data" / LOCAL_PERSONAL_DEALS_FILE).read_text(
            encoding="utf-8"
        )
    )
    client = LocalSampleClient(local_data_dir=tmp_path / "local-data")
    assert raw_payload["deals"] == []
    assert client.ping()["data_mode"] == "local_personal"
    assert client.get_deal("sample-pavebridge") is None
