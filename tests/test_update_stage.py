from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from deal_intel import _context, mcp_server
from deal_intel.errors import ErrorCode, MCPError, Stage
from deal_intel.tools import update_stage


class FakeMongo:
    def __init__(self, deal: dict | None) -> None:
        self.deal = deepcopy(deal)
        self.saved: dict | None = None

    def get_deal(self, deal_id: str) -> dict | None:
        if self.deal is None or self.deal.get("deal_id") != deal_id:
            return None
        return deepcopy(self.deal)

    def upsert_deal(self, deal: dict) -> None:
        self.saved = deepcopy(deal)


def _deal(*, stage: str = "negotiation", actual_close_date: str | None = None) -> dict:
    return {
        "deal_id": "deal-1",
        "company": "Test Co",
        "deal_stage": stage,
        "actual_close_date": actual_close_date,
        "meetings": [],
        "stage_history": [
            {
                "stage": stage,
                "entered_at": "2026-05-01T00:00:00+00:00",
            }
        ],
    }


def test_terminal_stage_stores_explicit_actual_close_date() -> None:
    mongo = FakeMongo(_deal())

    result = update_stage.handle(
        mongo=mongo,
        cfg={},
        deal_id="deal-1",
        new_stage="won",
        actual_close_date="2026-06-02",
    )

    assert result["actual_close_date"] == "2026-06-02"
    assert mongo.saved is not None
    assert mongo.saved["deal_stage"] == "won"
    assert mongo.saved["actual_close_date"] == "2026-06-02"
    assert mongo.saved["stage_history"][-1]["stage"] == "won"
    assert result["stuck_threshold_days"] is None


def test_terminal_stage_defaults_actual_close_date_to_processing_day() -> None:
    mongo = FakeMongo(_deal())
    dates_around_call = {datetime.now(ZoneInfo("Asia/Seoul")).date().isoformat()}

    result = update_stage.handle(
        mongo=mongo,
        cfg={},
        deal_id="deal-1",
        new_stage="lost",
    )
    dates_around_call.add(datetime.now(ZoneInfo("Asia/Seoul")).date().isoformat())

    assert result["actual_close_date"] in dates_around_call
    assert mongo.saved is not None
    assert mongo.saved["actual_close_date"] == result["actual_close_date"]


def test_reopening_a_terminal_deal_clears_actual_close_date() -> None:
    mongo = FakeMongo(_deal(stage="won", actual_close_date="2026-05-23"))

    result = update_stage.handle(
        mongo=mongo,
        cfg={},
        deal_id="deal-1",
        new_stage="qualification",
    )

    assert result["actual_close_date"] is None
    assert result["stuck_threshold_days"] == 14
    assert mongo.saved is not None
    assert mongo.saved["actual_close_date"] is None


def test_update_stage_recomputes_qualification_latest_gap_context() -> None:
    deal = _deal(stage="negotiation")
    deal["interactions"] = [
        {
            "interaction_id": "int-1",
            "date": "2026-06-10",
            "scoring_applied": True,
            "meddpicc": {"champion": {"score": 1}},
        }
    ]
    mongo = FakeMongo(deal)

    result = update_stage.handle(
        mongo=mongo,
        cfg={"meddpicc": {"weights": {}}},
        deal_id="deal-1",
        new_stage="won",
        actual_close_date="2026-06-02",
    )

    assert result["ok"] is True
    assert mongo.saved is not None
    assert mongo.saved["meddpicc_latest"]["gaps"] == []
    assert mongo.saved["qualification_latest"]["framework_key"] == "meddpicc"
    assert mongo.saved["qualification_latest"]["gaps"] == []
    assert mongo.saved["qualification_latest"]["dimensions"]["champion"]["score"] == 1.0


def test_update_stage_returns_config_error_for_invalid_active_framework() -> None:
    deal = _deal(stage="negotiation")
    deal["interactions"] = [
        {
            "interaction_id": "int-1",
            "date": "2026-06-10",
            "scoring_applied": True,
            "meddpicc": {"champion": {"score": 1}},
        }
    ]
    mongo = FakeMongo(deal)

    with pytest.raises(MCPError) as exc_info:
        update_stage.handle(
            mongo=mongo,
            cfg={"qualification": {"active_framework": "missing_framework"}},
            deal_id="deal-1",
            new_stage="won",
            actual_close_date="2026-06-02",
        )

    assert exc_info.value.error_code == ErrorCode.CONFIG_ERROR
    assert exc_info.value.stage == Stage.PREFLIGHT
    assert "missing_framework" in exc_info.value.message
    assert mongo.saved is None


@pytest.mark.parametrize("actual_close_date", ["06/02/2026", "2026-02-30", ""])
def test_invalid_actual_close_date_fails_explicitly(actual_close_date: str) -> None:
    mongo = FakeMongo(_deal())

    with pytest.raises(MCPError) as exc_info:
        update_stage.handle(
            mongo=mongo,
            cfg={},
            deal_id="deal-1",
            new_stage="won",
            actual_close_date=actual_close_date,
        )

    assert exc_info.value.error_code == ErrorCode.INVALID_INPUT
    assert exc_info.value.stage == Stage.PREFLIGHT
    assert mongo.saved is None


def test_non_terminal_stage_rejects_actual_close_date() -> None:
    mongo = FakeMongo(_deal())

    with pytest.raises(MCPError, match="only valid for won or lost"):
        update_stage.handle(
            mongo=mongo,
            cfg={},
            deal_id="deal-1",
            new_stage="proposal",
            actual_close_date="2026-06-02",
        )

    assert mongo.saved is None


def test_mcp_update_stage_forwards_actual_close_date(monkeypatch) -> None:
    mongo = FakeMongo(_deal())
    monkeypatch.setattr(_context, "mongo", lambda: mongo)
    monkeypatch.setattr(_context, "config", lambda: {})

    result = mcp_server.update_stage(
        "deal-1",
        "won",
        actual_close_date="2026-06-02",
    )

    assert result["ok"] is True
    assert result["actual_close_date"] == "2026-06-02"
    assert mongo.saved is not None
    assert mongo.saved["actual_close_date"] == "2026-06-02"
