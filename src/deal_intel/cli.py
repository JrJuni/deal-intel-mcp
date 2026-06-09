from __future__ import annotations

import json
from pathlib import Path

import typer

app = typer.Typer(help="deal-intel CLI")


@app.command("login-chatgpt")
def login_chatgpt(
    force: bool = typer.Option(
        False,
        "--force",
        help="Re-authenticate even with a valid cached token",
    ),
) -> None:
    """Authenticate with ChatGPT OAuth (opens browser). Run once before first use."""
    from deal_intel._env import load_config
    from deal_intel.providers import llm as _llm

    cfg = load_config()
    # Force chatgpt_oauth regardless of defaults so this command always works
    cfg.setdefault("llm", {})["provider"] = "chatgpt_oauth"
    provider = _llm.make_llm_provider(cfg)
    assert isinstance(provider, _llm.ChatGPTOAuthProvider)
    result = provider.login(force=force)
    typer.echo(f"ok  model={result['model']}  token_path={result['token_path']}")


@app.command("backfill-customer-themes")
def backfill_customer_themes(
    apply: bool = typer.Option(
        False,
        "--apply",
        help="Write extracted themes to MongoDB. Without this flag, run as dry-run.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Reprocess meetings that already have customer_themes.",
    ),
    limit: int = typer.Option(0, "--limit", min=0, help="Maximum deals to scan; 0 means all."),
) -> None:
    """Extract customer themes for existing meeting records."""
    from deal_intel import _context
    from deal_intel.tools import backfill_customer_themes as _t

    result = _t.handle(
        mongo=_context.mongo(),
        llm=_context.llm_provider(),
        limit=limit,
        force=force,
        dry_run=not apply,
    )
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))


@app.command("render-atlas-dashboard")
def render_atlas_dashboard(
    as_of: str | None = typer.Option(
        None,
        "--as-of",
        help="Business date for rendered Atlas Charts placeholders, YYYY-MM-DD.",
    ),
    dashboard: str = typer.Option(
        "weekly_pipeline_review",
        "--dashboard",
        help="Dashboard id: weekly_pipeline_review or pipeline_trend.",
    ),
    chart_id: str | None = typer.Option(
        None,
        "--chart-id",
        help="Optional chart id. If omitted, render the full dashboard spec.",
    ),
    lookback_days: int = typer.Option(
        7,
        "--lookback-days",
        help="Trend lookback window, used only by the pipeline_trend dashboard.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Optional path to write rendered JSON. Prints to stdout when omitted.",
    ),
) -> None:
    """Render Atlas Charts dashboard JSON for Atlas UI copy/paste."""
    from deal_intel._env import load_config
    from deal_intel.reports.atlas_charts import (
        render_chart_pipeline,
        render_dashboard_spec,
    )

    cfg = load_config()
    try:
        payload = (
            render_chart_pipeline(
                chart_id,
                cfg,
                as_of=as_of,
                lookback_days=lookback_days,
                dashboard=dashboard,
            )
            if chart_id
            else render_dashboard_spec(
                dashboard,
                cfg,
                as_of=as_of,
                lookback_days=lookback_days,
            )
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if output is None:
        typer.echo(text)
        return

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text + "\n", encoding="utf-8")
    typer.echo(str(output.resolve()))


@app.command("crosscheck-weekly-dashboard")
def crosscheck_weekly_dashboard(
    as_of: str | None = typer.Option(
        None,
        "--as-of",
        help="Business date for cross-checking metrics, reports, and Atlas pipelines.",
    ),
    output_dir: Path | None = typer.Option(
        None,
        "--output-dir",
        help="Directory for the generated CSV/Markdown report artifacts.",
    ),
) -> None:
    """Cross-check get_metrics, weekly reports, and Atlas Charts pipelines."""
    from deal_intel import _context
    from deal_intel.reports.atlas_charts import render_chart_pipeline
    from deal_intel.reports.dashboard_crosscheck import (
        build_weekly_pipeline_dashboard_crosscheck,
    )
    from deal_intel.tools import export_report as _export_report
    from deal_intel.tools import get_metrics as _get_metrics

    cfg = _context.config()
    mongo = _context.mongo()
    metrics_result = _get_metrics.handle(
        mongo=mongo,
        cfg=cfg,
        metric_type="pipeline_health",
        as_of=as_of,
    )
    report_result = _export_report.handle(
        mongo=mongo,
        cfg=cfg,
        report_type="weekly_pipeline",
        output_dir=str(output_dir) if output_dir is not None else None,
        as_of=as_of,
    )
    atlas_results = {
        chart_id: mongo.aggregate_deals(
            render_chart_pipeline(chart_id, cfg, as_of=as_of)
        )
        for chart_id in (
            "pipeline_kpis",
            "stage_breakdown",
            "health_bands",
            "attention_deals",
            "meddpicc_gap_distribution",
        )
    }
    result = build_weekly_pipeline_dashboard_crosscheck(
        metrics_result=metrics_result,
        report_result=report_result,
        atlas_results=atlas_results,
    )
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["ok"]:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
