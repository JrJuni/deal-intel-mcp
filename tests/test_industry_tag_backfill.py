from __future__ import annotations

from copy import deepcopy

import pytest
from typer.testing import CliRunner

from deal_intel import _context
from deal_intel.cli import app
from deal_intel.errors import ErrorCode, MCPError
from deal_intel.tools import backfill_industry_tags


class FakeMongo:
    def __init__(self, deals: list[dict]) -> None:
        self.deals = deepcopy(deals)
        self.saved: list[dict] = []

    def list_deals_for_metrics(self) -> list[dict]:
        return deepcopy(self.deals)

    def get_deal(self, deal_id: str) -> dict | None:
        for deal in self.deals:
            if deal.get("deal_id") == deal_id:
                return deepcopy(deal)
        return None

    def upsert_deal(self, deal: dict) -> None:
        self.saved.append(deepcopy(deal))


def _deal(
    deal_id: str,
    *,
    company: str | None = None,
    industry: str | None = "Finance",
    industry_tags: list[str] | None = None,
    customer_segment: str | None = None,
) -> dict:
    deal = {
        "deal_id": deal_id,
        "company": company or deal_id,
        "deal_stage": "discovery",
        "industry": industry,
        "expected_close_date": "2026-06-30",
    }
    if industry_tags is not None:
        deal["industry_tags"] = industry_tags
    if customer_segment is not None:
        deal["customer_segment"] = customer_segment
    return deal


def test_industry_tag_backfill_defaults_to_dry_run() -> None:
    mongo = FakeMongo([_deal("d1", industry_tags=None)])

    result = backfill_industry_tags.handle(mongo)

    assert result["ok"] is True
    assert result["dry_run"] is True
    assert result["storage_written"] is False
    assert result["summary"]["candidate_count"] == 1
    assert result["candidates"][0]["action"] == "backfill_missing_tags"
    assert result["candidates"][0]["suggested_industry"] == "Finance"
    assert result["candidates"][0]["suggested_industry_tags"] == ["Finance"]
    assert mongo.saved == []


def test_industry_tag_backfill_repairs_primary_missing_from_existing_tags() -> None:
    result = backfill_industry_tags.handle(
        FakeMongo([_deal("d1", industry="Finance", industry_tags=["Insurance"])]),
    )

    assert result["summary"]["candidate_count"] == 1
    assert result["candidates"][0]["action"] == "repair_primary_tag"
    assert result["candidates"][0]["suggested_industry_tags"] == [
        "Finance",
        "Insurance",
    ]


def test_industry_tag_backfill_auto_classifies_cross_industry_labels() -> None:
    result = backfill_industry_tags.handle(
        FakeMongo([_deal("mixed", industry="Insurance/Finance/enterprise")])
    )

    assert result["summary"]["candidate_count"] == 1
    row = result["candidates"][0]
    assert row["action"] == "normalize_industry_and_segment"
    assert row["suggested_industry"] == "Insurance"
    assert row["suggested_industry_tags"] == ["Insurance", "Finance"]
    assert row["suggested_customer_segment"] == "enterprise"


def test_industry_tag_backfill_splits_stage_like_segments() -> None:
    result = backfill_industry_tags.handle(
        FakeMongo([_deal("agtech", industry="AgTech/startup/Series B")])
    )

    assert result["summary"]["candidate_count"] == 1
    row = result["candidates"][0]
    assert row["suggested_industry"] == "AgTech"
    assert row["suggested_industry_tags"] == ["AgTech"]
    assert row["suggested_customer_segment"] == "startup; Series B"


def test_industry_tag_backfill_uses_custom_draft_for_unmapped_industry() -> None:
    result = backfill_industry_tags.handle(
        FakeMongo([_deal("unmapped", industry="Space Mining")])
    )

    assert result["summary"]["candidate_count"] == 1
    assert result["summary"]["skipped_count"] == 0
    row = result["candidates"][0]
    assert row["action"] == "custom_industry_draft"
    assert row["suggested_industry"] == "Space Mining"
    assert row["taxonomy_warnings"][0]["code"] == "low_confidence_custom_industry_draft"


def test_industry_tag_backfill_marks_missing_industry_as_research_task() -> None:
    result = backfill_industry_tags.handle(
        FakeMongo([_deal("missing", company="Mystery Co", industry=None)])
    )

    assert result["summary"]["candidate_count"] == 0
    assert result["summary"]["research_count"] == 1
    assert result["summary"]["skipped_count"] == 0
    row = result["research"][0]
    assert row["action"] == "research_missing_industry"
    assert row["research_query"] == "Mystery Co company industry"
    assert row["taxonomy_warnings"][0]["code"] == "online_research_needed"


def test_industry_tag_backfill_infers_missing_industry_from_company_name() -> None:
    result = backfill_industry_tags.handle(
        FakeMongo([_deal("missing", company="Aurora Insurance", industry=None)])
    )

    assert result["summary"]["candidate_count"] == 1
    row = result["candidates"][0]
    assert row["action"] == "infer_missing_industry_from_company"
    assert row["suggested_industry"] == "Insurance"
    assert row["confidence"] == "medium"


def test_industry_tag_backfill_requires_confirmation_for_apply() -> None:
    with pytest.raises(MCPError) as exc_info:
        backfill_industry_tags.handle(
            FakeMongo([_deal("d1")]),
            dry_run=False,
            confirmed_by_user=False,
        )

    assert exc_info.value.error_code == ErrorCode.INVALID_INPUT


def test_industry_tag_backfill_applies_through_update_deal() -> None:
    mongo = FakeMongo(
        [_deal("d1", industry="Insurance/Finance/enterprise", industry_tags=None)]
    )

    result = backfill_industry_tags.handle(
        mongo,
        dry_run=False,
        confirmed_by_user=True,
    )

    assert result["ok"] is True
    assert result["storage_written"] is True
    assert result["summary"]["applied_count"] == 1
    assert mongo.saved[0]["industry"] == "Insurance"
    assert mongo.saved[0]["industry_tags"] == ["Insurance", "Finance"]
    assert mongo.saved[0]["customer_segment"] == "enterprise"
    history = mongo.saved[0]["deal_metadata_history"][-1]
    assert history["source"] == "update_deal"
    assert history["changed_fields"] == [
        "industry",
        "industry_tags",
        "customer_segment",
    ]


def test_industry_tag_backfill_cli_is_dry_run_by_default(monkeypatch) -> None:
    mongo = FakeMongo([_deal("d1", company="PayBridge", industry_tags=None)])
    monkeypatch.setattr(_context, "mongo", lambda: mongo)

    result = CliRunner().invoke(app, ["backfill-industry-tags"])

    assert result.exit_code == 0
    assert "Industry metadata backfill: dry-run" in result.stdout
    assert "PayBridge" in result.stdout
    assert mongo.saved == []


def test_industry_tag_backfill_cli_applies_with_confirmation(monkeypatch) -> None:
    mongo = FakeMongo([_deal("d1", industry_tags=None)])
    monkeypatch.setattr(_context, "mongo", lambda: mongo)

    result = CliRunner().invoke(
        app,
        ["backfill-industry-tags", "--apply", "--confirmed-by-user", "--json"],
    )

    assert result.exit_code == 0
    assert '"applied_count": 1' in result.stdout
    assert mongo.saved[0]["industry_tags"] == ["Finance"]
