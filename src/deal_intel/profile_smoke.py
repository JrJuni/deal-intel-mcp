from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from deal_intel.config_doctor import build_config_doctor_report
from deal_intel.config_profiles import infer_config_profile, merge_profile_patch
from deal_intel.profile_smoke_matrix import get_profile_smoke_contract
from deal_intel.storage.local_sample import LocalSampleClient
from deal_intel.storage.mongodb import MongoDBClient

StoragePing = Callable[[], dict[str, Any]]


def build_profile_smoke_report(
    profile_name: str,
    base_config: dict[str, Any],
    *,
    offline: bool = False,
    storage_ping: StoragePing | None = None,
) -> dict[str, Any]:
    """Build a no-write first-run smoke report for a target profile."""

    contract = get_profile_smoke_contract(profile_name)
    target_config = merge_profile_patch(base_config, contract.profile)
    target_values = contract.profile_values()
    current_profile = infer_config_profile(base_config)
    generated_at = datetime.now(UTC).isoformat(timespec="seconds")

    doctor = build_config_doctor_report(
        target_config,
        offline=offline,
        storage_ping=storage_ping or _storage_ping_for_config(target_config),
    )
    checks = _build_contract_checks(contract=contract, target_config=target_config)
    failed_contract_checks = sum(1 for check in checks if check["status"] == "fail")

    next_actions = list(doctor.get("next_actions") or [])
    if current_profile != contract.profile:
        next_actions.append(
            {
                "check_id": "profile_switch",
                "action": (
                    "Preview `deal-intel config switch "
                    f"{contract.profile} --dry-run` before changing user config."
                ),
            }
        )

    return {
        "ok": doctor["ok"] and failed_contract_checks == 0,
        "profile": contract.profile,
        "current_profile": current_profile,
        "generated_at": generated_at,
        "offline": offline,
        "target_profile_values": target_values,
        "contract": contract.to_dict(),
        "doctor": doctor,
        "checks": checks,
        "next_actions": next_actions,
    }


def _storage_ping_for_config(cfg: dict[str, Any]) -> StoragePing:
    def _ping() -> dict[str, Any]:
        storage = _mapping(cfg.get("storage"))
        backend = storage.get("backend", "mongo")
        if backend == "local_sample":
            return LocalSampleClient(
                local_data_dir=storage.get("local_data_dir")
            ).ping()
        database = _mapping(cfg.get("mongodb")).get("database", "deal_intel")
        return MongoDBClient(database=database).ping()

    return _ping


def _build_contract_checks(
    *,
    contract,
    target_config: dict[str, Any],
) -> list[dict[str, Any]]:
    target_values = {
        "storage.backend": _mapping(target_config.get("storage")).get("backend"),
        "mongodb.vector_search": _mapping(target_config.get("mongodb")).get(
            "vector_search"
        ),
        "llm.provider": _mapping(target_config.get("llm")).get("provider"),
    }
    storage = _mapping(target_config.get("storage"))
    if "local_data_dir" in storage:
        target_values["storage.local_data_dir"] = storage["local_data_dir"]
    expected_values = contract.profile_values()
    return [
        {
            "id": "profile_values",
            "label": "Profile-managed values",
            "status": "pass" if target_values == expected_values else "fail",
            "message": (
                "Target config matches the smoke contract."
                if target_values == expected_values
                else "Target config differs from the smoke contract."
            ),
            "details": {
                "expected": expected_values,
                "actual": target_values,
            },
        },
        {
            "id": "write_policy",
            "label": "Write policy",
            "status": "pass",
            "message": f"Smoke is {contract.write_policy}; no writes are attempted.",
            "details": {"write_policy": contract.write_policy},
        },
        {
            "id": "live_call_boundary",
            "label": "Live-call boundary",
            "status": "pass",
            "message": "No LLM completions, embeddings, Atlas admin APIs, or writes are called.",
            "details": {"no_live_calls": list(contract.no_live_calls)},
        },
    ]


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
