from __future__ import annotations

import json

from typer.testing import CliRunner

from deal_intel import _env
from deal_intel.cli import app
from deal_intel.profile_smoke import build_profile_smoke_report
from deal_intel.providers.llm import ChatGPTOAuthProvider


def _status(result: dict, check_id: str) -> str:
    return next(check for check in result["doctor"]["checks"] if check["id"] == check_id)[
        "status"
    ]


def _missing_user_config(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(_env, "_USER_CONFIG_PATH", tmp_path / "missing.yaml")


def test_profile_smoke_sample_passes_without_external_setup(monkeypatch, tmp_path) -> None:
    _missing_user_config(monkeypatch, tmp_path)
    monkeypatch.setattr(ChatGPTOAuthProvider, "_TOKEN_PATH", tmp_path / "missing.json")
    monkeypatch.delenv("MONGODB_URI", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    result = build_profile_smoke_report("sample", {}, offline=False)

    assert result["ok"] is True
    assert result["profile"] == "sample"
    assert result["target_profile_values"] == {
        "storage.backend": "local_sample",
        "storage.local_data_dir": "~/.deal-intel/local-data",
        "mongodb.vector_search": "python_cosine",
        "llm.provider": "chatgpt_oauth",
    }
    assert _status(result, "sample_storage") == "pass"
    assert _status(result, "llm_provider") == "warn"


def test_profile_smoke_full_missing_mongodb_fails_offline(monkeypatch, tmp_path) -> None:
    _missing_user_config(monkeypatch, tmp_path)
    monkeypatch.setattr(ChatGPTOAuthProvider, "_TOKEN_PATH", tmp_path / "missing.json")
    monkeypatch.delenv("MONGODB_URI", raising=False)

    result = build_profile_smoke_report("full", {}, offline=True)

    assert result["ok"] is False
    assert result["profile"] == "full"
    assert _status(result, "mongodb_uri") == "fail"
    assert _status(result, "storage_ping") == "skipped"
    assert _status(result, "llm_provider") == "warn"


def test_profile_smoke_pro_ready_is_secret_safe(monkeypatch, tmp_path) -> None:
    _missing_user_config(monkeypatch, tmp_path)
    monkeypatch.setenv("MONGODB_URI", "configured-mongodb-uri-sentinel")
    monkeypatch.setenv("OPENAI_API_KEY", "configured-openai-key-sentinel")

    result = build_profile_smoke_report("pro", {}, offline=True)

    assert result["ok"] is True
    assert result["profile"] == "pro"
    assert _status(result, "mongodb_uri") == "pass"
    assert _status(result, "llm_provider") == "pass"
    assert _status(result, "vector_search") == "warn"
    payload = json.dumps(result, ensure_ascii=False)
    assert "configured-mongodb-uri-sentinel" not in payload
    assert "configured-openai-key-sentinel" not in payload


def test_smoke_profile_cli_sample_json(monkeypatch, tmp_path) -> None:
    _missing_user_config(monkeypatch, tmp_path)
    monkeypatch.setattr(ChatGPTOAuthProvider, "_TOKEN_PATH", tmp_path / "missing.json")
    monkeypatch.delenv("MONGODB_URI", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    result = CliRunner().invoke(
        app,
        ["smoke-profile", "--profile", "sample", "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["profile"] == "sample"
    assert payload["contract"]["write_policy"] == "read_only"
    assert payload["doctor"]["summary"]["storage_backend"] == "local_sample"


def test_smoke_profile_cli_full_missing_uri_exits_nonzero(
    monkeypatch,
    tmp_path,
) -> None:
    _missing_user_config(monkeypatch, tmp_path)
    monkeypatch.setattr(ChatGPTOAuthProvider, "_TOKEN_PATH", tmp_path / "missing.json")
    monkeypatch.delenv("MONGODB_URI", raising=False)

    result = CliRunner().invoke(
        app,
        ["smoke-profile", "--profile", "full", "--offline", "--json"],
    )

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["profile"] == "full"
    assert _status(payload, "mongodb_uri") == "fail"


def test_smoke_profile_cli_rejects_unknown_profile() -> None:
    result = CliRunner().invoke(app, ["smoke-profile", "--profile", "enterprise"])

    assert result.exit_code == 1
    assert "profile must be one of: sample, full, pro" in result.stdout
