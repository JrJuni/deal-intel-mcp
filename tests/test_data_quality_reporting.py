from __future__ import annotations

from copy import deepcopy
from datetime import UTC, date, datetime

import pytest

from deal_intel import _context, mcp_server
from deal_intel.errors import ErrorCode, MCPError
from deal_intel.schema.metrics import (
    DataQualityStatus,
    ReportingContext,
    assess_deal_data_quality,
    summarize_data_quality,
)
from deal_intel.schema.qualification import compute_qualification_latest
from deal_intel.schema.qualification_framework import get_qualification_template
from deal_intel.storage.mongodb import MongoDBClient
from deal_intel.tools import get_insights, list_deals


def _deal(*, stage: str = "discovery") -> dict:
    deal = {
        "deal_id": "deal-1",
        "company": "Test Co",
        "industry": "IT",
        "deal_stage": stage,
        "stage_history": [
            {
                "stage": stage,
                "entered_at": "2026-06-01T00:00:00+00:00",
            }
        ],
        "expected_close_date": "2026-06-30",
        "expected_close_date_source": "config_default",
        "deal_size_amount": 10_000_000,
        "deal_size_status": "rough_estimate",
        "meetings": [],
        "meddpicc_latest": {},
        "actual_close_date": None,
        "close_reason": None,
    }
    if stage in {"won", "lost"}:
        deal["expected_close_date"] = None
        deal["expected_close_date_source"] = None
        deal["deal_size_amount"] = None
        deal["deal_size_status"] = None
        deal["meetings"] = [{"date": "2026-05-20"}]
        deal["meddpicc_latest"] = {"filled_count": 1, "health_pct": 80}
    return deal


class FakeMongo:
    def __init__(self, deals: list[dict]) -> None:
        self.deals = deepcopy(deals)

    def list_deals(self, *, stage: str | None = None, limit: int = 50) -> list[dict]:
        return [
            deepcopy(deal)
            for deal in self.deals
            if stage is None or deal.get("deal_stage") == stage
        ][:limit]


def test_reporting_context_uses_configured_business_timezone() -> None:
    context = ReportingContext.from_config(
        {"reporting": {"timezone": "Asia/Seoul"}},
        generated_at=datetime(2026, 6, 7, 16, tzinfo=UTC),
    )

    assert context.as_of == date(2026, 6, 8)
    assert context.timezone == "Asia/Seoul"
    assert context.generated_at == datetime(2026, 6, 7, 16, tzinfo=UTC)


def test_reporting_context_accepts_explicit_as_of_and_rejects_bad_inputs() -> None:
    context = ReportingContext.from_config({}, as_of="2026-05-31")

    assert context.as_of == date(2026, 5, 31)
    with pytest.raises(ValueError, match="as_of"):
        ReportingContext.from_config({}, as_of="05/31/2026")
    with pytest.raises(ValueError, match="IANA timezone"):
        ReportingContext.from_config({"reporting": {"timezone": "Moon/Base"}})


def test_open_deal_distinguishes_estimated_from_confirmed_coverage() -> None:
    result = assess_deal_data_quality(_deal())

    assert result.field_statuses["expected_close_date"] == DataQualityStatus.ESTIMATED
    assert result.field_statuses["deal_value"] == DataQualityStatus.ESTIMATED
    assert result.field_statuses["meetings"] == DataQualityStatus.NOT_APPLICABLE
    assert result.field_statuses["actual_close_date"] == DataQualityStatus.NOT_APPLICABLE
    assert result.is_complete is True
    assert result.is_confirmed_complete is False
    assert result.coverage_pct == 100.0
    assert result.confirmed_coverage_pct == 66.7


def test_qualified_deal_requires_meeting_and_health_assessment() -> None:
    deal = _deal(stage="qualification")

    result = assess_deal_data_quality(deal)

    assert result.field_statuses["meetings"] == DataQualityStatus.MISSING
    assert result.field_statuses["health_assessment"] == DataQualityStatus.MISSING
    assert result.is_complete is False


def test_qualified_deal_accepts_canonical_interaction_as_meeting_evidence() -> None:
    deal = _deal(stage="qualification")
    deal["interactions"] = [
        {
            "interaction_id": "i1",
            "date": "2026-06-10",
            "interaction_type": "user_interview",
            "source_confidence": "customer_stated",
        }
    ]

    result = assess_deal_data_quality(deal)

    assert result.field_statuses["meetings"] == DataQualityStatus.VALID


def test_terminal_quality_requires_actual_close_and_lost_reason() -> None:
    won = assess_deal_data_quality(_deal(stage="won"))
    lost = assess_deal_data_quality(_deal(stage="lost"))

    assert won.field_statuses["actual_close_date"] == DataQualityStatus.MISSING
    assert won.field_statuses["close_reason"] == DataQualityStatus.NOT_APPLICABLE
    assert lost.field_statuses["actual_close_date"] == DataQualityStatus.MISSING
    assert lost.field_statuses["close_reason"] == DataQualityStatus.MISSING


def test_data_quality_summary_preserves_field_denominators() -> None:
    confirmed = _deal()
    confirmed["expected_close_date_source"] = "user_provided"
    confirmed["deal_size_status"] = "quoted"

    result = summarize_data_quality([_deal(), confirmed])

    assert result["deal_count"] == 2
    assert result["complete_deal_count"] == 2
    assert result["confirmed_complete_deal_count"] == 1
    assert result["field_coverage"]["expected_close_date"]["estimated"] == 1
    assert result["field_coverage"]["expected_close_date"]["valid"] == 1
    assert result["field_coverage"]["actual_close_date"]["applicable_count"] == 0
    assert result["field_coverage"]["actual_close_date"]["coverage_pct"] is None


def test_list_deals_returns_reporting_context_and_quality() -> None:
    result = list_deals.handle(
        mongo=FakeMongo([_deal()]),
        cfg={"reporting": {"timezone": "Asia/Seoul"}},
        stage=None,
        limit=20,
        as_of="2026-06-08",
    )

    assert result["as_of"] == "2026-06-08"
    assert result["timezone"] == "Asia/Seoul"
    assert result["generated_at"].endswith("+00:00")
    assert result["data_quality"]["deal_count"] == 1
    assert result["deals"][0]["data_quality"]["estimated_fields"] == [
        "expected_close_date",
        "deal_value",
    ]


def test_list_deals_uses_active_qualification_snapshot_for_health() -> None:
    framework = get_qualification_template("simple_b2b")
    deal = _deal(stage="proposal")
    deal["meddpicc_latest"] = {}
    deal["meetings"] = [{"date": "2026-06-01"}]
    deal["qualification_latest"] = compute_qualification_latest(
        [
            {
                "qualification": {
                    "business_need": {"score": 5},
                    "buyer_owner": {"score": 2},
                }
            }
        ],
        framework=framework,
        evidence_fields=("qualification",),
        deal_stage="proposal",
    )

    result = list_deals.handle(
        mongo=FakeMongo([deal]),
        cfg={},
        stage=None,
        limit=20,
        as_of="2026-06-08",
    )

    row = result["deals"][0]
    assert row["qualification"]["framework_key"] == "simple_b2b"
    assert row["qualification_source_field"] == "qualification_latest"
    assert row["health_pct"] == deal["qualification_latest"]["health_pct"]
    assert row["filled_count"] == 2
    assert row["gaps"] == ["next_step"]
    assert row["qualification_gaps"] == ["next_step"]
    assert row["data_quality"]["field_statuses"]["health_assessment"] == "valid"


def test_list_deals_rejects_invalid_as_of_as_input_error() -> None:
    class FailingMongo:
        def list_deals(self, *, stage: str | None = None, limit: int = 50) -> list[dict]:
            raise AssertionError("invalid input should fail before storage access")

    with pytest.raises(MCPError) as exc_info:
        list_deals.handle(
            mongo=FailingMongo(),
            cfg={},
            stage=None,
            limit=20,
            as_of="not-a-date",
        )

    assert exc_info.value.error_code == ErrorCode.INVALID_INPUT


def test_get_insights_and_mcp_forward_reporting_context(monkeypatch) -> None:
    class FakeInsightMongo:
        def list_deals_for_metrics(self) -> list[dict]:
            open_deal = _deal()
            won_deal = _deal(stage="won")
            won_deal["deal_size_amount"] = 99_000_000
            won_deal["deal_size_status"] = "quoted"
            won_deal["actual_close_date"] = "2026-06-01"
            return [open_deal, won_deal]

        def _get_db(self) -> None:
            raise AssertionError("pipeline_overview should use metrics read path")

    mongo = FakeInsightMongo()
    direct = get_insights.handle(
        mongo=mongo,
        cfg={},
        query_type="pipeline_overview",
        as_of="2026-06-08",
    )
    monkeypatch.setattr(_context, "mongo", lambda: mongo)
    monkeypatch.setattr(_context, "config", lambda: {})
    via_mcp = mcp_server.get_insights("pipeline_overview", as_of="2026-06-08")

    assert direct["as_of"] == "2026-06-08"
    assert direct["timezone"] == "Asia/Seoul"
    assert direct["total_deals"] == 2
    assert direct["total_size_amount"] == 10_000_000
    assert direct["total_size_currency"] == "KRW"
    assert direct["mixed_total_size_currency"] is False
    assert direct["kpis"]["open_pipeline_value_amount"] == 10_000_000
    assert "stage_breakdown" in direct
    assert "pipeline_values" in direct
    assert via_mcp["ok"] is True
    assert via_mcp["as_of"] == "2026-06-08"


def test_get_insights_pipeline_overview_uses_active_qualification_snapshot() -> None:
    framework = get_qualification_template("simple_b2b")
    deal = _deal(stage="proposal")
    deal["meddpicc_latest"] = {"filled_count": 1, "health_pct": 95}
    deal["qualification_latest"] = compute_qualification_latest(
        [{"qualification": {"business_need": {"score": 1}}}],
        framework=framework,
        evidence_fields=("qualification",),
        deal_stage="proposal",
    )

    class FakeInsightMongo:
        def list_deals_for_metrics(self) -> list[dict]:
            return [deepcopy(deal)]

        def _get_db(self) -> None:
            raise AssertionError("pipeline_overview should use metrics read path")

    result = get_insights.handle(
        mongo=FakeInsightMongo(),
        cfg={},
        query_type="pipeline_overview",
        as_of="2026-06-08",
    )

    expected_health = deal["qualification_latest"]["health_pct"]
    assert result["kpis"]["avg_health_pct"] == expected_health
    assert result["health_bands"]["at_risk"] == 1
    proposal = next(
        row for row in result["stage_breakdown"] if row["stage"] == "proposal"
    )
    assert proposal["avg_health_pct"] == expected_health


def test_get_insights_legacy_modes_self_label_meddpicc_scope() -> None:
    class FakeCollection:
        def aggregate(self, _pipeline):
            return [
                {
                    "_id": None,
                    "count": 1,
                    "avg_health_pct": 80.0,
                    "metrics": 4.0,
                }
            ]

    class FakeDB:
        deals = FakeCollection()

    class FakeInsightMongo:
        def _get_db(self):
            return FakeDB()

    result = get_insights.handle(
        mongo=FakeInsightMongo(),
        cfg={},
        query_type="win_patterns",
        as_of="2026-06-08",
    )

    assert result["ok"] is True
    assert result["framework_scope"] == "meddpicc_legacy"
    assert "MEDDPICC compatibility fields" in result["compatibility_note"]
    assert "meddpicc_legacy_insight" in result["warnings"]


def test_get_insights_pipeline_overview_does_not_mark_legacy_scope() -> None:
    class FakeInsightMongo:
        def list_deals_for_metrics(self) -> list[dict]:
            return [_deal()]

        def _get_db(self) -> None:
            raise AssertionError("pipeline_overview should use metrics read path")

    result = get_insights.handle(
        mongo=FakeInsightMongo(),
        cfg={},
        query_type="pipeline_overview",
        as_of="2026-06-08",
    )

    assert "framework_scope" not in result
    assert "compatibility_note" not in result


def test_get_insights_preflight_errors_happen_before_storage() -> None:
    class FailingMongo:
        def list_deals_for_metrics(self) -> list[dict]:
            raise AssertionError("preflight should fail before storage")

        def _get_db(self) -> None:
            raise AssertionError("preflight should fail before storage")

    with pytest.raises(MCPError) as invalid_config:
        get_insights.handle(
            mongo=FailingMongo(),
            cfg={"metrics": {"health_bands": {"healthy_min": 40, "watch_min": 70}}},
            query_type="pipeline_overview",
            as_of="2026-06-08",
        )
    with pytest.raises(MCPError) as invalid_as_of:
        get_insights.handle(
            mongo=FailingMongo(),
            cfg={},
            query_type="pipeline_overview",
            as_of="not-a-date",
        )

    assert invalid_config.value.error_code == ErrorCode.CONFIG_ERROR
    assert invalid_as_of.value.error_code == ErrorCode.INVALID_INPUT


def test_metrics_read_path_excludes_raw_notes_contacts_and_vectors() -> None:
    class FakeCollection:
        query: dict | None = None
        projection: dict | None = None

        def find(self, query: dict, projection: dict) -> list[dict]:
            self.query = query
            self.projection = projection
            return [{"deal_id": "deal-1"}]

    class FakeDatabase:
        def __init__(self) -> None:
            self.deals = FakeCollection()

    db = FakeDatabase()
    client = MongoDBClient(uri="mongodb://unused")
    client._db = db

    result = client.list_deals_for_metrics()

    assert result == [{"deal_id": "deal-1"}]
    assert db.deals.query == {"archived": {"$ne": True}}
    assert db.deals.projection == {
        "_id": 0,
        "meetings.raw_notes": 0,
        "interactions.raw_content": 0,
        "contacts": 0,
        "summary_embedding": 0,
    }
