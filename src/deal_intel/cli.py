from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import typer

app = typer.Typer(help="deal-intel CLI")

SENSITIVE_RESULT_KEYS = {"raw_notes", "contacts", "summary_embedding"}
ALERT_RANK = {"alert": 3, "watch": 2, "info": 1, "none": 0}
UNCERTAINTY_RANK = {"high": 2, "medium": 1, "low": 0}
ISSUE_SEVERITY_RANK = {"high": 3, "medium": 2, "low": 1}


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
        help="Dashboard id: weekly_pipeline_review, pipeline_trend, or customer_themes.",
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


@app.command("smoke-deal-review")
def smoke_deal_review(
    deal_id: str | None = typer.Option(
        None,
        "--deal-id",
        help="Exact deal_id to review. Overrides --company and --limit selection.",
    ),
    company: str | None = typer.Option(
        None,
        "--company",
        help="Case-insensitive company name substring to review.",
    ),
    limit: int = typer.Option(
        5,
        "--limit",
        min=1,
        max=20,
        help="Maximum deals to review when --deal-id is omitted.",
    ),
    as_of: str | None = typer.Option(
        None,
        "--as-of",
        help="Business date for deal review, YYYY-MM-DD.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Print full structured JSON instead of concise text.",
    ),
) -> None:
    """Run local read-only get_deal_review smoke checks without a Desktop MCP client."""
    from deal_intel import _context
    from deal_intel.errors import MCPError
    from deal_intel.tools import get_deal_review as _get_deal_review

    cfg = _context.config()
    mongo = _context.mongo()
    try:
        deals = mongo.list_deals_for_metrics()
        selected = _select_deal_review_smoke_deals(
            deals,
            deal_id=deal_id,
            company=company,
            limit=limit,
        )
        results = [
            _get_deal_review.handle(
                mongo=mongo,
                cfg=cfg,
                deal_id=str(deal["deal_id"]),
                as_of=as_of,
            )
            for deal in selected
        ]
    except MCPError as exc:
        _emit_smoke_error(exc.to_envelope(), json_output=json_output)
        raise typer.Exit(code=1) from exc
    except ValueError as exc:
        _emit_smoke_error(
            {
                "ok": False,
                "error_code": "INVALID_INPUT",
                "stage": "preflight",
                "message": str(exc),
                "hint": None,
                "retryable": False,
            },
            json_output=json_output,
        )
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        _emit_smoke_error(
            {
                "ok": False,
                "error_code": "INTERNAL",
                "stage": "cli",
                "message": f"{type(exc).__name__}: {exc}",
                "hint": None,
                "retryable": False,
            },
            json_output=json_output,
        )
        raise typer.Exit(code=1) from exc

    payload = {
        "ok": True,
        "as_of": results[0].get("as_of") if results else as_of,
        "timezone": results[0].get("timezone") if results else None,
        "count": len(results),
        "sensitive_field_check": {"ok": True},
        "results": results,
    }
    if _contains_sensitive_result_key(payload):
        payload["ok"] = False
        payload["sensitive_field_check"]["ok"] = False
        _emit_smoke_error(
            {
                "ok": False,
                "error_code": "SENSITIVE_FIELD_EXPOSED",
                "stage": "cli",
                "message": "Smoke result contains a restricted sensitive field key.",
                "hint": {"blocked_keys": sorted(SENSITIVE_RESULT_KEYS)},
                "retryable": False,
            },
            json_output=json_output,
        )
        raise typer.Exit(code=2)

    if json_output:
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    typer.echo(_format_deal_review_smoke(payload))


@app.command("smoke-deal-review-audit")
def smoke_deal_review_audit(
    company: str | None = typer.Option(
        None,
        "--company",
        help="Case-insensitive company name substring to include.",
    ),
    stage: str | None = typer.Option(
        None,
        "--stage",
        help="Exact pipeline stage to include.",
    ),
    industry: str | None = typer.Option(
        None,
        "--industry",
        help="Exact industry value to include.",
    ),
    limit: int = typer.Option(
        50,
        "--limit",
        min=1,
        max=200,
        help="Maximum deals to review.",
    ),
    as_of: str | None = typer.Option(
        None,
        "--as-of",
        help="Business date for deal review, YYYY-MM-DD.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Print full structured JSON instead of concise text.",
    ),
    fail_on_issues: bool = typer.Option(
        False,
        "--fail-on-issues",
        help="Exit with code 2 when the audit finds review-quality issues.",
    ),
) -> None:
    """Audit all selected deal reviews for payload quality and decision usefulness."""
    from deal_intel import _context
    from deal_intel.schema.deal_review import build_deal_review
    from deal_intel.schema.metrics import (
        VALID_STAGES,
        HealthBandThresholds,
        PipelineTimingSettings,
        ReportingContext,
    )

    cfg = _context.config()
    mongo = _context.mongo()
    try:
        if stage is not None and stage.strip() and stage.strip() not in VALID_STAGES:
            raise ValueError(f"stage {stage.strip()!r} is not valid")
        reporting = ReportingContext.from_config(cfg, as_of=as_of)
        health_thresholds = HealthBandThresholds.from_config(cfg)
        timing_settings = PipelineTimingSettings.from_config(cfg)
        deals = mongo.list_deals_for_metrics()
        selected = _select_deal_review_audit_deals(
            deals,
            company=company,
            stage=stage,
            industry=industry,
            limit=limit,
        )
        results = []
        for deal in selected:
            review = build_deal_review(
                deal,
                as_of=reporting.as_of,
                health_thresholds=health_thresholds,
                timing_settings=timing_settings,
            )
            review["_audit_actual_close_date"] = deal.get("actual_close_date")
            review["_audit_close_reason"] = deal.get("close_reason")
            results.append(
                {
                    "ok": True,
                    **reporting.to_dict(),
                    "review": review,
                }
            )
    except ValueError as exc:
        _emit_smoke_error(
            {
                "ok": False,
                "error_code": "INVALID_INPUT",
                "stage": "preflight",
                "message": str(exc),
                "hint": None,
                "retryable": False,
            },
            json_output=json_output,
        )
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        _emit_smoke_error(
            {
                "ok": False,
                "error_code": "INTERNAL",
                "stage": "cli",
                "message": f"{type(exc).__name__}: {exc}",
                "hint": None,
                "retryable": False,
            },
            json_output=json_output,
        )
        raise typer.Exit(code=1) from exc

    payload = _build_deal_review_audit_payload(
        results,
        filters={
            "company": company.strip() if company and company.strip() else None,
            "stage": stage.strip() if stage and stage.strip() else None,
            "industry": industry.strip() if industry and industry.strip() else None,
            "limit": limit,
        },
    )
    if _contains_sensitive_result_key(payload):
        payload["ok"] = False
        payload["sensitive_field_check"]["ok"] = False
        _emit_smoke_error(
            {
                "ok": False,
                "error_code": "SENSITIVE_FIELD_EXPOSED",
                "stage": "cli",
                "message": "Audit result contains a restricted sensitive field key.",
                "hint": {"blocked_keys": sorted(SENSITIVE_RESULT_KEYS)},
                "retryable": False,
            },
            json_output=json_output,
        )
        raise typer.Exit(code=2)

    if json_output:
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        typer.echo(_format_deal_review_audit(payload))

    if fail_on_issues and payload["summary"]["quality_issue_count"] > 0:
        raise typer.Exit(code=2)


def _select_deal_review_smoke_deals(
    deals: list[dict],
    *,
    deal_id: str | None,
    company: str | None,
    limit: int,
) -> list[dict]:
    if deal_id is not None and deal_id.strip():
        needle = deal_id.strip()
        for deal in deals:
            if deal.get("deal_id") == needle:
                return [deal]
        raise ValueError(f"deal_id {needle!r} not found")

    selected = deals
    if company is not None and company.strip():
        needle = company.strip().casefold()
        selected = [
            deal
            for deal in deals
            if needle in str(deal.get("company") or "").casefold()
        ]
        if not selected:
            raise ValueError(f"company containing {company.strip()!r} not found")

    selected = [
        deal
        for deal in selected
        if isinstance(deal.get("deal_id"), str) and deal.get("deal_id")
    ]
    if not selected:
        raise ValueError("no deals available for smoke review")
    return selected[:limit]


def _select_deal_review_audit_deals(
    deals: list[dict],
    *,
    company: str | None,
    stage: str | None,
    industry: str | None,
    limit: int,
) -> list[dict]:
    selected = [
        deal
        for deal in deals
        if isinstance(deal.get("deal_id"), str) and deal.get("deal_id")
    ]
    if company is not None and company.strip():
        needle = company.strip().casefold()
        selected = [
            deal
            for deal in selected
            if needle in str(deal.get("company") or "").casefold()
        ]
    if stage is not None and stage.strip():
        stage_value = stage.strip()
        selected = [
            deal for deal in selected if deal.get("deal_stage") == stage_value
        ]
    if industry is not None and industry.strip():
        industry_value = industry.strip()
        selected = [
            deal for deal in selected if deal.get("industry") == industry_value
        ]
    if not selected:
        raise ValueError("no deals matched the audit filters")
    return selected[:limit]


def _build_deal_review_audit_payload(results: list[dict], *, filters: dict) -> dict:
    rows = [_build_deal_review_audit_row(result.get("review") or {}) for result in results]
    rows.sort(key=_deal_review_audit_sort_key)
    quality_issues = [
        issue
        for row in rows
        for issue in row["quality_issues"]
    ]
    summary = {
        "reviewed_count": len(rows),
        "quality_issue_count": len(quality_issues),
        "quality_issue_deal_count": sum(1 for row in rows if row["quality_issues"]),
        "alert_level_counts": _counter_dict(row["alert_level"] for row in rows),
        "uncertainty_counts": _counter_dict(row["uncertainty_level"] for row in rows),
        "review_band_counts": _counter_dict(row["review_band"] for row in rows),
        "warning_counts": _counter_dict(
            warning for row in rows for warning in row["warnings"]
        ),
        "quality_issue_counts": _counter_dict(
            issue["issue_id"] for issue in quality_issues
        ),
        "high_uncertainty_deal_count": sum(
            1 for row in rows if row["uncertainty_level"] == "high"
        ),
        "missing_information_deal_count": sum(
            1 for row in rows if row["missing_information_count"] > 0
        ),
        "confirmed_risk_deal_count": sum(
            1 for row in rows if row["confirmed_risk_count"] > 0
        ),
    }
    return {
        "ok": True,
        "as_of": results[0].get("as_of") if results else None,
        "timezone": results[0].get("timezone") if results else None,
        "generated_at": results[0].get("generated_at") if results else None,
        "filters": filters,
        "summary": summary,
        "sensitive_field_check": {"ok": True},
        "deals": rows,
    }


def _build_deal_review_audit_row(review: dict) -> dict:
    interpretation = review.get("health_interpretation") or {}
    warnings = [str(item) for item in review.get("warnings") or []]
    quality_issues = _audit_deal_review_quality(review)
    return {
        "deal_id": review.get("deal_id"),
        "company": review.get("company"),
        "industry": review.get("industry"),
        "deal_stage": review.get("deal_stage"),
        "deal_size_krw": review.get("deal_size_krw"),
        "deal_size_status": review.get("deal_size_status"),
        "expected_close_date": review.get("expected_close_date"),
        "legacy_health_pct": interpretation.get("legacy_health_pct"),
        "health_band": interpretation.get("health_band"),
        "evidence_coverage_pct": interpretation.get("evidence_coverage_pct"),
        "review_band": interpretation.get("review_band"),
        "alert_level": interpretation.get("alert_level"),
        "uncertainty_level": interpretation.get("uncertainty_level"),
        "attention_reasons": review.get("attention_reasons") or [],
        "missing_information_count": len(review.get("missing_information") or []),
        "confirmed_risk_count": len(review.get("confirmed_risks") or []),
        "recommended_question_count": len(review.get("recommended_questions") or []),
        "recommended_action_count": len(review.get("recommended_actions") or []),
        "warnings": warnings,
        "quality_issues": quality_issues,
    }


def _audit_deal_review_quality(review: dict) -> list[dict]:
    interpretation = review.get("health_interpretation") or {}
    warnings = set(str(item) for item in review.get("warnings") or [])
    missing = review.get("missing_information") or []
    risks = review.get("confirmed_risks") or []
    questions = review.get("recommended_questions") or []
    actions = review.get("recommended_actions") or []
    review_band = interpretation.get("review_band")
    alert_level = interpretation.get("alert_level")
    health_band = interpretation.get("health_band")
    coverage = interpretation.get("evidence_coverage_pct")
    stage = review.get("deal_stage")
    issues = []

    if "win_probability_suppressed" not in warnings:
        issues.append(
            _quality_issue(
                "missing_win_probability_suppression",
                "high",
                "Review must explicitly suppress uncalibrated win probability.",
            )
        )

    if _is_low_coverage(coverage) and health_band == "healthy":
        if "overconfidence_warning" not in warnings:
            issues.append(
                _quality_issue(
                    "overconfidence_warning_missing",
                    "high",
                    "Healthy-looking low-evidence deals must warn about overconfidence.",
                )
            )
        if review_band == "verified_healthy":
            issues.append(
                _quality_issue(
                    "verified_healthy_with_low_coverage",
                    "high",
                    "Low-evidence deals must not be classified as verified healthy.",
                )
            )

    if review_band == "confirmed_risk":
        if alert_level != "alert":
            issues.append(
                _quality_issue(
                    "confirmed_risk_without_alert",
                    "high",
                    "Confirmed risk reviews must use alert level.",
                )
            )
        if not risks:
            issues.append(
                _quality_issue(
                    "confirmed_risk_without_risk_rows",
                    "high",
                    "Confirmed risk reviews must include concrete risk rows.",
                )
            )

    if risks and alert_level == "none":
        issues.append(
            _quality_issue(
                "risk_rows_without_attention_level",
                "medium",
                "Reviews with confirmed risk rows must be at least watch-level.",
            )
        )

    if interpretation.get("uncertainty_level") == "high" and not missing:
        if "insufficient_evidence" not in warnings:
            issues.append(
                _quality_issue(
                    "high_uncertainty_without_gap_or_warning",
                    "medium",
                    "High uncertainty must be backed by missing information or warning.",
                )
            )

    if missing and not questions:
        issues.append(
            _quality_issue(
                "missing_information_without_questions",
                "medium",
                "Missing information must produce follow-up questions.",
            )
        )

    if risks and not actions:
        issues.append(
            _quality_issue(
                "confirmed_risks_without_actions",
                "medium",
                "Confirmed risks must produce recommended actions.",
            )
        )

    missing_fields = {str(item.get("field")) for item in missing if isinstance(item, dict)}
    actual_close_date = review.get("actual_close_date") or review.get(
        "_audit_actual_close_date"
    )
    close_reason = review.get("close_reason") or review.get("_audit_close_reason")
    if stage in {"won", "lost"} and "actual_close_date" not in missing_fields:
        if not actual_close_date:
            issues.append(
                _quality_issue(
                    "closed_actual_close_gap_not_reported",
                    "medium",
                    "Closed deals missing actual close date must surface that gap.",
                )
            )
    if stage == "lost" and "close_reason" not in missing_fields:
        if not close_reason:
            issues.append(
                _quality_issue(
                    "lost_close_reason_gap_not_reported",
                    "medium",
                    "Lost deals missing close reason must surface that gap.",
                )
            )

    if _guidance_contains_percent_estimate(review):
        issues.append(
            _quality_issue(
                "percent_estimate_in_guidance",
                "high",
                "Guidance must not include uncalibrated percentage estimates.",
            )
        )

    return issues


def _quality_issue(issue_id: str, severity: str, reason: str) -> dict:
    return {"issue_id": issue_id, "severity": severity, "reason": reason}


def _is_low_coverage(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value < 70


def _guidance_contains_percent_estimate(review: dict) -> bool:
    guidance = []
    for key in (
        "recommended_questions",
        "recommended_actions",
        "confirmed_risks",
        "known_signals",
        "missing_information",
    ):
        guidance.extend(_string_values(review.get(key)))
    return any("%" in item for item in guidance)


def _string_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        result = []
        for child in value.values():
            result.extend(_string_values(child))
        return result
    if isinstance(value, list):
        result = []
        for child in value:
            result.extend(_string_values(child))
        return result
    return []


def _deal_review_audit_sort_key(row: dict) -> tuple:
    max_issue_severity = max(
        (
            ISSUE_SEVERITY_RANK.get(issue.get("severity"), 0)
            for issue in row["quality_issues"]
        ),
        default=0,
    )
    return (
        -max_issue_severity,
        -ALERT_RANK.get(row["alert_level"], 0),
        -UNCERTAINTY_RANK.get(row["uncertainty_level"], 0),
        -row["confirmed_risk_count"],
        -row["missing_information_count"],
        -(row.get("deal_size_krw") or 0),
        str(row.get("company") or ""),
    )


def _counter_dict(values: Any) -> dict:
    return dict(sorted(Counter(value for value in values if value is not None).items()))


def _contains_sensitive_result_key(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            key in SENSITIVE_RESULT_KEYS or _contains_sensitive_result_key(child)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return any(_contains_sensitive_result_key(item) for item in value)
    return False


def _emit_smoke_error(payload: dict, *, json_output: bool) -> None:
    if json_output:
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2), err=True)
        return
    typer.echo(
        f"Smoke failed: {payload.get('error_code')} "
        f"({payload.get('stage')}) - {payload.get('message')}",
        err=True,
    )


def _format_deal_review_smoke(payload: dict) -> str:
    lines = [
        f"Deal Review Smoke (as_of={payload.get('as_of')}, count={payload.get('count')})",
        "",
    ]
    for result in payload.get("results", []):
        review = result.get("review") or {}
        interpretation = review.get("health_interpretation") or {}
        lines.extend(
            [
                f"[{review.get('company')}] {review.get('deal_id')}",
                (
                    f"Stage: {review.get('deal_stage')} | "
                    f"Industry: {review.get('industry')} | "
                    f"Value: {_format_krw(review.get('deal_size_krw'))} "
                    f"({review.get('deal_size_status') or 'unknown'})"
                ),
                (
                    f"Band: {interpretation.get('review_band')} | "
                    f"Alert: {interpretation.get('alert_level')} | "
                    f"Uncertainty: {interpretation.get('uncertainty_level')}"
                ),
                (
                    f"Health: {interpretation.get('legacy_health_pct')} | "
                    f"Evidence coverage: {interpretation.get('evidence_coverage_pct')}% "
                    f"({interpretation.get('filled_meddpicc_count')}/"
                    f"{interpretation.get('total_meddpicc_count')})"
                ),
                f"Attention: {_format_string_list(review.get('attention_reasons') or [])}",
                f"Missing: {_format_gap_list(review.get('missing_information') or [])}",
                f"Risks: {_format_risk_list(review.get('confirmed_risks') or [])}",
                "Questions: "
                f"{_format_string_list(review.get('recommended_questions') or [], limit=3)}",
                f"Warnings: {_format_string_list(review.get('warnings') or [])}",
                "",
            ]
        )
    lines.append("Sensitive field check: passed")
    return "\n".join(lines)


def _format_deal_review_audit(payload: dict) -> str:
    summary = payload["summary"]
    sensitive_status = (
        "passed" if payload["sensitive_field_check"]["ok"] else "failed"
    )
    quality_status = (
        "passed"
        if summary["quality_issue_count"] == 0
        else f"{summary['quality_issue_count']} issue(s)"
    )
    lines = [
        (
            f"Deal Review Audit (as_of={payload.get('as_of')}, "
            f"reviewed={summary['reviewed_count']})"
        ),
        "",
        f"Sensitive field check: {sensitive_status}",
        f"Quality rules: {quality_status}",
        f"Alert levels: {_format_counts(summary['alert_level_counts'])}",
        f"Uncertainty: {_format_counts(summary['uncertainty_counts'])}",
        f"Review bands: {_format_counts(summary['review_band_counts'])}",
        f"Warnings: {_format_counts(summary['warning_counts'])}",
        "",
        "Top review targets:",
    ]
    for row in payload["deals"][:10]:
        lines.append(
            f"- {row.get('company')} | {row.get('deal_stage')} | "
            f"{row.get('review_band')} | alert={row.get('alert_level')} | "
            f"uncertainty={row.get('uncertainty_level')} | "
            f"coverage={row.get('evidence_coverage_pct')}% | "
            f"missing={row.get('missing_information_count')} | "
            f"risks={row.get('confirmed_risk_count')} | "
            f"issues={_format_issue_ids(row.get('quality_issues') or [])}"
        )
    if len(payload["deals"]) > 10:
        lines.append(f"... +{len(payload['deals']) - 10} more deal(s)")
    return "\n".join(lines)


def _format_counts(counts: dict) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in counts.items())


def _format_issue_ids(issues: list[dict]) -> str:
    if not issues:
        return "none"
    return ", ".join(str(issue.get("issue_id")) for issue in issues[:3])


def _format_krw(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return "unknown"
    return f"{int(value):,} KRW"


def _format_string_list(items: list[Any], *, limit: int = 5) -> str:
    values = [str(item) for item in items if item is not None]
    if not values:
        return "none"
    visible = values[:limit]
    suffix = f" (+{len(values) - limit} more)" if len(values) > limit else ""
    return "; ".join(visible) + suffix


def _format_gap_list(gaps: list[dict]) -> str:
    if not gaps:
        return "none"
    values = [
        f"{gap.get('field')}:{gap.get('status')}:{gap.get('severity')}"
        for gap in gaps[:3]
    ]
    suffix = f" (+{len(gaps) - 3} more)" if len(gaps) > 3 else ""
    return "; ".join(values) + suffix


def _format_risk_list(risks: list[dict]) -> str:
    if not risks:
        return "none"
    values = [
        f"{risk.get('risk_id')}:{risk.get('severity')}"
        for risk in risks[:3]
    ]
    suffix = f" (+{len(risks) - 3} more)" if len(risks) > 3 else ""
    return "; ".join(values) + suffix


if __name__ == "__main__":
    app()
