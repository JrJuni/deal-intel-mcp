from __future__ import annotations

import asyncio
import csv
from copy import deepcopy
from pathlib import Path

import pytest

from deal_intel import _context, mcp_server
from deal_intel.errors import ErrorCode, MCPError
from deal_intel.tools import export_report


class FakeMongo:
    def __init__(self, deals: list[dict]) -> None:
        self.deals = deepcopy(deals)
        self.read_count = 0

    def list_deals_for_metrics(self) -> list[dict]:
        self.read_count += 1
        return deepcopy(self.deals)

    def _get_db(self) -> None:
        raise AssertionError("export_report should use the metrics read path")


class FakeTrendMongo:
    def __init__(self, snapshots: list[dict]) -> None:
        self.snapshots = deepcopy(snapshots)
        self.snapshot_read_args: dict | None = None

    def list_deals_for_metrics(self) -> list[dict]:
        raise AssertionError("pipeline_trend should use the snapshot read path")

    def list_analytics_snapshots(
        self,
        *,
        start_date: str,
        end_date: str,
        stage: str | None = None,
        industry: str | None = None,
    ) -> list[dict]:
        self.snapshot_read_args = {
            "start_date": start_date,
            "end_date": end_date,
            "stage": stage,
            "industry": industry,
        }
        return deepcopy(self.snapshots)

    def _get_db(self) -> None:
        raise AssertionError("export_report should use the snapshot read path")


class FailingMongo:
    def list_deals_for_metrics(self) -> list[dict]:
        raise AssertionError("preflight should fail before storage")

    def list_analytics_snapshots(self, **_kwargs) -> list[dict]:
        raise AssertionError("preflight should fail before storage")

    def _get_db(self) -> None:
        raise AssertionError("preflight should fail before storage")


def _deal(
    deal_id: str,
    *,
    company: str,
    stage: str = "proposal",
    industry: str = "IT",
    amount: int | None = 10_000_000,
    amount_status: str | None = "quoted",
    health_pct: float | None = 80,
    expected_close_date: str | None = "2026-06-30",
) -> dict:
    return {
        "deal_id": deal_id,
        "company": company,
        "industry": industry,
        "deal_stage": stage,
        "deal_size_krw": amount,
        "deal_size_status": amount_status,
        "stage_history": [
            {
                "stage": stage,
                "entered_at": "2026-06-01T00:00:00+00:00",
            }
        ],
        "expected_close_date": expected_close_date,
        "expected_close_date_source": "user_provided",
        "meetings": [{"meeting_id": f"m-{deal_id}", "date": "2026-06-01"}],
        "customer_themes": [
            {
                "theme_key": "operational_efficiency",
                "label": "Operational efficiency",
                "dimension": "identify_pain",
                "evidence": "manual report takes too long",
                "importance": 4,
                "meeting_id": f"m-{deal_id}",
                "meeting_date": "2026-06-01",
            },
            {
                "theme_key": "integration_migration",
                "label": "Integration and migration",
                "dimension": "decision_criteria",
                "evidence": "GitHub and Jira integration required",
                "importance": 5,
                "meeting_id": f"m-{deal_id}",
                "meeting_date": "2026-06-01",
            },
        ],
        "contacts": [{"name": "secret"}],
        "summary_embedding": [0.1, 0.2],
        "meddpicc_latest": (
            {
                "filled_count": 1,
                "health_pct": health_pct,
                "gaps": ["economic_buyer"],
            }
            if health_pct is not None
            else {}
        ),
    }


def test_export_report_writes_weekly_pipeline_csv_and_markdown(tmp_path) -> None:
    mongo = FakeMongo(
        [
            _deal(
                "overdue",
                company="PayBridge",
                amount=72_000_000,
                expected_close_date="2026-06-01",
            ),
            _deal(
                "filtered",
                company="OtherIndustry",
                industry="Finance",
                amount=30_000_000,
            ),
            _deal(
                "won",
                company="Terminal",
                stage="won",
                amount=100_000_000,
            ),
        ]
    )

    result = export_report.handle(
        mongo=mongo,
        cfg={"reporting": {"output_dir": str(tmp_path)}},
        report_type="weekly_pipeline",
        stage="proposal",
        industry="IT",
        as_of="2026-06-10",
    )

    assert result["ok"] is True
    assert result["report_type"] == "weekly_pipeline"
    assert result["as_of"] == "2026-06-10"
    assert result["filters"] == {"stage": "proposal", "industry": "IT"}
    assert result["row_count"] == 1
    assert result["metrics"]["pipeline_value_krw"] == 72_000_000
    assert result["metrics"]["attention_deal_count"] == 1
    assert result["output_dir"] == str(tmp_path.resolve())
    assert result["csv_path"] == result["artifacts"]["csv"]["path"]
    assert result["markdown_path"] == result["artifacts"]["markdown"]["path"]
    assert mongo.read_count == 1

    csv_path = Path(result["csv_path"])
    markdown_path = Path(result["markdown_path"])
    assert csv_path.is_absolute()
    assert markdown_path.is_absolute()
    assert csv_path.exists()
    assert markdown_path.exists()
    assert csv_path.name.startswith("weekly_pipeline_")
    assert markdown_path.name.startswith("weekly_pipeline_")
    assert csv_path.suffix == ".csv"
    assert markdown_path.suffix == ".md"
    assert csv_path.read_bytes().startswith(b"\xef\xbb\xbf")
    assert "Weekly Pipeline Report" in markdown_path.read_text(encoding="utf-8")

    with csv_path.open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    assert len(rows) == result["row_count"]
    assert rows[0]["company"] == "PayBridge"
    payload = csv_path.read_text(encoding="utf-8-sig")
    assert "secret" not in payload
    assert "summary_embedding" not in payload


def test_export_report_writes_pipeline_trend_csv_and_markdown(tmp_path) -> None:
    mongo = FakeTrendMongo(
        [
            {
                "event_id": "start-a",
                "as_of": "2026-06-03",
                "occurred_at": "2026-06-03T00:00:00+00:00",
                "deal_id": "deal-a",
                "company": "Alpha",
                "industry": "IT",
                "deal_stage": "proposal",
                "deal_size_krw": 100_000_000,
                "health_pct": 70,
                "attention_reasons": [],
            },
            {
                "event_id": "end-a",
                "as_of": "2026-06-10",
                "occurred_at": "2026-06-10T00:00:00+00:00",
                "deal_id": "deal-a",
                "company": "Alpha",
                "industry": "IT",
                "deal_stage": "negotiation",
                "deal_size_krw": 120_000_000,
                "health_pct": 80,
                "attention_reasons": ["overdue"],
            },
            {
                "event_id": "end-b",
                "as_of": "2026-06-10",
                "occurred_at": "2026-06-10T00:00:00+00:00",
                "deal_id": "deal-b",
                "company": "Beta",
                "industry": "IT",
                "deal_stage": "discovery",
                "deal_size_krw": 50_000_000,
                "health_pct": 60,
                "attention_reasons": [],
            },
        ]
    )

    result = export_report.handle(
        mongo=mongo,
        cfg={"reporting": {"output_dir": str(tmp_path)}},
        report_type="pipeline_trend",
        stage="proposal",
        industry="IT",
        as_of="2026-06-10",
        lookback_days=7,
    )

    assert result["ok"] is True
    assert result["report_type"] == "pipeline_trend"
    assert result["window"] == {
        "lookback_days": 7,
        "start_date": "2026-06-03",
        "end_date": "2026-06-10",
    }
    assert result["filters"] == {"stage": "proposal", "industry": "IT"}
    assert mongo.snapshot_read_args == {
        "start_date": "2026-06-03",
        "end_date": "2026-06-10",
        "stage": "proposal",
        "industry": "IT",
    }
    assert result["metrics"]["start"]["open_pipeline_value_krw"] == 100_000_000
    assert result["metrics"]["end"]["open_pipeline_value_krw"] == 100_000_000
    assert result["metrics"]["delta"]["active_deal_count"] == 0
    assert result["row_count"] >= 7

    csv_path = Path(result["csv_path"])
    markdown_path = Path(result["markdown_path"])
    assert csv_path.name.startswith("pipeline_trend_")
    assert markdown_path.name.startswith("pipeline_trend_")
    assert csv_path.read_bytes().startswith(b"\xef\xbb\xbf")
    assert "Pipeline Trend Report" in markdown_path.read_text(encoding="utf-8")

    with csv_path.open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    open_value = next(
        row for row in rows if row["item"] == "open_pipeline_value_krw"
    )
    assert open_value["start_value"] == "100000000"
    assert open_value["end_value"] == "100000000"


def test_export_report_mcp_wrapper_forwards_to_handler(monkeypatch, tmp_path) -> None:
    mongo = FakeMongo([_deal("deal-1", company="PublicCo")])
    monkeypatch.setattr(_context, "mongo", lambda: mongo)
    monkeypatch.setattr(
        _context,
        "config",
        lambda: {"reporting": {"output_dir": str(tmp_path)}},
    )

    result = mcp_server.export_report(as_of="2026-06-10")

    assert result["ok"] is True
    assert result["report_type"] == "weekly_pipeline"
    assert Path(result["csv_path"]).exists()
    assert Path(result["markdown_path"]).exists()


def test_export_report_mcp_wrapper_forwards_pipeline_trend(
    monkeypatch,
    tmp_path,
) -> None:
    mongo = FakeTrendMongo([])
    monkeypatch.setattr(_context, "mongo", lambda: mongo)
    monkeypatch.setattr(
        _context,
        "config",
        lambda: {"reporting": {"output_dir": str(tmp_path)}},
    )

    result = mcp_server.export_report(
        report_type="pipeline_trend",
        as_of="2026-06-10",
        lookback_days=14,
    )

    assert result["ok"] is True
    assert result["report_type"] == "pipeline_trend"
    assert result["window"]["lookback_days"] == 14
    assert Path(result["csv_path"]).exists()
    assert Path(result["markdown_path"]).exists()


def test_export_report_rejects_invalid_inputs_before_storage(tmp_path) -> None:
    with pytest.raises(MCPError) as invalid_report_type:
        export_report.handle(
            mongo=FailingMongo(),
            cfg={"reporting": {"output_dir": str(tmp_path)}},
            report_type="customer_themes",
            as_of="2026-06-10",
        )
    with pytest.raises(MCPError) as invalid_stage:
        export_report.handle(
            mongo=FailingMongo(),
            cfg={"reporting": {"output_dir": str(tmp_path)}},
            report_type="weekly_pipeline",
            stage="not-a-stage",
            as_of="2026-06-10",
        )
    with pytest.raises(MCPError) as invalid_as_of:
        export_report.handle(
            mongo=FailingMongo(),
            cfg={"reporting": {"output_dir": str(tmp_path)}},
            report_type="weekly_pipeline",
            as_of="not-a-date",
        )
    with pytest.raises(MCPError) as invalid_lookback:
        export_report.handle(
            mongo=FailingMongo(),
            cfg={"reporting": {"output_dir": str(tmp_path)}},
            report_type="pipeline_trend",
            as_of="2026-06-10",
            lookback_days=0,
        )

    assert invalid_report_type.value.error_code == ErrorCode.INVALID_INPUT
    assert invalid_report_type.value.hint == {
        "valid_report_types": ["pipeline_trend", "weekly_pipeline"]
    }
    assert invalid_stage.value.error_code == ErrorCode.INVALID_INPUT
    assert invalid_as_of.value.error_code == ErrorCode.INVALID_INPUT
    assert invalid_lookback.value.error_code == ErrorCode.INVALID_INPUT


def test_export_report_returns_io_error_when_artifact_write_fails(tmp_path) -> None:
    output_file = tmp_path / "not-a-directory"
    output_file.write_text("occupied", encoding="utf-8")

    with pytest.raises(MCPError) as exc_info:
        export_report.handle(
            mongo=FakeMongo([_deal("deal-1", company="PublicCo")]),
            cfg={},
            report_type="weekly_pipeline",
            output_dir=str(output_file),
            as_of="2026-06-10",
        )

    assert exc_info.value.error_code == ErrorCode.IO_ERROR
    assert exc_info.value.stage == "storage"
    assert exc_info.value.hint == {"output_dir": str(output_file)}


def test_mcp_runtime_registers_export_report() -> None:
    tools = asyncio.run(mcp_server.app.list_tools())
    names = sorted(tool.name for tool in tools)

    assert len(names) == 22
    assert "export_report" in names
