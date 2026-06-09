from __future__ import annotations

import asyncio
from copy import deepcopy

import pytest

from deal_intel import _context, mcp_server
from deal_intel.errors import ErrorCode, MCPError
from deal_intel.tools import get_metrics


class FakeMongo:
    def __init__(self, deals: list[dict]) -> None:
        self.deals = deepcopy(deals)
        self.read_count = 0

    def list_deals_for_metrics(self) -> list[dict]:
        self.read_count += 1
        return deepcopy(self.deals)

    def _get_db(self) -> None:
        raise AssertionError("get_metrics should use the metrics read path")


class FailingMongo:
    def list_deals_for_metrics(self) -> list[dict]:
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
        "deal_size_krw": amount,
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
    assert result["kpis"]["open_pipeline_value_krw"] == 10
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
    assert invalid_metric.value.hint == {"valid_metric_types": ["pipeline_health"]}
    assert invalid_stage.value.error_code == ErrorCode.INVALID_INPUT


def test_get_metrics_preflight_config_and_as_of_errors_before_storage() -> None:
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

    assert invalid_config.value.error_code == ErrorCode.CONFIG_ERROR
    assert invalid_as_of.value.error_code == ErrorCode.INVALID_INPUT


def test_mcp_runtime_registers_get_metrics() -> None:
    tools = asyncio.run(mcp_server.app.list_tools())
    names = sorted(tool.name for tool in tools)

    assert len(names) == 16
    assert "get_metrics" in names
