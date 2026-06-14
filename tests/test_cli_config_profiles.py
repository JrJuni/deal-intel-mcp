from __future__ import annotations

import json

from typer.testing import CliRunner

from deal_intel import _env
from deal_intel.cli import app


def test_config_profiles_cli_returns_profile_catalog_json() -> None:
    result = CliRunner().invoke(app, ["config", "profiles", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert [profile["name"] for profile in payload["profiles"]] == [
        "sample",
        "full",
        "pro",
    ]
    assert payload["profiles"][0]["config_patch"]["storage"]["backend"] == (
        "local_sample"
    )
    assert payload["profiles"][0]["config_patch"]["storage"]["local_data_dir"] == (
        "~/.deal-intel/local-data"
    )
    command_blob = json.dumps(payload["profiles"], ensure_ascii=False)
    assert "config init" not in command_blob
    assert "config doctor" not in command_blob


def test_config_profiles_cli_text_is_human_readable() -> None:
    result = CliRunner().invoke(app, ["config", "profiles"])

    assert result.exit_code == 0
    assert "Config profiles:" in result.stdout
    assert "- sample" in result.stdout
    assert "- full" in result.stdout
    assert "- pro" in result.stdout


def test_config_show_cli_summarizes_effective_config_without_secrets(
    monkeypatch,
    tmp_path,
) -> None:
    user_config = tmp_path / "config.yaml"
    user_config.write_text(
        "storage:\n"
        "  backend: local_sample\n"
        "llm:\n"
        "  provider: openai_api\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(_env, "_USER_CONFIG_PATH", user_config)
    monkeypatch.setenv(
        "MONGODB_URI",
        "configured-mongodb-uri-sentinel",
    )
    monkeypatch.setenv("OPENAI_API_KEY", "configured-openai-key-sentinel")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "configured-anthropic-key-sentinel")

    result = CliRunner().invoke(app, ["config", "show", "--json"])

    assert result.exit_code == 0
    assert "configured-mongodb-uri-sentinel" not in result.stdout
    assert "configured-openai-key-sentinel" not in result.stdout
    assert "configured-anthropic-key-sentinel" not in result.stdout
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["profile"] == "sample"
    assert payload["user_config_exists"] is True
    assert payload["effective_config"]["storage"]["backend"] == "local_sample"
    assert payload["effective_config"]["storage"]["local_data_dir"] == (
        "~/.deal-intel/local-data"
    )
    assert payload["effective_config"]["tools"] == {
        "surface": "auto",
        "resolved_surface": "sample",
            "mcp_tool_count": 23,
    }
    assert payload["effective_config"]["llm"]["provider"] == "openai_api"
    assert payload["environment"]["MONGODB_URI"]["configured"] is True
    assert payload["environment"]["OPENAI_API_KEY"]["configured"] is True
    assert payload["environment"]["ANTHROPIC_API_KEY"]["configured"] is True


def test_config_show_cli_uses_env_storage_override(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(_env, "_USER_CONFIG_PATH", tmp_path / "missing.yaml")
    monkeypatch.setenv("DEAL_INTEL_STORAGE_BACKEND", "local_sample")

    result = CliRunner().invoke(app, ["config", "show", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["profile"] == "sample"
    assert payload["user_config_exists"] is False
    assert payload["effective_config"]["storage"]["backend"] == "local_sample"
    assert payload["effective_config"]["storage"]["local_data_dir"] == (
        "~/.deal-intel/local-data"
    )
    assert payload["effective_config"]["tools"]["resolved_surface"] == "sample"
    assert payload["environment"]["DEAL_INTEL_STORAGE_BACKEND"]["configured"] is True


def test_config_show_cli_text_does_not_print_secret_values(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(_env, "_USER_CONFIG_PATH", tmp_path / "missing.yaml")
    monkeypatch.setenv("MONGODB_URI", "configured-mongodb-uri-sentinel")

    result = CliRunner().invoke(app, ["config", "show"])

    assert result.exit_code == 0
    assert "Config profile:" in result.stdout
    assert "MONGODB_URI" in result.stdout
    assert "configured-mongodb-uri-sentinel" not in result.stdout
