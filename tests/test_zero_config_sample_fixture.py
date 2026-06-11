from __future__ import annotations

import json
from datetime import date

from deal_intel.reports.weekly_pipeline import build_weekly_pipeline_rows
from deal_intel.schema.customer_theme_insights import (
    build_customer_theme_breakdown,
    build_customer_theme_evidence,
)
from deal_intel.schema.deal_gaps import build_deal_gaps_summary
from deal_intel.schema.deal_review import build_deal_review
from deal_intel.schema.pipeline_metrics import build_pipeline_health_summary
from deal_intel.schema.pipeline_trends import build_pipeline_trend_summary
from deal_intel.storage.local_sample_fixture import (
    SENSITIVE_FIELD_NAMES,
    ZERO_CONFIG_SAMPLE_AS_OF,
    load_zero_config_sample_deals,
    load_zero_config_sample_snapshots,
    validate_zero_config_sample_fixture,
)

AS_OF = date.fromisoformat(ZERO_CONFIG_SAMPLE_AS_OF)


def test_zero_config_sample_fixture_is_safe_and_varied() -> None:
    deals = load_zero_config_sample_deals()
    snapshots = load_zero_config_sample_snapshots()
    validation = validate_zero_config_sample_fixture(
        deals=deals,
        snapshots=snapshots,
    )

    assert validation["ok"] is True
    assert validation["errors"] == []
    assert validation["summary"]["deal_count"] >= 10
    assert validation["summary"]["snapshot_count"] >= 20

    stages = {deal["deal_stage"] for deal in deals}
    assert stages >= {
        "discovery",
        "qualification",
        "proposal",
        "negotiation",
        "stalled",
        "won",
        "lost",
    }
    statuses = {deal["deal_size_status"] for deal in deals}
    assert statuses >= {
        "unknown",
        "rough_estimate",
        "customer_budget",
        "quoted",
        "strategic_zero",
    }
    interaction_types = {
        interaction.get("interaction_type")
        for deal in deals
        for interaction in deal.get("interactions", [])
        if isinstance(interaction, dict)
    }
    assert {"meeting", "email_thread", "user_interview"} <= interaction_types

    payload = json.dumps(
        {"deals": deals, "snapshots": snapshots},
        ensure_ascii=False,
    )
    for field_name in SENSITIVE_FIELD_NAMES:
        assert field_name not in payload
    assert "raw_content" not in payload


def test_zero_config_sample_fixture_drives_pipeline_metrics_and_report() -> None:
    deals = load_zero_config_sample_deals()

    summary = build_pipeline_health_summary(deals, as_of=AS_OF)
    report = build_weekly_pipeline_rows(deals, as_of=AS_OF)

    assert summary["kpis"]["active_deal_count"] > 0
    assert summary["kpis"]["open_deal_count"] > 0
    assert summary["kpis"]["open_pipeline_value_krw"] > 0
    assert summary["kpis"]["attention_deal_count"] > 0
    assert summary["health_bands"]["healthy"] > 0
    assert summary["health_bands"]["unassessed"] > 0
    assert report["row_count"] == summary["kpis"]["open_deal_count"]
    assert any(row["primary_pain"] for row in report["rows"])
    assert any(row["primary_decision_criteria"] for row in report["rows"])


def test_zero_config_sample_fixture_drives_deal_review_and_gaps() -> None:
    deals = load_zero_config_sample_deals()
    by_id = {deal["deal_id"]: deal for deal in deals}

    review = build_deal_review(by_id["sample-orion-insurance"], as_of=AS_OF)
    gaps = build_deal_gaps_summary(
        deals,
        as_of=AS_OF,
        min_priority="medium",
        limit=20,
    )

    assert review["health_interpretation"]["review_band"] == "confirmed_risk"
    assert review["health_interpretation"]["alert_level"] == "alert"
    assert review["confirmed_risks"]
    assert gaps["summary"]["returned_deal_count"] > 0
    assert any(
        deal["deal_id"] == "sample-orion-insurance" for deal in gaps["deals"]
    )


def test_zero_config_sample_fixture_drives_customer_theme_views() -> None:
    deals = load_zero_config_sample_deals()

    breakdown = build_customer_theme_breakdown(
        deals,
        dimension="decision_criteria",
        stage="active",
        group_by="stage",
        top_k=5,
    )
    evidence = build_customer_theme_evidence(
        deals,
        theme_key="compliance_security",
        dimension="decision_criteria",
        stage="all",
        limit=5,
        min_importance=4,
    )

    assert breakdown["summary"]["group_count"] >= 3
    assert breakdown["summary"]["deals_with_evidence"] > 0
    assert evidence["summary"]["returned_count"] > 0
    assert all("raw_notes" not in row for row in evidence["evidence"])

    source_evidence = build_customer_theme_evidence(
        deals,
        theme_key="reporting_visibility",
        dimension="all",
        stage="active",
        limit=20,
        min_importance=1,
    )
    source_types = {
        row.get("interaction_type")
        for row in source_evidence["evidence"]
        if row.get("interaction_type") in {"email_thread", "user_interview"}
    }
    assert source_types == {"email_thread", "user_interview"}
    encoded = json.dumps(source_evidence, ensure_ascii=False)
    assert "raw_notes" not in encoded
    assert "raw_content" not in encoded

    email_evidence = build_customer_theme_evidence(
        deals,
        theme_key="reporting_visibility",
        dimension="all",
        stage="active",
        interaction_type="email_thread",
    )
    interview_evidence = build_customer_theme_evidence(
        deals,
        theme_key="reporting_visibility",
        dimension="all",
        stage="active",
        interaction_type="user_interview",
    )
    assert email_evidence["summary"]["evidence_count"] == 1
    assert interview_evidence["summary"]["evidence_count"] == 1


def test_zero_config_sample_fixture_drives_pipeline_trend() -> None:
    snapshots = load_zero_config_sample_snapshots()

    result = build_pipeline_trend_summary(
        snapshots,
        as_of=AS_OF,
        lookback_days=7,
    )

    assert result["snapshot_count"] >= 20
    assert result["deal_count"] >= 10
    assert result["start"]["open_deal_count"] > result["end"]["open_deal_count"]
    assert result["delta"]["won_deal_count"] > 0
    assert result["delta"]["lost_deal_count"] > 0
    assert result["stage_changes"]["transition_count"] > 0
    assert result["warnings"] == []
