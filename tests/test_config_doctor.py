from __future__ import annotations

import asyncio
import json

from typer.testing import CliRunner

from deal_intel import _context, _env, mcp_server
from deal_intel.cli import app
from deal_intel.config_doctor import build_config_doctor_report
from deal_intel.providers.llm import ChatGPTOAuthProvider


def _cfg(
    *,
    storage_backend: str = "local_sample",
    vector_search: str = "python_cosine",
    llm_provider: str = "chatgpt_oauth",
) -> dict:
    return {
        "storage": {"backend": storage_backend},
        "mongodb": {
            "database": "deal_intel",
            "vector_search": vector_search,
        },
        "llm": {
            "provider": llm_provider,
            "chatgpt_oauth_model": "gpt-5.5",
            "openai_api_model": "gpt-5.5",
            "draft_model": "claude-sonnet-4-6",
        },
    }


def _ok_sample_ping() -> dict:
    return {
        "status": "ok",
        "storage_backend": "local_sample",
        "database": "local_sample",
        "sample_dataset": "zero_config_sample",
        "sample_dataset_version": "v1",
        "deal_count": 10,
        "snapshot_count": 20,
    }


def _status(result: dict, check_id: str) -> str:
    return next(check for check in result["checks"] if check["id"] == check_id)[
        "status"
    ]


def test_config_doctor_sample_profile_passes_without_mongodb_uri(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(_env, "_USER_CONFIG_PATH", tmp_path / "missing.yaml")
    monkeypatch.setattr(ChatGPTOAuthProvider, "_TOKEN_PATH", tmp_path / "missing.json")
    monkeypatch.delenv("MONGODB_URI", raising=False)

    result = build_config_doctor_report(
        _cfg(),
        storage_ping=_ok_sample_ping,
    )

    assert result["ok"] is True
    assert result["profile"] == "sample"
    assert _status(result, "tool_surface") == "pass"
    assert result["summary"]["resolved_tool_surface"] == "sample"
    assert _status(result, "sample_storage") == "pass"
    assert _status(result, "llm_provider") == "warn"


def test_config_doctor_full_profile_fails_when_mongodb_uri_is_missing(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(_env, "_USER_CONFIG_PATH", tmp_path / "missing.yaml")
    monkeypatch.delenv("MONGODB_URI", raising=False)

    result = build_config_doctor_report(
        _cfg(storage_backend="mongo"),
        storage_ping=lambda: {
            "status": "missing_uri",
            "message": "MONGODB_URI is not set",
        },
    )

    assert result["ok"] is False
    assert result["profile"] == "full"
    assert _status(result, "mongodb_uri") == "fail"
    assert result["next_actions"]


def test_config_doctor_pro_profile_warns_about_atlas_vector_search(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(_env, "_USER_CONFIG_PATH", tmp_path / "missing.yaml")
    monkeypatch.setenv("MONGODB_URI", "configured-mongodb-uri-sentinel")
    monkeypatch.setenv("OPENAI_API_KEY", "configured-openai-key-sentinel")

    result = build_config_doctor_report(
        _cfg(
            storage_backend="mongo",
            vector_search="atlas",
            llm_provider="openai_api",
        ),
        storage_ping=lambda: {"status": "ok", "database": "deal_intel"},
    )

    assert result["ok"] is True
    assert result["profile"] == "pro"
    assert _status(result, "vector_search") == "warn"
    payload = json.dumps(result, ensure_ascii=False)
    assert "configured-mongodb-uri-sentinel" not in payload
    assert "configured-openai-key-sentinel" not in payload


def test_config_doctor_openai_api_without_key_fails(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(_env, "_USER_CONFIG_PATH", tmp_path / "missing.yaml")
    monkeypatch.setenv("MONGODB_URI", "configured-mongodb-uri-sentinel")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = build_config_doctor_report(
        _cfg(
            storage_backend="mongo",
            vector_search="atlas",
            llm_provider="openai_api",
        ),
        storage_ping=lambda: {"status": "ok", "database": "deal_intel"},
    )

    assert result["ok"] is False
    assert _status(result, "llm_provider") == "fail"
    assert "OPENAI_API_KEY" in json.dumps(result, ensure_ascii=False)
    assert "configured-mongodb-uri-sentinel" not in json.dumps(
        result,
        ensure_ascii=False,
    )


def test_config_doctor_redacts_secret_values_from_error_messages(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(_env, "_USER_CONFIG_PATH", tmp_path / "missing.yaml")
    monkeypatch.setattr(ChatGPTOAuthProvider, "_TOKEN_PATH", tmp_path / "missing.json")
    monkeypatch.setenv("MONGODB_URI", "configured-mongodb-uri-sentinel")

    result = build_config_doctor_report(
        _cfg(storage_backend="mongo"),
        storage_ping=lambda: {
            "status": "error",
            "message": "failed for configured-mongodb-uri-sentinel",
        },
    )

    payload = json.dumps(result, ensure_ascii=False)
    assert "configured-mongodb-uri-sentinel" not in payload
    assert "<redacted:MONGODB_URI>" in payload


def test_config_doctor_offline_skips_storage_ping(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(_env, "_USER_CONFIG_PATH", tmp_path / "missing.yaml")
    monkeypatch.setattr(ChatGPTOAuthProvider, "_TOKEN_PATH", tmp_path / "missing.json")

    def fail_if_called() -> dict:
        raise AssertionError("offline doctor must not call storage ping")

    result = build_config_doctor_report(
        _cfg(),
        offline=True,
        storage_ping=fail_if_called,
    )

    assert result["ok"] is True
    assert _status(result, "sample_storage") == "skipped"


def test_config_doctor_invalid_tool_surface_fails(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(_env, "_USER_CONFIG_PATH", tmp_path / "missing.yaml")
    monkeypatch.setattr(ChatGPTOAuthProvider, "_TOKEN_PATH", tmp_path / "missing.json")

    result = build_config_doctor_report(
        {
            **_cfg(),
            "tools": {"surface": "everything"},
        },
        storage_ping=_ok_sample_ping,
    )

    assert result["ok"] is False
    assert _status(result, "tool_surface") == "fail"
    assert result["summary"]["resolved_tool_surface"] is None
    assert result["summary"]["mcp_tool_count"] == 1


def test_config_doctor_cli_json_and_text_are_secret_safe(monkeypatch, tmp_path) -> None:
    user_config = tmp_path / "config.yaml"
    user_config.write_text(
        "storage:\n"
        "  backend: local_sample\n"
        "llm:\n"
        "  provider: openai_api\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(_env, "_USER_CONFIG_PATH", user_config)
    monkeypatch.setenv("OPENAI_API_KEY", "configured-openai-key-sentinel")
    monkeypatch.delenv("MONGODB_URI", raising=False)

    json_result = CliRunner().invoke(app, ["config", "doctor", "--json"])
    text_result = CliRunner().invoke(app, ["config", "doctor"])

    assert json_result.exit_code == 0
    assert text_result.exit_code == 0
    assert "configured-openai-key-sentinel" not in json_result.stdout
    assert "configured-openai-key-sentinel" not in text_result.stdout
    payload = json.loads(json_result.stdout)
    assert payload["ok"] is True
    assert payload["summary"]["storage_backend"] == "local_sample"


def test_config_doctor_cli_exits_nonzero_on_fail(monkeypatch, tmp_path) -> None:
    user_config = tmp_path / "config.yaml"
    user_config.write_text(
        "storage:\n"
        "  backend: local_sample\n"
        "llm:\n"
        "  provider: openai_api\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(_env, "_USER_CONFIG_PATH", user_config)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = CliRunner().invoke(app, ["config", "doctor", "--json"])

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert _status(payload, "llm_provider") == "fail"


def test_config_doctor_mcp_wrapper_uses_shared_report(monkeypatch, tmp_path) -> None:
    class FakeStorage:
        def ping(self) -> dict:
            return _ok_sample_ping()

    monkeypatch.setattr(_env, "_USER_CONFIG_PATH", tmp_path / "missing.yaml")
    monkeypatch.setattr(_context, "config", lambda: _cfg())
    monkeypatch.setattr(_context, "mongo", lambda: FakeStorage())
    monkeypatch.setattr(ChatGPTOAuthProvider, "_TOKEN_PATH", tmp_path / "missing.json")

    result = mcp_server.config_doctor()

    assert result["ok"] is True
    assert result["profile"] == "sample"
    assert _status(result, "sample_storage") == "pass"


def test_config_doctor_mcp_runtime_registers_tool(monkeypatch) -> None:
    monkeypatch.setattr(
        _context,
        "config",
        lambda: {"tools": {"surface": "developer"}},
    )
    tools = asyncio.run(mcp_server.app.list_tools())
    names = sorted(tool.name for tool in tools)

    assert len(names) == 23
    assert "config_doctor" in names
