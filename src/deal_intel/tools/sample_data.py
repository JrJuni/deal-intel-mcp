from __future__ import annotations

import re
from dataclasses import dataclass

from deal_intel.errors import ErrorCode, MCPError, Stage
from deal_intel.storage.mongodb import MongoDBClient
from deal_intel.tools.sample_dataset import (
    SAMPLE_BATCH_ID,
    SUPPORTED_DATASETS,
)

_DATABASE_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_RESERVED_DATABASES = frozenset({"admin", "config", "local"})


@dataclass(frozen=True)
class DemoDatabaseSelection:
    primary_database: str
    demo_database: str


def resolve_demo_database(
    cfg: dict,
    *,
    demo_database: str | None = None,
) -> DemoDatabaseSelection:
    mongodb_cfg = cfg.get("mongodb", {})
    primary = str(mongodb_cfg.get("database") or "deal_intel").strip()
    demo = str(
        demo_database
        or mongodb_cfg.get("demo_database")
        or "deal_intel_demo"
    ).strip()
    _validate_database_name(primary, field_name="mongodb.database")
    _validate_database_name(demo, field_name="demo_database")
    if demo == primary:
        raise MCPError(
            error_code=ErrorCode.INVALID_INPUT,
            stage=Stage.PREFLIGHT,
            message="demo_database must be different from the primary database",
            hint={
                "primary_database": primary,
                "recommended_demo_database": f"{primary}_demo",
            },
            retryable=False,
        )
    return DemoDatabaseSelection(primary_database=primary, demo_database=demo)


def validate_dataset(dataset: str) -> str:
    cleaned = (dataset or "").strip() or "weekly_pipeline_demo"
    if cleaned not in SUPPORTED_DATASETS:
        raise MCPError(
            error_code=ErrorCode.INVALID_INPUT,
            stage=Stage.PREFLIGHT,
            message=f"dataset {cleaned!r} is not supported",
            hint={"supported_datasets": sorted(SUPPORTED_DATASETS)},
            retryable=False,
        )
    return cleaned


def require_confirmation(*, confirmed_by_user: bool, action: str) -> None:
    if not confirmed_by_user:
        raise MCPError(
            error_code=ErrorCode.INVALID_INPUT,
            stage=Stage.PREFLIGHT,
            message=f"{action} requires explicit user confirmation",
            hint={"required": "confirmed_by_user=true"},
            retryable=False,
        )


def sample_query() -> dict:
    return {"is_sample": True, "sample_batch_id": SAMPLE_BATCH_ID}


def validate_demo_client(
    mongo: MongoDBClient,
    selection: DemoDatabaseSelection,
) -> None:
    actual = getattr(mongo, "database_name", None)
    if actual != selection.demo_database:
        raise MCPError(
            error_code=ErrorCode.INVALID_INPUT,
            stage=Stage.PREFLIGHT,
            message="sample data tools must use the resolved demo database client",
            hint={
                "expected_demo_database": selection.demo_database,
                "actual_database": actual,
            },
            retryable=False,
        )


def _validate_database_name(value: str, *, field_name: str) -> None:
    if not value or not _DATABASE_RE.fullmatch(value):
        raise MCPError(
            error_code=ErrorCode.INVALID_INPUT,
            stage=Stage.PREFLIGHT,
            message=f"{field_name} must be 1-64 chars: letters, numbers, _ or -",
            retryable=False,
        )
    if value in _RESERVED_DATABASES:
        raise MCPError(
            error_code=ErrorCode.INVALID_INPUT,
            stage=Stage.PREFLIGHT,
            message=f"{field_name} uses a reserved MongoDB database name",
            hint={"reserved": sorted(_RESERVED_DATABASES)},
            retryable=False,
        )
