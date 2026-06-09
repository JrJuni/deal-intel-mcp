from __future__ import annotations

import os
from typing import Any


def unarchived_deal_filter() -> dict[str, Any]:
    """Match visible deals, including legacy docs that predate archive fields."""
    return {"archived": {"$ne": True}}


def with_unarchived_deal_filter(query: dict | None = None) -> dict:
    """Compose a Mongo query with the standard archived exclusion filter."""
    merged = dict(query or {})
    merged.setdefault("archived", {"$ne": True})
    return merged


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
                raise RuntimeError(
                    "MONGODB_URI not set. "
                    "Add MONGODB_URI=mongodb+srv://... to .env (see .env.example)."
                )
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
        from pymongo import ASCENDING, DESCENDING
        col = self._get_db().deals

        # Point lookups by deal_id (also enforces uniqueness).
        col.create_index([("deal_id", ASCENDING)], unique=True, name="deal_id_unique")

        # list_deals: stage filter + updated_at sort (most common query path).
        col.create_index(
            [("deal_stage", ASCENDING), ("updated_at", DESCENDING)],
            name="stage_updated",
        )

        # list_deals: no stage filter, updated_at sort only.
        col.create_index([("updated_at", DESCENDING)], name="updated_desc")

        # Default read paths hide archived deals while preserving legacy docs
        # where the field is absent.
        col.create_index(
            [("archived", ASCENDING), ("updated_at", DESCENDING)],
            name="archived_updated",
        )

        # BI / get_insights: sort by health score (used in Phase 2).
        col.create_index(
            [("meddpicc_latest.health_pct", DESCENDING)],
            name="health_pct_desc",
        )

        # Customer-theme BI: stage filter + multikey theme grouping.
        col.create_index(
            [("deal_stage", ASCENDING), ("customer_themes.theme_key", ASCENDING)],
            name="stage_customer_theme",
        )

        audit_col = self._get_db().delete_audit_logs
        audit_col.create_index(
            [("deal_id", ASCENDING), ("deleted_at", DESCENDING)],
            name="delete_audit_deal_deleted",
        )

        col.create_index(
            [("is_sample", ASCENDING), ("sample_batch_id", ASCENDING)],
            name="sample_batch",
        )

    def ping(self) -> dict:
        if not self._uri:
            return {
                "status": "missing_uri",
                "fix": "Set MONGODB_URI in .env (see .env.example)",
            }
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

    def get_deal(self, deal_id: str) -> dict | None:
        db = self._get_db()
        return db.deals.find_one({"deal_id": deal_id}, {"_id": 0})

    def list_deals(self, *, stage: str | None = None, limit: int = 50) -> list[dict]:
        db = self._get_db()
        query = with_unarchived_deal_filter()
        if stage:
            query["deal_stage"] = stage
        cursor = db.deals.find(query, {"_id": 0, "meetings.raw_notes": 0}).sort(
            "updated_at", -1
        ).limit(limit)
        return list(cursor)

    def list_deals_for_metrics(self) -> list[dict]:
        db = self._get_db()
        projection = {
            "_id": 0,
            "meetings.raw_notes": 0,
            "contacts": 0,
            "summary_embedding": 0,
        }
        cursor = db.deals.find(with_unarchived_deal_filter(), projection)
        return list(cursor)

    def count_deals(self, query: dict) -> int:
        return self._get_db().deals.count_documents(query)

    def aggregate_deals(self, pipeline: list[dict]) -> list[dict]:
        return list(self._get_db().deals.aggregate(pipeline))

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
                "deal_size_krw": 1,
                "meddpicc_latest.health_pct": 1,
                "meddpicc_latest.gaps": 1,
                "summary_embedding": 1,
            },
        )
        return list(cursor)

    # --- reserved for M10+ upgrade ---

    def ensure_vector_index(self, dimensions: int = 384) -> None:
        """Create Atlas Vector Search index. Requires M10+ cluster — no-op on M0."""
        db = self._get_db()
        try:
            db.command({
                "createSearchIndexes": "deals",
                "indexes": [{
                    "name": "deal_summary_vector",
                    "type": "vectorSearch",
                    "definition": {
                        "fields": [{
                            "type": "vector",
                            "path": "summary_embedding",
                            "numDimensions": dimensions,
                            "similarity": "cosine",
                        }]
                    },
                }],
            })
        except Exception as e:
            msg = str(e).lower()
            if "already exists" in msg or "duplicate" in msg:
                pass
            # M0 silently ignores — do not warn, not supported on free tier

    def search_by_embedding(self, embedding: list[float], *, limit: int = 5) -> list[dict]:
        """$vectorSearch aggregation — M10+ only. Use get_deals_for_search() on M0."""
        col = self._get_db().deals
        pipeline = [
            {
                "$vectorSearch": {
                    "index": "deal_summary_vector",
                    "path": "summary_embedding",
                    "queryVector": embedding,
                    "numCandidates": max(limit * 10, 50),
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
                    "deal_size_krw": 1,
                    "health_pct": "$meddpicc_latest.health_pct",
                    "gaps": "$meddpicc_latest.gaps",
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
