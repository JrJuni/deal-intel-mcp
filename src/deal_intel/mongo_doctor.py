from __future__ import annotations

import os
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from deal_intel.config_profiles import infer_config_profile
from deal_intel.mongo_contracts import deals_schema_contract_summary

MongoClientFactory = Callable[[str], Any]

_SECRET_ENV_KEYS = ("MONGODB_URI", "ANTHROPIC_API_KEY", "OPENAI_API_KEY")


def build_mongo_doctor_report(
    cfg: dict[str, Any],
    *,
    offline: bool = False,
    mongo_client_factory: MongoClientFactory | None = None,
) -> dict[str, Any]:
    """Build a secret-safe MongoDB operational readiness report."""

    checks: list[dict[str, Any]] = []
    storage = _mapping(cfg.get("storage"))
    mongodb = _mapping(cfg.get("mongodb"))
    backend = storage.get("backend", "mongo")
    database = mongodb.get("database", "deal_intel")
    vector_search = mongodb.get("vector_search", "python_cosine")
    profile = infer_config_profile(cfg)

    _add_check(
        checks,
        check_id="storage_backend",
        label="Storage backend",
        status="pass" if backend == "mongo" else "warn",
        message=(
            "storage.backend is mongo."
            if backend == "mongo"
            else "Mongo doctor is intended for mongo storage; current backend is not mongo."
        ),
        details={"storage_backend": backend},
        hint="Use `deal-intel config switch full` before checking Atlas-backed storage."
        if backend != "mongo"
        else None,
    )

    if backend != "mongo":
        _add_skipped_mongo_checks(checks, "storage.backend is not mongo.")
    else:
        _add_mongo_checks(
            checks,
            database=database,
            offline=offline,
            mongo_client_factory=mongo_client_factory,
        )

    _add_vector_search_check(checks, backend=backend, vector_search=vector_search)

    status_counts = _status_counts(checks)
    failed = status_counts.get("fail", 0)
    warnings = status_counts.get("warn", 0)
    skipped = status_counts.get("skipped", 0)
    return {
        "ok": failed == 0,
        "profile": profile,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "summary": {
            "status": "ready" if failed == 0 else "needs_attention",
            "offline": offline,
            "storage_backend": backend,
            "mongodb_database": database,
            "vector_search": vector_search,
            "failed_checks": failed,
            "warning_checks": warnings,
            "skipped_checks": skipped,
        },
        "checks": checks,
        "next_actions": _next_actions(checks),
    }


def _add_mongo_checks(
    checks: list[dict[str, Any]],
    *,
    database: Any,
    offline: bool,
    mongo_client_factory: MongoClientFactory | None,
) -> None:
    uri_configured = bool(os.environ.get("MONGODB_URI"))
    if uri_configured:
        _add_check(
            checks,
            check_id="mongodb_uri",
            label="MongoDB URI",
            status="pass",
            message="MONGODB_URI is configured.",
            details={"configured": True, "database": database},
        )
    else:
        _add_check(
            checks,
            check_id="mongodb_uri",
            label="MongoDB URI",
            status="fail",
            message="MONGODB_URI is not configured for mongo storage.",
            details={"configured": False, "database": database},
            hint="Set MONGODB_URI in .env or switch to local_sample for zero-config tests.",
        )

    if offline:
        _add_skipped_mongo_checks(checks, "offline mode requested.", include_uri=False)
        return
    if not uri_configured:
        _add_skipped_mongo_checks(checks, "MONGODB_URI is missing.", include_uri=False)
        return

    client = _make_client(database=database, factory=mongo_client_factory)
    ping = client.ping()
    ping_status = ping.get("status")
    if ping_status == "ok":
        _add_check(
            checks,
            check_id="storage_ping",
            label="Storage ping",
            status="pass",
            message="MongoDB ping succeeded.",
            details=_redact(ping),
        )
    else:
        _add_check(
            checks,
            check_id="storage_ping",
            label="Storage ping",
            status="fail",
            message="MongoDB ping failed.",
            details=_redact(ping),
            hint="Check Atlas network access, credentials, and the target database name.",
        )
        _add_skipped_mongo_checks(checks, "MongoDB ping failed.", include_uri=False)
        return

    _add_index_check(checks, client)
    _add_schema_check(checks, client)


def _add_index_check(checks: list[dict[str, Any]], client: Any) -> None:
    try:
        report = client.check_indexes()
    except Exception as exc:
        _add_check(
            checks,
            check_id="mongo_indexes",
            label="Mongo indexes",
            status="fail",
            message=f"Could not read MongoDB indexes: {type(exc).__name__}",
            details={"error": _redact_text(str(exc))},
            hint="Run `deal-intel mongo apply-indexes --apply` after confirming Atlas access.",
        )
        return

    missing = int(report.get("missing_count", 0))
    mismatched = int(report.get("mismatch_count", 0))
    _add_check(
        checks,
        check_id="mongo_indexes",
        label="Mongo indexes",
        status="pass" if report.get("ok") else "fail",
        message=(
            "Expected MongoDB indexes are present."
            if report.get("ok")
            else (
                "MongoDB index contract drift detected: "
                f"{missing} missing, {mismatched} mismatched."
            )
        ),
        details={
            "missing_count": missing,
            "mismatch_count": mismatched,
            "collections": report.get("collections", {}),
        },
        hint="Run the app once or call an index maintenance command to create missing indexes."
        if not report.get("ok")
        else None,
    )


def _add_schema_check(checks: list[dict[str, Any]], client: Any) -> None:
    try:
        report = client.check_deals_schema_validation()
    except Exception as exc:
        _add_check(
            checks,
            check_id="deals_schema",
            label="Deals schema validation",
            status="fail",
            message=f"Could not read deals schema validation: {type(exc).__name__}",
            details={"error": _redact_text(str(exc))},
            hint="Run `deal-intel mongo apply-schema --dry-run` to inspect the intended validator.",
        )
        return

    status = "pass" if report.get("ok") else "warn"
    _add_check(
        checks,
        check_id="deals_schema",
        label="Deals schema validation",
        status=status,
        message=(
            "Deals collection validator matches the v1 contract."
            if report.get("ok")
            else "Deals collection validator is missing or differs from the v1 contract."
        ),
        details=report,
        hint=(
            "Run `deal-intel mongo apply-schema --dry-run`, then `--apply` "
            "if the command looks correct."
        )
        if not report.get("ok")
        else None,
    )


def _add_vector_search_check(
    checks: list[dict[str, Any]],
    *,
    backend: Any,
    vector_search: Any,
) -> None:
    if vector_search == "python_cosine":
        _add_check(
            checks,
            check_id="vector_search",
            label="Vector search mode",
            status="pass",
            message="Python cosine vector search is M0/full compatible.",
            details={"vector_search": vector_search},
        )
        return
    if vector_search == "atlas":
        _add_check(
            checks,
            check_id="vector_search",
            label="Vector search mode",
            status="warn",
            message="Atlas Vector Search is a pro/M10+ feature.",
            details={
                "vector_search": vector_search,
                "storage_backend": backend,
                "minimum_cluster_tier": "M10",
            },
            hint="Keep python_cosine for full/M0; use atlas only for the pro profile.",
        )
        return
    _add_check(
        checks,
        check_id="vector_search",
        label="Vector search mode",
        status="fail",
        message="mongodb.vector_search must be python_cosine or atlas.",
        details={"vector_search": vector_search},
    )


def _add_skipped_mongo_checks(
    checks: list[dict[str, Any]],
    reason: str,
    *,
    include_uri: bool = True,
) -> None:
    if include_uri:
        _add_check(
            checks,
            check_id="mongodb_uri",
            label="MongoDB URI",
            status="skipped",
            message=f"MongoDB URI check skipped because {reason}",
        )
    _add_check(
        checks,
        check_id="storage_ping",
        label="Storage ping",
        status="skipped",
        message=f"MongoDB ping skipped because {reason}",
    )
    _add_check(
        checks,
        check_id="mongo_indexes",
        label="Mongo indexes",
        status="skipped",
        message=f"MongoDB index check skipped because {reason}",
    )
    _add_check(
        checks,
        check_id="deals_schema",
        label="Deals schema validation",
        status="skipped",
        message=f"Deals schema check skipped because {reason}",
        details={"expected": deals_schema_contract_summary()},
    )


def _make_client(*, database: Any, factory: MongoClientFactory | None) -> Any:
    if factory is not None:
        return factory(str(database))
    from deal_intel.storage.mongodb import MongoDBClient

    return MongoDBClient(database=str(database))


def _add_check(
    checks: list[dict[str, Any]],
    *,
    check_id: str,
    label: str,
    status: str,
    message: str,
    details: dict[str, Any] | None = None,
    hint: str | dict[str, Any] | None = None,
) -> None:
    check = {
        "id": check_id,
        "label": label,
        "status": status,
        "message": message,
    }
    if details is not None:
        check["details"] = _redact(details)
    if hint:
        check["hint"] = hint
    checks.append(check)


def _status_counts(checks: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"pass": 0, "warn": 0, "fail": 0, "skipped": 0}
    for check in checks:
        status = str(check.get("status"))
        counts[status] = counts.get(status, 0) + 1
    return counts


def _next_actions(checks: list[dict[str, Any]]) -> list[dict[str, str]]:
    actions = []
    for check in checks:
        if check.get("status") in {"fail", "warn"} and check.get("hint"):
            actions.append(
                {
                    "check_id": str(check["id"]),
                    "label": str(check["label"]),
                    "hint": str(check["hint"]),
                }
            )
    return actions


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _redact(nested) for key, nested in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, str):
        return _redact_text(value)
    return value


def _redact_text(value: str) -> str:
    redacted = value
    for key in _SECRET_ENV_KEYS:
        secret = os.environ.get(key)
        if secret:
            redacted = redacted.replace(secret, f"<redacted:{key}>")
    return redacted
