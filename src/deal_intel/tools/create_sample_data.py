from __future__ import annotations

from datetime import UTC, datetime

from deal_intel.errors import ErrorCode, MCPError, Stage
from deal_intel.storage.mongodb import MongoDBClient
from deal_intel.tools.sample_data import (
    require_confirmation,
    resolve_demo_database,
    sample_query,
    validate_dataset,
    validate_demo_client,
)
from deal_intel.tools.sample_dataset import (
    SAMPLE_BATCH_ID,
    build_sample_deals,
    sample_preview,
)


def handle(
    mongo: MongoDBClient,
    cfg: dict,
    *,
    dataset: str = "weekly_pipeline_demo",
    demo_database: str | None = None,
    confirmed_by_user: bool = False,
    dry_run: bool = True,
    overwrite: bool = False,
) -> dict:
    dataset = validate_dataset(dataset)
    selection = resolve_demo_database(cfg, demo_database=demo_database)
    validate_demo_client(mongo, selection)
    now = datetime.now(UTC).isoformat()
    deals = build_sample_deals(loaded_at=now)
    try:
        existing_count = mongo.count_deals(sample_query())
    except Exception as exc:
        raise MCPError(
            error_code=ErrorCode.STORAGE_ERROR,
            stage=Stage.STORAGE,
            message=str(exc),
            retryable=True,
        ) from exc

    base = {
        "ok": True,
        "dataset": dataset,
        "sample_batch_id": SAMPLE_BATCH_ID,
        "primary_database": selection.primary_database,
        "demo_database": selection.demo_database,
        "dry_run": dry_run,
        "overwrite": overwrite,
        "existing_count": existing_count,
        "deal_count": len(deals),
        "preview": sample_preview(deals),
    }
    if dry_run:
        return {
            **base,
            "would_create_or_replace_count": len(deals),
            "would_delete_existing_count": existing_count if overwrite else 0,
            "storage_written": False,
            "warnings": _warnings(existing_count=existing_count, overwrite=overwrite),
        }

    require_confirmation(
        confirmed_by_user=confirmed_by_user,
        action="create_sample_data",
    )
    if existing_count and not overwrite:
        raise MCPError(
            error_code=ErrorCode.INVALID_INPUT,
            stage=Stage.PREFLIGHT,
            message="sample data already exists in the demo database",
            hint={
                "existing_count": existing_count,
                "fix": "Set overwrite=true to replace this sample batch.",
            },
            retryable=False,
        )

    try:
        deleted_existing_count = (
            mongo.delete_sample_deals(SAMPLE_BATCH_ID) if existing_count else 0
        )
        upserted_count = mongo.upsert_deals(deals)
    except Exception as exc:
        raise MCPError(
            error_code=ErrorCode.STORAGE_ERROR,
            stage=Stage.STORAGE,
            message=str(exc),
            retryable=True,
        ) from exc

    return {
        **base,
        "dry_run": False,
        "deleted_existing_count": deleted_existing_count,
        "created_or_replaced_count": upserted_count,
        "storage_written": True,
        "warnings": [],
    }


def _warnings(*, existing_count: int, overwrite: bool) -> list[str]:
    if existing_count and not overwrite:
        return ["sample_data_exists"]
    return []
