from __future__ import annotations

import json

from typer.testing import CliRunner

from deal_intel.cli import app


def test_render_atlas_dashboard_cli_prints_single_chart_pipeline() -> None:
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "render-atlas-dashboard",
            "--as-of",
            "2026-06-09",
            "--chart-id",
            "pipeline_kpis",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert isinstance(payload, list)
    assert payload[0]["$addFields"]["_as_of"]["$dateFromString"]["dateString"] == (
        "2026-06-09T00:00:00Z"
    )
    assert "{{" not in result.stdout


def test_render_atlas_dashboard_cli_writes_full_spec(tmp_path) -> None:
    runner = CliRunner()
    output = tmp_path / "weekly_pipeline_review.rendered.json"

    result = runner.invoke(
        app,
        [
            "render-atlas-dashboard",
            "--as-of",
            "2026-06-09",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0
    assert str(output.resolve()) in result.stdout
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["dashboard_title"] == "Weekly Pipeline Review"
    assert {chart["id"] for chart in payload["charts"]} == {
        "pipeline_kpis",
        "stage_breakdown",
        "health_bands",
        "attention_deals",
        "meddpicc_gap_distribution",
    }
    assert "{{" not in output.read_text(encoding="utf-8")


def test_render_atlas_dashboard_cli_rejects_unknown_chart_id() -> None:
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "render-atlas-dashboard",
            "--as-of",
            "2026-06-09",
            "--chart-id",
            "unknown",
        ],
    )

    assert result.exit_code != 0
    assert "chart_id" in result.output
