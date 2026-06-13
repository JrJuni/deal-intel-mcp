from __future__ import annotations

from deal_intel.storage.mongodb import MongoDBClient


class FakeCollection:
    def __init__(self) -> None:
        self.indexes: list[dict] = []

    def create_index(self, keys: list[tuple[str, int]], **kwargs):
        self.indexes.append({"keys": keys, "kwargs": kwargs})
        return kwargs.get("name")

    def list_indexes(self) -> list[dict]:
        return [
            {
                "name": index["kwargs"].get("name"),
                "key": dict(index["keys"]),
                **({"unique": True} if index["kwargs"].get("unique") else {}),
            }
            for index in self.indexes
        ]


class FakeIndexDB:
    def __init__(self) -> None:
        self.deals = FakeCollection()
        self.delete_audit_logs = FakeCollection()
        self.analytics_snapshots = FakeCollection()


def _index_by_name(collection: FakeCollection, name: str) -> dict:
    for index in collection.indexes:
        if index["kwargs"].get("name") == name:
            return index
    raise AssertionError(f"missing index: {name}")


def test_ensure_indexes_creates_compound_indexes_for_core_read_paths() -> None:
    db = FakeIndexDB()
    client = MongoDBClient(uri="mongodb://example.invalid")
    client._db = db

    client.ensure_indexes()

    list_index = _index_by_name(db.deals, "archived_stage_updated")
    assert list_index["keys"] == [
        ("archived", 1),
        ("deal_stage", 1),
        ("updated_at", -1),
    ]

    trend_index = _index_by_name(
        db.analytics_snapshots,
        "analytics_snapshot_as_of_occurred_created",
    )
    assert trend_index["keys"] == [
        ("as_of", 1),
        ("occurred_at", 1),
        ("created_at", 1),
    ]


def test_ensure_indexes_preserves_existing_unique_and_lifecycle_indexes() -> None:
    db = FakeIndexDB()
    client = MongoDBClient(uri="mongodb://example.invalid")
    client._db = db

    client.ensure_indexes()

    deal_id_index = _index_by_name(db.deals, "deal_id_unique")
    assert deal_id_index["keys"] == [("deal_id", 1)]
    assert deal_id_index["kwargs"]["unique"] is True

    snapshot_event_index = _index_by_name(
        db.analytics_snapshots,
        "analytics_snapshot_event_id_unique",
    )
    assert snapshot_event_index["keys"] == [("event_id", 1)]
    assert snapshot_event_index["kwargs"]["unique"] is True

    assert _index_by_name(db.deals, "archived_updated")["keys"] == [
        ("archived", 1),
        ("updated_at", -1),
    ]
    assert _index_by_name(db.deals, "sample_batch")["keys"] == [
        ("is_sample", 1),
        ("sample_batch_id", 1),
    ]


def test_check_indexes_reports_contract_ok_after_ensure_indexes() -> None:
    db = FakeIndexDB()
    client = MongoDBClient(uri="mongodb://example.invalid")
    client._db = db

    client.ensure_indexes()
    report = client.check_indexes()

    assert report["ok"] is True
    assert report["missing_count"] == 0
    assert report["mismatch_count"] == 0
    assert (
        report["collections"]["deals"][0]["name"]
        == "deal_id_unique"
    )


def test_check_indexes_reports_missing_indexes() -> None:
    db = FakeIndexDB()
    client = MongoDBClient(uri="mongodb://example.invalid")
    client._db = db

    report = client.check_indexes()

    assert report["ok"] is False
    assert report["missing_count"] > 0
    assert report["collections"]["deals"][0]["status"] == "missing"
