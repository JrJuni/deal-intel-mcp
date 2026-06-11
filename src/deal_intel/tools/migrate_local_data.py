from __future__ import annotations

from copy import deepcopy
from typing import Any

from deal_intel.errors import ErrorCode, MCPError, Stage
from deal_intel.storage.local_personal import LocalPersonalStore

MIGRATION_TYPE = "local_personal_to_mongo"


def handle(
    *,
    source_store: LocalPersonalStore,
    target_mongo: Any,
    dry_run: bool = True,
    overwrite: bool = False,
    confirmed_by_user: bool = False,
) -> dict:
    """Migrate user-created local personal deals into a Mongo-backed store.

    Bundled zero-config fixture records are intentionally not part of this
    path. The source store only exposes records from storage.local_data_dir.
    """

    if not dry_run and not confirmed_by_user:
        raise MCPError(
            error_code=ErrorCode.INVALID_INPUT,
            stage=Stage.PREFLIGHT,
            message="migrate_local_data requires confirmed_by_user=true when dry_run=false",
            hint="Run a dry-run first, then retry with confirmed_by_user=true.",
        )

    deals = source_store.load_deals()
    audit_logs = source_store.load_delete_audit_logs()

    if dry_run and not deals:
        counts = _count_rows([])
        warnings = _build_warnings(
            source_deals=0,
            delete_audit_log_count=len(audit_logs),
            skipped_existing=0,
        )
        warnings.append(
            {
                "code": "target_not_checked_no_source_deals",
                "message": (
                    "Target MongoDB readiness was not checked because there "
                    "are no local personal deals to migrate."
                ),
            }
        )
        return {
            "ok": True,
            "migration_type": MIGRATION_TYPE,
            "dry_run": dry_run,
            "storage_written": False,
            "source": {
                "dataset": "local_personal",
                "data_dir": str(source_store.data_dir),
                "deals_path": str(source_store.deals_path),
                "deal_count": 0,
                "delete_audit_log_count": len(audit_logs),
            },
            "target": {
                "storage_backend": "mongo",
                "database": getattr(target_mongo, "database_name", None),
                "readiness": "not_checked_no_source_deals",
            },
            "options": {
                "overwrite": overwrite,
            },
            "counts": counts,
            "deals": [],
            "warnings": warnings,
        }

    target_ping = _safe_ping(target_mongo)
    if target_ping.get("status") != "ok":
        raise MCPError(
            error_code=ErrorCode.STORAGE_ERROR,
            stage=Stage.STORAGE,
            message="Target MongoDB storage is not ready for migration.",
            hint=target_ping,
        )

    rows = [_build_row(target_mongo, deal, overwrite=overwrite) for deal in deals]
    counts = _count_rows(rows)
    warnings = _build_warnings(
        source_deals=len(deals),
        delete_audit_log_count=len(audit_logs),
        skipped_existing=counts["would_skip_existing"],
    )

    migrated = 0
    overwritten = 0
    if not dry_run:
        for row, deal in zip(rows, deals, strict=True):
            if row["action"] not in {"create", "overwrite"}:
                continue
            _safe_upsert_deal(target_mongo, deal)
            if row["action"] == "overwrite":
                overwritten += 1
            else:
                migrated += 1

    counts.update(
        {
            "migrated": migrated,
            "overwritten": overwritten,
            "skipped_existing": counts["would_skip_existing"] if not dry_run else 0,
        }
    )

    return {
        "ok": True,
        "migration_type": MIGRATION_TYPE,
        "dry_run": dry_run,
        "storage_written": (not dry_run and (migrated + overwritten) > 0),
        "source": {
            "dataset": "local_personal",
            "data_dir": str(source_store.data_dir),
            "deals_path": str(source_store.deals_path),
            "deal_count": len(deals),
            "delete_audit_log_count": len(audit_logs),
        },
        "target": {
            "storage_backend": "mongo",
            "database": getattr(target_mongo, "database_name", None),
        },
        "options": {
            "overwrite": overwrite,
        },
        "counts": counts,
        "deals": rows,
        "warnings": warnings,
    }


def _safe_ping(target_mongo: Any) -> dict:
    try:
        ping = target_mongo.ping()
    except Exception as exc:
        raise MCPError(
            error_code=ErrorCode.STORAGE_ERROR,
            stage=Stage.STORAGE,
            message=f"Target MongoDB ping failed: {type(exc).__name__}: {exc}",
            retryable=True,
        ) from exc
    return ping if isinstance(ping, dict) else {"status": "error", "message": str(ping)}


def _build_row(target_mongo: Any, deal: dict, *, overwrite: bool) -> dict:
    deal_id = str(deal.get("deal_id") or "").strip()
    company = str(deal.get("company") or "").strip()
    existing = _safe_get_deal(target_mongo, deal_id)
    if existing and overwrite:
        action = "overwrite"
        reason = "target_deal_exists_overwrite_enabled"
    elif existing:
        action = "skip_existing"
        reason = "target_deal_exists"
    else:
        action = "create"
        reason = "target_deal_missing"
    return {
        "deal_id": deal_id,
        "company": company,
        "deal_stage": deal.get("deal_stage"),
        "action": action,
        "reason": reason,
    }


def _safe_get_deal(target_mongo: Any, deal_id: str) -> dict | None:
    try:
        return target_mongo.get_deal(deal_id)
    except Exception as exc:
        raise MCPError(
            error_code=ErrorCode.STORAGE_ERROR,
            stage=Stage.STORAGE,
            message=f"Target MongoDB read failed for deal_id={deal_id}: {exc}",
            retryable=True,
        ) from exc


def _safe_upsert_deal(target_mongo: Any, deal: dict) -> None:
    deal_id = str(deal.get("deal_id") or "").strip()
    try:
        target_mongo.upsert_deal(deepcopy(deal))
    except Exception as exc:
        raise MCPError(
            error_code=ErrorCode.STORAGE_ERROR,
            stage=Stage.STORAGE,
            message=f"Target MongoDB write failed for deal_id={deal_id}: {exc}",
            retryable=True,
        ) from exc


def _count_rows(rows: list[dict]) -> dict:
    would_create = sum(1 for row in rows if row["action"] == "create")
    would_overwrite = sum(1 for row in rows if row["action"] == "overwrite")
    would_skip_existing = sum(1 for row in rows if row["action"] == "skip_existing")
    return {
        "source_deals": len(rows),
        "would_create": would_create,
        "would_overwrite": would_overwrite,
        "would_skip_existing": would_skip_existing,
        "would_write": would_create + would_overwrite,
    }


def _build_warnings(
    *,
    source_deals: int,
    delete_audit_log_count: int,
    skipped_existing: int,
) -> list[dict]:
    warnings: list[dict] = []
    if source_deals == 0:
        warnings.append(
            {
                "code": "no_local_personal_deals",
                "message": "No user-created local personal deals were found.",
            }
        )
    if delete_audit_log_count:
        warnings.append(
            {
                "code": "delete_audit_logs_not_migrated",
                "message": (
                    "Local delete audit logs stay in local_data_dir and are not "
                    "migrated to MongoDB in this command."
                ),
            }
        )
    if skipped_existing:
        warnings.append(
            {
                "code": "existing_deals_skipped",
                "message": (
                    "One or more target MongoDB deals already exist and will be "
                    "skipped unless overwrite is enabled."
                ),
            }
        )
    return warnings
