from __future__ import annotations

import os
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from deal_intel import _env
from deal_intel.config_profiles import list_config_profiles
from deal_intel.providers.llm import make_llm_provider
from deal_intel.storage.diagnostics import local_sample_mode_hint
from deal_intel.tool_surfaces import resolve_tool_surface, tool_names_for_config

CheckStatus = str
StoragePing = Callable[[], dict[str, Any]]

_VALID_STORAGE_BACKENDS = {"mongo", "local_sample"}
_VALID_VECTOR_SEARCH_MODES = {"python_cosine", "atlas"}
_VALID_LLM_PROVIDERS = {"chatgpt_oauth", "openai_api", "anthropic"}
_VALID_TOOL_SURFACES = {"auto", "sample", "standard", "developer"}
_SECRET_ENV_KEYS = ("MONGODB_URI", "ANTHROPIC_API_KEY", "OPENAI_API_KEY")


def build_config_doctor_report(
    cfg: dict[str, Any],
    *,
    offline: bool = False,
    storage_ping: StoragePing | None = None,
) -> dict[str, Any]:
    """Build a secret-safe setup diagnostic report.

    The doctor is read-only. It may call the provided storage ping function
    unless offline=True, but it never calls LLM completion APIs or embeddings.
    """

    checks: list[dict[str, Any]] = []
    profile = _infer_exact_profile(cfg)
    storage = _mapping(cfg.get("storage"))
    mongodb = _mapping(cfg.get("mongodb"))
    llm = _mapping(cfg.get("llm"))
    tools = _mapping(cfg.get("tools"))

    backend = storage.get("backend", "mongo")
    database = mongodb.get("database", "deal_intel")
    vector_search = mongodb.get("vector_search", "python_cosine")
    provider_name = llm.get("provider", "chatgpt_oauth")
    configured_tool_surface = tools.get("surface", "auto")
    resolved_tool_surface, mcp_tool_count = _resolve_surface_summary(cfg)

    _add_check(
        checks,
        check_id="profile",
        label="Effective profile",
        status="pass" if profile != "custom" else "warn",
        message=(
            f"Effective config matches the {profile} profile."
            if profile != "custom"
            else "Effective config does not exactly match sample/full/pro."
        ),
        details={"profile": profile},
        hint="Run `deal-intel config profiles` to compare supported profiles."
        if profile == "custom"
        else None,
    )
    _add_user_config_check(checks)
    _add_storage_backend_check(checks, backend)
    _add_tool_surface_check(
        checks,
        configured_surface=configured_tool_surface,
        resolved_surface=resolved_tool_surface,
        mcp_tool_count=mcp_tool_count,
    )
    _add_mongo_readiness_check(
        checks,
        backend=backend,
        database=database,
        offline=offline,
        storage_ping=storage_ping,
    )
    _add_vector_search_check(
        checks,
        backend=backend,
        vector_search=vector_search,
    )
    _add_llm_provider_check(checks, cfg=cfg, provider_name=provider_name)

    status_counts = _status_counts(checks)
    failed = status_counts.get("fail", 0)
    warnings = status_counts.get("warn", 0)
    skipped = status_counts.get("skipped", 0)
    report = {
        "ok": failed == 0,
        "profile": profile,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "summary": {
            "status": "ready" if failed == 0 else "needs_attention",
            "offline": offline,
            "storage_backend": backend,
            "mongodb_database": database,
            "vector_search": vector_search,
            "llm_provider": provider_name,
            "tools_surface": configured_tool_surface,
            "resolved_tool_surface": resolved_tool_surface,
            "mcp_tool_count": mcp_tool_count,
            "failed_checks": failed,
            "warning_checks": warnings,
            "skipped_checks": skipped,
        },
        "checks": checks,
        "next_actions": _next_actions(checks),
    }
    return report


def _add_user_config_check(checks: list[dict[str, Any]]) -> None:
    path = _env.user_config_path()
    exists = path.exists()
    if not exists:
        _add_check(
            checks,
            check_id="user_config",
            label="User config",
            status="pass",
            message="No user config file found; defaults and env overrides are in use.",
            details={"exists": False, "path": str(path)},
        )
        return

    try:
        path.read_text(encoding="utf-8")
    except Exception as exc:
        _add_check(
            checks,
            check_id="user_config",
            label="User config",
            status="fail",
            message=f"User config exists but could not be read: {type(exc).__name__}",
            details={"exists": True, "path": str(path)},
            hint="Fix file permissions or replace the config file.",
        )
        return

    _add_check(
        checks,
        check_id="user_config",
        label="User config",
        status="pass",
        message="User config file is readable.",
        details={"exists": True, "path": str(path)},
    )


def _add_storage_backend_check(checks: list[dict[str, Any]], backend: Any) -> None:
    if backend in _VALID_STORAGE_BACKENDS:
        _add_check(
            checks,
            check_id="storage_backend",
            label="Storage backend",
            status="pass",
            message=f"storage.backend is {backend}.",
            details={"storage_backend": backend},
        )
        return

    _add_check(
        checks,
        check_id="storage_backend",
        label="Storage backend",
        status="fail",
        message="storage.backend must be 'mongo' or 'local_sample'.",
        details={"storage_backend": backend},
        hint="Set storage.backend to mongo or local_sample.",
    )


def _add_tool_surface_check(
    checks: list[dict[str, Any]],
    *,
    configured_surface: Any,
    resolved_surface: str | None,
    mcp_tool_count: int,
) -> None:
    if configured_surface in _VALID_TOOL_SURFACES:
        _add_check(
            checks,
            check_id="tool_surface",
            label="MCP tool surface",
            status="pass",
            message=(
                f"tools.surface is {configured_surface}; MCP will expose "
                f"{mcp_tool_count} tool(s) through the {resolved_surface} surface."
            ),
            details={
                "tools_surface": configured_surface,
                "resolved_tool_surface": resolved_surface,
                "mcp_tool_count": mcp_tool_count,
            },
        )
        return

    _add_check(
        checks,
        check_id="tool_surface",
        label="MCP tool surface",
        status="fail",
        message="tools.surface must be auto, sample, standard, or developer.",
        details={
            "tools_surface": configured_surface,
            "resolved_tool_surface": resolved_surface,
            "mcp_tool_count": mcp_tool_count,
        },
        hint="Set tools.surface to auto, sample, standard, or developer.",
    )


def _add_mongo_readiness_check(
    checks: list[dict[str, Any]],
    *,
    backend: Any,
    database: Any,
    offline: bool,
    storage_ping: StoragePing | None,
) -> None:
    if backend == "local_sample":
        _add_sample_storage_check(
            checks,
            offline=offline,
            storage_ping=storage_ping,
        )
        return
    if backend != "mongo":
        _add_check(
            checks,
            check_id="storage_ping",
            label="Storage ping",
            status="skipped",
            message="Storage ping skipped because storage.backend is invalid.",
        )
        return

    if not os.environ.get("MONGODB_URI"):
        _add_check(
            checks,
            check_id="mongodb_uri",
            label="MongoDB URI",
            status="fail",
            message="MONGODB_URI is not configured for mongo storage.",
            details={"configured": False, "database": database},
            hint={
                "fix": "Set MONGODB_URI in .env or switch to local_sample.",
                "sample_mode": local_sample_mode_hint(),
            },
        )
    else:
        _add_check(
            checks,
            check_id="mongodb_uri",
            label="MongoDB URI",
            status="pass",
            message="MONGODB_URI is configured.",
            details={"configured": True, "database": database},
        )

    _add_storage_ping_check(
        checks,
        offline=offline,
        storage_ping=storage_ping,
    )


def _add_sample_storage_check(
    checks: list[dict[str, Any]],
    *,
    offline: bool,
    storage_ping: StoragePing | None,
) -> None:
    if offline:
        _add_check(
            checks,
            check_id="sample_storage",
            label="Sample storage",
            status="skipped",
            message="Sample storage ping skipped in offline mode.",
        )
        return
    _add_storage_ping_check(
        checks,
        offline=offline,
        storage_ping=storage_ping,
        check_id="sample_storage",
        label="Sample storage",
    )


def _add_storage_ping_check(
    checks: list[dict[str, Any]],
    *,
    offline: bool,
    storage_ping: StoragePing | None,
    check_id: str = "storage_ping",
    label: str = "Storage ping",
) -> None:
    if offline:
        _add_check(
            checks,
            check_id=check_id,
            label=label,
            status="skipped",
            message="Storage ping skipped in offline mode.",
        )
        return
    if storage_ping is None:
        _add_check(
            checks,
            check_id=check_id,
            label=label,
            status="skipped",
            message="No storage ping function was provided.",
        )
        return

    try:
        ping = storage_ping()
    except Exception as exc:
        _add_check(
            checks,
            check_id=check_id,
            label=label,
            status="fail",
            message=f"Storage ping failed: {type(exc).__name__}: {exc}",
            hint=local_sample_mode_hint(),
        )
        return

    status = ping.get("status")
    if status == "ok":
        _add_check(
            checks,
            check_id=check_id,
            label=label,
            status="pass",
            message="Storage ping succeeded.",
            details=_safe_ping_details(ping),
        )
        return

    _add_check(
        checks,
        check_id=check_id,
        label=label,
        status="fail",
        message=str(ping.get("message") or f"Storage ping returned {status}."),
        details=_safe_ping_details(ping),
        hint=ping.get("sample_mode_hint") or ping.get("fix") or local_sample_mode_hint(),
    )


def _add_vector_search_check(
    checks: list[dict[str, Any]],
    *,
    backend: Any,
    vector_search: Any,
) -> None:
    if vector_search not in _VALID_VECTOR_SEARCH_MODES:
        _add_check(
            checks,
            check_id="vector_search",
            label="Vector search mode",
            status="fail",
            message="mongodb.vector_search must be 'python_cosine' or 'atlas'.",
            details={"vector_search": vector_search},
            hint="Set mongodb.vector_search to python_cosine or atlas.",
        )
        return

    if vector_search == "atlas":
        status = "warn" if backend == "mongo" else "fail"
        _add_check(
            checks,
            check_id="vector_search",
            label="Vector search mode",
            status=status,
            message=(
                "Atlas Vector Search is selected; doctor does not verify cluster tier "
                "or index existence."
            ),
            details={
                "vector_search": "atlas",
                "requires": "MongoDB Atlas M10+ and a vector index",
            },
            hint="Use python_cosine on M0/free clusters or verify the Atlas index manually.",
        )
        return

    _add_check(
        checks,
        check_id="vector_search",
        label="Vector search mode",
        status="pass",
        message="Python cosine vector search is selected.",
        details={"vector_search": "python_cosine"},
    )


def _add_llm_provider_check(
    checks: list[dict[str, Any]],
    *,
    cfg: dict[str, Any],
    provider_name: Any,
) -> None:
    if provider_name not in _VALID_LLM_PROVIDERS:
        _add_check(
            checks,
            check_id="llm_provider",
            label="LLM provider",
            status="fail",
            message="llm.provider must be chatgpt_oauth, openai_api, or anthropic.",
            details={"llm_provider": provider_name},
            hint="Set DEAL_INTEL_LLM_PROVIDER or llm.provider to a valid provider.",
        )
        return

    try:
        ping = make_llm_provider(cfg).ping()
    except Exception as exc:
        _add_check(
            checks,
            check_id="llm_provider",
            label="LLM provider",
            status="fail",
            message=f"LLM provider config failed: {type(exc).__name__}: {exc}",
            details={"llm_provider": provider_name},
        )
        return

    ping_status = ping.get("status")
    if ping_status == "ok":
        _add_check(
            checks,
            check_id="llm_provider",
            label="LLM provider",
            status="pass",
            message=f"{provider_name} readiness check passed.",
            details=_safe_llm_ping_details(provider_name, ping),
        )
        return

    status = "warn" if provider_name == "chatgpt_oauth" else "fail"
    _add_check(
        checks,
        check_id="llm_provider",
        label="LLM provider",
        status=status,
        message=str(ping.get("message") or f"{provider_name} is not ready."),
        details=_safe_llm_ping_details(provider_name, ping),
        hint=ping.get("fix"),
    )


def _add_check(
    checks: list[dict[str, Any]],
    *,
    check_id: str,
    label: str,
    status: CheckStatus,
    message: str,
    details: dict[str, Any] | None = None,
    hint: str | dict[str, Any] | None = None,
) -> None:
    checks.append(
        {
            "id": check_id,
            "label": label,
            "status": status,
            "severity": _severity_for_status(status),
            "message": _redact_known_secrets(message),
            "details": _redact_known_secrets(details or {}),
            "hint": _redact_known_secrets(hint),
        }
    )


def _infer_exact_profile(cfg: dict[str, Any]) -> str:
    storage = _mapping(cfg.get("storage"))
    mongodb = _mapping(cfg.get("mongodb"))
    llm = _mapping(cfg.get("llm"))
    current = {
        "storage": {"backend": storage.get("backend", "mongo")},
        "mongodb": {"vector_search": mongodb.get("vector_search", "python_cosine")},
        "llm": {"provider": llm.get("provider", "chatgpt_oauth")},
    }
    for profile in list_config_profiles():
        patch = profile.config_patch
        expected = {
            "storage": {"backend": patch["storage"]["backend"]},
            "mongodb": {"vector_search": patch["mongodb"]["vector_search"]},
            "llm": {"provider": patch["llm"]["provider"]},
        }
        if current == expected:
            return profile.name
    return "custom"


def _status_counts(checks: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"pass": 0, "warn": 0, "fail": 0, "skipped": 0}
    for check in checks:
        status = str(check.get("status") or "")
        if status in counts:
            counts[status] += 1
    return counts


def _next_actions(checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for check in checks:
        if check.get("status") not in {"warn", "fail"}:
            continue
        hint = check.get("hint")
        if not hint:
            continue
        actions.append(
            {
                "check_id": check["id"],
                "severity": check["severity"],
                "action": hint,
            }
        )
    return actions


def _safe_ping_details(ping: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "status",
        "storage_backend",
        "database",
        "sample_dataset",
        "sample_dataset_version",
        "data_mode",
        "deal_count",
        "snapshot_count",
        "local_data_dir",
        "local_deal_count",
        "fixture_archived",
        "message",
        "fix",
    }
    return {
        key: value
        for key, value in ping.items()
        if key in allowed and not isinstance(value, (bytes, bytearray))
    }


def _safe_llm_ping_details(provider_name: str, ping: dict[str, Any]) -> dict[str, Any]:
    allowed = {"status", "model", "message", "fix"}
    details = {
        key: value
        for key, value in ping.items()
        if key in allowed and not isinstance(value, (bytes, bytearray))
    }
    details["llm_provider"] = provider_name
    return details


def _resolve_surface_summary(cfg: dict[str, Any]) -> tuple[str | None, int]:
    try:
        return resolve_tool_surface(cfg), len(tool_names_for_config(cfg))
    except ValueError:
        return None, 1


def _severity_for_status(status: str) -> str:
    if status == "fail":
        return "error"
    if status == "warn":
        return "warning"
    return "info"


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _redact_known_secrets(value: Any) -> Any:
    if isinstance(value, str):
        redacted = value
        for key in _SECRET_ENV_KEYS:
            secret = os.environ.get(key)
            if secret:
                redacted = redacted.replace(secret, f"<redacted:{key}>")
        return redacted
    if isinstance(value, dict):
        return {
            key: _redact_known_secrets(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_known_secrets(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact_known_secrets(item) for item in value)
    return value
