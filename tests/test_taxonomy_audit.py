from __future__ import annotations

from copy import deepcopy

from typer.testing import CliRunner

from deal_intel import _context
from deal_intel.cli import app
from deal_intel.schema.taxonomy_audit import build_taxonomy_audit


class FakeMongo:
    def __init__(self, deals: list[dict]) -> None:
        self.deals = deepcopy(deals)
        self.written = False
        self.saved: list[dict] = []

    def list_deals_for_metrics(self) -> list[dict]:
        return deepcopy(self.deals)

    def get_deal(self, deal_id: str) -> dict | None:
        for deal in self.deals:
            if deal.get("deal_id") == deal_id:
                return deepcopy(deal)
        return None

    def upsert_deal(self, deal: dict) -> None:
        self.written = True
        self.saved.append(deepcopy(deal))


def test_taxonomy_audit_splits_industry_and_segment_candidates() -> None:
    payload = build_taxonomy_audit(
        [
            {
                "deal_id": "deal-1",
                "company": "Lumino AI",
                "industry": "IT 스타트업·Series B",
                "customer_segment": None,
                "deal_stage": "discovery",
                "customer_themes": [
                    {
                        "dimension": "identify_pain",
                        "label": "Operational efficiency",
                        "evidence": "Engineering team wants faster weekly reporting.",
                    }
                ],
            }
        ]
    )

    assert payload["summary"]["issue_deal_count"] == 1
    row = payload["deals"][0]
    assert row["suggested_industry"] == "IT"
    assert row["suggested_industry_tags"] == ["IT"]
    assert row["suggested_customer_segment"] == "startup; Series B"
    assert row["confidence"] == "high"
    assert row["needs_human_review"] is False
    assert row["review_explanation"]["review_level"] == "auto_apply_candidate"
    assert row["update_deal_payload"] == {
        "deal_id": "deal-1",
        "confirmed_by_user": True,
        "industry": "IT",
        "industry_tags": ["IT"],
        "customer_segment": "startup; Series B",
        "update_note": "User confirmed taxonomy cleanup after reviewing deal context.",
    }


def test_taxonomy_audit_auto_tags_cross_industry_labels() -> None:
    payload = build_taxonomy_audit(
        [
            {
                "deal_id": "deal-1",
                "company": "Mixed Co",
                "industry": "보험·금융·대기업",
                "customer_segment": None,
                "deal_stage": "proposal",
            }
        ]
    )

    row = payload["deals"][0]
    assert row["suggested_industry"] == "Insurance"
    assert row["suggested_industry_tags"] == ["Insurance", "Finance"]
    assert row["suggested_customer_segment"] == "enterprise"
    assert row["confidence"] == "high"
    assert row["needs_human_review"] is False
    assert "cross_industry_tags_detected" in row["issues"]


def test_taxonomy_audit_marks_unmapped_industry_for_review() -> None:
    payload = build_taxonomy_audit(
        [
            {
                "deal_id": "deal-1",
                "company": "Unknown Co",
                "industry": "우주광물채굴",
                "customer_segment": None,
                "deal_stage": "proposal",
            }
        ]
    )

    row = payload["deals"][0]
    assert row["suggested_industry"] is None
    assert row["confidence"] == "low"
    assert row["needs_human_review"] is True
    assert "unmapped_industry" in row["issues"]


def test_taxonomy_audit_cli_is_read_only(monkeypatch) -> None:
    mongo = FakeMongo(
        [
            {
                "deal_id": "deal-1",
                "company": "Aero Co",
                "industry": "UAM·항공모빌리티·Pre-IPO",
                "deal_stage": "negotiation",
            }
        ]
    )
    monkeypatch.setattr(_context, "mongo", lambda: mongo)

    result = CliRunner().invoke(app, ["audit-taxonomy", "--json"])

    assert result.exit_code == 0
    assert '"suggested_industry": "Aviation Mobility"' in result.stdout
    assert '"suggested_customer_segment": "Pre-IPO"' in result.stdout
    assert mongo.written is False


def test_apply_taxonomy_cleanup_defaults_to_dry_run(monkeypatch) -> None:
    mongo = FakeMongo(
        [
            {
                "deal_id": "deal-1",
                "company": "Lumino AI",
                "industry": "IT 스타트업·Series B",
                "customer_segment": None,
                "deal_stage": "discovery",
                "expected_close_date": "2026-06-30",
            }
        ]
    )
    monkeypatch.setattr(_context, "mongo", lambda: mongo)

    result = CliRunner().invoke(app, ["apply-taxonomy-cleanup"])

    assert result.exit_code == 0
    assert "Taxonomy cleanup: dry-run" in result.stdout
    assert "Lumino AI" in result.stdout
    assert mongo.written is False


def test_apply_taxonomy_cleanup_requires_confirmation_for_writes(monkeypatch) -> None:
    mongo = FakeMongo(
        [
            {
                "deal_id": "deal-1",
                "company": "Lumino AI",
                "industry": "IT 스타트업·Series B",
                "customer_segment": None,
                "deal_stage": "discovery",
            }
        ]
    )
    monkeypatch.setattr(_context, "mongo", lambda: mongo)

    result = CliRunner().invoke(app, ["apply-taxonomy-cleanup", "--apply"])

    assert result.exit_code == 1
    assert "CONFIRMATION_REQUIRED" in result.stdout
    assert mongo.written is False


def test_apply_taxonomy_cleanup_writes_high_confidence_by_default(
    monkeypatch,
) -> None:
    mongo = FakeMongo(
        [
            {
                "deal_id": "deal-1",
                "company": "Lumino AI",
                "industry": "보험·금융·대기업",
                "customer_segment": None,
                "deal_stage": "discovery",
                "expected_close_date": "2026-06-30",
                "expected_close_date_source": "config_default",
            },
            {
                "deal_id": "deal-2",
                "company": "Unknown Co",
                "industry": "우주광물채굴",
                "customer_segment": None,
                "deal_stage": "proposal",
                "expected_close_date": "2026-06-30",
                "expected_close_date_source": "config_default",
            },
        ]
    )
    monkeypatch.setattr(_context, "mongo", lambda: mongo)

    result = CliRunner().invoke(
        app,
        ["apply-taxonomy-cleanup", "--apply", "--confirmed-by-user"],
    )

    assert result.exit_code == 0
    assert "Applied: 1 row(s), errors: 0" in result.stdout
    assert len(mongo.saved) == 1
    assert mongo.saved[0]["deal_id"] == "deal-1"
    assert mongo.saved[0]["industry"] == "Insurance"
    assert mongo.saved[0]["industry_tags"] == ["Insurance", "Finance"]
    assert mongo.saved[0]["customer_segment"] == "enterprise"
    assert mongo.saved[0]["deal_metadata_history"][-1]["source"] == "update_deal"
