from __future__ import annotations

import json
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import typer

app = typer.Typer(help="deal-intel CLI")
config_app = typer.Typer(help="Inspect and prepare deal-intel config profiles.")
app.add_typer(config_app, name="config")
local_data_app = typer.Typer(help="Inspect, export, and reset local personal data.")
app.add_typer(local_data_app, name="local-data")
mongo_app = typer.Typer(help="Diagnose and apply MongoDB operational contracts.")
app.add_typer(mongo_app, name="mongo")

SENSITIVE_RESULT_KEYS = {"raw_notes", "raw_content", "contacts", "summary_embedding"}
ALERT_RANK = {"alert": 3, "watch": 2, "info": 1, "none": 0}
UNCERTAINTY_RANK = {"high": 2, "medium": 1, "low": 0}
ISSUE_SEVERITY_RANK = {"high": 3, "medium": 2, "low": 1}
CONFIG_ENV_KEYS = (
    "MONGODB_URI",
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "DEAL_INTEL_LLM_PROVIDER",
    "DEAL_INTEL_USE_CHATGPT_OAUTH",
    "DEAL_INTEL_STORAGE_BACKEND",
    "DEAL_INTEL_TOOLS_SURFACE",
)


def _configure_stdio_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8")
            except (OSError, ValueError):
                pass


_configure_stdio_utf8()


@app.command("login-chatgpt")
def login_chatgpt(
    force: bool = typer.Option(
        False,
        "--force",
        help="Re-authenticate even with a valid cached token",
    ),
) -> None:
    """Authenticate with ChatGPT OAuth (opens browser). Run once before first use."""
    from deal_intel._env import load_config
    from deal_intel.providers import llm as _llm

    cfg = load_config()
    # Force chatgpt_oauth regardless of defaults so this command always works
    cfg.setdefault("llm", {})["provider"] = "chatgpt_oauth"
    provider = _llm.make_llm_provider(cfg)
    assert isinstance(provider, _llm.ChatGPTOAuthProvider)
    result = provider.login(force=force)
    typer.echo(f"ok  model={result['model']}  token_path={result['token_path']}")


@config_app.command("profiles")
def config_profiles(
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Print structured JSON instead of concise text.",
    ),
) -> None:
    """List available one-package config profiles."""

    from deal_intel.config_profiles import list_config_profiles

    payload = {
        "ok": True,
        "profiles": [profile.to_dict() for profile in list_config_profiles()],
    }
    if json_output:
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    else:
        typer.echo(_format_config_profiles(payload))


@config_app.command("show")
def config_show(
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Print structured JSON instead of concise text.",
    ),
) -> None:
    """Show the effective config summary without printing secret values."""

    from deal_intel import _env
    from deal_intel.config_profiles import get_config_profile, infer_config_profile

    cfg = _env.load_config()
    profile_name = infer_config_profile(cfg)
    profile = get_config_profile(profile_name)
    user_config = _env.user_config_path()
    payload = {
        "ok": True,
        "profile": profile_name,
        "profile_metadata": profile.to_dict(),
        "user_config_path": str(user_config),
        "user_config_exists": user_config.exists(),
        "effective_config": _summarize_config_for_display(cfg),
        "environment": _summarize_config_environment(),
    }
    if json_output:
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    else:
        typer.echo(_format_config_show(payload))


@config_app.command("doctor")
def config_doctor(
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Print structured JSON instead of concise text.",
    ),
    offline: bool = typer.Option(
        False,
        "--offline",
        help="Skip live storage ping and run static checks only.",
    ),
) -> None:
    """Diagnose profile, storage, vector search, and LLM readiness."""

    from deal_intel import _env
    from deal_intel.config_doctor import build_config_doctor_report
    from deal_intel.storage.local_sample import LocalSampleClient
    from deal_intel.storage.mongodb import MongoDBClient

    cfg = _env.load_config()

    def _storage_ping() -> dict:
        storage = _mapping(cfg.get("storage"))
        backend = storage.get("backend", "mongo")
        if backend == "local_sample":
            return LocalSampleClient(
                local_data_dir=storage.get("local_data_dir")
            ).ping()
        database = _mapping(cfg.get("mongodb")).get("database", "deal_intel")
        return MongoDBClient(database=database).ping()

    payload = build_config_doctor_report(
        cfg,
        offline=offline,
        storage_ping=_storage_ping,
    )
    if json_output:
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    else:
        typer.echo(_format_config_doctor(payload))

    if not payload["ok"]:
        raise typer.Exit(code=1)


@config_app.command("init")
def config_init(
    profile: str = typer.Option(
        ...,
        "--profile",
        help="Profile to initialize: sample, full, or pro.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Back up and overwrite an existing user config.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Preview the config change without writing files.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Print structured JSON instead of concise text.",
    ),
) -> None:
    """Initialize ~/.deal-intel/config.yaml for a profile."""

    from deal_intel.config_writer import init_config_profile

    try:
        payload = init_config_profile(
            profile,
            force=force,
            dry_run=dry_run,
        )
    except ValueError as exc:
        payload = _config_write_error_payload("init", profile, str(exc))

    if json_output:
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    else:
        typer.echo(_format_config_write_result(payload))

    if not payload["ok"]:
        raise typer.Exit(code=1)


@config_app.command("switch")
def config_switch(
    profile: str = typer.Argument(
        ...,
        help="Profile to switch to: sample, full, or pro.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Back up and apply profile-managed config changes.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Preview the config change without writing files.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Print structured JSON instead of concise text.",
    ),
) -> None:
    """Switch an existing user config between sample, full, and pro."""

    from deal_intel.config_writer import switch_config_profile

    try:
        payload = switch_config_profile(
            profile,
            force=force,
            dry_run=dry_run,
        )
    except ValueError as exc:
        payload = _config_write_error_payload("switch", profile, str(exc))

    if json_output:
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    else:
        typer.echo(_format_config_write_result(payload))

    if not payload["ok"]:
        raise typer.Exit(code=1)


@app.command("smoke-profile")
def smoke_profile(
    profile: str = typer.Option(
        ...,
        "--profile",
        help="Profile to smoke check: sample, full, or pro.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Print structured JSON instead of concise text.",
    ),
    offline: bool = typer.Option(
        False,
        "--offline",
        help="Skip live storage ping and run static checks only.",
    ),
) -> None:
    """Run a no-write first-run smoke check for a target profile."""

    from deal_intel import _env
    from deal_intel.profile_smoke import build_profile_smoke_report

    try:
        payload = build_profile_smoke_report(
            profile,
            _env.load_config(),
            offline=offline,
        )
    except ValueError as exc:
        payload = {
            "ok": False,
            "profile": profile,
            "error_code": "INVALID_PROFILE",
            "message": str(exc),
        }

    if json_output:
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    else:
        typer.echo(_format_profile_smoke(payload))

    if not payload["ok"]:
        raise typer.Exit(code=1)


@app.command("storage-status")
def storage_status(
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Print structured JSON instead of concise text.",
    ),
) -> None:
    """Check the configured storage backend without starting an MCP client."""

    from deal_intel import _context
    from deal_intel.storage.diagnostics import local_sample_mode_hint

    try:
        backend = _context.storage_backend_name()
        storage = _context.mongo()
        ping = storage.ping()
        payload = {
            "ok": ping.get("status") == "ok",
            "storage_backend": backend,
            "database": getattr(storage, "database_name", None),
            "ping": ping,
        }
        if backend == "mongo" and ping.get("status") != "ok":
            payload["sample_mode_hint"] = ping.get(
                "sample_mode_hint",
                local_sample_mode_hint(),
            )
    except ValueError as exc:
        payload = {
            "ok": False,
            "storage_backend": None,
            "database": None,
            "ping": None,
            "error": str(exc),
            "sample_mode_hint": local_sample_mode_hint(),
        }

    if json_output:
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        typer.echo(_format_storage_status(payload))

    if not payload["ok"]:
        raise typer.Exit(code=1)


@app.command("audit-taxonomy")
def audit_taxonomy(
    include_all: bool = typer.Option(
        False,
        "--include-all",
        help="Include clean rows as well as rows that need taxonomy cleanup.",
    ),
    limit: int = typer.Option(
        50,
        "--limit",
        min=1,
        max=500,
        help="Maximum rows to return.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Print structured JSON instead of concise text.",
    ),
) -> None:
    """Audit industry/customer_segment hygiene without writing to storage."""

    from deal_intel import _context
    from deal_intel.schema.taxonomy_audit import build_taxonomy_audit

    deals = _context.mongo().list_deals_for_metrics()
    payload = build_taxonomy_audit(
        deals,
        include_all=include_all,
        limit=limit,
    )
    if json_output:
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    else:
        typer.echo(_format_taxonomy_audit(payload))


@app.command("apply-taxonomy-cleanup")
def apply_taxonomy_cleanup(
    limit: int = typer.Option(
        50,
        "--limit",
        min=1,
        max=500,
        help="Maximum audit rows to consider.",
    ),
    min_confidence: str = typer.Option(
        "high",
        "--min-confidence",
        help="Minimum confidence to include: high, medium, or low.",
    ),
    include_human_review: bool = typer.Option(
        False,
        "--include-human-review",
        help=(
            "Include rows that require human review. Intended for explicit, "
            "deal-by-deal operator decisions."
        ),
    ),
    apply: bool = typer.Option(
        False,
        "--apply",
        help="Write updates. Without this flag, only print a dry-run plan.",
    ),
    confirmed_by_user: bool = typer.Option(
        False,
        "--confirmed-by-user",
        help="Required with --apply to confirm the taxonomy cleanup should be written.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Print structured JSON instead of concise text.",
    ),
) -> None:
    """Apply safe industry/customer_segment cleanup through update_deal."""

    from deal_intel import _context
    from deal_intel.schema.taxonomy_audit import build_taxonomy_audit
    from deal_intel.tools import update_deal as _update_deal

    confidence_order = {"high": 0, "medium": 1, "low": 2}
    normalized_confidence = min_confidence.strip().lower()
    if normalized_confidence not in confidence_order:
        raise typer.BadParameter("min-confidence must be one of: high, medium, low")

    if apply and not confirmed_by_user:
        payload = {
            "ok": False,
            "dry_run": False,
            "error_code": "CONFIRMATION_REQUIRED",
            "message": (
                "apply-taxonomy-cleanup requires --confirmed-by-user with --apply."
            ),
        }
        if json_output:
            typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            typer.echo(_format_taxonomy_cleanup_result(payload))
        raise typer.Exit(code=1)

    mongo = _context.mongo()
    audit = build_taxonomy_audit(
        mongo.list_deals_for_metrics(),
        include_all=False,
        limit=limit,
    )
    candidates, skipped = _taxonomy_cleanup_candidates(
        audit.get("deals") or [],
        min_confidence=normalized_confidence,
        include_human_review=include_human_review,
    )
    results = []
    errors = []
    if apply:
        for row in candidates:
            payload = row.get("update_deal_payload") or {}
            try:
                result = _update_deal.handle(
                    mongo=mongo,
                    deal_id=payload["deal_id"],
                    industry=payload.get("industry"),
                    industry_tags=payload.get("industry_tags"),
                    customer_segment=payload.get("customer_segment"),
                    update_note=payload.get("update_note"),
                    confirmed_by_user=True,
                )
                results.append(
                    {
                        "deal_id": result["deal_id"],
                        "company": result["company"],
                        "changed_fields": result["changed_metadata_fields"],
                        "storage_written": result["storage_written"],
                    }
                )
            except Exception as exc:  # pragma: no cover - defensive CLI envelope
                errors.append(
                    {
                        "deal_id": row.get("deal_id"),
                        "company": row.get("company"),
                        "error": _redact_cli_error(exc),
                    }
                )

    payload = {
        "ok": not errors,
        "dry_run": not apply,
        "min_confidence": normalized_confidence,
        "include_human_review": include_human_review,
        "summary": {
            "audited_count": audit["summary"]["deal_count"],
            "issue_deal_count": audit["summary"]["issue_deal_count"],
            "candidate_count": len(candidates),
            "skipped_count": len(skipped),
            "applied_count": len(results),
            "error_count": len(errors),
        },
        "candidates": [
            {
                "deal_id": row.get("deal_id"),
                "company": row.get("company"),
                "current_industry": row.get("current_industry"),
                "current_customer_segment": row.get("current_customer_segment"),
                "suggested_industry": row.get("suggested_industry"),
                "suggested_industry_tags": row.get("suggested_industry_tags"),
                "suggested_customer_segment": row.get("suggested_customer_segment"),
                "confidence": row.get("confidence"),
                "needs_human_review": row.get("needs_human_review"),
                "review_explanation": row.get("review_explanation"),
            }
            for row in candidates
        ],
        "skipped": skipped,
        "results": results,
        "errors": errors,
    }
    if json_output:
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    else:
        typer.echo(_format_taxonomy_cleanup_result(payload))

    if not payload["ok"]:
        raise typer.Exit(code=1)


@app.command("backfill-industry-tags")
def backfill_industry_tags(
    limit: int = typer.Option(
        0,
        "--limit",
        min=0,
        max=5000,
        help="Maximum deals to scan. 0 means scan all readable deals.",
    ),
    apply: bool = typer.Option(
        False,
        "--apply",
        help="Write updates. Without this flag, only print a dry-run plan.",
    ),
    confirmed_by_user: bool = typer.Option(
        False,
        "--confirmed-by-user",
        help="Required with --apply to confirm the backfill should be written.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Print structured JSON instead of concise text.",
    ),
) -> None:
    """Backfill and normalize industry metadata from existing labels."""

    from deal_intel import _context
    from deal_intel.errors import MCPError
    from deal_intel.tools import backfill_industry_tags as _t

    try:
        payload = _t.handle(
            mongo=_context.mongo(),
            limit=limit,
            dry_run=not apply,
            confirmed_by_user=confirmed_by_user,
        )
    except MCPError as exc:
        payload = exc.to_envelope()
        if json_output:
            typer.echo(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
        else:
            typer.echo(_format_industry_tag_backfill_result(payload))
        raise typer.Exit(code=1) from exc

    if json_output:
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    else:
        typer.echo(_format_industry_tag_backfill_result(payload))

    if not payload["ok"]:
        raise typer.Exit(code=1)


@mongo_app.command("doctor")
def mongo_doctor(
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Print structured JSON instead of concise text.",
    ),
    offline: bool = typer.Option(
        False,
        "--offline",
        help="Skip live MongoDB ping, index, and schema reads.",
    ),
) -> None:
    """Diagnose MongoDB readiness for the full/pro profiles."""

    from deal_intel import _env
    from deal_intel.mongo_doctor import build_mongo_doctor_report

    payload = build_mongo_doctor_report(_env.load_config(), offline=offline)
    if json_output:
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        typer.echo(_format_mongo_doctor(payload))

    if not payload["ok"]:
        raise typer.Exit(code=1)


@mongo_app.command("apply-indexes")
def mongo_apply_indexes(
    apply: bool = typer.Option(
        False,
        "--apply",
        help="Create missing MongoDB indexes. Without this flag, only print dry-run output.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Print structured JSON instead of concise text.",
    ),
) -> None:
    """Create the versioned MongoDB index contract when --apply is set."""

    from deal_intel import _env
    from deal_intel.mongo_contracts import expected_mongo_indexes
    from deal_intel.storage.mongodb import MongoDBClient

    cfg = _env.load_config()
    database = _mapping(_mapping(cfg).get("mongodb")).get("database", "deal_intel")
    payload = {
        "ok": True,
        "dry_run": not apply,
        "database": database,
        "collections": {
            collection: [
                {
                    "name": spec.name,
                    "keys": list(spec.keys),
                    "unique": spec.unique,
                }
                for spec in specs
            ]
            for collection, specs in expected_mongo_indexes().items()
        },
    }
    if apply:
        try:
            client = MongoDBClient(database=database)
            client.ensure_indexes()
            payload["result"] = "applied"
        except Exception as exc:
            payload.update(
                {
                    "ok": False,
                    "result": "error",
                    "error": _redact_cli_error(exc),
                }
            )

    if json_output:
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    else:
        typer.echo(_format_mongo_apply_indexes(payload))

    if not payload["ok"]:
        raise typer.Exit(code=1)


@mongo_app.command("apply-schema")
def mongo_apply_schema(
    apply: bool = typer.Option(
        False,
        "--apply",
        help="Apply a MongoDB collection validator. Without this flag, only print dry-run output.",
    ),
    collection: str = typer.Option(
        "deals",
        "--collection",
        help=(
            "Validator target: deals, analytics_snapshots, delete_audit_logs, "
            "or all. Defaults to deals."
        ),
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Print structured JSON instead of concise text.",
    ),
) -> None:
    """Apply permissive v1 MongoDB collection validators when --apply is set."""

    from deal_intel import _env
    from deal_intel.mongo_contracts import (
        build_collection_schema_command,
        mongo_schema_collections,
    )
    from deal_intel.storage.mongodb import MongoDBClient

    managed_collections = mongo_schema_collections()
    if collection == "all":
        selected_collections = managed_collections
    elif collection in managed_collections:
        selected_collections = (collection,)
    else:
        valid = ", ".join((*managed_collections, "all"))
        raise typer.BadParameter(f"collection must be one of: {valid}")

    cfg = _env.load_config()
    database = _mapping(_mapping(cfg).get("mongodb")).get("database", "deal_intel")
    commands = {
        name: build_collection_schema_command(name) for name in selected_collections
    }
    command = commands[selected_collections[0]]
    payload = {
        "ok": True,
        "dry_run": not apply,
        "database": database,
        "collection": collection,
        "collections": list(selected_collections),
        "validation_action": command["validationAction"]
        if len(selected_collections) == 1
        else "mixed",
        "validation_level": command["validationLevel"]
        if len(selected_collections) == 1
        else "mixed",
        "available_collections": list(managed_collections),
    }
    if len(selected_collections) == 1:
        payload["command"] = command
    else:
        payload["commands"] = commands
    if apply:
        try:
            client = MongoDBClient(database=database)
            results = {
                name: _safe_mongo_command_result(
                    client.apply_deals_schema_validation()
                    if name == "deals"
                    else client.apply_collection_schema_validation(name)
                )
                for name in selected_collections
            }
            payload["result"] = (
                results[selected_collections[0]]
                if len(selected_collections) == 1
                else results
            )
        except Exception as exc:
            payload.update(
                {
                    "ok": False,
                    "result": "error",
                    "error": _redact_cli_error(exc),
                }
            )

    if json_output:
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    else:
        typer.echo(_format_mongo_apply_schema(payload))

    if not payload["ok"]:
        raise typer.Exit(code=1)


@mongo_app.command("apply-vector-index")
def mongo_apply_vector_index(
    apply: bool = typer.Option(
        False,
        "--apply",
        help=(
            "Create the Atlas Vector Search index. Requires M10+. Without this "
            "flag, only print dry-run output."
        ),
    ),
    dimensions: int = typer.Option(
        384,
        "--dimensions",
        help="Embedding vector dimensions for the deal_summary_vector index.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Print structured JSON instead of concise text.",
    ),
) -> None:
    """Create the Pro Atlas Vector Search index when --apply is set."""

    from deal_intel import _env
    from deal_intel.atlas_vector_indexes import (
        build_create_search_index_command,
        deal_summary_vector_index_name,
        load_deal_summary_vector_index_spec,
    )
    from deal_intel.storage.mongodb import MongoDBClient

    cfg = _env.load_config()
    database = _mapping(_mapping(cfg).get("mongodb")).get("database", "deal_intel")
    spec = load_deal_summary_vector_index_spec()
    command = build_create_search_index_command(dimensions=dimensions)
    payload = {
        "ok": True,
        "dry_run": not apply,
        "database": database,
        "collection": spec["collection"],
        "index_name": deal_summary_vector_index_name(),
        "minimum_cluster_tier": spec["minimum_cluster_tier"],
        "dimensions": dimensions,
        "command": command,
        "policy": "Pro/atlas mode must not silently fall back to python_cosine.",
    }
    if apply:
        try:
            client = MongoDBClient(database=database)
            payload["result"] = _safe_mongo_command_result(
                client.ensure_vector_index(dimensions=dimensions)
            )
        except Exception as exc:
            payload.update(
                {
                    "ok": False,
                    "result": "error",
                    "error": _redact_cli_error(exc),
                    "hint": (
                        "Atlas Vector Search requires M10+. Use full/python_cosine "
                        "until the pro cluster and index are ready."
                    ),
                }
            )

    if json_output:
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    else:
        typer.echo(_format_mongo_apply_vector_index(payload))

    if not payload["ok"]:
        raise typer.Exit(code=1)


@local_data_app.command("status")
def local_data_status(
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Print structured JSON instead of concise text.",
    ),
) -> None:
    """Show the local personal data directory and row counts."""

    store = _local_personal_store_from_config()
    payload = {
        "ok": True,
        "storage_backend": "local_personal",
        **store.summary(),
    }
    if json_output:
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        typer.echo(_format_local_data_status(payload))


@local_data_app.command("export")
def local_data_export(
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help=(
            "Optional JSON export path. Defaults to "
            "storage.local_data_dir/exports/local-data-<timestamp>.json."
        ),
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Print structured JSON instead of concise text.",
    ),
) -> None:
    """Export local personal deals and delete audit logs to a JSON snapshot."""

    store = _local_personal_store_from_config()
    payload = store.export_data(output_path=output)
    if json_output:
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        typer.echo(_format_local_data_export(payload))


@local_data_app.command("reset")
def local_data_reset(
    force: bool = typer.Option(
        False,
        "--force",
        help=(
            "Actually clear local personal deals. Without this flag the command "
            "is a dry-run."
        ),
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Print structured JSON instead of concise text.",
    ),
) -> None:
    """Clear local personal deals while preserving delete audit logs."""

    store = _local_personal_store_from_config()
    payload = store.reset_deals(force=force)
    if json_output:
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        typer.echo(_format_local_data_reset(payload))


@local_data_app.command("migrate-to-mongo")
def local_data_migrate_to_mongo(
    database: str = typer.Option(
        "",
        "--database",
        help="Target MongoDB database. Defaults to mongodb.database from config.",
    ),
    apply: bool = typer.Option(
        False,
        "--apply",
        help="Write to MongoDB. Without this flag the command is a dry-run.",
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        help="Replace target deals that already have the same deal_id.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Print structured JSON instead of concise text.",
    ),
) -> None:
    """Migrate user-created local personal deals into MongoDB."""

    from deal_intel import _env
    from deal_intel.errors import Stage, envelope_from_exception
    from deal_intel.storage.mongodb import MongoDBClient
    from deal_intel.tools import migrate_local_data as _migrate

    cfg = _env.load_config()
    target_database = database.strip() or _mapping(cfg.get("mongodb")).get(
        "database",
        "deal_intel",
    )
    try:
        payload = _migrate.handle(
            source_store=_local_personal_store_from_config(),
            target_mongo=MongoDBClient(database=target_database),
            dry_run=not apply,
            overwrite=overwrite,
            confirmed_by_user=apply,
        )
    except Exception as exc:
        payload = envelope_from_exception(exc, stage=Stage.STORAGE)

    if json_output:
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        typer.echo(_format_local_data_migration(payload))

    if not payload["ok"]:
        raise typer.Exit(code=1)


@app.command("backfill-customer-themes")
def backfill_customer_themes(
    apply: bool = typer.Option(
        False,
        "--apply",
        help="Write extracted themes to MongoDB. Without this flag, run as dry-run.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Reprocess meetings that already have customer_themes.",
    ),
    limit: int = typer.Option(0, "--limit", min=0, help="Maximum deals to scan; 0 means all."),
) -> None:
    """Extract customer themes for existing meeting records."""
    from deal_intel import _context
    from deal_intel.tools import backfill_customer_themes as _t

    result = _t.handle(
        mongo=_context.mongo(),
        llm=_context.llm_provider(),
        limit=limit,
        force=force,
        dry_run=not apply,
    )
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))


@app.command("render-atlas-dashboard")
def render_atlas_dashboard(
    as_of: str | None = typer.Option(
        None,
        "--as-of",
        help="Business date for rendered Atlas Charts placeholders, YYYY-MM-DD.",
    ),
    dashboard: str = typer.Option(
        "weekly_pipeline_review",
        "--dashboard",
        help="Dashboard id: weekly_pipeline_review, pipeline_trend, or customer_themes.",
    ),
    chart_id: str | None = typer.Option(
        None,
        "--chart-id",
        help="Optional chart id. If omitted, render the full dashboard spec.",
    ),
    lookback_days: int = typer.Option(
        7,
        "--lookback-days",
        help="Trend lookback window, used only by the pipeline_trend dashboard.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Optional path to write rendered JSON. Prints to stdout when omitted.",
    ),
) -> None:
    """Render Atlas Charts dashboard JSON for Atlas UI copy/paste."""
    from deal_intel._env import load_config
    from deal_intel.reports.atlas_charts import (
        render_chart_pipeline,
        render_dashboard_spec,
    )

    cfg = load_config()
    try:
        payload = (
            render_chart_pipeline(
                chart_id,
                cfg,
                as_of=as_of,
                lookback_days=lookback_days,
                dashboard=dashboard,
            )
            if chart_id
            else render_dashboard_spec(
                dashboard,
                cfg,
                as_of=as_of,
                lookback_days=lookback_days,
            )
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if output is None:
        typer.echo(text)
        return

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text + "\n", encoding="utf-8")
    typer.echo(str(output.resolve()))


@app.command("crosscheck-weekly-dashboard")
def crosscheck_weekly_dashboard(
    as_of: str | None = typer.Option(
        None,
        "--as-of",
        help="Business date for cross-checking metrics, reports, and Atlas pipelines.",
    ),
    output_dir: Path | None = typer.Option(
        None,
        "--output-dir",
        help="Directory for the generated CSV/Markdown report artifacts.",
    ),
) -> None:
    """Cross-check get_metrics, weekly reports, and Atlas Charts pipelines."""
    from deal_intel import _context
    from deal_intel.reports.atlas_charts import render_chart_pipeline
    from deal_intel.reports.dashboard_crosscheck import (
        build_weekly_pipeline_dashboard_crosscheck,
    )
    from deal_intel.tools import export_report as _export_report
    from deal_intel.tools import get_metrics as _get_metrics

    cfg = _context.config()
    mongo = _context.mongo()
    metrics_result = _get_metrics.handle(
        mongo=mongo,
        cfg=cfg,
        metric_type="pipeline_health",
        as_of=as_of,
    )
    report_result = _export_report.handle(
        mongo=mongo,
        cfg=cfg,
        report_type="weekly_pipeline",
        output_dir=str(output_dir) if output_dir is not None else None,
        as_of=as_of,
    )
    atlas_results = {
        chart_id: mongo.aggregate_deals(
            render_chart_pipeline(chart_id, cfg, as_of=as_of)
        )
        for chart_id in (
            "pipeline_kpis",
            "stage_breakdown",
            "health_bands",
            "attention_deals",
            "meddpicc_gap_distribution",
        )
    }
    result = build_weekly_pipeline_dashboard_crosscheck(
        metrics_result=metrics_result,
        report_result=report_result,
        atlas_results=atlas_results,
    )
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["ok"]:
        raise typer.Exit(code=1)


@app.command("smoke-deal-review")
def smoke_deal_review(
    deal_id: str | None = typer.Option(
        None,
        "--deal-id",
        help="Exact deal_id to review. Overrides --company and --limit selection.",
    ),
    company: str | None = typer.Option(
        None,
        "--company",
        help="Case-insensitive company name substring to review.",
    ),
    limit: int = typer.Option(
        5,
        "--limit",
        min=1,
        max=20,
        help="Maximum deals to review when --deal-id is omitted.",
    ),
    as_of: str | None = typer.Option(
        None,
        "--as-of",
        help="Business date for deal review, YYYY-MM-DD.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Print full structured JSON instead of concise text.",
    ),
) -> None:
    """Run local read-only get_deal_review smoke checks without a Desktop MCP client."""
    from deal_intel import _context
    from deal_intel.errors import MCPError
    from deal_intel.tools import get_deal_review as _get_deal_review

    cfg = _context.config()
    mongo = _context.mongo()
    try:
        deals = mongo.list_deals_for_metrics()
        selected = _select_deal_review_smoke_deals(
            deals,
            deal_id=deal_id,
            company=company,
            limit=limit,
        )
        results = [
            _get_deal_review.handle(
                mongo=mongo,
                cfg=cfg,
                deal_id=str(deal["deal_id"]),
                as_of=as_of,
            )
            for deal in selected
        ]
    except MCPError as exc:
        _emit_smoke_error(exc.to_envelope(), json_output=json_output)
        raise typer.Exit(code=1) from exc
    except ValueError as exc:
        _emit_smoke_error(
            {
                "ok": False,
                "error_code": "INVALID_INPUT",
                "stage": "preflight",
                "message": str(exc),
                "hint": None,
                "retryable": False,
            },
            json_output=json_output,
        )
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        _emit_smoke_error(
            {
                "ok": False,
                "error_code": "INTERNAL",
                "stage": "cli",
                "message": f"{type(exc).__name__}: {exc}",
                "hint": None,
                "retryable": False,
            },
            json_output=json_output,
        )
        raise typer.Exit(code=1) from exc

    payload = {
        "ok": True,
        "as_of": results[0].get("as_of") if results else as_of,
        "timezone": results[0].get("timezone") if results else None,
        "count": len(results),
        "sensitive_field_check": {"ok": True},
        "results": results,
    }
    if _contains_sensitive_result_key(payload):
        payload["ok"] = False
        payload["sensitive_field_check"]["ok"] = False
        _emit_smoke_error(
            {
                "ok": False,
                "error_code": "SENSITIVE_FIELD_EXPOSED",
                "stage": "cli",
                "message": "Smoke result contains a restricted sensitive field key.",
                "hint": {"blocked_keys": sorted(SENSITIVE_RESULT_KEYS)},
                "retryable": False,
            },
            json_output=json_output,
        )
        raise typer.Exit(code=2)

    if json_output:
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    typer.echo(_format_deal_review_smoke(payload))


@app.command("smoke-deal-review-audit")
def smoke_deal_review_audit(
    company: str | None = typer.Option(
        None,
        "--company",
        help="Case-insensitive company name substring to include.",
    ),
    stage: str | None = typer.Option(
        None,
        "--stage",
        help="Exact pipeline stage to include.",
    ),
    industry: str | None = typer.Option(
        None,
        "--industry",
        help="Exact industry value to include.",
    ),
    limit: int = typer.Option(
        50,
        "--limit",
        min=1,
        max=200,
        help="Maximum deals to review.",
    ),
    as_of: str | None = typer.Option(
        None,
        "--as-of",
        help="Business date for deal review, YYYY-MM-DD.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Print full structured JSON instead of concise text.",
    ),
    fail_on_issues: bool = typer.Option(
        False,
        "--fail-on-issues",
        help="Exit with code 2 when the audit finds review-quality issues.",
    ),
) -> None:
    """Audit all selected deal reviews for payload quality and decision usefulness."""
    from deal_intel import _context
    from deal_intel.schema.deal_review import build_deal_review
    from deal_intel.schema.metrics import (
        VALID_STAGES,
        HealthBandThresholds,
        PipelineTimingSettings,
        ReportingContext,
    )

    cfg = _context.config()
    mongo = _context.mongo()
    try:
        if stage is not None and stage.strip() and stage.strip() not in VALID_STAGES:
            raise ValueError(f"stage {stage.strip()!r} is not valid")
        reporting = ReportingContext.from_config(cfg, as_of=as_of)
        health_thresholds = HealthBandThresholds.from_config(cfg)
        timing_settings = PipelineTimingSettings.from_config(cfg)
        deals = mongo.list_deals_for_metrics()
        selected = _select_deal_review_audit_deals(
            deals,
            company=company,
            stage=stage,
            industry=industry,
            limit=limit,
        )
        results = []
        for deal in selected:
            review = build_deal_review(
                deal,
                as_of=reporting.as_of,
                health_thresholds=health_thresholds,
                timing_settings=timing_settings,
            )
            review["_audit_actual_close_date"] = deal.get("actual_close_date")
            review["_audit_close_reason"] = deal.get("close_reason")
            results.append(
                {
                    "ok": True,
                    **reporting.to_dict(),
                    "review": review,
                }
            )
    except ValueError as exc:
        _emit_smoke_error(
            {
                "ok": False,
                "error_code": "INVALID_INPUT",
                "stage": "preflight",
                "message": str(exc),
                "hint": None,
                "retryable": False,
            },
            json_output=json_output,
        )
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        _emit_smoke_error(
            {
                "ok": False,
                "error_code": "INTERNAL",
                "stage": "cli",
                "message": f"{type(exc).__name__}: {exc}",
                "hint": None,
                "retryable": False,
            },
            json_output=json_output,
        )
        raise typer.Exit(code=1) from exc

    payload = _build_deal_review_audit_payload(
        results,
        filters={
            "company": company.strip() if company and company.strip() else None,
            "stage": stage.strip() if stage and stage.strip() else None,
            "industry": industry.strip() if industry and industry.strip() else None,
            "limit": limit,
        },
    )
    if _contains_sensitive_result_key(payload):
        payload["ok"] = False
        payload["sensitive_field_check"]["ok"] = False
        _emit_smoke_error(
            {
                "ok": False,
                "error_code": "SENSITIVE_FIELD_EXPOSED",
                "stage": "cli",
                "message": "Audit result contains a restricted sensitive field key.",
                "hint": {"blocked_keys": sorted(SENSITIVE_RESULT_KEYS)},
                "retryable": False,
            },
            json_output=json_output,
        )
        raise typer.Exit(code=2)

    if json_output:
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        typer.echo(_format_deal_review_audit(payload))

    if fail_on_issues and payload["summary"]["quality_issue_count"] > 0:
        raise typer.Exit(code=2)


@app.command("smoke-natural-questions")
def smoke_natural_questions(
    as_of: str | None = typer.Option(
        None,
        "--as-of",
        help="Business date for deterministic natural-question smoke checks.",
    ),
    output_dir: Path | None = typer.Option(
        None,
        "--output-dir",
        help="Directory for summary.md, summary.json, and per-question JSON files.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Print full structured JSON instead of concise text.",
    ),
) -> None:
    """Run deterministic natural-question smoke checks and save evidence files."""
    from deal_intel import _context

    cfg = _context.config()
    mongo = _context.mongo()
    try:
        payload = _build_natural_question_smoke_pack(
            mongo=mongo,
            cfg=cfg,
            as_of=as_of,
        )
        payload["output_dir"] = str(
            _write_natural_question_smoke_artifacts(payload, output_dir=output_dir)
        )
    except Exception as exc:
        _emit_smoke_error(
            {
                "ok": False,
                "error_code": "INTERNAL",
                "stage": "cli",
                "message": f"{type(exc).__name__}: {exc}",
                "hint": None,
                "retryable": False,
            },
            json_output=json_output,
        )
        raise typer.Exit(code=1) from exc

    if json_output:
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    else:
        typer.echo(_format_natural_question_smoke(payload))

    if not payload["ok"]:
        raise typer.Exit(code=2)


def _format_storage_status(payload: dict) -> str:
    status = "OK" if payload.get("ok") else "not ready"
    lines = [
        f"Storage status: {status}",
        f"Backend: {payload.get('storage_backend') or 'unknown'}",
        f"Database: {payload.get('database') or 'unknown'}",
    ]
    ping = payload.get("ping") or {}
    if ping:
        lines.append(f"Ping: {ping.get('status')}")
        if ping.get("sample_dataset"):
            lines.append(
                "Sample dataset: "
                f"{ping.get('sample_dataset')} "
                f"({ping.get('sample_dataset_version')})"
            )
        if ping.get("deal_count") is not None:
            lines.append(
                f"Sample rows: deals={ping.get('deal_count')}, "
                f"snapshots={ping.get('snapshot_count')}"
            )
        if ping.get("message"):
            lines.append(f"Message: {ping.get('message')}")
        if ping.get("fix"):
            lines.append(f"Fix: {ping.get('fix')}")
    if payload.get("error"):
        lines.append(f"Error: {payload.get('error')}")

    hint = payload.get("sample_mode_hint")
    if isinstance(hint, dict):
        lines.extend(
            [
                "",
                "Sample mode:",
                f"- Temporary PowerShell: {hint.get('powershell')}",
                f"- Persistent config: add to {hint.get('user_config_path')}",
                "  storage:",
                "    backend: local_sample",
            ]
        )
    return "\n".join(lines)


def _format_taxonomy_audit(payload: dict) -> str:
    summary = payload["summary"]
    lines = [
        "Taxonomy audit: read-only",
        (
            "Deals: "
            f"{summary['deal_count']} scanned, "
            f"{summary['issue_deal_count']} need review, "
            f"{summary['returned_count']} shown"
        ),
    ]
    if summary.get("issue_counts"):
        issues = ", ".join(
            f"{key}={value}" for key, value in summary["issue_counts"].items()
        )
        lines.append(f"Issues: {issues}")
    if summary.get("needs_human_review_count"):
        lines.append(
            f"Human review required: {summary['needs_human_review_count']} rows"
        )
    warnings = payload.get("warnings") or []
    for warning in warnings:
        lines.append(f"Warning: {warning.get('code')} - {warning.get('message')}")

    rows = payload.get("deals") or []
    if not rows:
        lines.append("")
        lines.append("No taxonomy issues found.")
        return "\n".join(lines)

    lines.append("")
    lines.append("Rows:")
    for row in rows:
        lines.append(
            "- "
            f"{row.get('company')} ({row.get('deal_id')}) "
            f"[{row.get('confidence')}]"
        )
        lines.append(
            "  current: "
            f"industry={row.get('current_industry') or '-'}, "
            f"segment={row.get('current_customer_segment') or '-'}"
        )
        lines.append(
            "  suggested: "
            f"industry={row.get('suggested_industry') or '-'}, "
            f"segment={row.get('suggested_customer_segment') or '-'}"
        )
        lines.append(f"  issues: {', '.join(row.get('issues') or [])}")
        if row.get("needs_human_review"):
            explanation = row.get("review_explanation") or {}
            lines.append("  review: confirm against full deal context before update_deal")
            if explanation.get("why_human_review"):
                lines.append(f"  why: {explanation['why_human_review']}")
            checks = explanation.get("what_to_check") or []
            if checks:
                lines.append(f"  check: {' / '.join(str(item) for item in checks)}")
    return "\n".join(lines)


def _taxonomy_cleanup_candidates(
    rows: list[dict],
    *,
    min_confidence: str,
    include_human_review: bool,
) -> tuple[list[dict], list[dict]]:
    confidence_rank = {"high": 0, "medium": 1, "low": 2}
    max_rank = confidence_rank[min_confidence]
    candidates = []
    skipped = []
    for row in rows:
        confidence = str(row.get("confidence") or "low")
        rank = confidence_rank.get(confidence, 99)
        reason = None
        if rank > max_rank:
            reason = f"confidence_below_{min_confidence}"
        elif row.get("needs_human_review") and not include_human_review:
            reason = "human_review_required"
        elif not row.get("update_deal_payload"):
            reason = "no_update_payload"
        if reason is None:
            candidates.append(row)
        else:
            skipped.append(
                {
                    "deal_id": row.get("deal_id"),
                    "company": row.get("company"),
                    "confidence": confidence,
                    "reason": reason,
                    "review_explanation": row.get("review_explanation"),
                }
            )
    return candidates, skipped


def _format_taxonomy_cleanup_result(payload: dict) -> str:
    if not payload.get("ok") and payload.get("error_code"):
        return (
            "Taxonomy cleanup: not applied\n"
            f"Error: {payload.get('error_code')} - {payload.get('message')}"
        )

    summary = payload["summary"]
    mode = "dry-run" if payload.get("dry_run") else "apply"
    lines = [
        f"Taxonomy cleanup: {mode}",
        (
            "Deals: "
            f"{summary['audited_count']} audited, "
            f"{summary['issue_deal_count']} issue rows, "
            f"{summary['candidate_count']} candidate(s), "
            f"{summary['skipped_count']} skipped"
        ),
    ]
    if payload.get("dry_run"):
        lines.append(
            "No storage writes were made. Re-run with --apply --confirmed-by-user "
            "to write the candidate rows."
        )
    else:
        lines.append(
            f"Applied: {summary['applied_count']} row(s), "
            f"errors: {summary['error_count']}"
        )

    candidates = payload.get("candidates") or []
    if candidates:
        lines.append("")
        lines.append("Candidates:")
        for row in candidates:
            lines.append(
                "- "
                f"{row.get('company')} ({row.get('deal_id')}) "
                f"[{row.get('confidence')}]"
            )
            lines.append(
                "  current: "
                f"industry={row.get('current_industry') or '-'}, "
                f"segment={row.get('current_customer_segment') or '-'}"
            )
            lines.append(
                "  update: "
                f"industry={row.get('suggested_industry') or '-'}, "
                f"segment={row.get('suggested_customer_segment') or '-'}"
            )
            explanation = row.get("review_explanation") or {}
            if explanation.get("reason"):
                lines.append(f"  why safe: {explanation['reason']}")

    skipped = payload.get("skipped") or []
    if skipped:
        lines.append("")
        lines.append("Skipped:")
        for row in skipped[:10]:
            lines.append(
                "- "
                f"{row.get('company')} ({row.get('deal_id')}) "
                f"[{row.get('confidence')}] {row.get('reason')}"
            )
            explanation = row.get("review_explanation") or {}
            why = explanation.get("why_human_review") or explanation.get("reason")
            if why:
                lines.append(f"  why: {why}")
        if len(skipped) > 10:
            lines.append(f"... +{len(skipped) - 10} more skipped row(s)")

    errors = payload.get("errors") or []
    if errors:
        lines.append("")
        lines.append("Errors:")
        for error in errors:
            lines.append(
                f"- {error.get('company')} ({error.get('deal_id')}): "
                f"{error.get('error')}"
            )
    return "\n".join(lines)


def _format_industry_tag_backfill_result(payload: dict) -> str:
    if not payload.get("ok") and payload.get("error_code"):
        return (
            "Industry metadata backfill: not applied\n"
            f"Error: {payload.get('error_code')} - {payload.get('message')}"
        )

    summary = payload["summary"]
    mode = "dry-run" if payload.get("dry_run") else "apply"
    lines = [
        f"Industry metadata backfill: {mode}",
        (
            "Deals: "
            f"{summary['deals_scanned']} scanned, "
            f"{summary['candidate_count']} candidate(s), "
            f"{summary.get('research_count', 0)} research, "
            f"{summary['clean_count']} clean, "
            f"{summary['skipped_count']} skipped"
        ),
    ]
    if summary.get("issue_counts"):
        issue_text = ", ".join(
            f"{key}={value}" for key, value in summary["issue_counts"].items()
        )
        lines.append(f"Issue/action counts: {issue_text}")

    if payload.get("dry_run"):
        lines.append(
            "No storage writes were made. Re-run with --apply --confirmed-by-user "
            "after reviewing the candidates."
        )
    else:
        lines.append(
            f"Applied: {summary['applied_count']} row(s), "
            f"errors: {summary['error_count']}"
        )

    candidates = payload.get("candidates") or []
    if candidates:
        lines.append("")
        lines.append("Candidates:")
        for row in candidates:
            lines.append(
                "- "
                f"{row.get('company')} ({row.get('deal_id')}) "
                f"action={row.get('action')}"
            )
            lines.append(
                "  "
                f"current_industry={row.get('industry') or '-'}, "
                f"suggested_industry={row.get('suggested_industry') or '-'}, "
                f"current_tags={row.get('current_industry_tags') or []}, "
                f"suggested_tags={row.get('suggested_industry_tags') or []}, "
                f"segment={row.get('current_customer_segment') or '-'} -> "
                f"{row.get('suggested_customer_segment') or '-'}"
            )
            if row.get("confidence"):
                lines.append(f"  confidence={row.get('confidence')}")
            if row.get("taxonomy_warnings"):
                codes = [
                    str(warning.get("code"))
                    for warning in row.get("taxonomy_warnings") or []
                ]
                lines.append(f"  warnings={codes}")

    research = payload.get("research") or []
    if research:
        lines.append("")
        lines.append("Needs AI research:")
        for row in research[:10]:
            lines.append(
                "- "
                f"{row.get('company')} ({row.get('deal_id')}) "
                f"action={row.get('action')}"
            )
            if row.get("research_query"):
                lines.append(f"  search: {row.get('research_query')}")
            if row.get("recommended_action"):
                lines.append(f"  next: {row.get('recommended_action')}")
        if len(research) > 10:
            lines.append(f"... {len(research) - 10} more research row(s)")

    skipped = payload.get("skipped") or []
    if skipped:
        lines.append("")
        lines.append("Skipped:")
        for row in skipped[:10]:
            lines.append(
                "- "
                f"{row.get('company')} ({row.get('deal_id')}) "
                f"reason={row.get('reason')}"
            )
            if row.get("candidates"):
                lines.append(f"  candidates={row.get('candidates')}")
            if row.get("suggested_industry"):
                lines.append(f"  suggested_industry={row.get('suggested_industry')}")
            if row.get("unmapped_parts"):
                lines.append(f"  unmapped_parts={row.get('unmapped_parts')}")
        if len(skipped) > 10:
            lines.append(f"... {len(skipped) - 10} more skipped row(s)")

    errors = payload.get("errors") or []
    if errors:
        lines.append("")
        lines.append("Errors:")
        for row in errors:
            lines.append(
                "- "
                f"{row.get('company')} ({row.get('deal_id')}): {row.get('error')}"
            )
    return "\n".join(lines)


def _format_mongo_doctor(payload: dict) -> str:
    summary = payload["summary"]
    lines = [
        f"Mongo doctor: {'OK' if payload['ok'] else 'not ready'}",
        f"Profile: {payload['profile']}",
        (
            "Runtime: "
            f"storage={summary['storage_backend']}, "
            f"database={summary['mongodb_database']}, "
            f"vector_search={summary['vector_search']}, "
            f"offline={summary['offline']}"
        ),
        (
            "Checks: "
            f"fail={summary['failed_checks']}, "
            f"warn={summary['warning_checks']}, "
            f"skipped={summary['skipped_checks']}"
        ),
        "",
        "Details:",
    ]
    for check in payload["checks"]:
        marker = {
            "pass": "PASS",
            "warn": "WARN",
            "fail": "FAIL",
            "skipped": "SKIP",
        }.get(check.get("status"), str(check.get("status")).upper())
        lines.append(f"- {marker} {check['label']}: {check['message']}")
    if payload["next_actions"]:
        lines.extend(["", "Next actions:"])
        for action in payload["next_actions"]:
            lines.append(f"- [{action['check_id']}] {action['hint']}")
    return "\n".join(lines)


def _format_mongo_apply_indexes(payload: dict) -> str:
    status = "dry-run" if payload.get("dry_run") else payload.get("result", "applied")
    lines = [
        f"Mongo index contract: {status}",
        f"Database: {payload.get('database')}",
    ]
    collections = _mapping(payload.get("collections"))
    for collection, specs in collections.items():
        lines.append(f"- {collection}: {len(specs)} index(es)")
    if payload.get("dry_run"):
        lines.append("Run again with --apply to create missing indexes.")
    if payload.get("error"):
        lines.append(f"Error: {payload['error']}")
    return "\n".join(lines)


def _format_mongo_apply_schema(payload: dict) -> str:
    status = "dry-run" if payload.get("dry_run") else payload.get("result", "applied")
    collections = payload.get("collections") or [payload.get("collection")]
    lines = [
        f"Mongo schema contract: {status}",
        f"Database: {payload.get('database')}",
        f"Collection: {payload.get('collection')}",
        (
            "Validation: "
            f"action={payload.get('validation_action')}, "
            f"level={payload.get('validation_level')}"
        ),
    ]
    if collections:
        lines.append(f"Managed validators: {', '.join(str(item) for item in collections)}")
    if payload.get("dry_run"):
        lines.append("Run again with --apply to apply this collection validator.")
    if payload.get("error"):
        lines.append(f"Error: {payload['error']}")
    return "\n".join(lines)


def _format_mongo_apply_vector_index(payload: dict) -> str:
    status = "dry-run" if payload.get("dry_run") else payload.get("result", "applied")
    lines = [
        f"Mongo Atlas vector index: {status}",
        f"Database: {payload.get('database')}",
        f"Collection: {payload.get('collection')}",
        f"Index: {payload.get('index_name')}",
        f"Minimum cluster tier: {payload.get('minimum_cluster_tier')}",
        f"Dimensions: {payload.get('dimensions')}",
        f"Policy: {payload.get('policy')}",
    ]
    if payload.get("dry_run"):
        lines.append("Run again with --apply only on a prepared M10+ Atlas cluster.")
    if payload.get("error"):
        lines.append(f"Error: {payload['error']}")
    if payload.get("hint"):
        lines.append(f"Hint: {payload['hint']}")
    return "\n".join(lines)


def _format_local_data_status(payload: dict) -> str:
    return "\n".join(
        [
            "Local personal data:",
            f"Data dir: {payload.get('data_dir')}",
            f"Deals file: {payload.get('deals_path')}",
            f"Delete audit file: {payload.get('delete_audit_logs_path')}",
            f"Deals: {payload.get('deal_count')}",
            f"Delete audit logs: {payload.get('delete_audit_log_count')}",
            (
                "Note: bundled fixture data is immutable and is not counted as "
                "local personal data."
            ),
        ]
    )


def _format_local_data_export(payload: dict) -> str:
    return "\n".join(
        [
            "Local personal data export: OK",
            f"Export path: {payload.get('export_path')}",
            f"Data dir: {payload.get('data_dir')}",
            f"Deals: {payload.get('deal_count')}",
            f"Delete audit logs: {payload.get('delete_audit_log_count')}",
        ]
    )


def _format_local_data_reset(payload: dict) -> str:
    status = "dry-run" if payload.get("dry_run") else "applied"
    lines = [
        f"Local personal data reset: {status}",
        f"Data dir: {payload.get('data_dir')}",
        f"Deals file: {payload.get('deals_path')}",
        f"Would delete deals: {payload.get('would_delete_deal_count')}",
        (
            "Preserved delete audit logs: "
            f"{payload.get('preserved_delete_audit_log_count')}"
        ),
        f"Storage written: {payload.get('storage_written')}",
    ]
    if payload.get("dry_run"):
        lines.append("Run again with --force to clear only local personal deals.")
    else:
        lines.append("Delete audit logs were preserved.")
    return "\n".join(lines)


def _format_local_data_migration(payload: dict) -> str:
    if not payload.get("ok"):
        lines = [
            "Local personal data migration: not ready",
            f"Error: {payload.get('error_code')}",
            f"Stage: {payload.get('stage')}",
            f"Message: {payload.get('message')}",
        ]
        if payload.get("hint") is not None:
            lines.append(f"Hint: {payload.get('hint')}")
        return "\n".join(lines)

    status = "dry-run" if payload.get("dry_run") else "applied"
    counts = _mapping(payload.get("counts"))
    source = _mapping(payload.get("source"))
    target = _mapping(payload.get("target"))
    lines = [
        f"Local personal data migration: {status}",
        f"Source data dir: {source.get('data_dir')}",
        f"Target MongoDB database: {target.get('database')}",
        f"Source deals: {counts.get('source_deals')}",
        f"Would create: {counts.get('would_create')}",
        f"Would overwrite: {counts.get('would_overwrite')}",
        f"Would skip existing: {counts.get('would_skip_existing')}",
        f"Storage written: {payload.get('storage_written')}",
    ]
    if payload.get("dry_run"):
        lines.append("Run again with --apply to write these local deals to MongoDB.")
    else:
        lines.extend(
            [
                f"Migrated: {counts.get('migrated')}",
                f"Overwritten: {counts.get('overwritten')}",
                f"Skipped existing: {counts.get('skipped_existing')}",
            ]
        )
    warnings = payload.get("warnings") or []
    if warnings:
        lines.append("Warnings:")
        for warning in warnings:
            lines.append(f"- {warning.get('code')}: {warning.get('message')}")
    return "\n".join(lines)


def _summarize_config_for_display(cfg: dict[str, Any]) -> dict[str, Any]:
    from deal_intel.tool_surfaces import resolve_tool_surface, tool_names_for_config

    llm = _mapping(cfg.get("llm"))
    mongodb = _mapping(cfg.get("mongodb"))
    storage = _mapping(cfg.get("storage"))
    tools = _mapping(cfg.get("tools"))
    reporting = _mapping(cfg.get("reporting"))
    pipeline = _mapping(cfg.get("pipeline"))
    expected_close = _mapping(pipeline.get("expected_close"))
    metrics = _mapping(cfg.get("metrics"))
    health_bands = _mapping(metrics.get("health_bands"))
    try:
        resolved_tool_surface = resolve_tool_surface(cfg)
        mcp_tool_count = len(tool_names_for_config(cfg))
    except ValueError:
        resolved_tool_surface = None
        mcp_tool_count = 1
    return {
        "storage": {
            "backend": storage.get("backend", "mongo"),
            "local_data_dir": storage.get("local_data_dir"),
        },
        "tools": {
            "surface": tools.get("surface", "auto"),
            "resolved_surface": resolved_tool_surface,
            "mcp_tool_count": mcp_tool_count,
        },
        "mongodb": {
            "database": mongodb.get("database", "deal_intel"),
            "demo_database": mongodb.get("demo_database"),
            "vector_search": mongodb.get("vector_search", "python_cosine"),
        },
        "llm": {
            "provider": llm.get("provider", "chatgpt_oauth"),
            "chatgpt_oauth_model": llm.get("chatgpt_oauth_model"),
            "openai_api_model": llm.get("openai_api_model"),
            "openai_api_reasoning_effort": llm.get("openai_api_reasoning_effort"),
            "draft_model": llm.get("draft_model"),
        },
        "reporting": {
            "timezone": reporting.get("timezone"),
            "output_dir": reporting.get("output_dir"),
        },
        "pipeline": {
            "expected_close_default_days": expected_close.get("default_days"),
            "stuck_threshold_days": pipeline.get("stuck_threshold_days"),
        },
        "metrics": {
            "healthy_min": health_bands.get("healthy_min"),
            "watch_min": health_bands.get("watch_min"),
        },
    }


def _summarize_config_environment() -> dict[str, dict[str, bool]]:
    return {
        key: {"configured": bool(os.environ.get(key))}
        for key in CONFIG_ENV_KEYS
    }


def _format_config_profiles(payload: dict) -> str:
    lines = ["Config profiles:"]
    for profile in payload["profiles"]:
        storage_patch = profile["config_patch"]["storage"]
        mongodb_patch = profile["config_patch"]["mongodb"]
        llm_patch = profile["config_patch"]["llm"]
        local_data_dir = storage_patch.get("local_data_dir", "preserve")
        lines.extend(
            [
                f"- {profile['name']} ({profile['title']}): "
                f"{profile['description']}",
                f"  storage={storage_patch['backend']}, "
                f"local_data_dir={local_data_dir}, "
                f"vector_search={mongodb_patch['vector_search']}, "
                f"llm={llm_patch['provider']}",
            ]
        )
    return "\n".join(lines)


def _format_config_show(payload: dict) -> str:
    cfg = payload["effective_config"]
    env = payload["environment"]
    configured_env = [
        key for key, value in env.items() if value.get("configured")
    ]
    lines = [
        f"Config profile: {payload['profile']}",
        f"User config: {payload['user_config_path']} "
        f"({'exists' if payload['user_config_exists'] else 'missing'})",
        (
            "Storage: "
            f"{cfg['storage']['backend']} | "
            f"local_data_dir={cfg['storage']['local_data_dir']} | "
            f"Mongo database: {cfg['mongodb']['database']} | "
            f"Vector search: {cfg['mongodb']['vector_search']}"
        ),
        (
            "Tools: "
            f"surface={cfg['tools']['surface']} | "
            f"resolved={cfg['tools']['resolved_surface']} | "
            f"mcp_tools={cfg['tools']['mcp_tool_count']}"
        ),
        (
            "LLM: "
            f"{cfg['llm']['provider']} | "
            f"ChatGPT model: {cfg['llm']['chatgpt_oauth_model']} | "
            f"OpenAI model: {cfg['llm']['openai_api_model']}"
        ),
        (
            "Reporting: "
            f"timezone={cfg['reporting']['timezone']}, "
            f"output_dir={cfg['reporting']['output_dir']}"
        ),
        (
            "Configured env keys: "
            f"{', '.join(configured_env) if configured_env else 'none'}"
        ),
        "Secret values are redacted; only configured true/false is shown.",
    ]
    return "\n".join(lines)


def _format_config_doctor(payload: dict) -> str:
    summary = payload["summary"]
    lines = [
        f"Config doctor: {'OK' if payload['ok'] else 'not ready'}",
        f"Profile: {payload['profile']}",
        (
            "Runtime: "
            f"storage={summary['storage_backend']}, "
            f"database={summary['mongodb_database']}, "
            f"vector_search={summary['vector_search']}, "
            f"llm={summary['llm_provider']}, "
            f"tools={summary.get('resolved_tool_surface')}"
        ),
        (
            "Checks: "
            f"fail={summary['failed_checks']}, "
            f"warn={summary['warning_checks']}, "
            f"skipped={summary['skipped_checks']}"
        ),
        "",
        "Details:",
    ]
    for check in payload["checks"]:
        marker = {
            "pass": "PASS",
            "warn": "WARN",
            "fail": "FAIL",
            "skipped": "SKIP",
        }.get(check.get("status"), str(check.get("status")).upper())
        lines.append(f"- {marker} {check['label']}: {check['message']}")
    if payload["next_actions"]:
        lines.extend(["", "Next actions:"])
        for action in payload["next_actions"]:
            rendered = action["action"]
            if isinstance(rendered, dict):
                rendered = json.dumps(rendered, ensure_ascii=False)
            lines.append(f"- [{action['check_id']}] {rendered}")
    return "\n".join(lines)


def _format_config_write_result(payload: dict) -> str:
    command = payload.get("command", "config")
    status = "OK" if payload.get("ok") else "not applied"
    lines = [
        f"Config {command}: {status}",
        f"Profile: {payload.get('profile')}",
        f"User config: {payload.get('user_config_path')}",
        (
            "Mode: "
            f"dry_run={payload.get('dry_run')}, "
            f"force={payload.get('force')}, "
            f"storage_written={payload.get('storage_written')}"
        ),
    ]
    if payload.get("backup_written"):
        lines.append(f"Backup written: {payload.get('backup_path')}")
    elif payload.get("backup_path") and payload.get("force"):
        lines.append(f"Backup path: {payload.get('backup_path')}")
    if payload.get("message"):
        lines.append(f"Message: {payload.get('message')}")

    changes = payload.get("changed_fields") or []
    if changes:
        lines.extend(["", "Profile-managed changes:"])
        for change in changes:
            lines.append(
                f"- {change['field']}: {change.get('old')!r} -> {change.get('new')!r}"
            )
    target_values = payload.get("target_profile_values") or {}
    if target_values:
        lines.extend(["", "Target profile values:"])
        for field, value in target_values.items():
            lines.append(f"- {field}: {value}")

    doctor = payload.get("doctor")
    if isinstance(doctor, dict):
        summary = doctor.get("summary") or {}
        lines.extend(
            [
                "",
                "Doctor preview (offline):",
                (
                    "- "
                    f"status={summary.get('status')}, "
                    f"fail={summary.get('failed_checks')}, "
                    f"warn={summary.get('warning_checks')}, "
                    f"skipped={summary.get('skipped_checks')}"
                ),
            ]
        )
    if payload.get("requires_force"):
        lines.extend(["", "Re-run with --force to apply after backup."])
    return "\n".join(lines)


def _format_profile_smoke(payload: dict) -> str:
    if not payload.get("ok") and payload.get("error_code"):
        return "\n".join(
            [
                "Profile smoke: not ready",
                f"Profile: {payload.get('profile')}",
                f"Error: {payload.get('message')}",
            ]
        )

    contract = payload.get("contract") or {}
    doctor = payload.get("doctor") or {}
    summary = doctor.get("summary") or {}
    target_values = payload.get("target_profile_values") or {}
    lines = [
        f"Profile smoke: {'OK' if payload.get('ok') else 'not ready'}",
        f"Profile: {payload.get('profile')} (current: {payload.get('current_profile')})",
        f"Offline: {payload.get('offline')}",
        (
            "Runtime: "
            f"storage={target_values.get('storage.backend')}, "
            f"vector_search={target_values.get('mongodb.vector_search')}, "
            f"llm={target_values.get('llm.provider')}"
        ),
        f"Write policy: {contract.get('write_policy')}",
    ]
    bi_setup = contract.get("bi_smoke_required_setup") or []
    llm_setup = contract.get("llm_tool_required_setup") or []
    lines.extend(
        [
            (
                "BI smoke setup: "
                f"{', '.join(bi_setup) if bi_setup else 'none'}"
            ),
            (
                "LLM tool setup: "
                f"{', '.join(llm_setup) if llm_setup else 'none'}"
            ),
            (
                "Doctor: "
                f"fail={summary.get('failed_checks')}, "
                f"warn={summary.get('warning_checks')}, "
                f"skipped={summary.get('skipped_checks')}"
            ),
            "",
            "Contract checks:",
        ]
    )
    for check in payload.get("checks") or []:
        marker = _status_marker(check.get("status"))
        lines.append(f"- {marker} {check['label']}: {check['message']}")

    if doctor.get("checks"):
        lines.extend(["", "Doctor checks:"])
        for check in doctor["checks"]:
            marker = _status_marker(check.get("status"))
            lines.append(f"- {marker} {check['label']}: {check['message']}")

    deferred = contract.get("deferred_checks") or []
    if deferred:
        lines.extend(["", "Deferred checks:"])
        for item in deferred:
            lines.append(f"- {item}")

    if payload.get("next_actions"):
        lines.extend(["", "Next actions:"])
        for action in payload["next_actions"]:
            rendered = action["action"]
            if isinstance(rendered, dict):
                rendered = json.dumps(rendered, ensure_ascii=False)
            lines.append(f"- [{action['check_id']}] {rendered}")
    return "\n".join(lines)


def _status_marker(status: Any) -> str:
    return {
        "pass": "PASS",
        "warn": "WARN",
        "fail": "FAIL",
        "skipped": "SKIP",
    }.get(status, str(status).upper())


def _config_write_error_payload(command: str, profile: str, message: str) -> dict:
    return {
        "ok": False,
        "command": command,
        "profile": profile,
        "error_code": "INVALID_PROFILE",
        "message": message,
        "user_config_path": None,
        "dry_run": False,
        "force": False,
        "requires_force": False,
        "storage_written": False,
        "backup_written": False,
        "backup_path": None,
        "changed_fields": [],
        "target_profile_values": {},
        "doctor": None,
    }


def _mapping(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _redact_cli_error(exc: Exception) -> str:
    message = f"{type(exc).__name__}: {exc}"
    for key in ("MONGODB_URI", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        secret = os.environ.get(key)
        if secret:
            message = message.replace(secret, f"<redacted:{key}>")
    return message


def _safe_mongo_command_result(result: Any) -> Any:
    """Return a CLI-safe summary of a raw MongoDB command response."""

    if not isinstance(result, dict):
        return result
    safe: dict[str, Any] = {}
    for key in ("ok", "status", "message", "operationTime"):
        if key in result:
            safe[key] = result[key]
    if "result" in result:
        safe["result"] = _safe_mongo_command_result(result["result"])
    return safe or {"summary": str(result)}


def _local_personal_store_from_config() -> Any:
    from deal_intel import _env
    from deal_intel.storage.local_personal import LocalPersonalStore

    cfg = _env.load_config()
    storage = _mapping(cfg.get("storage"))
    return LocalPersonalStore(storage.get("local_data_dir"))


def _build_natural_question_smoke_pack(
    *,
    mongo: Any,
    cfg: dict,
    as_of: str | None,
) -> dict:
    from deal_intel.errors import MCPError
    from deal_intel.tools import get_customer_theme_breakdown as _theme_breakdown
    from deal_intel.tools import get_customer_theme_evidence as _theme_evidence
    from deal_intel.tools import get_deal_gaps as _get_deal_gaps
    from deal_intel.tools import get_deal_review as _get_deal_review
    from deal_intel.tools import get_metrics as _get_metrics

    generated_at = datetime.now().isoformat(timespec="seconds")
    deals = mongo.list_deals_for_metrics()

    def call(question_id: str, question: str, answerability: str, fn: Any) -> dict:
        try:
            payload = fn()
            sensitive_ok = not _contains_sensitive_result_key(payload)
            return {
                "id": question_id,
                "question": question,
                "answerability": answerability,
                "sensitive": "pass" if sensitive_ok else "fail",
                "file": _natural_question_file_name(question_id),
                "quick_read": _natural_question_quick_read(question_id, payload),
                "payload": payload,
            }
        except MCPError as exc:
            return _natural_question_blocked_row(
                question_id,
                question,
                answerability,
                exc.to_envelope(),
            )
        except Exception as exc:
            return _natural_question_blocked_row(
                question_id,
                question,
                answerability,
                {
                    "ok": False,
                    "error_code": "INTERNAL",
                    "stage": "cli",
                    "message": f"{type(exc).__name__}: {exc}",
                    "hint": None,
                    "retryable": False,
                },
            )

    target_deal = _find_company_deal(deals, ("페이브릿지", "paybridge"))
    top_theme_key: str | None = None

    questions = [
        call(
            "q01_pipeline_health",
            "현재 파이프라인 건강도 어때?",
            "direct",
            lambda: _get_metrics.handle(
                mongo=mongo,
                cfg=cfg,
                metric_type="pipeline_health",
                as_of=as_of,
            ),
        ),
        call(
            "q02_company_status_paybridge",
            "페이브릿지 딜 진행상황 알려줘.",
            "direct",
            lambda: _get_deal_review.handle(
                mongo=mongo,
                cfg=cfg,
                deal_id=str((target_deal or {})["deal_id"]),
                as_of=as_of,
            ),
        ),
        call(
            "q03_riskiest_deals",
            "지금 가장 위험하거나 먼저 봐야 하는 딜은 뭐야?",
            "direct",
            lambda: _get_deal_gaps.handle(
                mongo=mongo,
                cfg=cfg,
                as_of=as_of,
                min_priority="high",
                limit=10,
            ),
        ),
        call(
            "q04_high_health_uncertain",
            "health는 높지만 아직 확신하면 안 되는 딜 있어?",
            "derived",
            lambda: _build_high_health_uncertain_payload(
                mongo=mongo,
                cfg=cfg,
                deals=deals,
                as_of=as_of,
            ),
        ),
        call(
            "q05_closing_candidates_gaps",
            "클로징 가까운 딜 중 보강할 정보는 뭐야?",
            "derived",
            lambda: _build_closing_candidate_gap_payload(
                _get_deal_gaps.handle(
                    mongo=mongo,
                    cfg=cfg,
                    as_of=as_of,
                    min_priority="low",
                    limit=50,
                )
            ),
        ),
        call(
            "q06_closed_postmortem_gaps",
            "won/lost 처리된 딜 중 사후 분석 정보 빠진 것 있어?",
            "derived",
            lambda: _build_closed_postmortem_gap_payload(
                _get_deal_gaps.handle(
                    mongo=mongo,
                    cfg=cfg,
                    as_of=as_of,
                    min_priority="low",
                    limit=50,
                )
            ),
        ),
        call(
            "q07_decision_criteria_themes",
            "고객들이 decision criteria로 가장 많이 고민한 건 뭐야?",
            "direct",
            lambda: _theme_breakdown.handle(
                mongo=mongo,
                dimension="decision_criteria",
                stage="active",
                group_by="stage",
                top_k=5,
            ),
        ),
    ]

    top_theme_key = _top_decision_theme_key(questions[-1].get("payload") or {})
    questions.append(
        call(
            "q08_theme_evidence_drilldown",
            "그 decision criteria의 대표 evidence를 보여줘.",
            "direct",
            lambda: _theme_evidence.handle(
                mongo=mongo,
                theme_key=top_theme_key or "other",
                dimension="decision_criteria",
                stage="active",
                limit=12,
                min_importance=1,
            ),
        )
    )

    questions.append(
        call(
            "q09_interaction_source_evidence",
            "Which customer themes are supported by email or user interview evidence?",
            "derived",
            lambda: _build_interaction_source_evidence_payload(
                [
                    _theme_evidence.handle(
                        mongo=mongo,
                        cfg=cfg,
                        theme_key="reporting_visibility",
                        dimension="all",
                        stage="active",
                        limit=50,
                        min_importance=1,
                        interaction_type="email_thread",
                    ),
                    _theme_evidence.handle(
                        mongo=mongo,
                        cfg=cfg,
                        theme_key="reporting_visibility",
                        dimension="all",
                        stage="active",
                        limit=50,
                        min_importance=1,
                        interaction_type="user_interview",
                    ),
                ]
            ),
        )
    )

    questions.extend(
        [
            call(
                "q10_pipeline_trend",
                "지난 7일 파이프라인 흐름은 좋아졌어 나빠졌어?",
                "direct",
                lambda: _get_metrics.handle(
                    mongo=mongo,
                    cfg=cfg,
                    metric_type="pipeline_trend",
                    as_of=as_of,
                    lookback_days=7,
                ),
            ),
            call(
                "q11_deal_review_actionability",
                "딜 리뷰에서 바로 행동할 것과 관찰만 할 gap이 구분돼?",
                "derived",
                lambda: _build_deal_review_actionability_payload(
                    mongo=mongo,
                    cfg=cfg,
                    deals=deals,
                    as_of=as_of,
                ),
            ),
            call(
                "q12_interaction_source_coverage",
                "샘플 데이터에는 회의, 이메일, 인터뷰 evidence가 모두 들어있어?",
                "derived",
                lambda: _build_interaction_source_coverage_payload(deals),
            ),
        ]
    )

    sensitive_failures = [
        row["id"] for row in questions if row.get("sensitive") == "fail"
    ]
    blocked_questions = [
        row["id"] for row in questions if row.get("blocked_reason") is not None
    ]
    answerability_counts = _counter_dict(row["answerability"] for row in questions)
    return {
        "ok": not sensitive_failures and not blocked_questions,
        "generated_at": generated_at,
        "as_of": _first_question_as_of(questions) or as_of,
        "question_count": len(questions),
        "answerability_counts": answerability_counts,
        "sensitive_failures": sensitive_failures,
        "blocked_questions": blocked_questions,
        "questions": questions,
    }


def _natural_question_blocked_row(
    question_id: str,
    question: str,
    answerability: str,
    payload: dict,
) -> dict:
    return {
        "id": question_id,
        "question": question,
        "answerability": answerability,
        "sensitive": "pass",
        "file": _natural_question_file_name(question_id),
        "quick_read": "blocked",
        "blocked_reason": payload.get("message") or payload.get("error_code"),
        "payload": payload,
    }


def _natural_question_file_name(question_id: str) -> str:
    return f"{question_id}.json"


def _find_company_deal(deals: list[dict], names: tuple[str, ...]) -> dict | None:
    for name in names:
        needle = name.casefold()
        for deal in deals:
            if needle in str(deal.get("company") or "").casefold():
                return deal
    return next(
        (
            deal
            for deal in deals
            if isinstance(deal.get("deal_id"), str) and deal.get("deal_id")
        ),
        None,
    )


def _build_high_health_uncertain_payload(
    *,
    mongo: Any,
    cfg: dict,
    deals: list[dict],
    as_of: str | None,
) -> dict:
    from deal_intel.tools import get_deal_review as _get_deal_review

    rows = []
    for deal in deals:
        deal_id = deal.get("deal_id")
        if not isinstance(deal_id, str) or not deal_id:
            continue
        result = _get_deal_review.handle(
            mongo=mongo,
            cfg=cfg,
            deal_id=deal_id,
            as_of=as_of,
        )
        review = result.get("review") or {}
        interpretation = review.get("health_interpretation") or {}
        if interpretation.get("health_band") != "healthy":
            continue
        if (
            interpretation.get("uncertainty_level") == "low"
            and interpretation.get("review_band") == "verified_healthy"
        ):
            continue
        rows.append(
            {
                "deal_id": review.get("deal_id"),
                "company": review.get("company"),
                "deal_stage": review.get("deal_stage"),
                "deal_size_amount": review.get("deal_size_amount"),
                "review_band": interpretation.get("review_band"),
                "uncertainty_level": interpretation.get("uncertainty_level"),
                "evidence_coverage_pct": interpretation.get("evidence_coverage_pct"),
                "missing_information_count": len(review.get("missing_information") or []),
                "confirmed_risk_count": len(review.get("confirmed_risks") or []),
                "warnings": review.get("warnings") or [],
            }
        )
    rows.sort(
        key=lambda row: (
            -UNCERTAINTY_RANK.get(row.get("uncertainty_level"), 0),
            -int(row.get("missing_information_count") or 0),
            -int(row.get("confirmed_risk_count") or 0),
            -(row.get("deal_size_amount") or 0),
            str(row.get("company") or ""),
        )
    )
    return {
        "ok": True,
        "as_of": as_of,
        "summary": {"candidate_count": len(rows), "returned_count": len(rows[:10])},
        "deals": rows[:10],
    }


def _build_closing_candidate_gap_payload(gap_payload: dict) -> dict:
    rows = [
        row
        for row in gap_payload.get("deals") or []
        if row.get("deal_stage") not in {"won", "lost"}
    ]
    rows.sort(
        key=lambda row: (
            _date_sort_value(row.get("expected_close_date")),
            -float(row.get("priority_score") or 0),
            -(row.get("deal_size_amount") or 0),
            str(row.get("company") or ""),
        )
    )
    return {
        "ok": True,
        "as_of": gap_payload.get("as_of"),
        "summary": {"candidate_count": len(rows), "returned_count": len(rows[:10])},
        "deals": rows[:10],
        "source_summary": gap_payload.get("summary") or {},
        "warnings": gap_payload.get("warnings") or [],
    }


def _build_closed_postmortem_gap_payload(gap_payload: dict) -> dict:
    rows = []
    for row in gap_payload.get("deals") or []:
        gaps = row.get("gaps") or []
        if row.get("deal_stage") in {"won", "lost"} or any(
            gap.get("impact_area") == "postmortem" for gap in gaps if isinstance(gap, dict)
        ):
            rows.append(row)
    rows.sort(
        key=lambda row: (
            0 if row.get("deal_stage") == "lost" else 1,
            -float(row.get("priority_score") or 0),
            str(row.get("company") or ""),
        )
    )
    return {
        "ok": True,
        "as_of": gap_payload.get("as_of"),
        "summary": {"candidate_count": len(rows), "returned_count": len(rows[:10])},
        "deals": rows[:10],
        "source_summary": gap_payload.get("summary") or {},
        "warnings": gap_payload.get("warnings") or [],
    }


def _build_interaction_source_evidence_payload(
    evidence_payloads: list[dict],
) -> dict:
    source_types = {"email_thread", "user_interview"}
    rows = [
        row
        for payload in evidence_payloads
        for row in payload.get("evidence") or []
        if row.get("interaction_type") in source_types
    ]
    unique_deals = {str(row.get("deal_id") or "") for row in rows}
    unique_deals.discard("")
    return {
        "ok": True,
        "filters": {
            "theme_key": "reporting_visibility",
            "dimension": "all",
            "stage": "active",
            "interaction_types": sorted(source_types),
        },
        "summary": {
            "evidence_count": len(rows),
            "unique_deal_count": len(unique_deals),
            "source_type_counts": _counter_dict(
                str(row.get("interaction_type") or "unknown") for row in rows
            ),
        },
        "evidence": rows,
        "source_summaries": [payload.get("summary") or {} for payload in evidence_payloads],
        "warnings": [] if rows else ["no_email_or_user_interview_theme_evidence"],
    }


def _build_deal_review_actionability_payload(
    *,
    mongo: Any,
    cfg: dict,
    deals: list[dict],
    as_of: str | None,
) -> dict:
    from deal_intel.tools import get_deal_review as _get_deal_review

    rows = []
    for deal in deals:
        deal_id = deal.get("deal_id")
        if not isinstance(deal_id, str) or not deal_id:
            continue
        result = _get_deal_review.handle(
            mongo=mongo,
            cfg=cfg,
            deal_id=deal_id,
            as_of=as_of,
        )
        review = result.get("review") or {}
        interpretation = review.get("health_interpretation") or {}
        rows.append(
            {
                "deal_id": review.get("deal_id"),
                "company": review.get("company"),
                "deal_stage": review.get("deal_stage"),
                "review_band": interpretation.get("review_band"),
                "alert_level": interpretation.get("alert_level"),
                "uncertainty_level": interpretation.get("uncertainty_level"),
                "actionable_gap_count": len(review.get("actionable_gaps") or []),
                "gap_observation_count": len(review.get("gap_observations") or []),
                "recommended_action_count": len(
                    review.get("recommended_actions") or []
                ),
                "recommended_question_count": len(
                    review.get("recommended_questions") or []
                ),
                "missing_information_count": len(
                    review.get("missing_information") or []
                ),
                "confirmed_risk_count": len(review.get("confirmed_risks") or []),
                "warnings": review.get("warnings") or [],
            }
        )
    rows.sort(
        key=lambda row: (
            -int(row.get("confirmed_risk_count") or 0),
            -int(row.get("actionable_gap_count") or 0),
            -int(row.get("gap_observation_count") or 0),
            -UNCERTAINTY_RANK.get(row.get("uncertainty_level"), 0),
            str(row.get("company") or ""),
        )
    )
    return {
        "ok": True,
        "as_of": as_of,
        "summary": {
            "reviewed_count": len(rows),
            "deals_with_actionable_gaps": sum(
                1 for row in rows if row["actionable_gap_count"] > 0
            ),
            "deals_with_gap_observations": sum(
                1 for row in rows if row["gap_observation_count"] > 0
            ),
            "deals_with_confirmed_risks": sum(
                1 for row in rows if row["confirmed_risk_count"] > 0
            ),
            "deals_with_missing_information": sum(
                1 for row in rows if row["missing_information_count"] > 0
            ),
        },
        "deals": rows[:12],
        "warnings": [],
    }


def _build_interaction_source_coverage_payload(deals: list[dict]) -> dict:
    from deal_intel.schema.interactions import iter_interactions

    rows = []
    for deal in deals:
        for interaction in iter_interactions(deal):
            rows.append(
                {
                    "deal_id": deal.get("deal_id"),
                    "company": deal.get("company"),
                    "interaction_id": interaction.get("interaction_id"),
                    "interaction_type": interaction.get("interaction_type"),
                    "direction": interaction.get("direction"),
                    "source_confidence": interaction.get("source_confidence"),
                    "scoring_applied": interaction.get("scoring_applied"),
                    "subject": interaction.get("subject"),
                    "date": interaction.get("date"),
                }
            )
    return {
        "ok": True,
        "summary": {
            "interaction_count": len(rows),
            "deal_count": len(
                {str(row.get("deal_id") or "") for row in rows if row.get("deal_id")}
            ),
            "interaction_type_counts": _counter_dict(
                str(row.get("interaction_type") or "unknown") for row in rows
            ),
            "source_confidence_counts": _counter_dict(
                str(row.get("source_confidence") or "unknown") for row in rows
            ),
            "scoring_applied_counts": _counter_dict(
                str(row.get("scoring_applied")) for row in rows
            ),
        },
        "interactions": rows[:20],
        "warnings": [] if rows else ["no_interactions_found"],
    }


def _date_sort_value(value: Any) -> str:
    if isinstance(value, str) and value:
        return value
    return "9999-12-31"


def _top_decision_theme_key(payload: dict) -> str | None:
    totals: dict[str, dict] = {}
    for group in payload.get("groups") or []:
        for theme in group.get("themes") or []:
            theme_key = theme.get("theme_key")
            if not isinstance(theme_key, str) or not theme_key:
                continue
            bucket = totals.setdefault(
                theme_key,
                {
                    "theme_key": theme_key,
                    "deal_count": 0,
                    "importance_sum": 0.0,
                    "importance_count": 0,
                },
            )
            deal_count = int(theme.get("deal_count") or 0)
            bucket["deal_count"] += deal_count
            bucket["importance_sum"] += float(theme.get("avg_importance") or 0) * deal_count
            bucket["importance_count"] += deal_count
    if not totals:
        return None
    ranked = sorted(
        totals.values(),
        key=lambda item: (
            -int(item["deal_count"]),
            -(
                float(item["importance_sum"]) / int(item["importance_count"])
                if item["importance_count"]
                else 0.0
            ),
            str(item["theme_key"]),
        ),
    )
    return str(ranked[0]["theme_key"])


def _natural_question_quick_read(question_id: str, payload: dict) -> str:
    if not payload.get("ok", True):
        return "blocked"
    if question_id == "q01_pipeline_health":
        kpis = payload.get("kpis") or {}
        return (
            f"active={kpis.get('active_deal_count')}, "
            f"attention={kpis.get('attention_deal_count')}"
        )
    if question_id == "q02_company_status_paybridge":
        review = payload.get("review") or {}
        interpretation = review.get("health_interpretation") or {}
        return (
            f"{review.get('company')} / {interpretation.get('review_band')} / "
            f"{interpretation.get('uncertainty_level')}"
        )
    if question_id in {
        "q03_riskiest_deals",
        "q04_high_health_uncertain",
        "q05_closing_candidates_gaps",
        "q06_closed_postmortem_gaps",
    }:
        return _format_companies(payload.get("deals") or [], limit=3)
    if question_id == "q07_decision_criteria_themes":
        return f"groups={len(payload.get('groups') or [])}"
    if question_id == "q08_theme_evidence_drilldown":
        summary = payload.get("summary") or {}
        return f"evidence={summary.get('evidence_count')}"
    if question_id == "q09_interaction_source_evidence":
        summary = payload.get("summary") or {}
        counts = summary.get("source_type_counts") or {}
        return (
            f"source_evidence={summary.get('evidence_count')} "
            f"({_format_counts(counts)})"
        )
    if question_id == "q10_pipeline_trend":
        delta = payload.get("delta") or {}
        end = payload.get("end") or {}
        open_value_delta = _format_money(
            delta.get("open_pipeline_value_amount"),
            currency=end.get("open_pipeline_value_currency"),
        )
        return (
            f"open_value_delta={open_value_delta}, "
            f"won_delta={delta.get('won_deal_count')}"
        )
    if question_id == "q11_deal_review_actionability":
        summary = payload.get("summary") or {}
        return (
            f"actionable={summary.get('deals_with_actionable_gaps')}, "
            f"observations={summary.get('deals_with_gap_observations')}, "
            f"risks={summary.get('deals_with_confirmed_risks')}"
        )
    if question_id == "q12_interaction_source_coverage":
        summary = payload.get("summary") or {}
        return _format_counts(summary.get("interaction_type_counts") or {})
    return "ok"


def _first_question_as_of(questions: list[dict]) -> str | None:
    for question in questions:
        payload = question.get("payload") or {}
        value = payload.get("as_of")
        if isinstance(value, str) and value:
            return value
    return None


def _write_natural_question_smoke_artifacts(
    payload: dict,
    *,
    output_dir: Path | None,
) -> Path:
    output_dir = output_dir or _default_natural_question_output_dir()
    output_dir.mkdir(parents=True, exist_ok=True)
    for question in payload["questions"]:
        file_path = output_dir / question["file"]
        file_path.write_text(
            json.dumps(question["payload"], ensure_ascii=False, indent=2, default=str)
            + "\n",
            encoding="utf-8",
        )
    summary_payload = {
        key: value
        for key, value in payload.items()
        if key != "output_dir"
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary_payload, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    (output_dir / "summary.md").write_text(
        _format_natural_question_smoke_markdown(payload) + "\n",
        encoding="utf-8",
    )
    return output_dir.resolve()


def _default_natural_question_output_dir() -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path("outputs") / "smoke" / f"natural-question-pack-{stamp}"


def _format_natural_question_smoke(payload: dict) -> str:
    lines = [
        (
            "Natural Question Smoke "
            f"(as_of={payload.get('as_of')}, questions={payload.get('question_count')})"
        ),
        f"OK: {payload.get('ok')}",
        f"Answerability: {_format_counts(payload.get('answerability_counts') or {})}",
        (
            "Sensitive failures: "
            f"{_format_string_list(payload.get('sensitive_failures') or [])}"
        ),
        f"Blocked questions: {_format_string_list(payload.get('blocked_questions') or [])}",
    ]
    if payload.get("output_dir"):
        lines.append(f"Output: {payload['output_dir']}")
    lines.extend(["", "Questions:"])
    for index, question in enumerate(payload.get("questions") or [], start=1):
        lines.append(
            f"{index}. {question.get('question')} | "
            f"{question.get('answerability')} | "
            f"{question.get('sensitive')} | "
            f"{question.get('quick_read')}"
        )
    return "\n".join(lines)


def _format_natural_question_smoke_markdown(payload: dict) -> str:
    lines = [
        "# Natural Question Smoke Pack",
        "",
        f"- Generated at: {payload.get('generated_at')}",
        f"- As of: {payload.get('as_of')}",
        f"- Questions: {payload.get('question_count')}",
        f"- OK: {payload.get('ok')}",
        f"- Answerability: {payload.get('answerability_counts')}",
        (
            "- Sensitive failures: "
            f"{_format_string_list(payload.get('sensitive_failures') or [])}"
        ),
        f"- Blocked questions: {_format_string_list(payload.get('blocked_questions') or [])}",
        "",
        "## Questions",
        "",
        "| # | question | answerability | sensitive | file | quick read |",
        "|---:|---|---|:---:|---|---|",
    ]
    for index, question in enumerate(payload.get("questions") or [], start=1):
        lines.append(
            "| "
            f"{index} | "
            f"{_markdown_cell(question.get('question'))} | "
            f"{question.get('answerability')} | "
            f"{question.get('sensitive')} | "
            f"{question.get('file')} | "
            f"{_markdown_cell(question.get('quick_read'))} |"
        )
    source_rows = _natural_question_source_rows(payload)
    if source_rows:
        lines.extend(
            [
                "",
                "## Source Evidence",
                "",
                "| question | company | source | evidence |",
                "|---|---|---|---|",
            ]
        )
        for row in source_rows:
            lines.append(
                "| "
                f"{_markdown_cell(row['question_id'])} | "
                f"{_markdown_cell(row['company'])} | "
                f"{_markdown_cell(row['source'])} | "
                f"{_markdown_cell(row['evidence'])} |"
            )
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- This pack does not call an LLM. It checks whether deterministic tool "
            "payloads can support natural-language answers.",
            "- `derived` questions are answerable after deterministic filtering/sorting "
            "over existing tool payloads.",
        ]
    )
    return "\n".join(lines)


def _natural_question_source_rows(payload: dict, *, limit: int = 10) -> list[dict]:
    from deal_intel.schema.evidence_sources import evidence_source_label

    rows = []
    for question in payload.get("questions") or []:
        if not isinstance(question, dict):
            continue
        question_id = str(question.get("id") or "")
        question_payload = question.get("payload")
        if not isinstance(question_payload, dict):
            continue
        for evidence in question_payload.get("evidence") or []:
            if not isinstance(evidence, dict):
                continue
            rows.append(
                {
                    "question_id": question_id,
                    "company": evidence.get("company") or "N/A",
                    "source": evidence.get("source_label")
                    or evidence_source_label(evidence),
                    "evidence": _truncate_text(evidence.get("evidence"), limit=140),
                }
            )
            if len(rows) >= limit:
                return rows
    return rows


def _truncate_text(value: Any, *, limit: int) -> str:
    text = str(value or "")
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "..."


def _markdown_cell(value: Any) -> str:
    text = "N/A" if value is None else str(value)
    return text.replace("\r", " ").replace("\n", " ").replace("|", r"\|")


def _format_companies(rows: list[dict], *, limit: int = 3) -> str:
    values = [str(row.get("company")) for row in rows if row.get("company")]
    if not values:
        return "none"
    return "; ".join(values[:limit])


def _select_deal_review_smoke_deals(
    deals: list[dict],
    *,
    deal_id: str | None,
    company: str | None,
    limit: int,
) -> list[dict]:
    if deal_id is not None and deal_id.strip():
        needle = deal_id.strip()
        for deal in deals:
            if deal.get("deal_id") == needle:
                return [deal]
        raise ValueError(f"deal_id {needle!r} not found")

    selected = deals
    if company is not None and company.strip():
        needle = company.strip().casefold()
        selected = [
            deal
            for deal in deals
            if needle in str(deal.get("company") or "").casefold()
        ]
        if not selected:
            raise ValueError(f"company containing {company.strip()!r} not found")

    selected = [
        deal
        for deal in selected
        if isinstance(deal.get("deal_id"), str) and deal.get("deal_id")
    ]
    if not selected:
        raise ValueError("no deals available for smoke review")
    return selected[:limit]


def _select_deal_review_audit_deals(
    deals: list[dict],
    *,
    company: str | None,
    stage: str | None,
    industry: str | None,
    limit: int,
) -> list[dict]:
    selected = [
        deal
        for deal in deals
        if isinstance(deal.get("deal_id"), str) and deal.get("deal_id")
    ]
    if company is not None and company.strip():
        needle = company.strip().casefold()
        selected = [
            deal
            for deal in selected
            if needle in str(deal.get("company") or "").casefold()
        ]
    if stage is not None and stage.strip():
        stage_value = stage.strip()
        selected = [
            deal for deal in selected if deal.get("deal_stage") == stage_value
        ]
    if industry is not None and industry.strip():
        industry_value = industry.strip()
        selected = [
            deal for deal in selected if deal.get("industry") == industry_value
        ]
    if not selected:
        raise ValueError("no deals matched the audit filters")
    return selected[:limit]


def _build_deal_review_audit_payload(results: list[dict], *, filters: dict) -> dict:
    rows = [_build_deal_review_audit_row(result.get("review") or {}) for result in results]
    rows.sort(key=_deal_review_audit_sort_key)
    quality_issues = [
        issue
        for row in rows
        for issue in row["quality_issues"]
    ]
    summary = {
        "reviewed_count": len(rows),
        "quality_issue_count": len(quality_issues),
        "quality_issue_deal_count": sum(1 for row in rows if row["quality_issues"]),
        "alert_level_counts": _counter_dict(row["alert_level"] for row in rows),
        "uncertainty_counts": _counter_dict(row["uncertainty_level"] for row in rows),
        "review_band_counts": _counter_dict(row["review_band"] for row in rows),
        "warning_counts": _counter_dict(
            warning for row in rows for warning in row["warnings"]
        ),
        "quality_issue_counts": _counter_dict(
            issue["issue_id"] for issue in quality_issues
        ),
        "high_uncertainty_deal_count": sum(
            1 for row in rows if row["uncertainty_level"] == "high"
        ),
        "missing_information_deal_count": sum(
            1 for row in rows if row["missing_information_count"] > 0
        ),
        "confirmed_risk_deal_count": sum(
            1 for row in rows if row["confirmed_risk_count"] > 0
        ),
    }
    return {
        "ok": True,
        "as_of": results[0].get("as_of") if results else None,
        "timezone": results[0].get("timezone") if results else None,
        "generated_at": results[0].get("generated_at") if results else None,
        "filters": filters,
        "summary": summary,
        "sensitive_field_check": {"ok": True},
        "deals": rows,
    }


def _build_deal_review_audit_row(review: dict) -> dict:
    interpretation = review.get("health_interpretation") or {}
    assessment = review.get("assessment") or {}
    warnings = [str(item) for item in review.get("warnings") or []]
    quality_issues = _audit_deal_review_quality(review)
    return {
        "deal_id": review.get("deal_id"),
        "company": review.get("company"),
        "industry": review.get("industry"),
        "deal_stage": review.get("deal_stage"),
        "deal_size_amount": review.get("deal_size_amount"),
        "deal_size_status": review.get("deal_size_status"),
        "expected_close_date": review.get("expected_close_date"),
        "legacy_health_pct": interpretation.get("legacy_health_pct"),
        "health_band": interpretation.get("health_band"),
        "evidence_coverage_pct": interpretation.get("evidence_coverage_pct"),
        "review_band": interpretation.get("review_band"),
        "alert_level": interpretation.get("alert_level"),
        "uncertainty_level": interpretation.get("uncertainty_level"),
        "review_version": review.get("review_version"),
        "assessment": assessment,
        "attention_reasons": review.get("attention_reasons") or [],
        "actionable_gap_count": len(review.get("actionable_gaps") or []),
        "gap_observation_count": len(review.get("gap_observations") or []),
        "missing_information_count": len(review.get("missing_information") or []),
        "confirmed_risk_count": len(review.get("confirmed_risks") or []),
        "recommended_question_count": len(review.get("recommended_questions") or []),
        "recommended_action_count": len(review.get("recommended_actions") or []),
        "warnings": warnings,
        "quality_issues": quality_issues,
    }


def _audit_deal_review_quality(review: dict) -> list[dict]:
    interpretation = review.get("health_interpretation") or {}
    warnings = set(str(item) for item in review.get("warnings") or [])
    missing = review.get("missing_information") or []
    risks = review.get("confirmed_risks") or []
    questions = review.get("recommended_questions") or []
    actions = review.get("recommended_actions") or []
    actionable_gaps = review.get("actionable_gaps") or []
    gap_observations = review.get("gap_observations") or []
    data_quality = review.get("data_quality") or {}
    review_band = interpretation.get("review_band")
    alert_level = interpretation.get("alert_level")
    health_band = interpretation.get("health_band")
    coverage = interpretation.get("evidence_coverage_pct")
    stage = review.get("deal_stage")
    issues = []

    if "win_probability_suppressed" not in warnings:
        issues.append(
            _quality_issue(
                "missing_win_probability_suppression",
                "high",
                "Review must explicitly suppress uncalibrated win probability.",
            )
        )

    if review.get("review_version") != "v2":
        issues.append(
            _quality_issue(
                "missing_review_version_v2",
                "medium",
                "Deal review payload should identify review_version=v2.",
            )
        )

    if not isinstance(review.get("assessment"), dict):
        issues.append(
            _quality_issue(
                "missing_v2_assessment",
                "medium",
                "Deal review v2 must include a compact assessment object.",
            )
        )

    if _is_low_coverage(coverage) and health_band == "healthy":
        if "overconfidence_warning" not in warnings:
            issues.append(
                _quality_issue(
                    "overconfidence_warning_missing",
                    "high",
                    "Healthy-looking low-evidence deals must warn about overconfidence.",
                )
            )
        if review_band == "verified_healthy":
            issues.append(
                _quality_issue(
                    "verified_healthy_with_low_coverage",
                    "high",
                    "Low-evidence deals must not be classified as verified healthy.",
                )
            )

    if review_band == "confirmed_risk":
        if alert_level != "alert":
            issues.append(
                _quality_issue(
                    "confirmed_risk_without_alert",
                    "high",
                    "Confirmed risk reviews must use alert level.",
                )
            )
        if not risks:
            issues.append(
                _quality_issue(
                    "confirmed_risk_without_risk_rows",
                    "high",
                    "Confirmed risk reviews must include concrete risk rows.",
                )
            )

    if review_band == "verified_healthy":
        if missing or risks:
            issues.append(
                _quality_issue(
                    "verified_healthy_with_open_items",
                    "high",
                    "Verified healthy reviews must not have open gaps or risk rows.",
                )
            )
        if data_quality.get("is_confirmed_complete") is False:
            issues.append(
                _quality_issue(
                    "verified_healthy_without_confirmed_data",
                    "medium",
                    "Verified healthy reviews require confirmed data quality.",
                )
            )

    if interpretation.get("uncertainty_level") == "low":
        if missing:
            issues.append(
                _quality_issue(
                    "low_uncertainty_with_missing_information",
                    "medium",
                    "Low uncertainty reviews must not contain missing information.",
                )
            )
        if data_quality.get("is_confirmed_complete") is False:
            issues.append(
                _quality_issue(
                    "low_uncertainty_without_confirmed_data",
                    "medium",
                    "Low uncertainty reviews require confirmed data quality.",
                )
            )

    if risks and alert_level == "none":
        issues.append(
            _quality_issue(
                "risk_rows_without_attention_level",
                "medium",
                "Reviews with confirmed risk rows must be at least watch-level.",
            )
        )

    if interpretation.get("uncertainty_level") == "high" and not missing:
        if "insufficient_evidence" not in warnings:
            issues.append(
                _quality_issue(
                    "high_uncertainty_without_gap_or_warning",
                    "medium",
                    "High uncertainty must be backed by missing information or warning.",
                )
            )

    if missing and not questions:
        issues.append(
            _quality_issue(
                "missing_information_without_questions",
                "medium",
                "Missing information must produce follow-up questions.",
            )
        )

    if risks and not actions:
        issues.append(
            _quality_issue(
                "confirmed_risks_without_actions",
                "medium",
                "Confirmed risks must produce recommended actions.",
            )
        )

    action_set = {str(action) for action in actions}
    for gap in gap_observations:
        if not isinstance(gap, dict):
            continue
        if gap.get("actionability") == "cta_allowed":
            issues.append(
                _quality_issue(
                    "cta_allowed_gap_in_observations",
                    "medium",
                    "CTA-eligible gaps should be rendered as actionable gaps.",
                )
            )
        recommended_action = gap.get("recommended_action")
        if (
            gap.get("actionability") in {"needs_human_judgment", "observation_only"}
            and recommended_action
            and str(recommended_action) in action_set
        ):
            issues.append(
                _quality_issue(
                    "judgment_sensitive_gap_promoted_to_cta",
                    "high",
                    "Judgment-sensitive gaps must not be promoted to recommended actions.",
                )
            )

    for gap in actionable_gaps:
        if not isinstance(gap, dict):
            continue
        if gap.get("actionability") != "cta_allowed":
            issues.append(
                _quality_issue(
                    "non_cta_gap_in_actionable_gaps",
                    "medium",
                    "Only objective CTA-trigger gaps should be actionable gaps.",
                )
            )

    missing_fields = {str(item.get("field")) for item in missing if isinstance(item, dict)}
    actual_close_date = review.get("actual_close_date") or review.get(
        "_audit_actual_close_date"
    )
    close_reason = review.get("close_reason") or review.get("_audit_close_reason")
    if stage in {"won", "lost"} and "actual_close_date" not in missing_fields:
        if not actual_close_date:
            issues.append(
                _quality_issue(
                    "closed_actual_close_gap_not_reported",
                    "medium",
                    "Closed deals missing actual close date must surface that gap.",
                )
            )
    if stage == "lost" and "close_reason" not in missing_fields:
        if not close_reason:
            issues.append(
                _quality_issue(
                    "lost_close_reason_gap_not_reported",
                    "medium",
                    "Lost deals missing close reason must surface that gap.",
                )
            )

    if _guidance_contains_percent_estimate(review):
        issues.append(
            _quality_issue(
                "percent_estimate_in_guidance",
                "high",
                "Guidance must not include uncalibrated percentage estimates.",
            )
        )

    return issues


def _quality_issue(issue_id: str, severity: str, reason: str) -> dict:
    return {"issue_id": issue_id, "severity": severity, "reason": reason}


def _is_low_coverage(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value < 70


def _guidance_contains_percent_estimate(review: dict) -> bool:
    guidance = []
    for key in (
        "recommended_questions",
        "recommended_actions",
        "confirmed_risks",
        "known_signals",
        "missing_information",
        "actionable_gaps",
        "gap_observations",
    ):
        guidance.extend(_string_values(review.get(key)))
    return any("%" in item for item in guidance)


def _string_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        result = []
        for child in value.values():
            result.extend(_string_values(child))
        return result
    if isinstance(value, list):
        result = []
        for child in value:
            result.extend(_string_values(child))
        return result
    return []


def _deal_review_audit_sort_key(row: dict) -> tuple:
    max_issue_severity = max(
        (
            ISSUE_SEVERITY_RANK.get(issue.get("severity"), 0)
            for issue in row["quality_issues"]
        ),
        default=0,
    )
    return (
        -max_issue_severity,
        -ALERT_RANK.get(row["alert_level"], 0),
        -UNCERTAINTY_RANK.get(row["uncertainty_level"], 0),
        -row["confirmed_risk_count"],
        -row["missing_information_count"],
        -(row.get("deal_size_amount") or 0),
        str(row.get("company") or ""),
    )


def _counter_dict(values: Any) -> dict:
    return dict(sorted(Counter(value for value in values if value is not None).items()))


def _contains_sensitive_result_key(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            key in SENSITIVE_RESULT_KEYS or _contains_sensitive_result_key(child)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return any(_contains_sensitive_result_key(item) for item in value)
    return False


def _emit_smoke_error(payload: dict, *, json_output: bool) -> None:
    if json_output:
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2), err=True)
        return
    typer.echo(
        f"Smoke failed: {payload.get('error_code')} "
        f"({payload.get('stage')}) - {payload.get('message')}",
        err=True,
    )


def _format_deal_review_smoke(payload: dict) -> str:
    lines = [
        f"Deal Review Smoke (as_of={payload.get('as_of')}, count={payload.get('count')})",
        "",
    ]
    for result in payload.get("results", []):
        review = result.get("review") or {}
        interpretation = review.get("health_interpretation") or {}
        deal_value = _format_money(
            review.get("deal_size_amount"),
            currency=review.get("deal_size_currency"),
        )
        lines.extend(
            [
                f"[{review.get('company')}] {review.get('deal_id')}",
                (
                    f"Stage: {review.get('deal_stage')} | "
                    f"Industry: {review.get('industry')} | "
                    f"Value: {deal_value} "
                    f"({review.get('deal_size_status') or 'unknown'})"
                ),
                (
                    f"Band: {interpretation.get('review_band')} | "
                    f"Alert: {interpretation.get('alert_level')} | "
                    f"Uncertainty: {interpretation.get('uncertainty_level')}"
                ),
                (
                    f"Health: {interpretation.get('legacy_health_pct')} | "
                    f"Evidence coverage: {interpretation.get('evidence_coverage_pct')}% "
                    f"({interpretation.get('filled_meddpicc_count')}/"
                    f"{interpretation.get('total_meddpicc_count')})"
                ),
                f"Attention: {_format_string_list(review.get('attention_reasons') or [])}",
                f"Missing: {_format_gap_list(review.get('missing_information') or [])}",
                f"Risks: {_format_risk_list(review.get('confirmed_risks') or [])}",
                f"Actions: {_format_string_list(review.get('recommended_actions') or [])}",
                "Gap observations: "
                f"{_format_gap_list(review.get('gap_observations') or [], limit=3)}",
                "Questions: "
                f"{_format_string_list(review.get('recommended_questions') or [], limit=3)}",
                f"Warnings: {_format_string_list(review.get('warnings') or [])}",
                "",
            ]
        )
    lines.append("Sensitive field check: passed")
    return "\n".join(lines)


def _format_deal_review_audit(payload: dict) -> str:
    summary = payload["summary"]
    sensitive_status = (
        "passed" if payload["sensitive_field_check"]["ok"] else "failed"
    )
    quality_status = (
        "passed"
        if summary["quality_issue_count"] == 0
        else f"{summary['quality_issue_count']} issue(s)"
    )
    lines = [
        (
            f"Deal Review Audit (as_of={payload.get('as_of')}, "
            f"reviewed={summary['reviewed_count']})"
        ),
        "",
        f"Sensitive field check: {sensitive_status}",
        f"Quality rules: {quality_status}",
        f"Alert levels: {_format_counts(summary['alert_level_counts'])}",
        f"Uncertainty: {_format_counts(summary['uncertainty_counts'])}",
        f"Review bands: {_format_counts(summary['review_band_counts'])}",
        f"Warnings: {_format_counts(summary['warning_counts'])}",
        "",
        "Top review targets:",
    ]
    for row in payload["deals"][:10]:
        lines.append(
            f"- {row.get('company')} | {row.get('deal_stage')} | "
            f"{row.get('review_band')} | alert={row.get('alert_level')} | "
            f"uncertainty={row.get('uncertainty_level')} | "
            f"coverage={row.get('evidence_coverage_pct')}% | "
            f"actions={row.get('actionable_gap_count')} | "
            f"observations={row.get('gap_observation_count')} | "
            f"missing={row.get('missing_information_count')} | "
            f"risks={row.get('confirmed_risk_count')} | "
            f"issues={_format_issue_ids(row.get('quality_issues') or [])}"
        )
    if len(payload["deals"]) > 10:
        lines.append(f"... +{len(payload['deals']) - 10} more deal(s)")
    return "\n".join(lines)


def _format_counts(counts: dict) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in counts.items())


def _format_issue_ids(issues: list[dict]) -> str:
    if not issues:
        return "none"
    return ", ".join(str(issue.get("issue_id")) for issue in issues[:3])


def _format_money(value: Any, *, currency: Any = None) -> str:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return "unknown"
    currency_text = str(currency or "").strip().upper() or "amount"
    return f"{int(value):,} {currency_text}"


def _format_string_list(items: list[Any], *, limit: int = 5) -> str:
    values = [str(item) for item in items if item is not None]
    if not values:
        return "none"
    visible = values[:limit]
    suffix = f" (+{len(values) - limit} more)" if len(values) > limit else ""
    return "; ".join(visible) + suffix


def _format_gap_list(gaps: list[dict], *, limit: int = 3) -> str:
    if not gaps:
        return "none"
    values = [
        f"{gap.get('field')}:{gap.get('status')}:{gap.get('severity')}"
        for gap in gaps[:limit]
    ]
    suffix = f" (+{len(gaps) - limit} more)" if len(gaps) > limit else ""
    return "; ".join(values) + suffix


def _format_risk_list(risks: list[dict]) -> str:
    if not risks:
        return "none"
    values = [
        f"{risk.get('risk_id')}:{risk.get('severity')}"
        for risk in risks[:3]
    ]
    suffix = f" (+{len(risks) - 3} more)" if len(risks) > 3 else ""
    return "; ".join(values) + suffix


if __name__ == "__main__":
    app()
