from __future__ import annotations

from copy import deepcopy

from deal_intel.reports.dashboard_crosscheck import (
    build_weekly_pipeline_dashboard_crosscheck,
)


def _metrics_result() -> dict:
    return {
        "as_of": "2026-06-09",
        "kpis": {
            "deal_count": 4,
            "active_deal_count": 2,
            "open_deal_count": 3,
            "stalled_deal_count": 1,
            "terminal_deal_count": 1,
            "active_pipeline_value_krw": 300,
            "open_pipeline_value_krw": 350,
            "avg_health_pct": 85.5,
            "health_coverage_pct": 100.0,
            "health_assessed_count": 2,
            "stuck_deal_count": 0,
            "overdue_deal_count": 1,
            "attention_deal_count": 2,
        },
        "stage_breakdown": [
            {
                "stage": "discovery",
                "count": 1,
                "pipeline_value_krw": 100,
                "avg_health_pct": 90.0,
                "health_coverage_pct": 100.0,
                "stuck_count": 0,
                "overdue_count": 1,
            },
            {
                "stage": "proposal",
                "count": 1,
                "pipeline_value_krw": 200,
                "avg_health_pct": 81.0,
                "health_coverage_pct": 100.0,
                "stuck_count": 0,
                "overdue_count": 0,
            },
            {
                "stage": "stalled",
                "count": 1,
                "pipeline_value_krw": 50,
                "avg_health_pct": 62.9,
                "health_coverage_pct": 100.0,
                "stuck_count": 0,
                "overdue_count": 0,
            },
            {
                "stage": "qualification",
                "count": 0,
                "pipeline_value_krw": 0,
                "avg_health_pct": None,
                "health_coverage_pct": None,
                "stuck_count": 0,
                "overdue_count": 0,
            },
            {
                "stage": "won",
                "count": 1,
                "pipeline_value_krw": 0,
                "avg_health_pct": 95.0,
                "health_coverage_pct": 100.0,
                "stuck_count": 0,
                "overdue_count": 0,
            },
        ],
        "health_bands": {
            "healthy": 2,
            "watch": 1,
            "at_risk": 0,
            "unassessed": 1,
        },
    }


def _report_result() -> dict:
    return {
        "as_of": "2026-06-09",
        "metrics": {
            "open_deal_count": 3,
            "pipeline_value_krw": 350,
            "attention_deal_count": 2,
            "overdue_count": 1,
            "stuck_count": 0,
            "stalled_count": 1,
        },
        "artifacts": {
            "csv": {"path": "C:/tmp/report.csv"},
            "markdown": {"path": "C:/tmp/report.md"},
        },
        "csv_path": "C:/tmp/report.csv",
        "markdown_path": "C:/tmp/report.md",
    }


def _atlas_results() -> dict:
    return {
        "pipeline_kpis": [
            {
                "deal_count": 4,
                "active_deal_count": 2,
                "open_deal_count": 3,
                "stalled_deal_count": 1,
                "terminal_deal_count": 1,
                "active_pipeline_value_krw": 300,
                "open_pipeline_value_krw": 350,
                "avg_health_pct": 85.5,
                "health_coverage_pct": 100.0,
                "health_assessed_count": 2,
                "stuck_deal_count": 0,
                "overdue_deal_count": 1,
                "attention_deal_count": 2,
            }
        ],
        "stage_breakdown": [
            {
                "stage": "discovery",
                "count": 1,
                "pipeline_value_krw": 100,
                "avg_health_pct": 90.0,
                "health_coverage_pct": 100.0,
                "stuck_count": 0,
                "overdue_count": 1,
            },
            {
                "stage": "proposal",
                "count": 1,
                "pipeline_value_krw": 200,
                "avg_health_pct": 81.0,
                "health_coverage_pct": 100.0,
                "stuck_count": 0,
                "overdue_count": 0,
            },
            {
                "stage": "stalled",
                "count": 1,
                "pipeline_value_krw": 50,
                "avg_health_pct": 62.9,
                "health_coverage_pct": 100.0,
                "stuck_count": 0,
                "overdue_count": 0,
            },
            {
                "stage": "won",
                "count": 1,
                "pipeline_value_krw": 0,
                "avg_health_pct": 95.0,
                "health_coverage_pct": 100.0,
                "stuck_count": 0,
                "overdue_count": 0,
            },
        ],
        "health_bands": [
            {"health_band": "healthy", "count": 2},
            {"health_band": "watch", "count": 1},
            {"health_band": "unassessed", "count": 1},
        ],
        "attention_deals": [{"company": "A"}, {"company": "B"}],
    }


def test_weekly_pipeline_dashboard_crosscheck_passes_matching_sources() -> None:
    result = build_weekly_pipeline_dashboard_crosscheck(
        metrics_result=_metrics_result(),
        report_result=_report_result(),
        atlas_results=_atlas_results(),
    )

    assert result["ok"] is True
    assert result["as_of"] == "2026-06-09"
    assert result["mismatches"] == []
    assert result["csv_path"] == "C:/tmp/report.csv"
    assert any(
        check["metric"] == "open_pipeline_value_krw"
        and check["values"] == {
            "get_metrics": 350,
            "csv_markdown": 350,
            "atlas": 350,
        }
        for check in result["checks"]
    )
    assert any(
        check["metric"] == "health_bands.at_risk"
        and check["values"] == {"get_metrics": 0, "atlas": 0}
        for check in result["checks"]
    )
    assert any(
        check["metric"] == "stage_breakdown.qualification.avg_health_pct"
        and check["ok"] is True
        and check["values"] == {"get_metrics": None, "atlas": None}
        for check in result["checks"]
    )


def test_weekly_pipeline_dashboard_crosscheck_reports_mismatches() -> None:
    atlas_results = deepcopy(_atlas_results())
    atlas_results["pipeline_kpis"][0]["open_pipeline_value_krw"] = 999

    result = build_weekly_pipeline_dashboard_crosscheck(
        metrics_result=_metrics_result(),
        report_result=_report_result(),
        atlas_results=atlas_results,
    )

    assert result["ok"] is False
    assert result["mismatches"] == [
        {
            "metric": "open_pipeline_value_krw",
            "expected_source": "get_metrics",
            "expected": 350,
            "actual_source": "atlas",
            "actual": 999,
            "values": {
                "get_metrics": 350,
                "csv_markdown": 350,
                "atlas": 999,
            },
        }
    ]
