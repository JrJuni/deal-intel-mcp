from __future__ import annotations

import asyncio
import json
from copy import deepcopy
from datetime import date

import pytest

from deal_intel import _context, mcp_server
from deal_intel.errors import ErrorCode, MCPError, Stage
from deal_intel.schema.deal_review import build_deal_review
from deal_intel.tools import get_deal_review

AS_OF = date(2026, 6, 10)
MEDDPICC_DIMS = (
    "metrics",
    "economic_buyer",
    "decision_criteria",
    "decision_process",
    "identify_pain",
    "champion",
    "competition",
)


class FakeMongo:
    def __init__(self, deals: list[dict]) -> None:
        self.deals = deepcopy(deals)
        self.read_count = 0
        self.write_count = 0

    def list_deals_for_metrics(self) -> list[dict]:
        self.read_count += 1
        return deepcopy(self.deals)

    def upsert_deal(self, deal: dict) -> None:
        self.write_count += 1
        raise AssertionError("get_deal_review must be read-only")

    def get_deal(self, deal_id: str) -> dict | None:
        raise AssertionError("get_deal_review must not use raw get_deal")


class FailingMongo:
    def list_deals_for_metrics(self) -> list[dict]:
        raise RuntimeError("storage unavailable")


class PreflightFailingMongo:
    def list_deals_for_metrics(self) -> list[dict]:
        raise AssertionError("preflight should fail before storage")


def _snapshot(
    scores: dict[str, float],
    *,
    health_pct: float | None = None,
    gaps: list[str] | None = None,
) -> dict:
    snapshot = {
        dim: {"score": score, "trend": None}
        for dim, score in scores.items()
    }
    if health_pct is None:
        health_pct = round(sum(scores.values()) / (5 * len(MEDDPICC_DIMS)) * 100, 1)
    return {
        **snapshot,
        "filled_count": len(scores),
        "health_pct": health_pct,
        "gaps": gaps if gaps is not None else [
            dim for dim in MEDDPICC_DIMS if dim not in scores
        ],
    }


def _deal(
    deal_id: str = "deal-1",
    *,
    stage: str = "proposal",
    health_pct: float | None = 80,
    scores: dict[str, float] | None = None,
    gaps: list[str] | None = None,
    expected_close_date: str = "2026-06-30",
    expected_close_source: str = "user_provided",
    amount: int | None = 50_000_000,
    amount_status: str | None = "quoted",
) -> dict:
    if scores is None:
        scores = {dim: 4 for dim in MEDDPICC_DIMS}
    return {
        "deal_id": deal_id,
        "company": f"Company {deal_id}",
        "industry": "IT",
        "deal_stage": stage,
        "deal_size_krw": amount,
        "deal_size_status": amount_status,
        "expected_close_date": expected_close_date,
        "expected_close_date_source": expected_close_source,
        "stage_history": [
            {"stage": stage, "entered_at": "2026-06-01T00:00:00+00:00"}
        ],
        "meetings": [{"date": "2026-06-01", "raw_notes": "secret raw note"}],
        "contacts": [{"name": "secret contact"}],
        "summary_embedding": [0.1, 0.2],
        "meddpicc_latest": _snapshot(scores, health_pct=health_pct, gaps=gaps),
    }


def test_high_health_low_coverage_is_promising_but_unproven() -> None:
    review = build_deal_review(
        _deal(
            health_pct=86,
            scores={"metrics": 5, "identify_pain": 5},
        ),
        as_of=AS_OF,
    )

    interpretation = review["health_interpretation"]
    assert interpretation["legacy_health_pct"] == 86
    assert interpretation["evidence_coverage_pct"] == 28.6
    assert interpretation["uncertainty_level"] == "high"
    assert interpretation["review_band"] == "promising_but_unproven"
    assert interpretation["alert_level"] == "watch"
    assert "overconfidence_warning" in review["warnings"]
    assert review["missing_information"]
    assert any(item["status"] == "unknown" for item in review["scorecard"])
    payload = json.dumps(review, ensure_ascii=False)
    assert "probability_estimate" not in payload
    assert "65%" not in payload


def test_high_coverage_low_health_is_confirmed_alert() -> None:
    review = build_deal_review(
        _deal(
            health_pct=35,
            scores={dim: 1 for dim in MEDDPICC_DIMS},
            gaps=list(MEDDPICC_DIMS),
        ),
        as_of=AS_OF,
    )

    interpretation = review["health_interpretation"]
    assert interpretation["evidence_coverage_pct"] == 100.0
    assert interpretation["uncertainty_level"] == "low"
    assert interpretation["review_band"] == "confirmed_risk"
    assert interpretation["alert_level"] == "alert"
    assert any(risk["risk_id"] == "confirmed_meddpicc_risk" for risk in review["confirmed_risks"])
    assert "confirmed_risk_present" in review["warnings"]


def test_high_coverage_high_health_is_verified_healthy() -> None:
    review = build_deal_review(
        _deal(
            health_pct=88,
            scores={dim: 4.5 for dim in MEDDPICC_DIMS},
            gaps=[],
        ),
        as_of=AS_OF,
    )

    interpretation = review["health_interpretation"]
    assert interpretation["review_band"] == "verified_healthy"
    assert interpretation["alert_level"] == "none"
    assert interpretation["uncertainty_level"] == "low"
    assert not review["confirmed_risks"]
    assert review["known_signals"]


def test_low_coverage_low_health_prioritizes_missing_information() -> None:
    review = build_deal_review(
        _deal(
            health_pct=20,
            scores={"metrics": 1},
            gaps=["economic_buyer", "decision_criteria", "champion"],
        ),
        as_of=AS_OF,
    )

    interpretation = review["health_interpretation"]
    assert interpretation["review_band"] == "insufficient_evidence"
    assert interpretation["alert_level"] == "info"
    assert interpretation["uncertainty_level"] == "high"
    assert review["missing_information"]
    assert not any(
        risk["risk_id"] == "confirmed_meddpicc_risk"
        for risk in review["confirmed_risks"]
    )


def test_overdue_deal_separates_timing_risk_from_health() -> None:
    review = build_deal_review(
        _deal(
            health_pct=85,
            scores={"metrics": 5, "identify_pain": 5},
            expected_close_date="2026-06-01",
        ),
        as_of=AS_OF,
    )

    assert "overdue" in review["attention_reasons"]
    assert any(risk["risk_id"] == "timing:overdue" for risk in review["confirmed_risks"])
    assert review["health_interpretation"]["review_band"] == "promising_but_unproven"
    assert review["health_interpretation"]["alert_level"] == "watch"


def test_get_deal_review_tool_uses_restricted_read_path_and_excludes_sensitive_fields() -> None:
    mongo = FakeMongo([_deal("deal-1"), _deal("deal-2")])

    result = get_deal_review.handle(
        mongo=mongo,
        cfg={},
        deal_id="deal-1",
        as_of="2026-06-10",
    )

    assert result["ok"] is True
    assert result["as_of"] == "2026-06-10"
    assert result["review"]["deal_id"] == "deal-1"
    payload = json.dumps(result, ensure_ascii=False)
    assert "raw_notes" not in payload
    assert "secret raw note" not in payload
    assert "contacts" not in payload
    assert "summary_embedding" not in payload
    assert mongo.read_count == 1
    assert mongo.write_count == 0


def test_get_deal_review_mcp_wrapper_forwards_defaults(monkeypatch) -> None:
    mongo = FakeMongo([_deal("deal-1")])
    monkeypatch.setattr(_context, "mongo", lambda: mongo)
    monkeypatch.setattr(_context, "config", lambda: {})

    result = mcp_server.get_deal_review("deal-1", as_of="2026-06-10")

    assert result["ok"] is True
    assert result["review"]["deal_id"] == "deal-1"


def test_get_deal_review_rejects_invalid_inputs_before_storage() -> None:
    with pytest.raises(MCPError) as missing_id:
        get_deal_review.handle(
            mongo=PreflightFailingMongo(),
            cfg={},
            deal_id="",
            as_of="2026-06-10",
        )
    with pytest.raises(MCPError) as invalid_as_of:
        get_deal_review.handle(
            mongo=PreflightFailingMongo(),
            cfg={},
            deal_id="deal-1",
            as_of="not-a-date",
        )

    assert missing_id.value.error_code == ErrorCode.INVALID_INPUT
    assert missing_id.value.stage == Stage.PREFLIGHT
    assert invalid_as_of.value.error_code == ErrorCode.INVALID_INPUT
    assert invalid_as_of.value.stage == Stage.PREFLIGHT


def test_get_deal_review_storage_errors_and_not_found_are_structured() -> None:
    with pytest.raises(MCPError) as storage_error:
        get_deal_review.handle(
            mongo=FailingMongo(),
            cfg={},
            deal_id="deal-1",
            as_of="2026-06-10",
        )
    with pytest.raises(MCPError) as not_found:
        get_deal_review.handle(
            mongo=FakeMongo([_deal("other")]),
            cfg={},
            deal_id="deal-1",
            as_of="2026-06-10",
        )

    assert storage_error.value.error_code == ErrorCode.STORAGE_ERROR
    assert storage_error.value.retryable is True
    assert not_found.value.error_code == ErrorCode.NOT_FOUND
    assert not_found.value.retryable is False


def test_mcp_runtime_registers_get_deal_review() -> None:
    tools = asyncio.run(mcp_server.app.list_tools())
    names = sorted(tool.name for tool in tools)

    assert len(names) == 21
    assert "get_deal_review" in names
