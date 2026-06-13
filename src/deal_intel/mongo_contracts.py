from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

ASC = 1
DESC = -1

MONGO_SCHEMA_FILES = {
    "deals": "deals.v1.json",
    "analytics_snapshots": "analytics_snapshots.v1.json",
    "delete_audit_logs": "delete_audit_logs.v1.json",
}
DEALS_SCHEMA_FILE = MONGO_SCHEMA_FILES["deals"]
DEFAULT_DEALS_SCHEMA_SPEC = (
    Path(__file__).resolve().parent / "resources" / "mongo" / DEALS_SCHEMA_FILE
)


@dataclass(frozen=True)
class MongoIndexSpec:
    collection: str
    name: str
    keys: tuple[tuple[str, int], ...]
    unique: bool = False

    def create_kwargs(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = {"name": self.name}
        if self.unique:
            kwargs["unique"] = True
        return kwargs


def expected_mongo_indexes() -> dict[str, list[MongoIndexSpec]]:
    """Return the versioned index contract for the MongoDB-backed full profile."""

    return {
        "deals": [
            MongoIndexSpec(
                collection="deals",
                name="deal_id_unique",
                keys=(("deal_id", ASC),),
                unique=True,
            ),
            MongoIndexSpec(
                collection="deals",
                name="stage_updated",
                keys=(("deal_stage", ASC), ("updated_at", DESC)),
            ),
            MongoIndexSpec(
                collection="deals",
                name="updated_desc",
                keys=(("updated_at", DESC),),
            ),
            MongoIndexSpec(
                collection="deals",
                name="archived_updated",
                keys=(("archived", ASC), ("updated_at", DESC)),
            ),
            MongoIndexSpec(
                collection="deals",
                name="archived_stage_updated",
                keys=(("archived", ASC), ("deal_stage", ASC), ("updated_at", DESC)),
            ),
            MongoIndexSpec(
                collection="deals",
                name="health_pct_desc",
                keys=(("meddpicc_latest.health_pct", DESC),),
            ),
            MongoIndexSpec(
                collection="deals",
                name="stage_customer_theme",
                keys=(("deal_stage", ASC), ("customer_themes.theme_key", ASC)),
            ),
            MongoIndexSpec(
                collection="deals",
                name="sample_batch",
                keys=(("is_sample", ASC), ("sample_batch_id", ASC)),
            ),
        ],
        "delete_audit_logs": [
            MongoIndexSpec(
                collection="delete_audit_logs",
                name="delete_audit_deal_deleted",
                keys=(("deal_id", ASC), ("deleted_at", DESC)),
            ),
        ],
        "analytics_snapshots": [
            MongoIndexSpec(
                collection="analytics_snapshots",
                name="analytics_snapshot_event_id_unique",
                keys=(("event_id", ASC),),
                unique=True,
            ),
            MongoIndexSpec(
                collection="analytics_snapshots",
                name="analytics_snapshot_deal_occurred",
                keys=(("deal_id", ASC), ("occurred_at", DESC)),
            ),
            MongoIndexSpec(
                collection="analytics_snapshots",
                name="analytics_snapshot_event_occurred",
                keys=(("event_type", ASC), ("occurred_at", DESC)),
            ),
            MongoIndexSpec(
                collection="analytics_snapshots",
                name="analytics_snapshot_as_of_occurred_created",
                keys=(("as_of", ASC), ("occurred_at", ASC), ("created_at", ASC)),
            ),
        ],
    }


def load_deals_schema_spec(path: str | Path | None = None) -> dict[str, Any]:
    """Load the version-managed MongoDB collection validator spec."""

    return load_collection_schema_spec("deals", path=path)


def mongo_schema_collections() -> tuple[str, ...]:
    return tuple(MONGO_SCHEMA_FILES)


def load_collection_schema_spec(
    collection: str,
    *,
    path: str | Path | None = None,
) -> dict[str, Any]:
    """Load a version-managed MongoDB collection validator spec."""

    if path is not None:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    filename = _schema_filename(collection)
    schema_path = Path(__file__).resolve().parent / "resources" / "mongo" / filename
    if schema_path.exists():
        return json.loads(schema_path.read_text(encoding="utf-8"))
    return json.loads(_schema_resource_text(filename))


def build_deals_schema_command(
    *,
    validation_action: str | None = None,
    validation_level: str | None = None,
) -> dict[str, Any]:
    """Build a safe collMod command for the deals collection validator."""

    return build_collection_schema_command(
        "deals",
        validation_action=validation_action,
        validation_level=validation_level,
    )


def build_collection_schema_command(
    collection: str,
    *,
    validation_action: str | None = None,
    validation_level: str | None = None,
) -> dict[str, Any]:
    """Build a safe collMod command for a managed collection validator."""

    spec = load_collection_schema_spec(collection)
    return {
        "collMod": spec["collection"],
        "validator": deepcopy(spec["validator"]),
        "validationAction": validation_action or spec["validation_action"],
        "validationLevel": validation_level or spec["validation_level"],
    }


def deals_schema_contract_summary() -> dict[str, Any]:
    return collection_schema_contract_summary("deals")


def collection_schema_contract_summary(collection: str) -> dict[str, Any]:
    spec = load_collection_schema_spec(collection)
    return {
        "id": spec["id"],
        "version": spec["version"],
        "collection": spec["collection"],
        "validation_action": spec["validation_action"],
        "validation_level": spec["validation_level"],
        "required_fields": spec["validator"]["$jsonSchema"].get("required", []),
    }


def compare_mongo_indexes(
    actual_indexes: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    """Compare actual list_indexes() output against the expected contract."""

    collections: dict[str, Any] = {}
    missing_count = 0
    mismatch_count = 0
    for collection_name, specs in expected_mongo_indexes().items():
        actual_by_name = {
            str(index.get("name")): index for index in actual_indexes.get(collection_name, [])
        }
        collection_entries: list[dict[str, Any]] = []
        for spec in specs:
            actual = actual_by_name.get(spec.name)
            if actual is None:
                missing_count += 1
                collection_entries.append(
                    _index_report_entry(spec, status="missing", actual=None)
                )
                continue

            actual_keys = _normalize_index_keys(actual.get("key"))
            actual_unique = bool(actual.get("unique", False))
            expected_keys = list(spec.keys)
            mismatches = []
            if actual_keys != expected_keys:
                mismatches.append("keys")
            if actual_unique != spec.unique:
                mismatches.append("unique")
            if mismatches:
                mismatch_count += 1
                collection_entries.append(
                    _index_report_entry(
                        spec,
                        status="mismatched",
                        actual={
                            "keys": actual_keys,
                            "unique": actual_unique,
                            "mismatches": mismatches,
                        },
                    )
                )
                continue

            collection_entries.append(
                _index_report_entry(
                    spec,
                    status="ok",
                    actual={"keys": actual_keys, "unique": actual_unique},
                )
            )
        collections[collection_name] = collection_entries

    return {
        "ok": missing_count == 0 and mismatch_count == 0,
        "missing_count": missing_count,
        "mismatch_count": mismatch_count,
        "collections": collections,
    }


def _index_report_entry(
    spec: MongoIndexSpec,
    *,
    status: str,
    actual: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "name": spec.name,
        "status": status,
        "expected": {
            "keys": list(spec.keys),
            "unique": spec.unique,
        },
        "actual": actual,
    }


def _normalize_index_keys(value: Any) -> list[tuple[str, int]]:
    if value is None:
        return []
    if hasattr(value, "items"):
        return [(str(key), int(direction)) for key, direction in value.items()]
    return [(str(key), int(direction)) for key, direction in value]


def _schema_filename(collection: str) -> str:
    try:
        return MONGO_SCHEMA_FILES[collection]
    except KeyError as exc:
        valid = ", ".join(mongo_schema_collections())
        raise ValueError(f"unknown Mongo schema collection {collection!r}; valid: {valid}") from exc


def _schema_resource_text(filename: str) -> str:
    return (
        resources.files("deal_intel.resources")
        .joinpath("mongo", filename)
        .read_text(encoding="utf-8")
    )
