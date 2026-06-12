from __future__ import annotations

import json

import pytest

from deal_intel import _env
from deal_intel.config_doctor import build_config_doctor_report
from deal_intel.config_profiles import get_config_profile, profile_names
from deal_intel.config_writer import init_config_profile
from deal_intel.profile_smoke_matrix import (
    build_profile_smoke_matrix,
    get_profile_smoke_contract,
    list_profile_smoke_contracts,
)
from deal_intel.providers.llm import ChatGPTOAuthProvider


def _status(result: dict, check_id: str) -> str:
    return next(check for check in result["checks"] if check["id"] == check_id)[
        "status"
    ]


def _cfg_from_contract(profile: str) -> dict:
    contract = get_profile_smoke_contract(profile)
    return {
        "storage": {"backend": contract.storage_backend},
        "mongodb": {
            "database": "deal_intel",
            "vector_search": contract.vector_search,
        },
        "llm": {
            "provider": contract.llm_provider,
            "chatgpt_oauth_model": "gpt-5.5",
            "openai_api_model": "gpt-5.4-mini",
            "draft_model": "claude-sonnet-4-6",
        },
    }


def _sample_ping() -> dict:
    return {
        "status": "ok",
        "storage_backend": "local_sample",
        "database": "local_sample",
        "sample_dataset": "zero_config_sample",
        "sample_dataset_version": "v1",
        "deal_count": 12,
        "snapshot_count": 24,
    }


def _never_ping() -> dict:
    raise AssertionError("offline matrix checks must not call storage ping")


def test_profile_smoke_matrix_is_stable_and_serializable() -> None:
    matrix = build_profile_smoke_matrix()

    assert matrix["ok"] is True
    assert matrix["matrix_version"] == 1
    assert [profile["profile"] for profile in matrix["profiles"]] == [
        "sample",
        "full",
        "pro",
    ]
    json.dumps(matrix, ensure_ascii=False)


def test_profile_smoke_contract_matches_profile_patches() -> None:
    for contract in list_profile_smoke_contracts():
        profile = get_config_profile(contract.profile)

        expected = {
            "storage.backend": profile.config_patch["storage"]["backend"],
            "mongodb.vector_search": profile.config_patch["mongodb"]["vector_search"],
            "llm.provider": profile.config_patch["llm"]["provider"],
        }
        if "local_data_dir" in profile.config_patch["storage"]:
            expected["storage.local_data_dir"] = profile.config_patch["storage"][
                "local_data_dir"
            ]
        assert contract.profile_values() == expected
        assert profile.first_run_commands == tuple(
            contract.to_dict()["first_run_commands"]
        )


@pytest.mark.parametrize("profile", profile_names())
def test_config_init_dry_run_tracks_profile_smoke_values(tmp_path, profile: str) -> None:
    contract = get_profile_smoke_contract(profile)

    result = init_config_profile(
        profile,
        config_path=tmp_path / "config.yaml",
        dry_run=True,
    )

    assert result["ok"] is True
    assert result["storage_written"] is False
    assert result["target_profile_values"] == contract.profile_values()
    assert result["doctor"]["summary"]["storage_backend"] == contract.storage_backend
    assert result["doctor"]["summary"]["vector_search"] == contract.vector_search
    assert result["doctor"]["summary"]["llm_provider"] == contract.llm_provider


def test_sample_profile_smoke_is_zero_config_read_only(monkeypatch, tmp_path) -> None:
    contract = get_profile_smoke_contract("sample")
    monkeypatch.setattr(_env, "_USER_CONFIG_PATH", tmp_path / "missing.yaml")
    monkeypatch.setattr(ChatGPTOAuthProvider, "_TOKEN_PATH", tmp_path / "missing.json")
    monkeypatch.delenv("MONGODB_URI", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    assert contract.bi_smoke_required_setup == ()
    assert contract.write_policy == "read_only"

    offline = build_config_doctor_report(
        _cfg_from_contract("sample"),
        offline=True,
        storage_ping=_never_ping,
    )
    live_sample = build_config_doctor_report(
        _cfg_from_contract("sample"),
        storage_ping=_sample_ping,
    )

    assert offline["ok"] is True
    assert _status(offline, "sample_storage") == "skipped"
    assert _status(offline, "llm_provider") == "warn"
    assert live_sample["ok"] is True
    assert _status(live_sample, "sample_storage") == "pass"
    assert _status(live_sample, "llm_provider") == "warn"


def test_full_profile_unconfigured_and_ready_smoke_contract(monkeypatch, tmp_path) -> None:
    contract = get_profile_smoke_contract("full")
    monkeypatch.setattr(_env, "_USER_CONFIG_PATH", tmp_path / "missing.yaml")
    monkeypatch.setattr(ChatGPTOAuthProvider, "_TOKEN_PATH", tmp_path / "missing.json")
    monkeypatch.delenv("MONGODB_URI", raising=False)

    assert contract.bi_smoke_required_setup == ("MONGODB_URI",)
    assert contract.write_policy == "read_check_only"

    unconfigured = build_config_doctor_report(
        _cfg_from_contract("full"),
        offline=True,
        storage_ping=_never_ping,
    )

    assert unconfigured["ok"] is False
    for check_id in contract.unconfigured_offline_fail_checks:
        assert _status(unconfigured, check_id) == "fail"
    for check_id in contract.unconfigured_offline_warning_checks:
        assert _status(unconfigured, check_id) == "warn"

    monkeypatch.setenv("MONGODB_URI", "configured-mongodb-uri-sentinel")
    ready = build_config_doctor_report(
        _cfg_from_contract("full"),
        offline=True,
        storage_ping=_never_ping,
    )

    assert ready["ok"] is True
    assert _status(ready, "mongodb_uri") == "pass"
    assert _status(ready, "llm_provider") == "warn"
    assert "configured-mongodb-uri-sentinel" not in json.dumps(
        ready,
        ensure_ascii=False,
    )


def test_pro_profile_unconfigured_and_ready_smoke_contract(monkeypatch, tmp_path) -> None:
    contract = get_profile_smoke_contract("pro")
    monkeypatch.setattr(_env, "_USER_CONFIG_PATH", tmp_path / "missing.yaml")
    monkeypatch.delenv("MONGODB_URI", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    assert contract.bi_smoke_required_setup == (
        "MONGODB_URI",
        "Atlas M10+ cluster",
        "Atlas Vector Search index",
    )
    assert contract.llm_tool_required_setup == ("OPENAI_API_KEY",)

    unconfigured = build_config_doctor_report(
        _cfg_from_contract("pro"),
        offline=True,
        storage_ping=_never_ping,
    )

    assert unconfigured["ok"] is False
    for check_id in contract.unconfigured_offline_fail_checks:
        assert _status(unconfigured, check_id) == "fail"
    for check_id in contract.unconfigured_offline_warning_checks:
        assert _status(unconfigured, check_id) == "warn"

    monkeypatch.setenv("MONGODB_URI", "configured-mongodb-uri-sentinel")
    monkeypatch.setenv("OPENAI_API_KEY", "configured-openai-key-sentinel")
    ready = build_config_doctor_report(
        _cfg_from_contract("pro"),
        offline=True,
        storage_ping=_never_ping,
    )

    assert ready["ok"] is True
    assert _status(ready, "mongodb_uri") == "pass"
    assert _status(ready, "llm_provider") == "pass"
    assert _status(ready, "vector_search") == "warn"
    payload = json.dumps(ready, ensure_ascii=False)
    assert "configured-mongodb-uri-sentinel" not in payload
    assert "configured-openai-key-sentinel" not in payload
