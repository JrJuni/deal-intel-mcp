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
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "ok": False,
        "command": "update_qualification_framework",
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
