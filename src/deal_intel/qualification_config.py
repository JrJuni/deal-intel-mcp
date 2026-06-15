from __future__ import annotations

import shutil
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from deal_intel import _env
from deal_intel.schema.qualification_framework import (
    QualificationFramework,
    built_in_qualification_templates,
    get_qualification_template,
    validate_qualification_framework,
)


def build_qualification_templates_payload(
    *,
    template_key: str = "",
    include_dimensions: bool = True,
) -> dict[str, Any]:
    """Return built-in qualification framework templates."""
    templates = built_in_qualification_templates()
    requested_key = template_key.strip()
    if requested_key:
        if requested_key not in templates:
            return {
                "ok": False,
                "error_code": "UNKNOWN_TEMPLATE",
                "message": "Unknown qualification framework template.",
                "available_templates": sorted(templates),
            }
        selected = {requested_key: templates[requested_key]}
    else:
        selected = templates

    return {
        "ok": True,
        "template_count": len(selected),
        "available_templates": sorted(templates),
        "templates": [
            _template_summary(framework, include_dimensions=include_dimensions)
            for framework in selected.values()
        ],
        "usage_hint": (
            "Start from a built-in template, then validate custom edits with "
            "validate_qualification_framework before applying them with "
            "update_qualification_framework. Framework changes affect config "
            "only until a later recompute/backfill step is run."
        ),
    }


def validate_framework_input(
    *,
    template_key: str = "",
    framework_json: str = "",
) -> dict[str, Any]:
    """Validate a built-in template or a JSON/YAML framework payload."""
    parsed = _framework_from_input(
        template_key=template_key,
        framework_json=framework_json,
    )
    if not parsed["ok"]:
        return parsed
    result = validate_qualification_framework(parsed["payload"])
    result.update(
        {
            "source": parsed["source"],
            "template_key": parsed.get("template_key"),
        }
    )
    return result


def resolve_active_qualification_framework(cfg: dict[str, Any] | None) -> QualificationFramework:
    """Resolve the active qualification framework from effective config.

    The default remains the bundled MEDDPICC template. User config can add
    custom frameworks under `qualification.frameworks` and select one through
    `qualification.active_framework`.
    """
    config = cfg or {}
    qualification = config.get("qualification", {})
    if not isinstance(qualification, dict):
        raise ValueError("qualification config must be a mapping")

    active_key = str(qualification.get("active_framework") or "meddpicc").strip()
    if not active_key:
        active_key = "meddpicc"

    configured_frameworks = qualification.get("frameworks", {})
    if configured_frameworks is None:
        configured_frameworks = {}
    if not isinstance(configured_frameworks, dict):
        raise ValueError("qualification.frameworks must be a mapping")

    if active_key in configured_frameworks:
        payload = configured_frameworks[active_key]
        if not isinstance(payload, dict):
            raise ValueError(f"qualification.frameworks.{active_key} must be a mapping")
        return QualificationFramework.model_validate(payload)

    try:
        framework = get_qualification_template(active_key)
    except ValueError as exc:
        raise ValueError(
            f"qualification.active_framework {active_key!r} is not defined"
        ) from exc
    if active_key == "meddpicc":
        return _apply_legacy_meddpicc_overrides(framework, config)
    return framework


def _apply_legacy_meddpicc_overrides(
    framework: QualificationFramework,
    cfg: dict[str, Any],
) -> QualificationFramework:
    meddpicc_cfg = cfg.get("meddpicc", {})
    if not isinstance(meddpicc_cfg, dict):
        return framework

    target = framework.model_copy(deep=True)
    weights = meddpicc_cfg.get("weights", {})
    if "weights" in meddpicc_cfg:
        if not isinstance(weights, dict):
            raise ValueError("meddpicc.weights must be a mapping")
        for key, dimension in target.dimensions.items():
            dimension.weight = weights.get(key, 1.0)

    if "gap_threshold" in meddpicc_cfg:
        threshold = meddpicc_cfg["gap_threshold"]
        for dimension in target.dimensions.values():
            dimension.gap_threshold = threshold

    return QualificationFramework.model_validate(target.model_dump(mode="python"))


def update_qualification_framework_config(
    *,
    config_path: Path | None = None,
    template_key: str = "",
    framework_json: str = "",
    dry_run: bool = True,
    confirmed_by_user: bool = False,
    set_active: bool = True,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Preview or apply a validated qualification framework to user config."""
    path = config_path or _env.user_config_path()
    parsed = _framework_from_input(
        template_key=template_key,
        framework_json=framework_json,
    )
    if not parsed["ok"]:
        return _update_error(
            path=path,
            dry_run=dry_run,
            confirmed_by_user=confirmed_by_user,
            code=parsed["error_code"],
            message=parsed["message"],
            extra={
                key: value
                for key, value in parsed.items()
                if key not in {"ok", "error_code", "message"}
            },
        )

    validation = validate_qualification_framework(parsed["payload"])
    if not validation["ok"]:
        return _update_error(
            path=path,
            dry_run=dry_run,
            confirmed_by_user=confirmed_by_user,
            code="INVALID_FRAMEWORK",
            message="Qualification framework validation failed.",
            extra={"validation": validation},
        )

    framework = QualificationFramework.model_validate(validation["framework"])
    exists = path.exists()
    if exists:
        existing = _read_yaml_config(path)
        if not isinstance(existing, dict):
            return _update_error(
                path=path,
                dry_run=dry_run,
                confirmed_by_user=confirmed_by_user,
                code="CONFIG_INVALID",
                message="User config must be a YAML mapping.",
            )
    else:
        existing = {}

    target = deepcopy(existing)
    qualification = target.setdefault("qualification", {})
    if not isinstance(qualification, dict):
        return _update_error(
            path=path,
            dry_run=dry_run,
            confirmed_by_user=confirmed_by_user,
            code="CONFIG_INVALID",
            message="qualification config must be a YAML mapping.",
        )
    frameworks = qualification.setdefault("frameworks", {})
    if not isinstance(frameworks, dict):
        return _update_error(
            path=path,
            dry_run=dry_run,
            confirmed_by_user=confirmed_by_user,
            code="CONFIG_INVALID",
            message="qualification.frameworks must be a YAML mapping.",
        )

    frameworks[framework.key] = framework.model_dump(mode="json")
    if set_active:
        qualification["active_framework"] = framework.key

    changed_fields = _qualification_changes(existing, target, framework.key, set_active=set_active)
    backup_path = _backup_path(path, timestamp=timestamp) if exists and changed_fields else None
    payload = {
        "ok": True,
        "command": "update_qualification_framework",
        "user_config_path": str(path),
        "user_config_exists_before": exists,
        "dry_run": dry_run,
        "confirmed_by_user": confirmed_by_user,
        "requires_confirmation": False,
        "storage_written": False,
        "backup_path": str(backup_path) if backup_path else None,
        "backup_written": False,
        "restart_required": bool(changed_fields),
        "source": parsed["source"],
        "template_key": parsed.get("template_key"),
        "framework_key": framework.key,
        "set_active": set_active,
        "changed_fields": changed_fields,
        "framework": framework.model_dump(mode="json"),
        "validation": validation,
        "message": "",
    }

    if not changed_fields:
        payload["message"] = "User config already contains the requested framework."
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
    _write_yaml_config(path, target)
    payload.update(
        {
            "storage_written": True,
            "message": "Qualification framework config updated.",
        }
    )
    return payload


def list_qualification_frameworks_config(
    *,
    cfg: dict[str, Any] | None = None,
    config_path: Path | None = None,
    include_dimensions: bool = False,
) -> dict[str, Any]:
    """List built-in and user-configured qualification frameworks."""
    path = config_path or _env.user_config_path()
    config = cfg if cfg is not None else _read_user_config_or_empty(path)
    if not isinstance(config, dict):
        return _update_error(
            path=path,
            dry_run=True,
            confirmed_by_user=False,
            command="list_qualification_frameworks",
            code="CONFIG_INVALID",
            message="User config must be a YAML mapping.",
        )

    qualification = config.get("qualification", {}) or {}
    if not isinstance(qualification, dict):
        return _update_error(
            path=path,
            dry_run=True,
            confirmed_by_user=False,
            command="list_qualification_frameworks",
            code="CONFIG_INVALID",
            message="qualification config must be a YAML mapping.",
        )

    configured_frameworks = qualification.get("frameworks", {}) or {}
    if not isinstance(configured_frameworks, dict):
        return _update_error(
            path=path,
            dry_run=True,
            confirmed_by_user=False,
            command="list_qualification_frameworks",
            code="CONFIG_INVALID",
            message="qualification.frameworks must be a YAML mapping.",
        )

    built_ins = built_in_qualification_templates()
    active_key = _active_framework_key(qualification)
    keys = sorted(set(built_ins) | set(configured_frameworks))
    frameworks = [
        _framework_listing(
            key,
            built_ins=built_ins,
            configured_frameworks=configured_frameworks,
            active_key=active_key,
            include_dimensions=include_dimensions,
        )
        for key in keys
    ]
    warnings = []
    if active_key not in keys:
        warnings.append(
            {
                "code": "active_framework_not_defined",
                "message": (
                    "qualification.active_framework is not defined in built-in "
                    "templates or user config."
                ),
                "framework_key": active_key,
            }
        )
    invalid_keys = [
        framework["key"]
        for framework in frameworks
        if framework.get("valid") is False
    ]
    if invalid_keys:
        warnings.append(
            {
                "code": "invalid_configured_frameworks",
                "message": "Some configured frameworks failed validation.",
                "framework_keys": invalid_keys,
            }
        )

    return {
        "ok": True,
        "command": "list_qualification_frameworks",
        "user_config_path": str(path),
        "user_config_exists": path.exists(),
        "active_framework": active_key,
        "active_framework_defined": active_key in keys,
        "framework_count": len(frameworks),
        "available_frameworks": keys,
        "frameworks": frameworks,
        "warnings": warnings,
        "usage_hint": (
            "Use update_qualification_framework to create or revise a framework, "
            "set_active_qualification_framework to switch the active framework, "
            "and delete_qualification_framework to remove a stored custom "
            "framework after dry-run review."
        ),
    }


def set_active_qualification_framework_config(
    *,
    framework_key: str,
    config_path: Path | None = None,
    dry_run: bool = True,
    confirmed_by_user: bool = False,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Preview or apply the active qualification framework selection."""
    path = config_path or _env.user_config_path()
    requested_key = framework_key.strip()
    if not requested_key:
        return _update_error(
            path=path,
            dry_run=dry_run,
            confirmed_by_user=confirmed_by_user,
            command="set_active_qualification_framework",
            code="INVALID_INPUT",
            message="framework_key is required.",
        )

    loaded = _load_mutable_user_config(
        path=path,
        dry_run=dry_run,
        confirmed_by_user=confirmed_by_user,
        command="set_active_qualification_framework",
    )
    if not loaded["ok"]:
        return loaded
    existing = loaded["config"]
    qualification = loaded["qualification"]
    configured_frameworks = loaded["frameworks"]
    built_ins = built_in_qualification_templates()
    available = sorted(set(built_ins) | set(configured_frameworks))
    if requested_key not in available:
        return _update_error(
            path=path,
            dry_run=dry_run,
            confirmed_by_user=confirmed_by_user,
            command="set_active_qualification_framework",
            code="UNKNOWN_FRAMEWORK",
            message="Unknown qualification framework.",
            extra={"available_frameworks": available},
        )
    if requested_key in configured_frameworks:
        validation = validate_qualification_framework(configured_frameworks[requested_key])
        if not validation["ok"]:
            return _update_error(
                path=path,
                dry_run=dry_run,
                confirmed_by_user=confirmed_by_user,
                command="set_active_qualification_framework",
                code="INVALID_FRAMEWORK",
                message="Configured framework validation failed.",
                extra={"validation": validation},
            )

    target = deepcopy(existing)
    target_qualification = target.setdefault("qualification", {})
    target_qualification["active_framework"] = requested_key
    previous_key = _active_framework_key(qualification)
    changed_fields = []
    if previous_key != requested_key:
        changed_fields.append(
            {
                "field": "qualification.active_framework",
                "changed": True,
                "before": previous_key,
                "after": requested_key,
            }
        )
    backup_path = (
        _backup_path(path, timestamp=timestamp)
        if path.exists() and changed_fields
        else None
    )
    payload = _config_write_payload(
        command="set_active_qualification_framework",
        path=path,
        exists=path.exists(),
        dry_run=dry_run,
        confirmed_by_user=confirmed_by_user,
        backup_path=backup_path,
        changed_fields=changed_fields,
        extra={
            "framework_key": requested_key,
            "previous_framework": previous_key,
            "restart_required": bool(changed_fields),
        },
    )

    if not changed_fields:
        payload["message"] = "Requested framework is already active."
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

    _apply_config_write(path, target, payload, backup_path=backup_path)
    payload["message"] = "Active qualification framework updated."
    return payload


def delete_qualification_framework_config(
    *,
    framework_key: str,
    config_path: Path | None = None,
    dry_run: bool = True,
    confirmed_by_user: bool = False,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Preview or delete a stored custom qualification framework."""
    path = config_path or _env.user_config_path()
    requested_key = framework_key.strip()
    if not requested_key:
        return _update_error(
            path=path,
            dry_run=dry_run,
            confirmed_by_user=confirmed_by_user,
            command="delete_qualification_framework",
            code="INVALID_INPUT",
            message="framework_key is required.",
        )

    loaded = _load_mutable_user_config(
        path=path,
        dry_run=dry_run,
        confirmed_by_user=confirmed_by_user,
        command="delete_qualification_framework",
    )
    if not loaded["ok"]:
        return loaded
    existing = loaded["config"]
    qualification = loaded["qualification"]
    configured_frameworks = loaded["frameworks"]
    built_ins = built_in_qualification_templates()
    if requested_key not in configured_frameworks:
        code = (
            "BUILT_IN_FRAMEWORK_NOT_DELETABLE"
            if requested_key in built_ins
            else "UNKNOWN_FRAMEWORK"
        )
        return _update_error(
            path=path,
            dry_run=dry_run,
            confirmed_by_user=confirmed_by_user,
            command="delete_qualification_framework",
            code=code,
            message=(
                "Built-in frameworks cannot be deleted from user config."
                if requested_key in built_ins
                else "Unknown stored qualification framework."
            ),
            extra={"available_custom_frameworks": sorted(configured_frameworks)},
        )
    active_key = _active_framework_key(qualification)
    if active_key == requested_key:
        return _update_error(
            path=path,
            dry_run=dry_run,
            confirmed_by_user=confirmed_by_user,
            command="delete_qualification_framework",
            code="ACTIVE_FRAMEWORK_NOT_DELETABLE",
            message=(
                "The active qualification framework cannot be deleted. Switch "
                "to another framework first."
            ),
            extra={"active_framework": active_key},
        )

    deleted_payload = configured_frameworks[requested_key]
    target = deepcopy(existing)
    del target["qualification"]["frameworks"][requested_key]
    changed_fields = [
        {"field": f"qualification.frameworks.{requested_key}", "changed": True}
    ]
    backup_path = _backup_path(path, timestamp=timestamp) if path.exists() else None
    payload = _config_write_payload(
        command="delete_qualification_framework",
        path=path,
        exists=path.exists(),
        dry_run=dry_run,
        confirmed_by_user=confirmed_by_user,
        backup_path=backup_path,
        changed_fields=changed_fields,
        extra={
            "framework_key": requested_key,
            "deleted_framework": _safe_framework_summary(
                requested_key,
                deleted_payload,
                include_dimensions=False,
            ),
            "restart_required": True,
        },
    )

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

    _apply_config_write(path, target, payload, backup_path=backup_path)
    payload["message"] = "Stored qualification framework deleted."
    return payload


def _framework_from_input(
    *,
    template_key: str,
    framework_json: str,
) -> dict[str, Any]:
    requested_template = template_key.strip()
    raw = framework_json.strip()
    if requested_template and raw:
        return {
            "ok": False,
            "error_code": "INVALID_INPUT",
            "message": "Provide either template_key or framework_json, not both.",
        }
    if requested_template:
        try:
            framework = get_qualification_template(requested_template)
        except ValueError:
            return {
                "ok": False,
                "error_code": "UNKNOWN_TEMPLATE",
                "message": "Unknown qualification framework template.",
                "available_templates": sorted(built_in_qualification_templates()),
            }
        return {
            "ok": True,
            "source": "template",
            "template_key": requested_template,
            "payload": framework.model_dump(mode="json"),
        }
    if not raw:
        return {
            "ok": False,
            "error_code": "INVALID_INPUT",
            "message": "template_key or framework_json is required.",
        }
    try:
        parsed = yaml.safe_load(raw)
    except yaml.YAMLError:
        return {
            "ok": False,
            "error_code": "INVALID_INPUT",
            "message": "framework_json could not be parsed as JSON or YAML.",
        }
    if not isinstance(parsed, dict):
        return {
            "ok": False,
            "error_code": "INVALID_INPUT",
            "message": "framework_json must parse to an object.",
        }
    return {
        "ok": True,
        "source": "framework_json",
        "template_key": None,
        "payload": parsed,
    }


def _template_summary(
    framework: QualificationFramework,
    *,
    include_dimensions: bool,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "key": framework.key,
        "display_name": framework.display_name,
        "score_scale": framework.score_scale.model_dump(mode="json"),
        "dimension_count": len(framework.dimensions),
        "dimension_keys": list(framework.dimensions),
    }
    if include_dimensions:
        payload["dimensions"] = {
            key: dimension.model_dump(mode="json")
            for key, dimension in framework.dimensions.items()
        }
    return payload


def _framework_listing(
    key: str,
    *,
    built_ins: dict[str, QualificationFramework],
    configured_frameworks: dict[str, Any],
    active_key: str,
    include_dimensions: bool,
) -> dict[str, Any]:
    if key in configured_frameworks:
        summary = _safe_framework_summary(
            key,
            configured_frameworks[key],
            include_dimensions=include_dimensions,
        )
        summary.update(
            {
                "source": "user_config",
                "overrides_built_in": key in built_ins,
                "active": key == active_key,
            }
        )
        return summary

    summary = _template_summary(built_ins[key], include_dimensions=include_dimensions)
    summary.update(
        {
            "source": "built_in",
            "overrides_built_in": False,
            "active": key == active_key,
            "valid": True,
        }
    )
    return summary


def _safe_framework_summary(
    key: str,
    payload: Any,
    *,
    include_dimensions: bool,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {
            "key": key,
            "valid": False,
            "error_code": "INVALID_FRAMEWORK",
            "message": "Configured framework must be a mapping.",
        }
    validation = validate_qualification_framework(payload)
    if not validation["ok"]:
        return {
            "key": str(payload.get("key") or key),
            "display_name": str(payload.get("display_name") or key),
            "valid": False,
            "validation_errors": validation.get("errors", []),
            "validation_warnings": validation.get("warnings", []),
            "dimension_count": (
                len(payload.get("dimensions"))
                if isinstance(payload.get("dimensions"), dict)
                else 0
            ),
            "dimension_keys": (
                list(payload.get("dimensions"))
                if isinstance(payload.get("dimensions"), dict)
                else []
            ),
        }
    framework = QualificationFramework.model_validate(validation["framework"])
    summary = _template_summary(framework, include_dimensions=include_dimensions)
    summary["valid"] = True
    summary["validation_warnings"] = validation.get("warnings", [])
    return summary


def _qualification_changes(
    before: dict[str, Any],
    after: dict[str, Any],
    framework_key: str,
    *,
    set_active: bool,
) -> list[dict[str, Any]]:
    paths = [("qualification", "frameworks", framework_key)]
    if set_active:
        paths.append(("qualification", "active_framework"))

    changes: list[dict[str, Any]] = []
    for path in paths:
        if _get_nested(before, path) != _get_nested(after, path):
            changes.append({"field": ".".join(path), "changed": True})
    return changes


def _update_error(
    *,
    path: Path,
    dry_run: bool,
    confirmed_by_user: bool,
    code: str,
    message: str,
    command: str = "update_qualification_framework",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "ok": False,
        "command": command,
        "error_code": code,
        "message": message,
        "user_config_path": str(path),
        "dry_run": dry_run,
        "confirmed_by_user": confirmed_by_user,
        "storage_written": False,
        "backup_written": False,
        "changed_fields": [],
    }
    if extra:
        payload.update(extra)
    return payload


def _read_user_config_or_empty(path: Path) -> dict[str, Any]:
    return _read_yaml_config(path) if path.exists() else {}


def _load_mutable_user_config(
    *,
    path: Path,
    dry_run: bool,
    confirmed_by_user: bool,
    command: str,
) -> dict[str, Any]:
    exists = path.exists()
    if exists:
        existing = _read_yaml_config(path)
        if not isinstance(existing, dict):
            return _update_error(
                path=path,
                dry_run=dry_run,
                confirmed_by_user=confirmed_by_user,
                command=command,
                code="CONFIG_INVALID",
                message="User config must be a YAML mapping.",
            )
    else:
        existing = {}

    qualification = existing.setdefault("qualification", {})
    if not isinstance(qualification, dict):
        return _update_error(
            path=path,
            dry_run=dry_run,
            confirmed_by_user=confirmed_by_user,
            command=command,
            code="CONFIG_INVALID",
            message="qualification config must be a YAML mapping.",
        )
    frameworks = qualification.setdefault("frameworks", {})
    if not isinstance(frameworks, dict):
        return _update_error(
            path=path,
            dry_run=dry_run,
            confirmed_by_user=confirmed_by_user,
            command=command,
            code="CONFIG_INVALID",
            message="qualification.frameworks must be a YAML mapping.",
        )
    return {
        "ok": True,
        "config": existing,
        "qualification": qualification,
        "frameworks": frameworks,
    }


def _active_framework_key(qualification: dict[str, Any]) -> str:
    active_key = str(qualification.get("active_framework") or "meddpicc").strip()
    return active_key or "meddpicc"


def _config_write_payload(
    *,
    command: str,
    path: Path,
    exists: bool,
    dry_run: bool,
    confirmed_by_user: bool,
    backup_path: Path | None,
    changed_fields: list[dict[str, Any]],
    extra: dict[str, Any],
) -> dict[str, Any]:
    return {
        "ok": True,
        "command": command,
        "user_config_path": str(path),
        "user_config_exists_before": exists,
        "dry_run": dry_run,
        "confirmed_by_user": confirmed_by_user,
        "requires_confirmation": False,
        "storage_written": False,
        "backup_path": str(backup_path) if backup_path else None,
        "backup_written": False,
        "changed_fields": changed_fields,
        **extra,
    }


def _apply_config_write(
    path: Path,
    target: dict[str, Any],
    payload: dict[str, Any],
    *,
    backup_path: Path | None,
) -> None:
    if backup_path is not None:
        _backup_existing_config(path, backup_path)
        payload["backup_written"] = True
    _write_yaml_config(path, target)
    payload["storage_written"] = True


def _read_yaml_config(path: Path) -> Any:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _write_yaml_config(path: Path, cfg: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def _backup_existing_config(path: Path, backup_path: Path) -> None:
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, backup_path)


def _backup_path(path: Path, *, timestamp: str | None = None) -> Path:
    suffix = timestamp or datetime.now().strftime("%Y%m%d-%H%M%S")
    return path.with_name(f"{path.name}.bak.{suffix}")


def _get_nested(cfg: dict[str, Any], path: tuple[str, ...]) -> Any:
    value: Any = cfg
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value
