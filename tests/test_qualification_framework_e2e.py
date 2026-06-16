from __future__ import annotations

import csv
import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import yaml

from deal_intel.qualification_config import (
    delete_qualification_framework_config,
    list_qualification_frameworks_config,
    resolve_active_qualification_framework,
    set_active_qualification_framework_config,
    update_qualification_framework_config,
)
from deal_intel.schema.qualification import compute_qualification_latest
from deal_intel.schema.qualification_framework import get_qualification_template
from deal_intel.tools import (
    add_interaction,
    backfill_qualification_reextract,
    export_report,
    get_deal_gaps,
    get_deal_review,
    get_metrics,
    search_deals,
)
from deal_intel.tools.analytics_snapshot import build_analytics_snapshot


class FakeMongo:
    def __init__(self, deals: list[dict]) -> None:
        self.deals = deepcopy(deals)

    def list_deals_for_metrics(self) -> list[dict]:
        return deepcopy(self.deals)

    def get_deals_for_search(self) -> list[dict]:
        return deepcopy(self.deals)

    def get_deal(self, deal_id: str) -> dict | None:
        for deal in self.deals:
            if deal.get("deal_id") == deal_id:
                return deepcopy(deal)
        return None

    def upsert_deal(self, deal: dict) -> None:
        for index, existing in enumerate(self.deals):
            if existing.get("deal_id") == deal.get("deal_id"):
                self.deals[index] = deepcopy(deal)
                return
        self.deals.append(deepcopy(deal))

    def list_deals_for_qualification_reextract(self, *, limit: int = 0) -> list[dict]:
        deals = self.deals[:limit] if limit > 0 else self.deals
        return deepcopy(deals)

    def _get_db(self) -> None:
        raise AssertionError("QF-11 smoke should use safe read paths")


class FakeEmbedding:
    def embed(self, _query: str) -> list[float]:
        return [1.0, 0.0]


class FakeLLM:
    def __init__(self, responses: list[str]) -> None:
        self.responses = iter(responses)
        self.calls: list[dict] = []

    def chat_once(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            text=next(self.responses),
            usage={"input_tokens": 10, "output_tokens": 5},
        )


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _custom_framework_deal() -> dict:
    framework = get_qualification_template("simple_b2b")
    qualification_latest = compute_qualification_latest(
        [
            {
                "qualification": {
                    "business_need": {"score": 5},
                    "buyer_owner": {"score": 4},
                }
            }
        ],
        framework=framework,
        evidence_fields=("qualification",),
        deal_stage="proposal",
    )
    return {
        "deal_id": "qf11-custom",
        "company": "Custom Framework Co",
        "industry": "SaaS",
        "industry_tags": ["SaaS", "Fintech"],
        "customer_segment": "startup",
        "deal_stage": "proposal",
        "deal_size_amount": 120_000_000,
        "deal_size_currency": "KRW",
        "deal_size_status": "quoted",
        "expected_close_date": "2026-06-30",
        "expected_close_date_source": "user_provided",
        "stage_history": [
            {"stage": "proposal", "entered_at": "2026-06-01T00:00:00+00:00"}
        ],
        "meetings": [{"date": "2026-06-01", "raw_notes": "secret raw note"}],
        "interactions": [
            {
                "interaction_type": "meeting",
                "occurred_at": "2026-06-01T00:00:00+00:00",
                "raw_content": "secret interaction content",
                "qualification_framework": "simple_b2b",
            }
        ],
        "contacts": [{"name": "secret contact"}],
        "summary_embedding": [1.0, 0.0],
        "qualification_latest": qualification_latest,
        "meddpicc_latest": {
            "filled_count": 7,
            "health_pct": 99.0,
            "gaps": [],
        },
        "customer_themes": [
            {
                "label": "Integration",
                "dimension": "decision_criteria",
                "evidence": "API integration matters",
                "importance": 4,
                "meeting_date": "2026-06-01",
            }
        ],
    }


def test_custom_framework_surfaces_stay_generic_end_to_end(tmp_path) -> None:
    deal = _custom_framework_deal()
    mongo = FakeMongo([deal])
    expected_health = deal["qualification_latest"]["health_pct"]

    review = get_deal_review.handle(
        mongo=mongo,
        cfg={},
        deal_id="qf11-custom",
        as_of="2026-06-10",
    )
    review_payload = review["review"]
    assert review_payload["qualification"]["framework_key"] == "simple_b2b"
    assert review_payload["qualification"]["source_field"] == "qualification_latest"
    assert review_payload["health_interpretation"]["legacy_health_pct"] == 99.0
    assert review_payload["health_interpretation"]["qualification_framework"] == "simple_b2b"
    assert any(
        row["field"] == "qualification.next_step"
        for row in review_payload["gap_observations"]
    )

    gaps = get_deal_gaps.handle(
        mongo=mongo,
        cfg={},
        deal_id="qf11-custom",
        min_priority="low",
        as_of="2026-06-10",
    )
    gap_row = gaps["deals"][0]
    assert gap_row["qualification"]["framework_key"] == "simple_b2b"
    assert gap_row["qualification_source_field"] == "qualification_latest"
    assert gap_row["qualification_health_pct"] == expected_health
    assert gap_row["health_pct"] == expected_health
    assert gap_row["qualification_gaps"] == ["next_step"]

    metrics = get_metrics.handle(
        mongo=mongo,
        cfg={},
        metric_type="pipeline_health",
        as_of="2026-06-10",
    )
    assert metrics["kpis"]["avg_health_pct"] == expected_health
    assert metrics["kpis"]["avg_health_pct"] != 99.0
    proposal = next(
        row for row in metrics["stage_breakdown"] if row["stage"] == "proposal"
    )
    assert proposal["avg_health_pct"] == expected_health

    report = export_report.handle(
        mongo=mongo,
        cfg={"reporting": {"output_dir": str(tmp_path), "language": "en"}},
        report_type="weekly_pipeline",
        as_of="2026-06-10",
    )
    assert report["ok"] is True
    assert report["row_count"] == 1
    csv_path = Path(report["csv_path"])
    with csv_path.open(encoding="utf-8-sig", newline="") as file:
        report_rows = list(csv.DictReader(file))
    assert report_rows[0]["qualification_framework"] == "simple_b2b"
    assert report_rows[0]["qualification_source_field"] == "qualification_latest"
    assert json.loads(report_rows[0]["qualification_gaps"]) == ["next_step"]
    assert json.loads(report_rows[0]["meddpicc_gaps"]) == []

    search = search_deals.handle(
        mongo,
        FakeEmbedding(),
        cfg={"mongodb": {"vector_search": "python_cosine"}},
        query="integration",
    )
    search_row = search["results"][0]
    assert search_row["qualification_framework"] == "simple_b2b"
    assert search_row["qualification_source_field"] == "qualification_latest"
    assert search_row["qualification_health_pct"] == expected_health
    assert search_row["gaps"] == ["next_step"]
    assert "summary_embedding" not in search_row

    snapshot = build_analytics_snapshot(
        cfg={},
        event_type="qf11_smoke",
        event_id="qf11-custom:event",
        deal=deal,
        occurred_at=datetime(2026, 6, 10, tzinfo=UTC),
    )
    assert snapshot["qualification_framework"] == "simple_b2b"
    assert snapshot["qualification_source_field"] == "qualification_latest"
    assert snapshot["qualification_health_pct"] == expected_health
    assert snapshot["qualification_gaps"] == ["next_step"]
    assert snapshot["meddpicc_filled_count"] is None
    assert snapshot["meddpicc_gap_count"] is None
    assert snapshot["meddpicc_gaps"] == []

    public_payload = json.dumps(
        {
            "review": review,
            "gaps": gaps,
            "metrics": metrics,
            "report": report,
            "search": search,
            "snapshot": snapshot,
        },
        ensure_ascii=False,
    )
    assert "secret raw note" not in public_payload
    assert "secret interaction content" not in public_payload
    assert "secret contact" not in public_payload
    assert "summary_embedding" not in public_payload


def test_custom_framework_config_lifecycle_feeds_interaction_and_reextract_smoke(
    tmp_path,
) -> None:
    user_config = tmp_path / "config.yaml"

    copy_preview = update_qualification_framework_config(
        config_path=user_config,
        template_key="simple_b2b",
        copy_as_key="founder_led_sales",
        copy_display_name="Founder-Led Sales",
    )
    assert copy_preview["ok"] is True
    assert copy_preview["dry_run"] is True
    assert copy_preview["storage_written"] is False
    assert copy_preview["framework_key"] == "founder_led_sales"
    assert copy_preview["preset_immutable"] is False
    assert user_config.exists() is False

    copy_apply = update_qualification_framework_config(
        config_path=user_config,
        template_key="simple_b2b",
        copy_as_key="founder_led_sales",
        copy_display_name="Founder-Led Sales",
        dry_run=False,
        confirmed_by_user=True,
    )
    cfg = _load_yaml(user_config)
    assert copy_apply["ok"] is True
    assert copy_apply["storage_written"] is True
    assert cfg["qualification"]["active_framework"] == "founder_led_sales"
    assert "founder_led_sales" in cfg["qualification"]["frameworks"]

    frameworks = list_qualification_frameworks_config(
        config_path=user_config,
        include_dimensions=True,
    )
    assert frameworks["active_framework"] == "founder_led_sales"
    active_listing = next(
        item for item in frameworks["frameworks"] if item["key"] == "founder_led_sales"
    )
    assert active_listing["source"] == "user_config"
    assert active_listing["active"] is True
    assert active_listing["valid"] is True

    active_framework = resolve_active_qualification_framework(cfg)
    assert active_framework.key == "founder_led_sales"
    assert active_framework.display_name == "Founder-Led Sales"

    mongo = FakeMongo(
        [
            {
                "deal_id": "qf11-life",
                "company": "Lifecycle Co",
                "industry": "SaaS",
                "deal_stage": "proposal",
                "deal_size_amount": 55_000_000,
                "deal_size_currency": "KRW",
                "deal_size_status": "quoted",
                "expected_close_date": "2026-06-30",
                "expected_close_date_source": "user_provided",
                "stage_history": [
                    {
                        "stage": "proposal",
                        "entered_at": "2026-06-01T00:00:00+00:00",
                    }
                ],
                "interactions": [],
                "meetings": [],
                "customer_themes": [],
                "meddpicc_latest": {"health_pct": 99.0, "filled_count": 7, "gaps": []},
            }
        ]
    )
    llm = FakeLLM(
        [
            json.dumps(
                {
                    "qualification": {
                        "business_need": {
                            "score": 5,
                            "evidence": "Reporting close is blocked.",
                        },
                        "buyer_owner": {
                            "score": 4,
                            "evidence": "COO owns the buying decision.",
                        },
                    },
                    "customer_themes": [],
                }
            ),
            "Customer confirmed the reporting blocker and COO ownership.",
        ]
    )

    interaction_result = add_interaction.handle(
        mongo=mongo,
        llm=llm,
        cfg=cfg,
        embedding_provider=None,
        deal_id="qf11-life",
        date="2026-06-11",
        interaction_type="email_thread",
        direction="inbound",
        content="Customer reply: reporting close is blocked; COO owns approval.",
        participants="buyer@example.com, ae@example.com",
        subject="Re: reporting workflow",
    )
    assert interaction_result["ok"] is True
    assert interaction_result["active_qualification_framework"] == "founder_led_sales"
    assert interaction_result["qualification_latest"]["framework_key"] == (
        "founder_led_sales"
    )
    assert interaction_result["qualification_latest"]["health_pct"] != 99.0
    saved_deal = mongo.get_deal("qf11-life")
    assert saved_deal is not None
    saved_interaction = saved_deal["interactions"][0]
    assert saved_interaction["qualification_framework"] == "founder_led_sales"
    assert saved_interaction["qualification_framework_hash"]

    active_payload = cfg["qualification"]["frameworks"]["founder_led_sales"]
    active_payload["dimensions"]["next_step"]["extraction_hint"] = (
        "Look for a concrete mutual action plan owner, date, and committed next step."
    )
    active_payload["dimensions"]["next_step"]["suggested_question"] = (
        "Who owns the next step, and what exact date is committed?"
    )
    update_apply = update_qualification_framework_config(
        config_path=user_config,
        framework_json=yaml.safe_dump(active_payload, sort_keys=False),
        dry_run=False,
        confirmed_by_user=True,
    )
    updated_cfg = _load_yaml(user_config)
    assert update_apply["ok"] is True
    assert updated_cfg["qualification"]["active_framework"] == "founder_led_sales"

    reextract_plan = backfill_qualification_reextract.handle(
        mongo=mongo,
        llm=None,
        cfg=updated_cfg,
        dry_run=True,
    )
    assert reextract_plan["ok"] is True
    assert reextract_plan["summary"]["candidate_count"] == 1
    assert reextract_plan["candidates"][0]["reason"] == "stale_framework_hash"
    assert reextract_plan["candidates"][0]["deal_id"] == "qf11-life"

    active_delete = delete_qualification_framework_config(
        config_path=user_config,
        framework_key="founder_led_sales",
    )
    assert active_delete["ok"] is False
    assert active_delete["error_code"] == "ACTIVE_FRAMEWORK_NOT_DELETABLE"

    set_builtin = set_active_qualification_framework_config(
        config_path=user_config,
        framework_key="meddpicc",
        dry_run=False,
        confirmed_by_user=True,
    )
    assert set_builtin["ok"] is True
    assert _load_yaml(user_config)["qualification"]["active_framework"] == "meddpicc"

    delete_apply = delete_qualification_framework_config(
        config_path=user_config,
        framework_key="founder_led_sales",
        dry_run=False,
        confirmed_by_user=True,
    )
    final_cfg = _load_yaml(user_config)
    assert delete_apply["ok"] is True
    assert delete_apply["storage_written"] is True
    assert "founder_led_sales" not in final_cfg["qualification"]["frameworks"]
    assert final_cfg["qualification"]["active_framework"] == "meddpicc"
