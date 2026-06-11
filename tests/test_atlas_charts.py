from __future__ import annotations

import json

import pytest

from deal_intel.reports.atlas_charts import (
    load_customer_themes_dashboard_spec,
    load_pipeline_trend_dashboard_spec,
    load_weekly_pipeline_dashboard_spec,
    render_chart_pipeline,
    render_customer_themes_dashboard_spec,
    render_pipeline_trend_dashboard_spec,
    render_weekly_pipeline_dashboard_spec,
)

REQUIRED_CHART_IDS = {
    "pipeline_kpis",
    "stage_breakdown",
    "health_bands",
    "attention_deals",
    "meddpicc_gap_distribution",
}
TREND_CHART_IDS = {
    "trend_kpis",
    "trend_delta_bars",
}
CUSTOMER_THEME_CHART_IDS = {
    "theme_overview",
    "decision_criteria_by_stage",
    "pain_by_industry",
    "theme_evidence_drilldown",
}


def test_weekly_pipeline_dashboard_spec_is_versioned_and_complete() -> None:
    spec = load_weekly_pipeline_dashboard_spec()

    assert spec["dashboard_title"] == "Weekly Pipeline Review"
    assert spec["version"] == 1
    assert spec["database"] == "deal_intel"
    assert spec["collection"] == "deals"
    assert {chart["id"] for chart in spec["charts"]} == REQUIRED_CHART_IDS
    assert all(isinstance(chart["pipeline"], list) for chart in spec["charts"])
    assert all(chart["pipeline"] for chart in spec["charts"])


def test_pipeline_trend_dashboard_spec_is_versioned_and_complete() -> None:
    spec = load_pipeline_trend_dashboard_spec()

    assert spec["dashboard_title"] == "Pipeline Trend Review"
    assert spec["version"] == 1
    assert spec["database"] == "deal_intel"
    assert spec["collection"] == "analytics_snapshots"
    assert {chart["id"] for chart in spec["charts"]} == TREND_CHART_IDS
    assert all(isinstance(chart["pipeline"], list) for chart in spec["charts"])
    assert all(chart["pipeline"] for chart in spec["charts"])


def test_customer_themes_dashboard_spec_is_versioned_and_complete() -> None:
    spec = load_customer_themes_dashboard_spec()

    assert spec["dashboard_title"] == "Customer Themes Review"
    assert spec["version"] == 1
    assert spec["database"] == "deal_intel"
    assert spec["collection"] == "deals"
    assert {chart["id"] for chart in spec["charts"]} == CUSTOMER_THEME_CHART_IDS
    assert all(isinstance(chart["pipeline"], list) for chart in spec["charts"])
    assert all(chart["pipeline"] for chart in spec["charts"])


def test_weekly_pipeline_dashboard_render_replaces_config_tokens() -> None:
    rendered = render_weekly_pipeline_dashboard_spec(
        {
            "reporting": {"timezone": "Asia/Seoul"},
            "metrics": {
                "health_bands": {"healthy_min": 75, "watch_min": 45},
                "overdue": {"grace_days": 2},
            },
            "pipeline": {
                "stuck_threshold_days": 99,
                "stuck_threshold_days_by_stage": {
                    "discovery": 3,
                    "qualification": 4,
                    "proposal": 5,
                    "negotiation": 6,
                },
            },
        },
        as_of="2026-06-09",
    )

    payload = json.dumps(rendered, ensure_ascii=False)
    assert "{{" not in payload
    assert rendered["parameters"] == {
        "as_of_datetime": "2026-06-09T00:00:00Z",
        "healthy_min": 75.0,
        "watch_min": 45.0,
        "overdue_grace_days": 2,
        "stuck_days": {
            "discovery": 3,
            "qualification": 4,
            "proposal": 5,
            "negotiation": 6,
        },
    }
    assert rendered["rendered_parameters"]["healthy_min"] == 75.0


def test_pipeline_trend_dashboard_render_replaces_window_tokens() -> None:
    rendered = render_pipeline_trend_dashboard_spec(
        {"reporting": {"timezone": "Asia/Seoul"}},
        as_of="2026-06-10",
        lookback_days=14,
    )

    payload = json.dumps(rendered, ensure_ascii=False)
    assert "{{" not in payload
    assert rendered["parameters"] == {
        "start_date": "2026-05-27",
        "end_date": "2026-06-10",
        "lookback_days": 14,
    }
    assert rendered["rendered_parameters"]["start_date"] == "2026-05-27"
    assert rendered["rendered_parameters"]["as_of_date"] == "2026-06-10"
    assert rendered["rendered_parameters"]["lookback_days"] == 14


def test_customer_themes_dashboard_render_has_no_placeholders() -> None:
    rendered = render_customer_themes_dashboard_spec(
        {"reporting": {"timezone": "Asia/Seoul"}},
        as_of="2026-06-10",
    )

    payload = json.dumps(rendered, ensure_ascii=False)
    assert "{{" not in payload
    assert rendered["rendered_parameters"]["as_of_date"] == "2026-06-10"


def test_chart_pipeline_rendering_returns_single_pipeline_and_rejects_unknown_id() -> None:
    pipeline = render_chart_pipeline(
        "pipeline_kpis",
        {},
        as_of="2026-06-09",
    )

    assert isinstance(pipeline, list)
    assert pipeline[0]["$match"]["archived"] == {"$ne": True}
    assert pipeline[1]["$addFields"]["_as_of"]["$dateFromString"]["dateString"] == (
        "2026-06-09T00:00:00Z"
    )
    with pytest.raises(ValueError, match="chart_id"):
        render_chart_pipeline("not-a-chart", {}, as_of="2026-06-09")


def test_chart_pipeline_rendering_supports_trend_dashboard() -> None:
    pipeline = render_chart_pipeline(
        "trend_kpis",
        {},
        dashboard="pipeline_trend",
        as_of="2026-06-10",
        lookback_days=7,
    )

    assert pipeline[0]["$match"]["as_of"] == {
        "$gte": "2026-06-03",
        "$lte": "2026-06-10",
    }
    assert pipeline[-1]["$project"]["window_start"] == {"$literal": "2026-06-03"}
    assert pipeline[-1]["$project"]["lookback_days"] == {"$literal": 7}


def test_chart_pipeline_rendering_supports_customer_themes_dashboard() -> None:
    pipeline = render_chart_pipeline(
        "theme_overview",
        {},
        dashboard="customer_themes",
        as_of="2026-06-10",
    )

    assert pipeline[0]["$match"]["archived"] == {"$ne": True}
    assert pipeline[0]["$match"]["deal_stage"] == {"$nin": ["won", "lost"]}
    assert pipeline[-1]["$project"]["theme_key"] == "$_id"


def test_weekly_pipeline_chart_pipelines_exclude_archived_deals_first() -> None:
    rendered = render_weekly_pipeline_dashboard_spec({}, as_of="2026-06-09")

    for chart in rendered["charts"]:
        assert chart["pipeline"][0] == {"$match": {"archived": {"$ne": True}}}


def test_atlas_chart_pipelines_do_not_touch_sensitive_fields() -> None:
    rendered = render_weekly_pipeline_dashboard_spec({}, as_of="2026-06-09")
    trend_rendered = render_pipeline_trend_dashboard_spec({}, as_of="2026-06-10")
    theme_rendered = render_customer_themes_dashboard_spec({}, as_of="2026-06-10")

    payload = json.dumps([rendered, trend_rendered, theme_rendered], ensure_ascii=False)
    assert "raw_notes" not in payload
    assert "contacts" not in payload
    assert "summary_embedding" not in payload
