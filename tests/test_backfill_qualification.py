from __future__ import annotations

import json
from copy import deepcopy

import pytest
from typer.testing import CliRunner

from deal_intel import _context, mcp_server
from deal_intel.cli import app
from deal_intel.errors import ErrorCode, MCPError
from deal_intel.tools import backfill_qualification
from deal_intel.tools.qualification_snapshot import rebuild_latest_snapshots


class FakeMongo:
    def __init__(self, deals: list[dict]) -> None:
        self.deals = deepcopy(deals)
        self.snapshot_updates: list[dict] = []
        self.upsert_called = False

    def list_deals_for_metrics(self) -> list[dict]:
        return [_restricted(deal) for deal in self.deals]

    def update_deal_qualification_snapshots(
        self,
        deal_id: str,
        *,
        meddpicc_latest: dict,
        qualification_latest: dict,
        updated_at: str,
    ) -> bool:
        self.snapshot_updates.append(
            {
                "deal_id": deal_id,
                "meddpicc_latest": deepcopy(meddpicc_latest),
                "qualification_latest": deepcopy(qualification_latest),
                "updated_at": updated_at,
            }
        )
        for deal in self.deals:
            if deal.get("deal_id") != deal_id:
                continue
            deal["meddpicc_latest"] = deepcopy(meddpicc_latest)
            deal["qualification_latest"] = deepcopy(qualification_latest)
            deal["updated_at"] = updated_at
            return True
        return False

    def upsert_deal(self, _deal: dict) -> None:
        self.upsert_called = True
        raise AssertionError("backfill_qualification must patch snapshots, not upsert")


def _deal(
    deal_id: str,
    *,
    interactions: list[dict] | None = None,
    meddpicc_latest: dict | None = None,
    qualification_latest: dict | None = None,
) -> dict:
    return {
        "deal_id": deal_id,
        "company": deal_id,
        "deal_stage": "discovery",
        "interactions": interactions or [],
        "meddpicc_latest": meddpicc_latest or {},
        "qualification_latest": qualification_latest or {},
        "updated_at": "2026-06-01T00:00:00+00:00",
    }


def _meddpicc_interaction(score: int = 5) -> dict:
    return {
        "interaction_id": "i1",
        "scoring_applied": True,
        "raw_content": "private raw content sentinel",
        "meddpicc": {"champion": {"score": score, "evidence": "Champion confirmed"}},
    }


def _qualification_interaction(score: int = 5) -> dict:
    return {
        "interaction_id": "i1",
        "scoring_applied": True,
        "raw_content": "private raw content sentinel",
        "qualification": {
            "business_need": {"score": score, "evidence": "Need confirmed"}
        },
    }


def _restricted(deal: dict) -> dict:
    copied = deepcopy(deal)
    for interaction in copied.get("interactions", []):
        interaction.pop("raw_content", None)
    copied.pop("contacts", None)
    copied.pop("summary_embedding", None)
    return copied


def test_backfill_qualification_defaults_to_dry_run_without_llm() -> None:
    mongo = FakeMongo([_deal("d1", interactions=[_meddpicc_interaction()])])

    result = backfill_qualification.handle(mongo, {"meddpicc": {"weights": {}}})

    assert result["ok"] is True
    assert result["dry_run"] is True
    assert result["llm_calls"] is False
    assert result["storage_written"] is False
    assert result["summary"]["candidate_count"] == 1
    assert result["candidates"][0]["changed_fields"] == [
        "meddpicc_latest",
        "qualification_latest",
    ]
    assert mongo.snapshot_updates == []
    assert mongo.upsert_called is False
    assert "raw_content" not in json.dumps(result)


def test_backfill_qualification_requires_confirmation_for_apply() -> None:
    with pytest.raises(MCPError) as exc_info:
        backfill_qualification.handle(
            FakeMongo([_deal("d1", interactions=[_meddpicc_interaction()])]),
            {"meddpicc": {"weights": {}}},
            dry_run=False,
            confirmed_by_user=False,
        )

    assert exc_info.value.error_code == ErrorCode.INVALID_INPUT


def test_backfill_qualification_apply_patches_snapshots_without_replacing_deal() -> None:
    mongo = FakeMongo([_deal("d1", interactions=[_meddpicc_interaction()])])

    result = backfill_qualification.handle(
        mongo,
        {"meddpicc": {"weights": {}}},
        dry_run=False,
        confirmed_by_user=True,
    )

    assert result["ok"] is True
    assert result["storage_written"] is True
    assert result["summary"]["applied_count"] == 1
    assert len(mongo.snapshot_updates) == 1
    assert mongo.snapshot_updates[0]["qualification_latest"]["framework_key"] == "meddpicc"
    assert mongo.upsert_called is False
    assert (
        mongo.deals[0]["interactions"][0]["raw_content"]
        == "private raw content sentinel"
    )


def test_backfill_qualification_skips_deals_without_scoring_evidence() -> None:
    result = backfill_qualification.handle(
        FakeMongo([_deal("empty")]),
        {"meddpicc": {"weights": {}}},
    )

    assert result["summary"]["candidate_count"] == 0
    assert result["summary"]["skipped_count"] == 1
    assert result["skipped"][0]["reason"] == "no_scoring_evidence"
    assert result["warnings"][0]["code"] == "unassessed_deals_skipped"


def test_backfill_qualification_recomputes_custom_framework_evidence() -> None:
    mongo = FakeMongo([_deal("custom", interactions=[_qualification_interaction()])])

    result = backfill_qualification.handle(
        mongo,
        {"qualification": {"active_framework": "simple_b2b"}},
    )

    assert result["summary"]["candidate_count"] == 1
    row = result["candidates"][0]
    assert row["recomputed_qualification"]["framework_key"] == "simple_b2b"
    assert row["recomputed_qualification"]["filled_count"] == 1


def test_backfill_qualification_flags_custom_framework_reextraction_need() -> None:
    result = backfill_qualification.handle(
        FakeMongo([_deal("legacy", interactions=[_meddpicc_interaction()])]),
        {"qualification": {"active_framework": "simple_b2b"}},
    )

    assert result["summary"]["candidate_count"] == 0
    assert result["summary"]["needs_reextraction_count"] == 1
    assert result["needs_reextraction"][0]["reason"] == (
        "missing_active_framework_evidence"
    )
    assert result["warnings"][0]["code"] == "llm_reextraction_needed"


def test_backfill_qualification_clean_when_snapshots_already_match() -> None:
    deal = _deal("clean", interactions=[_meddpicc_interaction()])
    snapshots = rebuild_latest_snapshots(deal, {"meddpicc": {"weights": {}}})
    deal["meddpicc_latest"] = snapshots["meddpicc_latest"]
    deal["qualification_latest"] = snapshots["qualification_latest"]

    result = backfill_qualification.handle(
        FakeMongo([deal]),
        {"meddpicc": {"weights": {}}},
    )

    assert result["summary"]["candidate_count"] == 0
    assert result["summary"]["clean_count"] == 1


def test_backfill_qualification_limit_scopes_scan() -> None:
    result = backfill_qualification.handle(
        FakeMongo(
            [
                _deal("d1", interactions=[_meddpicc_interaction()]),
                _deal("d2", interactions=[_meddpicc_interaction()]),
            ]
        ),
        {"meddpicc": {"weights": {}}},
        limit=1,
    )

    assert result["summary"]["deals_scanned"] == 1
    assert [row["deal_id"] for row in result["candidates"]] == ["d1"]


def test_backfill_qualification_cli_dry_run(monkeypatch) -> None:
    mongo = FakeMongo([_deal("d1", interactions=[_meddpicc_interaction()])])
    monkeypatch.setattr(_context, "mongo", lambda: mongo)
    monkeypatch.setattr(_context, "config", lambda: {"meddpicc": {"weights": {}}})

    result = CliRunner().invoke(app, ["backfill-qualification", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["dry_run"] is True
    assert payload["summary"]["candidate_count"] == 1
    assert "raw_content" not in result.stdout


def test_backfill_qualification_mcp_wrapper_is_dry_run_and_llm_free(
    monkeypatch,
) -> None:
    mongo = FakeMongo([_deal("d1", interactions=[_meddpicc_interaction()])])
    monkeypatch.setattr(_context, "mongo", lambda: mongo)
    monkeypatch.setattr(_context, "config", lambda: {"meddpicc": {"weights": {}}})

    def fail_if_called():
        raise AssertionError("recompute-only backfill must not initialize LLM")

    monkeypatch.setattr(_context, "llm_provider", fail_if_called)

    result = mcp_server.backfill_qualification()

    assert result["ok"] is True
    assert result["dry_run"] is True
    assert result["llm_calls"] is False
    assert result["summary"]["candidate_count"] == 1
    assert mongo.snapshot_updates == []
    assert "private raw content sentinel" not in json.dumps(result)
