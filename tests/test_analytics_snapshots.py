from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from types import SimpleNamespace

from deal_intel.storage.mongodb import MongoDBClient
from deal_intel.tools import add_meeting, create_deal, update_stage
from deal_intel.tools.analytics_snapshot import (
    build_analytics_snapshot,
    record_analytics_snapshot,
)


class FakeLLM:
    def __init__(self, responses: list[str]) -> None:
        self.responses = iter(responses)

    def chat_once(self, **_kwargs):
        return SimpleNamespace(
            text=next(self.responses),
            usage={"input_tokens": 1, "output_tokens": 1},
        )


class FakeSnapshotMongo:
    def __init__(self, deal: dict | None = None, *, fail_snapshot: bool = False) -> None:
        self.deal = deepcopy(deal)
        self.saved: dict | None = None
        self.snapshots: dict[str, dict] = {}
        self.fail_snapshot = fail_snapshot

    def get_deal(self, deal_id: str) -> dict | None:
        if self.deal is None or self.deal.get("deal_id") != deal_id:
            return None
        return deepcopy(self.deal)

    def upsert_deal(self, deal: dict) -> None:
        self.saved = deepcopy(deal)
        self.deal = deepcopy(deal)

    def upsert_analytics_snapshot(self, snapshot: dict) -> bool:
        if self.fail_snapshot:
            raise RuntimeError("snapshot store unavailable")
        event_id = snapshot["event_id"]
        if event_id in self.snapshots:
            return False
        self.snapshots[event_id] = deepcopy(snapshot)
        return True


class FakeUpdateResult:
    def __init__(self, upserted_id) -> None:
        self.upserted_id = upserted_id


class FakeSnapshotCollection:
    def __init__(self) -> None:
        self.docs: dict[str, dict] = {}

    def update_one(self, query: dict, update: dict, *, upsert: bool):
        assert upsert is True
        event_id = query["event_id"]
        if event_id in self.docs:
            return FakeUpdateResult(None)
        self.docs[event_id] = deepcopy(update["$setOnInsert"])
        return FakeUpdateResult("inserted-id")


class FakeDB:
    def __init__(self) -> None:
        self.analytics_snapshots = FakeSnapshotCollection()


def _deal(**overrides) -> dict:
    deal = {
        "deal_id": "deal-1",
        "company": "Test Co",
        "industry": "IT",
        "deal_stage": "proposal",
        "deal_size_krw": 25_000_000,
        "deal_size_low_krw": None,
        "deal_size_high_krw": None,
        "deal_size_status": "quoted",
        "expected_close_date": "2026-06-20",
        "expected_close_date_source": "user_provided",
        "actual_close_date": None,
        "close_reason": None,
        "contacts": [{"name": "private contact"}],
        "meetings": [{"raw_notes": "secret raw notes", "summary": "safe summary"}],
        "summary_embedding": [0.1, 0.2, 0.3],
        "meddpicc_latest": {
            "health_pct": 75.0,
            "filled_count": 4,
            "gaps": ["champion"],
        },
        "stage_history": [
            {"stage": "proposal", "entered_at": "2026-06-01T00:00:00+00:00"}
        ],
    }
    deal.update(overrides)
    return deal


def test_build_analytics_snapshot_is_safe_and_metric_shaped() -> None:
    snapshot = build_analytics_snapshot(
        cfg={},
        event_type="add_meeting",
        event_id="event-1",
        deal=_deal(),
        occurred_at=datetime(2026, 6, 9, 12, 0, tzinfo=UTC),
    )

    assert snapshot["schema_version"] == 1
    assert snapshot["source"] == "deal_intel_mcp"
    assert snapshot["event_id"] == "event-1"
    assert snapshot["deal_id"] == "deal-1"
    assert snapshot["health_band"] == "healthy"
    assert snapshot["meddpicc_gap_count"] == 1
    assert snapshot["meddpicc_gaps"] == ["champion"]
    assert snapshot["days_in_stage"] == 8

    serialized = json.dumps(snapshot, ensure_ascii=False)
    assert "secret raw notes" not in serialized
    assert "private contact" not in serialized
    assert "summary_embedding" not in serialized


def test_mongodb_snapshot_upsert_is_idempotent_by_event_id() -> None:
    mongo = MongoDBClient(uri="mongodb://unused")
    mongo._db = FakeDB()

    assert mongo.upsert_analytics_snapshot({"event_id": "event-1"}) is True
    assert mongo.upsert_analytics_snapshot({"event_id": "event-1"}) is False
    assert len(mongo._db.analytics_snapshots.docs) == 1


def test_record_analytics_snapshot_reports_duplicate_without_second_insert() -> None:
    mongo = FakeSnapshotMongo(_deal())

    first = record_analytics_snapshot(
        mongo=mongo,
        cfg={},
        event_type="update_stage",
        event_id="event-1",
        deal=_deal(),
        occurred_at=datetime(2026, 6, 9, 12, 0, tzinfo=UTC),
    )
    second = record_analytics_snapshot(
        mongo=mongo,
        cfg={},
        event_type="update_stage",
        event_id="event-1",
        deal=_deal(),
        occurred_at=datetime(2026, 6, 9, 12, 0, tzinfo=UTC),
    )

    assert first is not None
    assert first["inserted"] is True
    assert first["duplicate"] is False
    assert second is not None
    assert second["inserted"] is False
    assert second["duplicate"] is True
    assert len(mongo.snapshots) == 1


def test_create_deal_records_analytics_snapshot_after_deal_upsert() -> None:
    mongo = FakeSnapshotMongo()

    result = create_deal.handle(
        mongo=mongo,
        cfg={},
        company="New Co",
        industry="IT",
        deal_size_krw=None,
    )

    assert result["ok"] is True
    assert result["analytics_snapshot"]["ok"] is True
    assert result["analytics_snapshot"]["event_type"] == "create_deal"
    assert result["analytics_snapshot"]["inserted"] is True
    assert len(mongo.snapshots) == 1
    snapshot = next(iter(mongo.snapshots.values()))
    assert snapshot["deal_id"] == result["deal_id"]
    assert snapshot["event_type"] == "create_deal"


def test_add_meeting_records_analytics_snapshot_for_meeting_event() -> None:
    mongo = FakeSnapshotMongo(_deal(deal_stage="discovery", meetings=[]))
    analysis = json.dumps(
        {
            "meddpicc": {
                "identify_pain": {
                    "score": 4,
                    "evidence": "Manual reporting takes too long",
                }
            },
            "customer_themes": [],
        }
    )
    llm = FakeLLM([analysis, "Customer wants faster reporting."])

    result = add_meeting.handle(
        mongo=mongo,
        llm=llm,
        cfg={"meddpicc": {"weights": {}}},
        deal_id="deal-1",
        date="2026-06-09",
        raw_notes="Manual reporting takes too long.",
    )

    assert result["ok"] is True
    assert result["analytics_snapshot"]["ok"] is True
    assert result["analytics_snapshot"]["event_type"] == "add_meeting"
    assert result["meeting_id"] in result["analytics_snapshot"]["event_id"]
    assert len(mongo.snapshots) == 1


def test_update_stage_snapshot_failure_returns_warning_without_blocking() -> None:
    mongo = FakeSnapshotMongo(_deal(deal_stage="proposal"), fail_snapshot=True)

    result = update_stage.handle(
        mongo=mongo,
        cfg={},
        deal_id="deal-1",
        new_stage="negotiation",
    )

    assert result["ok"] is True
    assert result["new_stage"] == "negotiation"
    assert mongo.saved is not None
    assert mongo.saved["deal_stage"] == "negotiation"
    assert result["analytics_snapshot"]["ok"] is False
    assert result["analytics_snapshot"]["warning"] == "analytics_snapshot_failed"
    assert result["analytics_snapshot"]["event_type"] == "update_stage"
    assert result["analytics_snapshot"]["message"] == "snapshot store unavailable"
    assert "update_stage:deal-1:negotiation:" in result["analytics_snapshot"]["event_id"]
