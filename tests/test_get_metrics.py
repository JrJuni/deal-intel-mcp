from __future__ import annotations

import asyncio
from copy import deepcopy

import pytest

from deal_intel import _context, mcp_server
from deal_intel.errors import ErrorCode, MCPError
from deal_intel.tools import get_metrics


class FakeMongo:
    def __init__(self, deals: list[dict], snapshots: list[dict] | None = None) -> None:
        self.deals = deepcopy(deals)
        self.snapshots = deepcopy(snapshots or [])
        self.read_count = 0
        self.snapshot_read_count = 0
        self.snapshot_query: dict | None = None

    def list_deals_for_metrics(self) -> list[dict]:
        self.read_count += 1
        return deepcopy(self.deals)

    def list_analytics_snapshots(
        self,
        *,
        start_date: str,
        end_date: str,
        stage: str | None = None,
        industry: str | None = None,
    ) -> list[dict]:
        self.snapshot_read_count += 1
        self.snapshot_query = {
            "start_date": start_date,
            "end_date": end_date,
            "stage": stage,
            "industry": industry,
        }
        return deepcopy(self.snapshots)

    def _get_db(self) -> None:
        raise AssertionError("get_metrics should use the metrics read path")


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
    stage: str = "discovery",
    industry: str = "IT",
    amount: int | None = 10_000_000,
    amount_status: str | None = "quoted",
    health_pct: float | None = 80,
) -> dict:
    return {
        "deal_id": deal_id,
        "company": f"Company {deal_id}",
        "industry": industry,
        "deal_stage": stage,
        "deal_size_amount": amount,
        "deal_size_status": amount_status,
        "stage_history": [
            {
                "stage": stage,
                "entered_at": "2026-06-01T00:00:00+00:00",
            }
        ],
        "expected_close_date": "2026-06-30",
        "expected_close_date_source": "user_provided",
        "actual_close_date": None,
        "close_reason": None,
        "meetings": [{"date": "2026-06-01"}],
        "meddpicc_latest": (
            {"filled_count": 1, "health_pct": health_pct}
            if health_pct is not None
            else {}
        ),
    }


def _snapshot(
    event_id: str,
    deal_id: str,
    as_of: str,
    *,
    stage: str = "discovery",
    industry: str = "IT",
    amount: int | None = 10,
    health_pct: float | None = 80,
) -> dict:
    return {
        "event_id": event_id,
        "deal_id": deal_id,
        "as_of": as_of,
        "occurred_at": f"{as_of}T00:00:00+00:00",
        "industry": industry,
        "deal_stage": stage,
        "deal_size_amount": amount,
        "health_pct": health_pct,
        "attention_reasons": [],
    }


def test_get_metrics_pipeline_health_returns_kpis_and_filters() -> None:
    mongo = FakeMongo(
        [
            _deal("it-discovery", stage="discovery", industry="IT", amount=10),
            _deal("finance-discovery", stage="discovery", industry="Finance", amount=20),
            _deal("it-proposal", stage="proposal", industry="IT", amount=30),
        ]
    )

    result = get_metrics.handle(
        mongo=mongo,
        cfg={},
        metric_type="pipeline_health",
        stage="discovery",
        industry="IT",
        as_of="2026-06-09",
    )

    assert result["ok"] is True
    assert result["metric_type"] == "pipeline_health"
    assert result["as_of"] == "2026-06-09"
    assert result["filters"] == {"stage": "discovery", "industry": "IT"}
    assert result["kpis"]["deal_count"] == 1
    assert result["kpis"]["open_pipeline_value_amount"] == 10
    assert result["stage_breakdown"][0]["stage"] == "discovery"
    assert result["stage_breakdown"][0]["count"] == 1
    assert "pipeline_values" in result
    assert "data_quality" in result
    assert mongo.read_count == 1


def test_get_metrics_mcp_wrapper_forwards_defaults(monkeypatch) -> None:
    mongo = FakeMongo([_deal("deal-1")])
    monkeypatch.setattr(_context, "mongo", lambda: mongo)
    monkeypatch.setattr(_context, "config", lambda: {})

    result = mcp_server.get_metrics(as_of="2026-06-09")

    assert result["ok"] is True
    assert result["metric_type"] == "pipeline_health"
    assert result["filters"] == {"stage": None, "industry": None}
    assert result["kpis"]["deal_count"] == 1


def test_get_metrics_pipeline_trend_uses_snapshot_read_path() -> None:
    mongo = FakeMongo(
        [],
        snapshots=[
            _snapshot("e1", "deal-1", "2026-06-02", amount=10, health_pct=50),
            _snapshot("e2", "deal-1", "2026-06-09", amount=20, health_pct=80),
        ],
    )

    result = get_metrics.handle(
        mongo=mongo,
        cfg={},
        metric_type="pipeline_trend",
        stage="discovery",
        industry="IT",
        as_of="2026-06-09",
        lookback_days=7,
    )

    assert result["ok"] is True
    assert result["metric_type"] == "pipeline_trend"
    assert result["window"] == {
        "lookback_days": 7,
        "start_date": "2026-06-02",
        "end_date": "2026-06-09",
    }
    assert result["delta"]["open_pipeline_value_amount"] == 10.0
    assert mongo.read_count == 0
    assert mongo.snapshot_read_count == 1
    assert mongo.snapshot_query == {
        "start_date": "2026-06-02",
        "end_date": "2026-06-09",
        "stage": "discovery",
        "industry": "IT",
    }


def test_get_metrics_pipeline_health_ignores_trend_lookback_days() -> None:
    mongo = FakeMongo([_deal("deal-1")])

    result = get_metrics.handle(
        mongo=mongo,
        cfg={},
        metric_type="pipeline_health",
        as_of="2026-06-09",
        lookback_days=0,
    )

    assert result["ok"] is True
    assert result["metric_type"] == "pipeline_health"
    assert mongo.read_count == 1
    assert mongo.snapshot_read_count == 0


def test_get_metrics_rejects_unknown_metric_type_and_stage_before_storage() -> None:
    with pytest.raises(MCPError) as invalid_metric:
        get_metrics.handle(
            mongo=FailingMongo(),
            cfg={},
            metric_type="win_rate",
            as_of="2026-06-09",
        )
    with pytest.raises(MCPError) as invalid_stage:
        get_metrics.handle(
            mongo=FailingMongo(),
            cfg={},
            metric_type="pipeline_health",
            stage="not-a-stage",
            as_of="2026-06-09",
        )

    assert invalid_metric.value.error_code == ErrorCode.INVALID_INPUT
    assert invalid_metric.value.hint == {
        "valid_metric_types": ["pipeline_health", "pipeline_trend"]
    }
    assert invalid_stage.value.error_code == ErrorCode.INVALID_INPUT


def test_get_metrics_preflight_config_as_of_and_lookback_errors_before_storage() -> None:
    with pytest.raises(MCPError) as invalid_config:
        get_metrics.handle(
            mongo=FailingMongo(),
            cfg={"metrics": {"health_bands": {"healthy_min": 40, "watch_min": 70}}},
            metric_type="pipeline_health",
            as_of="2026-06-09",
        )
    with pytest.raises(MCPError) as invalid_as_of:
        get_metrics.handle(
            mongo=FailingMongo(),
            cfg={},
            metric_type="pipeline_health",
            as_of="not-a-date",
        )
    with pytest.raises(MCPError) as invalid_lookback:
        get_metrics.handle(
            mongo=FailingMongo(),
            cfg={},
            metric_type="pipeline_trend",
            as_of="2026-06-09",
            lookback_days=0,
        )

    assert invalid_config.value.error_code == ErrorCode.CONFIG_ERROR
    assert invalid_as_of.value.error_code == ErrorCode.INVALID_INPUT
    assert invalid_lookback.value.error_code == ErrorCode.INVALID_INPUT


def test_mcp_runtime_registers_get_metrics() -> None:
    tools = asyncio.run(mcp_server.app.list_tools())
    names = sorted(tool.name for tool in tools)

    assert "get_metrics" in names
