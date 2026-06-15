from __future__ import annotations

import json
from copy import deepcopy

import pytest
from typer.testing import CliRunner

from deal_intel import _context, mcp_server
from deal_intel.cli import app
from deal_intel.errors import ErrorCode, MCPError
from deal_intel.providers.llm import LLMResponse
from deal_intel.schema.qualification_framework import (
    get_qualification_template,
    qualification_framework_fingerprint,
)
from deal_intel.tools import backfill_qualification_reextract


class FakeLLM:
    def __init__(self, text: str | None = None, *, fail: bool = False) -> None:
        self.text = text or json.dumps(
            {
                "qualification": {
                    "business_need": {
                        "score": 5,
                        "evidence": "Customer has clear business need.",
                        "confidence": "high",
                    }
                }
            }
        )
        self.fail = fail
        self.calls: list[dict] = []

    def chat_once(self, **kwargs) -> LLMResponse:
        self.calls.append(kwargs)
        if self.fail:
            raise RuntimeError("llm unavailable")
        return LLMResponse(
            text=self.text,
            usage={"input_tokens": 100, "output_tokens": 25},
            model="fake-model",
        )


class FakeMongo:
    def __init__(self, deals: list[dict]) -> None:
        self.deals = deepcopy(deals)
        self.updates: list[dict] = []

    def list_deals_for_qualification_reextract(self, *, limit: int = 0) -> list[dict]:
        deals = deepcopy(self.deals)
        return deals[:limit] if limit > 0 else deals

    def update_deal_qualification_reextraction(
        self,
        deal_id: str,
        *,
        interactions: list[dict],
        meddpicc_latest: dict,
        qualification_latest: dict,
        updated_at: str,
    ) -> bool:
        self.updates.append(
            {
                "deal_id": deal_id,
                "interactions": deepcopy(interactions),
                "meddpicc_latest": deepcopy(meddpicc_latest),
                "qualification_latest": deepcopy(qualification_latest),
                "updated_at": updated_at,
            }
        )
        for deal in self.deals:
            if deal.get("deal_id") != deal_id:
                continue
            deal["interactions"] = deepcopy(interactions)
            deal["meddpicc_latest"] = deepcopy(meddpicc_latest)
            deal["qualification_latest"] = deepcopy(qualification_latest)
            deal["updated_at"] = updated_at
            return True
        return False


def _deal(*, interactions: list[dict]) -> dict:
    return {
        "deal_id": "d1",
        "company": "Acme",
        "deal_stage": "proposal",
        "interactions": interactions,
        "meddpicc_latest": {},
        "qualification_latest": {},
    }


def _interaction(**overrides) -> dict:
    data = {
        "interaction_id": "i1",
        "date": "2026-06-01",
        "interaction_type": "meeting",
        "direction": "inbound",
        "source_confidence": "customer_stated",
        "scoring_applied": True,
        "raw_content": "private raw content sentinel",
    }
    data.update(overrides)
    return data


def test_reextract_plan_defaults_to_scoring_sources_and_30_call_limit() -> None:
    deals = [
        _deal(
            interactions=[
                _interaction(interaction_id=f"i{index}")
                for index in range(35)
            ]
        )
    ]

    result = backfill_qualification_reextract.build_qualification_reextract_plan(
        deals,
        {"qualification": {"active_framework": "simple_b2b"}},
    )

    assert result["summary"]["candidate_count"] == 35
    assert result["summary"]["selected_count"] == 30
    assert result["summary"]["max_llm_calls"] == 30
    assert result["warnings"][1]["code"] == "candidate_limit_applied"
    assert "private raw content sentinel" not in json.dumps(result)


def test_reextract_plan_skips_unconfirmed_by_default() -> None:
    result = backfill_qualification_reextract.build_qualification_reextract_plan(
        [
            _deal(
                interactions=[
                    _interaction(
                        source_confidence="internal",
                        direction="internal",
                        scoring_applied=False,
                    )
                ]
            )
        ],
        {"qualification": {"active_framework": "simple_b2b"}},
    )

    assert result["summary"]["candidate_count"] == 0
    assert result["skipped"][0]["reason"] == "non_scoring_source"


def test_reextract_plan_can_include_unconfirmed_context() -> None:
    result = backfill_qualification_reextract.build_qualification_reextract_plan(
        [
            _deal(
                interactions=[
                    _interaction(
                        source_confidence="internal",
                        direction="internal",
                        scoring_applied=False,
                    )
                ]
            )
        ],
        {"qualification": {"active_framework": "simple_b2b"}},
        include_unconfirmed=True,
    )

    assert result["summary"]["candidate_count"] == 1
    assert result["candidates"][0]["target_field"] == "unconfirmed_qualification"


def test_reextract_plan_uses_framework_hash_to_detect_stale_evidence() -> None:
    framework = get_qualification_template("simple_b2b")
    stale_hash = "old-hash"
    result = backfill_qualification_reextract.build_qualification_reextract_plan(
        [
            _deal(
                interactions=[
                    _interaction(
                        qualification={"business_need": {"score": 4}},
                        qualification_framework="simple_b2b",
                        qualification_framework_hash=stale_hash,
                    )
                ]
            )
        ],
        {"qualification": {"active_framework": "simple_b2b"}},
    )

    assert result["summary"]["candidate_count"] == 1
    assert result["candidates"][0]["reason"] == "stale_framework_hash"
    assert result["candidates"][0]["current_framework_hash"] == (
        qualification_framework_fingerprint(framework)
    )


def test_reextract_plan_keeps_existing_unhashed_evidence_clean_by_default() -> None:
    result = backfill_qualification_reextract.build_qualification_reextract_plan(
        [
            _deal(
                interactions=[
                    _interaction(
                        qualification={"business_need": {"score": 4}},
                        qualification_framework="simple_b2b",
                    )
                ]
            )
        ],
        {"qualification": {"active_framework": "simple_b2b"}},
    )

    assert result["summary"]["candidate_count"] == 0
    assert result["summary"]["clean_count"] == 1


def test_reextract_apply_updates_interaction_snapshots_and_usage_without_raw_leak() -> None:
    mongo = FakeMongo([
        _deal(interactions=[_interaction()])
    ])
    llm = FakeLLM()

    result = backfill_qualification_reextract.handle(
        mongo,
        llm,
        {"qualification": {"active_framework": "simple_b2b"}},
        dry_run=False,
        confirmed_by_user=True,
    )

    assert result["ok"] is True
    assert len(llm.calls) == 1
    assert result["summary"]["applied_count"] == 1
    updated_interaction = mongo.updates[0]["interactions"][0]
    assert updated_interaction["qualification"]["business_need"]["score"] == 5
    assert updated_interaction["qualification_framework"] == "simple_b2b"
    assert updated_interaction["qualification_framework_hash"]
    assert updated_interaction["qualification_backfill_usage"]["source_tool"] == (
        "backfill_qualification_reextract"
    )
    assert mongo.updates[0]["qualification_latest"]["framework_key"] == "simple_b2b"
    assert "private raw content sentinel" not in json.dumps(result)


def test_reextract_apply_requires_confirmation() -> None:
    with pytest.raises(MCPError) as exc_info:
        backfill_qualification_reextract.handle(
            FakeMongo([_deal(interactions=[_interaction()])]),
            FakeLLM(),
            {"qualification": {"active_framework": "simple_b2b"}},
            dry_run=False,
            confirmed_by_user=False,
        )

    assert exc_info.value.error_code == ErrorCode.INVALID_INPUT


def test_reextract_partial_llm_failure_is_structured() -> None:
    result = backfill_qualification_reextract.handle(
        FakeMongo([_deal(interactions=[_interaction()])]),
        FakeLLM(fail=True),
        {"qualification": {"active_framework": "simple_b2b"}},
        dry_run=False,
        confirmed_by_user=True,
    )

    assert result["ok"] is False
    assert result["summary"]["error_count"] == 1
    assert result["errors"][0]["interaction_id"] == "i1"
    assert "private raw content sentinel" not in json.dumps(result)


def test_reextract_cli_dry_run_json(monkeypatch) -> None:
    mongo = FakeMongo([_deal(interactions=[_interaction()])])
    monkeypatch.setattr(_context, "mongo", lambda: mongo)
    monkeypatch.setattr(
        _context,
        "llm_provider",
        lambda: (_ for _ in ()).throw(AssertionError("dry-run must not init llm")),
    )
    monkeypatch.setattr(
        _context,
        "config",
        lambda: {"qualification": {"active_framework": "simple_b2b"}},
    )

    result = CliRunner().invoke(
        app,
        ["backfill-qualification-reextract", "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["dry_run"] is True
    assert payload["summary"]["candidate_count"] == 1
    assert "private raw content sentinel" not in result.stdout


def test_reextract_mcp_dry_run_does_not_initialize_llm(monkeypatch) -> None:
    mongo = FakeMongo([_deal(interactions=[_interaction()])])
    monkeypatch.setattr(_context, "mongo", lambda: mongo)
    monkeypatch.setattr(
        _context,
        "llm_provider",
        lambda: (_ for _ in ()).throw(AssertionError("dry-run must not init llm")),
    )
    monkeypatch.setattr(
        _context,
        "config",
        lambda: {"qualification": {"active_framework": "simple_b2b"}},
    )

    result = mcp_server.backfill_qualification_reextract()

    assert result["ok"] is True
    assert result["dry_run"] is True
    assert result["llm_calls"] is False
    assert result["summary"]["selected_count"] == 1
    assert "private raw content sentinel" not in json.dumps(result)


def test_reextract_mcp_apply_uses_confirmed_llm_and_cap(monkeypatch) -> None:
    mongo = FakeMongo([_deal(interactions=[_interaction()])])
    llm = FakeLLM()
    monkeypatch.setattr(_context, "mongo", lambda: mongo)
    monkeypatch.setattr(_context, "llm_provider", lambda: llm)
    monkeypatch.setattr(
        _context,
        "config",
        lambda: {"qualification": {"active_framework": "simple_b2b"}},
    )

    result = mcp_server.backfill_qualification_reextract(
        dry_run=False,
        confirmed_by_user=True,
        max_llm_calls=1,
    )

    assert result["ok"] is True
    assert result["dry_run"] is False
    assert result["llm_calls"] is True
    assert len(llm.calls) == 1
    assert result["summary"]["applied_count"] == 1
    assert mongo.updates[0]["qualification_latest"]["framework_key"] == "simple_b2b"
