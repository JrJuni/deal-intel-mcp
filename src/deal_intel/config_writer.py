from __future__ import annotations

import shutil
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml

from deal_intel import _env
from deal_intel.config_doctor import build_config_doctor_report
from deal_intel.config_profiles import get_config_profile

PROFILE_MANAGED_PATHS: tuple[tuple[str, str], ...] = (
    ("storage", "backend"),
    ("storage", "local_data_dir"),
    ("mongodb", "vector_search"),
    ("llm", "provider"),
)
CONFIG_UPDATE_PATHS: tuple[tuple[str, str], ...] = (
    ("llm", "provider"),
    ("llm", "chatgpt_oauth_model"),
    ("llm", "openai_api_model"),
    ("reporting", "output_dir"),
    ("reporting", "timezone"),
    ("tools", "surface"),
)
_VALID_LLM_PROVIDERS = {"chatgpt_oauth", "anthropic", "openai_api"}
_VALID_TOOL_SURFACES = {"auto", "sample", "standard", "developer"}


def init_config_profile(
    profile_name: str,
    *,
    config_path: Path | None = None,
    force: bool = False,
    dry_run: bool = False,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Prepare or write a new user config for a profile.

    If a user config already exists, actual writes require force=True and the
    previous file is backed up first. dry_run never writes.
    """

    path = config_path or _env.user_config_path()
    profile = get_config_profile(profile_name)
    target_config = deepcopy(profile.config_patch)
    exists = path.exists()
    backup_path = _backup_path(path, timestamp=timestamp) if exists else None
    blocked = exists and not force and not dry_run
    payload = _base_payload(
        command="init",
        profile_name=profile.name,
        path=path,
        force=force,
        dry_run=dry_run,
        exists_before=exists,
        target_config=target_config,
    )
    payload.update(
        {
            "changed_fields": _profile_field_changes({}, target_config),
            "backup_path": str(backup_path) if backup_path else None,
            "backup_written": False,
        }
    )

    if blocked:
        payload.update(
            {
                "ok": False,
                "error_code": "CONFIG_EXISTS",
                "message": (
                    "User config already exists. Use --force to back it up and "
                    "replace it, or use config switch to preserve custom settings."
                ),
                "requires_force": True,
            }
        )
        return payload

    if dry_run:
        payload["message"] = "Dry run only; no config file was written."
        return payload

    if exists:
        assert backup_path is not None
        _backup_existing_config(path, backup_path)
        payload["backup_written"] = True

    _write_yaml_config(path, target_config)
    payload.update(
        {
            "storage_written": True,
            "message": "User config initialized.",
        }
    )
    return payload


def switch_config_profile(
    profile_name: str,
    *,
    config_path: Path | None = None,
    force: bool = False,
    dry_run: bool = False,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Switch only profile-managed keys in an existing user config."""

    path = config_path or _env.user_config_path()
    profile = get_config_profile(profile_name)
    if not path.exists():
        target_config = deepcopy(profile.config_patch)
        payload = _base_payload(
            command="switch",
            profile_name=profile.name,
            path=path,
            force=force,
            dry_run=dry_run,
            exists_before=False,
            target_config=target_config,
        )
        payload.update(
            {
                "ok": False,
                "error_code": "CONFIG_NOT_FOUND",
                "message": (
                    "User config does not exist. Run config init --profile "
                    f"{profile.name} first."
                ),
                "changed_fields": _profile_field_changes({}, target_config),
                "backup_path": None,
                "backup_written": False,
            }
        )
        return payload

    existing = _read_yaml_config(path)
    if not isinstance(existing, dict):
        payload = _base_payload(
            command="switch",
            profile_name=profile.name,
            path=path,
            force=force,
            dry_run=dry_run,
            exists_before=True,
            target_config=deepcopy(profile.config_patch),
        )
        payload.update(
            {
                "ok": False,
                "error_code": "CONFIG_INVALID",
                "message": "User config must be a YAML mapping.",
                "changed_fields": [],
                "backup_path": None,
                "backup_written": False,
            }
        )
        return payload

    target_config = deepcopy(existing)
    _apply_profile_managed_keys(target_config, profile.config_patch)
    changes = _profile_field_changes(existing, target_config)
    backup_path = _backup_path(path, timestamp=timestamp)
    payload = _base_payload(
        command="switch",
        profile_name=profile.name,
        path=path,
        force=force,
        dry_run=dry_run,
        exists_before=True,
        target_config=target_config,
    )
    payload.update(
        {
            "changed_fields": changes,
            "backup_path": str(backup_path),
            "backup_written": False,
        }
    )

    if not changes:
        payload["message"] = "User config already matches the requested profile."
        return payload

    if dry_run:
        payload["message"] = "Dry run only; no config file was written."
        return payload

    if not force:
        payload.update(
            {
                "ok": False,
                "error_code": "REQUIRES_FORCE",
                "message": (
                    "Switching profiles changes config-managed fields. Re-run "
                    "with --force to back up and apply the switch."
                ),
                "requires_force": True,
            }
        )
        return payload

    _backup_existing_config(path, backup_path)
    _write_yaml_config(path, target_config)
    payload.update(
        {
            "storage_written": True,
            "backup_written": True,
            "message": "User config switched.",
        }
    )
    return payload


def update_config_settings(
    *,
    config_path: Path | None = None,
    dry_run: bool = True,
    confirmed_by_user: bool = False,
    timestamp: str | None = None,
    llm_provider: str | None = None,
    chatgpt_oauth_model: str | None = None,
    openai_api_model: str | None = None,
    reporting_output_dir: str | None = None,
    reporting_timezone: str | None = None,
    tools_surface: str | None = None,
) -> dict[str, Any]:
    """Update safe, non-secret user-config fields.

    This intentionally does not accept MongoDB URIs or API keys. Those remain
    in `.env`, shell env, or MCPB sensitive user-config fields.
    """

    path = config_path or _env.user_config_path()
    exists = path.exists()
    if exists:
        existing = _read_yaml_config(path)
        if not isinstance(existing, dict):
            return {
                "ok": False,
                "command": "update",
                "error_code": "CONFIG_INVALID",
                "message": "User config must be a YAML mapping.",
                "user_config_path": str(path),
                "dry_run": dry_run,
                "confirmed_by_user": confirmed_by_user,
                "storage_written": False,
                "backup_written": False,
                "changed_fields": [],
            }
    else:
        existing = {}

    target_config = deepcopy(existing)
    try:
        requested = _validated_update_values(
            llm_provider=llm_provider,
            chatgpt_oauth_model=chatgpt_oauth_model,
            openai_api_model=openai_api_model,
            reporting_output_dir=reporting_output_dir,
            reporting_timezone=reporting_timezone,
            tools_surface=tools_surface,
        )
    except ValueError as exc:
        return {
            "ok": False,
            "command": "update",
            "error_code": "INVALID_INPUT",
            "message": str(exc),
            "user_config_path": str(path),
            "dry_run": dry_run,
            "confirmed_by_user": confirmed_by_user,
            "storage_written": False,
            "backup_written": False,
            "changed_fields": [],
        }

    for field_path, value in requested.items():
        _set_nested(target_config, field_path, value)

    changes = _field_changes(existing, target_config, CONFIG_UPDATE_PATHS)
    backup_path = _backup_path(path, timestamp=timestamp) if exists and changes else None
    payload = {
        "ok": True,
        "command": "update",
        "user_config_path": str(path),
        "user_config_exists_before": exists,
        "dry_run": dry_run,
        "confirmed_by_user": confirmed_by_user,
        "requires_confirmation": False,
        "storage_written": False,
        "backup_path": str(backup_path) if backup_path else None,
        "backup_written": False,
        "config_managed_fields": [_format_path(path) for path in CONFIG_UPDATE_PATHS],
        "changed_fields": changes,
        "doctor": build_config_doctor_report(
            target_config,
            offline=True,
            storage_ping=None,
        ),
    }

    if not requested:
        payload["message"] = "No supported config changes were requested."
        return payload
    if not changes:
        payload["message"] = "User config already matches the requested values."
        return payload
    if dry_run:
        payload["message"] = "Dry run only; no config file was written."
        return payload
    if not confirmed_by_user:
        payload.update(
            {
                "ok": False,
                "error_code": "REQUIRES_CONFIRMATION",
                "message": (
                    "Writing user config requires confirmed_by_user=true. "
                    "Run with dry_run=true first, then apply after user approval."
                ),
                "requires_confirmation": True,
            }
        )
        return payload

    if backup_path is not None:
        _backup_existing_config(path, backup_path)
        payload["backup_written"] = True
    _write_yaml_config(path, target_config)
    payload.update(
        {
            "storage_written": True,
            "message": "User config updated.",
        }
    )
    return payload


def _base_payload(
    *,
    command: str,
    profile_name: str,
    path: Path,
    force: bool,
    dry_run: bool,
    exists_before: bool,
    target_config: dict[str, Any],
) -> dict[str, Any]:
    return {
        "ok": True,
        "command": command,
        "profile": profile_name,
        "user_config_path": str(path),
        "user_config_exists_before": exists_before,
        "dry_run": dry_run,
        "force": force,
        "requires_force": False,
        "storage_written": False,
        "profile_managed_fields": [
            _format_path(path_parts)
            for path_parts in PROFILE_MANAGED_PATHS
        ],
        "target_profile_values": _profile_values(target_config),
        "doctor": build_config_doctor_report(
            target_config,
            offline=True,
            storage_ping=None,
        ),
        "message": "",
    }


def _read_yaml_config(path: Path) -> Any:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _write_yaml_config(path: Path, cfg: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = yaml.safe_dump(
        cfg,
        sort_keys=False,
        allow_unicode=True,
    )
    path.write_text(text, encoding="utf-8")


def _backup_existing_config(path: Path, backup_path: Path) -> None:
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, backup_path)


def _backup_path(path: Path, *, timestamp: str | None = None) -> Path:
    suffix = timestamp or datetime.now().strftime("%Y%m%d-%H%M%S")
    return path.with_name(f"{path.name}.bak.{suffix}")


def _apply_profile_managed_keys(
    target: dict[str, Any],
    profile_patch: dict[str, Any],
) -> None:
    for path in PROFILE_MANAGED_PATHS:
        if not _has_nested(profile_patch, path):
            continue
        value = _get_nested(profile_patch, path)
        _set_nested(target, path, value)


def _profile_field_changes(
    before: dict[str, Any],
    after: dict[str, Any],
) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    for path in PROFILE_MANAGED_PATHS:
        old_value = _get_nested(before, path)
        new_value = _get_nested(after, path)
        if old_value != new_value:
            changes.append(
                {
                    "field": _format_path(path),
                    "old": old_value,
                    "new": new_value,
                }
            )
    return changes


def _field_changes(
    before: dict[str, Any],
    after: dict[str, Any],
    paths: tuple[tuple[str, str], ...],
) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    for path in paths:
        old_value = _get_nested(before, path)
        new_value = _get_nested(after, path)
        if old_value != new_value:
            changes.append(
                {
                    "field": _format_path(path),
                    "old": old_value,
                    "new": new_value,
                }
            )
    return changes


def _validated_update_values(
    *,
    llm_provider: str | None,
    chatgpt_oauth_model: str | None,
    openai_api_model: str | None,
    reporting_output_dir: str | None,
    reporting_timezone: str | None,
    tools_surface: str | None,
) -> dict[tuple[str, str], str]:
    values: dict[tuple[str, str], str] = {}
    provider = _optional_string(llm_provider)
    if provider is not None:
        if provider not in _VALID_LLM_PROVIDERS:
            raise ValueError("llm_provider must be chatgpt_oauth, anthropic, or openai_api")
        values[("llm", "provider")] = provider

    oauth_model = _optional_string(chatgpt_oauth_model)
    if oauth_model is not None:
        values[("llm", "chatgpt_oauth_model")] = _validate_model_name(
            oauth_model,
            "chatgpt_oauth_model",
        )

    openai_model = _optional_string(openai_api_model)
    if openai_model is not None:
        values[("llm", "openai_api_model")] = _validate_model_name(
            openai_model,
            "openai_api_model",
        )

    output_dir = _optional_string(reporting_output_dir)
    if output_dir is not None:
        _reject_secret_like(output_dir, "reporting_output_dir")
        if "\n" in output_dir or "\r" in output_dir or "\x00" in output_dir:
            raise ValueError("reporting_output_dir must be a single path string")
        values[("reporting", "output_dir")] = output_dir

    timezone = _optional_string(reporting_timezone)
    if timezone is not None:
        try:
            ZoneInfo(timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("reporting_timezone must be a valid IANA timezone") from exc
        values[("reporting", "timezone")] = timezone

    surface = _optional_string(tools_surface)
    if surface is not None:
        if surface not in _VALID_TOOL_SURFACES:
            raise ValueError("tools_surface must be auto, sample, standard, or developer")
        values[("tools", "surface")] = surface

    return values


def _optional_string(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("config update values must be strings")
    stripped = value.strip()
    return stripped or None


def _validate_model_name(value: str, field: str) -> str:
    _reject_secret_like(value, field)
    if any(char in value for char in ("\n", "\r", "\x00", "/", "\\")):
        raise ValueError(f"{field} must be a single model identifier")
    if len(value) > 120:
        raise ValueError(f"{field} is too long")
    return value


def _reject_secret_like(value: str, field: str) -> None:
    lowered = value.lower()
    if "mongodb://" in lowered or "mongodb+srv://" in lowered:
        raise ValueError(f"{field} must not contain a MongoDB URI")
    if value.startswith(("sk-", "sk_", "xoxb-", "ghp_")):
        raise ValueError(f"{field} must not contain an API key or token")


def _profile_values(cfg: dict[str, Any]) -> dict[str, Any]:
    return {
        _format_path(path): _get_nested(cfg, path)
        for path in PROFILE_MANAGED_PATHS
        if _has_nested(cfg, path)
    }


def _get_nested(cfg: dict[str, Any], path: tuple[str, str]) -> Any:
    value: Any = cfg
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _has_nested(cfg: dict[str, Any], path: tuple[str, str]) -> bool:
    value: Any = cfg
    for key in path:
        if not isinstance(value, dict) or key not in value:
            return False
        value = value[key]
    return True


def _set_nested(cfg: dict[str, Any], path: tuple[str, str], value: Any) -> None:
    parent = cfg
    for key in path[:-1]:
        child = parent.get(key)
        if not isinstance(child, dict):
            child = {}
            parent[key] = child
        parent = child
    parent[path[-1]] = value


def _format_path(path: tuple[str, str]) -> str:
    return ".".join(path)
