from __future__ import annotations

import os
from typing import Any

from deal_intel.atlas_vector_indexes import (
    build_create_search_index_command,
    deal_summary_vector_index_name,
    deal_summary_vector_search_settings,
)
from deal_intel.mongo_contracts import (
    build_collection_schema_command,
    build_deals_schema_command,
    collection_schema_contract_summary,
    compare_mongo_indexes,
    expected_mongo_indexes,
    mongo_schema_collections,
)
from deal_intel.storage.diagnostics import (
    missing_mongodb_uri_message,
    missing_mongodb_uri_ping,
)


def unarchived_deal_filter() -> dict[str, Any]:
    """Match visible deals, including legacy docs that predate archive fields."""
    return {"archived": {"$ne": True}}


def with_unarchived_deal_filter(query: dict | None = None) -> dict:
    """Compose a Mongo query with the standard archived exclusion filter."""
    merged = dict(query or {})
    merged.setdefault("archived", {"$ne": True})
    return merged


def _get_collection(db: Any, name: str) -> Any:
    """Return a Mongo collection from real PyMongo or a simple test fake."""

    if hasattr(db, name):
        return getattr(db, name)
    return db[name]


def preload_driver() -> None:
    """Import pymongo on the main thread before background MongoDB work starts."""
    import pymongo  # noqa: F401


class MongoDBClient:
    """MongoDB Atlas client. pymongo is imported lazily (cold-start guard)."""

    def __init__(self, *, uri: str | None = None, database: str = "deal_intel") -> None:
        self._uri = uri or os.environ.get("MONGODB_URI")
        self._database_name = database
        self._client: Any = None
        self._db: Any = None

    @property
    def database_name(self) -> str:
        return self._database_name

    def _get_db(self) -> Any:
        if self._db is None:
            if not self._uri:
                raise RuntimeError(missing_mongodb_uri_message())
            from pymongo import MongoClient
            self._client = MongoClient(
                self._uri,
                serverSelectionTimeoutMS=8_000,
                connectTimeoutMS=8_000,
                socketTimeoutMS=15_000,
            )
            self._db = self._client[self._database_name]
        return self._db

    def ensure_indexes(self) -> None:
        """Create indexes if missing. Idempotent and safe to call on every startup."""
        db = self._get_db()
        for collection_name, specs in expected_mongo_indexes().items():
            collection = _get_collection(db, collection_name)
            for spec in specs:
                collection.create_index(list(spec.keys), **spec.create_kwargs())

    def check_indexes(self) -> dict:
        """Read-only check that the MongoDB index contract is present."""

        db = self._get_db()
        actual_indexes: dict[str, list[dict[str, Any]]] = {}
        for collection_name in expected_mongo_indexes():
            collection = _get_collection(db, collection_name)
            actual_indexes[collection_name] = list(collection.list_indexes())
        return compare_mongo_indexes(actual_indexes)

    def check_deals_schema_validation(self) -> dict:
        """Read-only check for the deals collection validator contract."""

        return self.check_collection_schema_validation("deals")

    def check_collection_schema_validation(self, collection: str) -> dict:
        """Read-only check for a managed collection validator contract."""

        db = self._get_db()
        expected = collection_schema_contract_summary(collection)
        response = db.command("listCollections", filter={"name": expected["collection"]})
        first_batch = response.get("cursor", {}).get("firstBatch", [])
        if not first_batch:
            return {
                "ok": False,
                "status": "missing_collection",
                "collection": expected["collection"],
                "expected": expected,
                "current": None,
            }

        options = first_batch[0].get("options", {})
        current = {
            "has_validator": bool(options.get("validator")),
            "validation_action": options.get("validationAction"),
            "validation_level": options.get("validationLevel"),
        }
        expected_command = build_collection_schema_command(collection)
        mismatches = []
        if options.get("validator") != expected_command["validator"]:
            mismatches.append("validator")
        if options.get("validationAction") != expected_command["validationAction"]:
            mismatches.append("validation_action")
        if options.get("validationLevel") != expected_command["validationLevel"]:
            mismatches.append("validation_level")
        return {
            "ok": not mismatches,
            "status": "ok" if not mismatches else "mismatched",
            "collection": expected["collection"],
            "expected": expected,
            "current": current,
            "mismatches": mismatches,
        }

    def check_schema_validations(self) -> dict[str, dict]:
        """Read-only checks for every managed collection validator contract."""

        return {
            collection: self.check_collection_schema_validation(collection)
            for collection in mongo_schema_collections()
        }

    def deals_schema_command(self) -> dict:
        """Return the versioned collMod command without executing it."""

        return build_deals_schema_command()

    def collection_schema_command(self, collection: str) -> dict:
        """Return a versioned collMod command without executing it."""

        return build_collection_schema_command(collection)

    def apply_deals_schema_validation(self) -> dict:
        """Apply the deals collection validator. Caller must gate this behind --apply."""

        return self.apply_collection_schema_validation("deals")

    def apply_collection_schema_validation(self, collection: str) -> dict:
        """Apply a collection validator. Caller must gate this behind --apply."""

        return self._get_db().command(build_collection_schema_command(collection))

    def ping(self) -> dict:
        if not self._uri:
            return missing_mongodb_uri_ping(database=self._database_name)
        try:
            db = self._get_db()
            db.command("ping")
            return {"status": "ok", "database": self._database_name}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    # --- deals collection ---

    def upsert_deal(self, deal: dict) -> None:
        db = self._get_db()
        db.deals.replace_one({"deal_id": deal["deal_id"]}, deal, upsert=True)

    def update_deal_qualification_snapshots(
        self,
        deal_id: str,
        *,
        meddpicc_latest: dict,
        qualification_latest: dict,
        updated_at: str,
    ) -> bool:
        db = self._get_db()
        result = db.deals.update_one(
            with_unarchived_deal_filter({"deal_id": deal_id}),
            {
                "$set": {
                    "meddpicc_latest": meddpicc_latest,
                    "qualification_latest": qualification_latest,
                    "updated_at": updated_at,
                }
            },
        )
        return bool(result.matched_count)

    def update_deal_qualification_reextraction(
        self,
        deal_id: str,
        *,
        interactions: list[dict],
        meddpicc_latest: dict,
        qualification_latest: dict,
        updated_at: str,
    ) -> bool:
        db = self._get_db()
        result = db.deals.update_one(
            with_unarchived_deal_filter({"deal_id": deal_id}),
            {
                "$set": {
                    "interactions": interactions,
                    "meddpicc_latest": meddpicc_latest,
                    "qualification_latest": qualification_latest,
                    "updated_at": updated_at,
                }
            },
        )
        return bool(result.matched_count)

    def get_deal(self, deal_id: str) -> dict | None:
        db = self._get_db()
        return db.deals.find_one({"deal_id": deal_id}, {"_id": 0})

    def list_deals(self, *, stage: str | None = None, limit: int = 50) -> list[dict]:
        db = self._get_db()
        query = with_unarchived_deal_filter()
        if stage:
            query["deal_stage"] = stage
        projection = {
            "_id": 0,
            "meetings.raw_notes": 0,
            "interactions.raw_content": 0,
            "contacts": 0,
            "summary_embedding": 0,
        }
        cursor = db.deals.find(query, projection).sort("updated_at", -1).limit(limit)
        return list(cursor)

    def list_deals_for_metrics(self) -> list[dict]:
        db = self._get_db()
        projection = {
            "_id": 0,
            "meetings.raw_notes": 0,
            "interactions.raw_content": 0,
            "contacts": 0,
            "summary_embedding": 0,
        }
        cursor = db.deals.find(with_unarchived_deal_filter(), projection)
        return list(cursor)

    def list_deals_for_qualification_reextract(self, *, limit: int = 0) -> list[dict]:
        db = self._get_db()
        projection = {
            "_id": 0,
            "meetings.raw_notes": 0,
            "contacts": 0,
            "summary_embedding": 0,
        }
        cursor = db.deals.find(with_unarchived_deal_filter(), projection)
        if limit > 0:
            cursor = cursor.limit(limit)
        return list(cursor)

    def count_deals(self, query: dict) -> int:
        return self._get_db().deals.count_documents(query)

    def aggregate_deals(self, pipeline: list[dict]) -> list[dict]:
        return list(self._get_db().deals.aggregate(pipeline))

    def aggregate_analytics_snapshots(self, pipeline: list[dict]) -> list[dict]:
        return list(self._get_db().analytics_snapshots.aggregate(pipeline))

    def list_deals_for_theme_backfill(self, *, limit: int = 0) -> list[dict]:
        cursor = self._get_db().deals.find(with_unarchived_deal_filter(), {"_id": 0})
        if limit > 0:
            cursor = cursor.limit(limit)
        return list(cursor)

    # --- semantic search (Python-side cosine, M0-compatible) ---

    def get_deals_for_search(self) -> list[dict]:
        """Fetch all deals that have a summary_embedding for Python-side similarity ranking.

        Returns only the fields needed for search results — summary_embedding is included
        for scoring but stripped before returning to the caller (handled in search_deals tool).

        Upgrade path: when cluster is M10+, replace the Python cosine loop in
        tools/search_deals.py with $vectorSearch + search_by_embedding() below.
        """
        db = self._get_db()
        cursor = db.deals.find(
            with_unarchived_deal_filter(
                {"summary_embedding": {"$exists": True, "$ne": None}}
            ),
            {
                "_id": 0,
                "deal_id": 1,
                "company": 1,
                "deal_stage": 1,
                "industry": 1,
                "industry_tags": 1,
                "customer_segment": 1,
                "deal_size_amount": 1,
                "deal_size_currency": 1,
                "qualification_latest.framework_key": 1,
                "qualification_latest.framework_display_name": 1,
                "qualification_latest.health_pct": 1,
                "qualification_latest.coverage_pct": 1,
                "qualification_latest.quality_pct": 1,
                "qualification_latest.filled_count": 1,
                "qualification_latest.total_count": 1,
                "qualification_latest.gaps": 1,
                "qualification_latest.dimensions": 1,
                "qualification_latest.dimension_metadata": 1,
                "meddpicc_latest.health_pct": 1,
                "meddpicc_latest.gaps": 1,
                "summary_embedding": 1,
            },
        )
        return list(cursor)

    # --- reserved for M10+ upgrade ---

    def ensure_vector_index(self, dimensions: int = 384) -> dict:
        """Create Atlas Vector Search index. Requires M10+ cluster."""

        db = self._get_db()
        try:
            result = db.command(build_create_search_index_command(dimensions=dimensions))
            return {"ok": True, "status": "applied", "result": result}
        except Exception as e:
            msg = str(e).lower()
            if "already exists" in msg or "duplicate" in msg:
                return {
                    "ok": True,
                    "status": "already_exists",
                    "message": str(e),
                }
            raise

    def search_by_embedding(self, embedding: list[float], *, limit: int = 5) -> list[dict]:
        """$vectorSearch aggregation — M10+ only. Use get_deals_for_search() on M0."""
        col = self._get_db().deals
        search_settings = deal_summary_vector_search_settings()
        pipeline = [
            {
                "$vectorSearch": {
                    "index": deal_summary_vector_index_name(),
                    "path": "summary_embedding",
                    "queryVector": embedding,
                    "numCandidates": max(
                        limit * search_settings["num_candidates_multiplier"],
                        search_settings["minimum_num_candidates"],
                    ),
                    "limit": limit,
                }
            },
            {"$match": with_unarchived_deal_filter()},
            {
                "$project": {
                    "_id": 0,
                    "deal_id": 1,
                    "company": 1,
                    "deal_stage": 1,
                    "industry": 1,
                    "industry_tags": 1,
                    "customer_segment": 1,
                    "deal_size_amount": 1,
                    "deal_size_currency": 1,
                    "qualification_framework": {
                        "$ifNull": [
                            "$qualification_latest.framework_key",
                            "meddpicc",
                        ]
                    },
                    "qualification_framework_display_name": {
                        "$ifNull": [
                            "$qualification_latest.framework_display_name",
                            "MEDDPICC",
                        ]
                    },
                    "qualification_source_field": {
                        "$cond": [
                            {
                                "$ne": [
                                    {
                                        "$ifNull": [
                                            "$qualification_latest.framework_key",
                                            None,
                                        ]
                                    },
                                    None,
                                ]
                            },
                            "qualification_latest",
                            "meddpicc_latest",
                        ]
                    },
                    "qualification_health_pct": {
                        "$ifNull": [
                            "$qualification_latest.health_pct",
                            "$meddpicc_latest.health_pct",
                        ]
                    },
                    "qualification_gaps": {
                        "$ifNull": [
                            "$qualification_latest.gaps",
                            "$meddpicc_latest.gaps",
                        ]
                    },
                    "health_pct": {
                        "$ifNull": [
                            "$qualification_latest.health_pct",
                            "$meddpicc_latest.health_pct",
                        ]
                    },
                    "gaps": {
                        "$ifNull": [
                            "$qualification_latest.gaps",
                            "$meddpicc_latest.gaps",
                        ]
                    },
                    "score": {"$meta": "vectorSearchScore"},
                }
            },
        ]
        return list(col.aggregate(pipeline))

    # --- lifecycle audit / hard delete ---

    def insert_delete_audit_log(self, entry: dict) -> None:
        self._get_db().delete_audit_logs.insert_one(entry)

    def hard_delete_deal(self, deal_id: str) -> int:
        result = self._get_db().deals.delete_one({"deal_id": deal_id})
        return int(result.deleted_count)

    # --- sample/demo data ---

    def upsert_deals(self, deals: list[dict]) -> int:
        if not deals:
            return 0
        from pymongo import ReplaceOne

        operations = [
            ReplaceOne({"deal_id": deal["deal_id"]}, deal, upsert=True)
            for deal in deals
        ]
        self._get_db().deals.bulk_write(operations, ordered=True)
        return len(deals)

    def list_sample_deals(self, sample_batch_id: str) -> list[dict]:
        cursor = self._get_db().deals.find(
            {"is_sample": True, "sample_batch_id": sample_batch_id},
            {"_id": 0, "deal_id": 1, "company": 1, "deal_stage": 1},
        )
        return list(cursor)

    def delete_sample_deals(self, sample_batch_id: str) -> int:
        result = self._get_db().deals.delete_many(
            {"is_sample": True, "sample_batch_id": sample_batch_id}
        )
        return int(result.deleted_count)

    # --- analytics snapshots / trend foundation ---

    def upsert_analytics_snapshot(self, snapshot: dict) -> bool:
        result = self._get_db().analytics_snapshots.update_one(
            {"event_id": snapshot["event_id"]},
            {"$setOnInsert": snapshot},
            upsert=True,
        )
        return result.upserted_id is not None

    def list_analytics_snapshots(
        self,
        *,
        start_date: str,
        end_date: str,
        stage: str | None = None,
        industry: str | None = None,
    ) -> list[dict]:
        query: dict[str, Any] = {"as_of": {"$gte": start_date, "$lte": end_date}}
        if stage:
            query["deal_stage"] = stage
        if industry:
            query["industry"] = industry
        projection = {
            "_id": 0,
            "event_id": 1,
            "event_type": 1,
            "occurred_at": 1,
            "created_at": 1,
            "as_of": 1,
            "timezone": 1,
            "deal_id": 1,
            "company": 1,
            "industry": 1,
            "industry_tags": 1,
            "customer_segment": 1,
            "deal_stage": 1,
            "deal_size_amount": 1,
            "deal_size_low_amount": 1,
            "deal_size_high_amount": 1,
            "deal_size_currency": 1,
            "deal_size_status": 1,
            "expected_close_date": 1,
            "expected_close_date_source": 1,
            "actual_close_date": 1,
            "close_reason_present": 1,
            "qualification_framework": 1,
            "qualification_framework_display_name": 1,
            "qualification_source_field": 1,
            "qualification_health_pct": 1,
            "qualification_coverage_pct": 1,
            "qualification_quality_pct": 1,
            "qualification_gap_count": 1,
            "qualification_gaps": 1,
            "health_pct": 1,
            "health_band": 1,
            "meddpicc_filled_count": 1,
            "meddpicc_gap_count": 1,
            "meddpicc_gaps": 1,
            "days_in_stage": 1,
            "stuck_threshold_days": 1,
            "is_stuck": 1,
            "close_date_status": 1,
            "is_overdue": 1,
            "overdue_days": 1,
            "attention_reasons": 1,
        }
        cursor = self._get_db().analytics_snapshots.find(query, projection).sort(
            [("as_of", 1), ("occurred_at", 1)]
        )
        return list(cursor)
