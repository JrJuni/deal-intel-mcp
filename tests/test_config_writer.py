from __future__ import annotations

import json

import yaml
from typer.testing import CliRunner

from deal_intel import _env
from deal_intel.cli import app
from deal_intel.config_writer import init_config_profile, switch_config_profile


def _load(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_init_config_profile_dry_run_does_not_write(tmp_path) -> None:
    user_config = tmp_path / "config.yaml"

    result = init_config_profile(
        "sample",
        config_path=user_config,
        dry_run=True,
    )

    assert result["ok"] is True
    assert result["dry_run"] is True
    assert result["storage_written"] is False
    assert user_config.exists() is False
    assert result["target_profile_values"] == {
        "storage.backend": "local_sample",
        "mongodb.vector_search": "python_cosine",
        "llm.provider": "chatgpt_oauth",
    }


def test_init_config_profile_writes_new_config(tmp_path) -> None:
    user_config = tmp_path / "config.yaml"

    result = init_config_profile("full", config_path=user_config)

    assert result["ok"] is True
    assert result["storage_written"] is True
    assert result["backup_written"] is False
    assert _load(user_config) == {
        "storage": {"backend": "mongo"},
        "mongodb": {"vector_search": "python_cosine"},
        "llm": {"provider": "chatgpt_oauth"},
    }


def test_init_config_profile_existing_config_requires_force(tmp_path) -> None:
    user_config = tmp_path / "config.yaml"
    user_config.write_text(
        "storage:\n"
        "  backend: mongo\n"
        "custom:\n"
        "  keep: true\n",
        encoding="utf-8",
    )

    result = init_config_profile("sample", config_path=user_config)

    assert result["ok"] is False
    assert result["error_code"] == "CONFIG_EXISTS"
    assert result["requires_force"] is True
    assert result["storage_written"] is False
    assert "custom:" in user_config.read_text(encoding="utf-8")


def test_init_config_profile_force_backs_up_and_overwrites(tmp_path) -> None:
    user_config = tmp_path / "config.yaml"
    user_config.write_text(
        "storage:\n"
        "  backend: mongo\n"
        "custom:\n"
        "  keep: true\n",
        encoding="utf-8",
    )

    result = init_config_profile(
        "sample",
        config_path=user_config,
        force=True,
        timestamp="20260611-010203",
    )

    backup = tmp_path / "config.yaml.bak.20260611-010203"
    assert result["ok"] is True
    assert result["storage_written"] is True
    assert result["backup_written"] is True
    assert result["backup_path"] == str(backup)
    assert backup.exists()
    assert "custom:" in backup.read_text(encoding="utf-8")
    assert _load(user_config) == {
        "storage": {"backend": "local_sample"},
        "mongodb": {"vector_search": "python_cosine"},
        "llm": {"provider": "chatgpt_oauth"},
    }


def test_switch_config_profile_dry_run_preserves_file(tmp_path) -> None:
    user_config = tmp_path / "config.yaml"
    user_config.write_text(
        "storage:\n"
        "  backend: mongo\n"
        "mongodb:\n"
        "  vector_search: python_cosine\n"
        "  database: custom_db\n"
        "llm:\n"
        "  provider: anthropic\n"
        "reporting:\n"
        "  output_dir: custom_reports\n",
        encoding="utf-8",
    )

    result = switch_config_profile(
        "sample",
        config_path=user_config,
        dry_run=True,
    )

    assert result["ok"] is True
    assert result["storage_written"] is False
    assert [change["field"] for change in result["changed_fields"]] == [
        "storage.backend",
        "llm.provider",
    ]
    assert _load(user_config)["storage"]["backend"] == "mongo"


def test_switch_config_profile_requires_force_when_changes_exist(tmp_path) -> None:
    user_config = tmp_path / "config.yaml"
    user_config.write_text(
        "storage:\n"
        "  backend: mongo\n"
        "mongodb:\n"
        "  vector_search: python_cosine\n"
        "llm:\n"
        "  provider: chatgpt_oauth\n",
        encoding="utf-8",
    )

    result = switch_config_profile("pro", config_path=user_config)

    assert result["ok"] is False
    assert result["error_code"] == "REQUIRES_FORCE"
    assert result["requires_force"] is True
    assert result["storage_written"] is False
    assert _load(user_config)["mongodb"]["vector_search"] == "python_cosine"


def test_switch_config_profile_force_preserves_custom_settings(tmp_path) -> None:
    user_config = tmp_path / "config.yaml"
    user_config.write_text(
        "storage:\n"
        "  backend: mongo\n"
        "mongodb:\n"
        "  vector_search: python_cosine\n"
        "  database: custom_db\n"
        "llm:\n"
        "  provider: anthropic\n"
        "reporting:\n"
        "  output_dir: custom_reports\n",
        encoding="utf-8",
    )

    result = switch_config_profile(
        "pro",
        config_path=user_config,
        force=True,
        timestamp="20260611-010204",
    )

    data = _load(user_config)
    assert result["ok"] is True
    assert result["storage_written"] is True
    assert result["backup_written"] is True
    assert data["storage"]["backend"] == "mongo"
    assert data["mongodb"]["vector_search"] == "atlas"
    assert data["mongodb"]["database"] == "custom_db"
    assert data["llm"]["provider"] == "openai_api"
    assert data["reporting"]["output_dir"] == "custom_reports"
    assert (tmp_path / "config.yaml.bak.20260611-010204").exists()


def test_switch_config_profile_missing_config_fails(tmp_path) -> None:
    user_config = tmp_path / "missing.yaml"

    result = switch_config_profile("sample", config_path=user_config)

    assert result["ok"] is False
    assert result["error_code"] == "CONFIG_NOT_FOUND"
    assert result["storage_written"] is False


def test_config_init_cli_json_uses_user_config_path(monkeypatch, tmp_path) -> None:
    user_config = tmp_path / "config.yaml"
    monkeypatch.setattr(_env, "_USER_CONFIG_PATH", user_config)

    result = CliRunner().invoke(
        app,
        ["config", "init", "--profile", "sample", "--dry-run", "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["dry_run"] is True
    assert payload["user_config_path"] == str(user_config)
    assert user_config.exists() is False


def test_config_switch_cli_text_does_not_print_custom_secret(monkeypatch, tmp_path) -> None:
    user_config = tmp_path / "config.yaml"
    user_config.write_text(
        "storage:\n"
        "  backend: mongo\n"
        "mongodb:\n"
        "  vector_search: python_cosine\n"
        "custom_secret: configured-custom-secret-sentinel\n"
        "llm:\n"
        "  provider: anthropic\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(_env, "_USER_CONFIG_PATH", user_config)

    result = CliRunner().invoke(
        app,
        ["config", "switch", "sample", "--dry-run"],
    )

    assert result.exit_code == 0
    assert "configured-custom-secret-sentinel" not in result.stdout
    assert "Profile-managed changes:" in result.stdout
