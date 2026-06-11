from __future__ import annotations

from deal_intel.storage.mongodb import MongoDBClient, with_unarchived_deal_filter
from deal_intel.tools import get_insights


class FakeCursor(list):
    def sort(self, *_args):
        return self

    def limit(self, _limit: int):
        return self


class FakeDeleteResult:
    deleted_count = 1


class FakeCollection:
    def __init__(self) -> None:
        self.find_calls: list[tuple[dict, dict]] = []
        self.aggregate_calls: list[list[dict]] = []
        self.delete_queries: list[dict] = []

    def find(self, query: dict, projection: dict) -> FakeCursor:
        self.find_calls.append((query, projection))
        return FakeCursor([{"deal_id": "legacy-visible"}])

    def aggregate(self, pipeline: list[dict]) -> list[dict]:
        self.aggregate_calls.append(pipeline)
        return []

    def delete_one(self, query: dict) -> FakeDeleteResult:
        self.delete_queries.append(query)
        return FakeDeleteResult()


class FakeDatabase:
    def __init__(self) -> None:
        self.deals = FakeCollection()


def _client_with_fake_db(db: FakeDatabase) -> MongoDBClient:
    client = MongoDBClient(uri="mongodb://unused")
    client._db = db
    return client


def test_unarchived_filter_uses_ne_true_for_legacy_documents() -> None:
    assert with_unarchived_deal_filter() == {"archived": {"$ne": True}}
    assert with_unarchived_deal_filter({"deal_stage": "discovery"}) == {
        "archived": {"$ne": True},
        "deal_stage": "discovery",
    }


def test_storage_read_paths_apply_legacy_safe_archived_filter() -> None:
    db = FakeDatabase()
    client = _client_with_fake_db(db)

    client.list_deals()
    client.list_deals_for_metrics()
    client.list_deals_for_theme_backfill()
    client.get_deals_for_search()

    queries = [query for query, _projection in db.deals.find_calls]
    assert queries == [
        {"archived": {"$ne": True}},
        {"archived": {"$ne": True}},
        {"archived": {"$ne": True}},
        {
            "archived": {"$ne": True},
            "summary_embedding": {"$exists": True, "$ne": None},
        },
    ]
    list_projection = db.deals.find_calls[0][1]
    assert list_projection == {
        "_id": 0,
        "meetings.raw_notes": 0,
        "contacts": 0,
        "summary_embedding": 0,
    }


def test_atlas_vector_search_pipeline_excludes_archived_deals() -> None:
    db = FakeDatabase()
    client = _client_with_fake_db(db)

    client.search_by_embedding([0.1, 0.2], limit=3)

    pipeline = db.deals.aggregate_calls[0]
    assert {"$match": {"archived": {"$ne": True}}} in pipeline


def test_get_insights_direct_aggregation_paths_exclude_archived_deals() -> None:
    collection = FakeCollection()

    get_insights._win_patterns(collection)
    get_insights._loss_patterns(collection)
    get_insights._compare_won_lost(collection)
    get_insights._gap_frequency(collection)
    get_insights._industry_benchmark(collection)
    get_insights._stage_velocity(collection)

    for pipeline in collection.aggregate_calls:
        match_stages = [stage["$match"] for stage in pipeline if "$match" in stage]
        assert match_stages
        assert all(match["archived"] == {"$ne": True} for match in match_stages)

    assert collection.find_calls[-1][0]["archived"] == {"$ne": True}
