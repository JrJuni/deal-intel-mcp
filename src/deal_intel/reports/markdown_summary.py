from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from deal_intel.reports.weekly_pipeline import REPORT_TYPE
from deal_intel.schema.metrics import HealthBand, assess_deal_value

WARNING_LABELS = {
    "no_open_deals": "No open deals",
    "unassessed_health": "Unassessed health",
    "missing_expected_close_date": "Missing expected close date",
    "invalid_expected_close_date": "Invalid expected close date",
    "missing_last_meeting_date": "Missing last meeting date",
    "missing_primary_pain": "Missing primary pain",
    "missing_primary_decision_criteria": "Missing primary decision criteria",
    "incomplete_data_quality": "Incomplete data quality",
}


def build_weekly_pipeline_markdown(
    report: dict,
    *,
    generated_at: datetime | None = None,
) -> dict:
    """Build an LLM-free Markdown summary from weekly pipeline report rows."""
    if report.get("report_type") != REPORT_TYPE:
        raise ValueError("report_type must be weekly_pipeline")

    generated = _generated_at(generated_at)
    rows = report.get("rows") if isinstance(report.get("rows"), list) else []
    warnings = [
        str(warning)
        for warning in report.get("warnings", [])
        if warning is not None
    ]
    metrics = _summarize_rows(rows)
    markdown = _build_markdown(
        rows,
        filters=report.get("filters") if isinstance(report.get("filters"), dict) else {},
        generated_at=generated,
        metrics=metrics,
        warnings=warnings,
    )
    return {
        "report_type": REPORT_TYPE,
        "generated_at": generated.isoformat(),
        "metrics": metrics,
        "warnings": warnings,
        "markdown": markdown,
    }


def _generated_at(value: datetime | None) -> datetime:
    generated = value or datetime.now(UTC)
    if generated.tzinfo is None or generated.utcoffset() is None:
        raise ValueError("generated_at must be timezone-aware")
    return generated.astimezone(UTC)


def _summarize_rows(rows: list[dict]) -> dict:
    health_values = [
        float(row["health_pct"])
        for row in rows
        if isinstance(row.get("health_pct"), (int, float))
        and not isinstance(row.get("health_pct"), bool)
    ]
    value_assessments = [assess_deal_value(row) for row in rows]
    known_value_assessments = [
        item for item in value_assessments if item.is_valid and item.is_known
    ]
    row_count = len(rows)
    attention_deal_count = sum(bool(row.get("attention_reasons")) for row in rows)
    return {
        "open_deal_count": row_count,
        "pipeline_value_krw": sum(
            assessment.amount_krw or 0 for assessment in known_value_assessments
        ),
        "known_amount_count": len(known_value_assessments),
        "amount_coverage_pct": _pct(len(known_value_assessments), row_count),
        "avg_health_pct": (
            round(sum(health_values) / len(health_values), 1)
            if health_values
            else None
        ),
        "assessed_health_count": len(health_values),
        "health_coverage_pct": _pct(len(health_values), row_count),
        "attention_deal_count": attention_deal_count,
        "objective_action_item_count": sum(
            len(row.get("objective_action_items") or []) for row in rows
        ),
        "gap_observation_count": sum(
            len(row.get("gap_observations") or []) for row in rows
        ),
        "overdue_count": sum(row.get("is_overdue") is True for row in rows),
        "stuck_count": sum(row.get("is_stuck") is True for row in rows),
        "stalled_count": sum(row.get("deal_stage") == "stalled" for row in rows),
        "at_risk_count": sum(
            row.get("health_band") == HealthBand.AT_RISK.value for row in rows
        ),
        "unassessed_health_count": sum(
            row.get("health_band") == HealthBand.UNASSESSED.value for row in rows
        ),
        "incomplete_data_quality_count": sum(
            not _is_complete_data_quality(row.get("data_quality")) for row in rows
        ),
        "missing_expected_close_date_count": sum(
            row.get("close_date_status") == "missing" for row in rows
        ),
        "invalid_expected_close_date_count": sum(
            row.get("close_date_status") == "invalid" for row in rows
        ),
        "missing_last_meeting_date_count": sum(
            row.get("last_meeting_date") is None for row in rows
        ),
        "missing_primary_pain_count": sum(
            row.get("primary_pain") is None for row in rows
        ),
        "missing_primary_decision_criteria_count": sum(
            row.get("primary_decision_criteria") is None for row in rows
        ),
    }


def _pct(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator * 100, 1) if denominator else None


def _is_complete_data_quality(value: Any) -> bool:
    return isinstance(value, dict) and value.get("is_complete") is True


def _build_markdown(
    rows: list[dict],
    *,
    filters: dict,
    generated_at: datetime,
    metrics: dict,
    warnings: list[str],
) -> str:
    lines = [
        "# Weekly Pipeline Report",
        "",
        f"Generated at: {generated_at.isoformat()}",
        f"Filters: stage={_filter_value(filters.get('stage'))}, "
        f"industry={_filter_value(filters.get('industry'))}",
        "",
        "## KPI",
        "",
        *_table(
            ["Metric", "Value"],
            [
                ["Open deals", str(metrics["open_deal_count"])],
                ["Pipeline value", _format_krw(metrics["pipeline_value_krw"])],
                [
                    "Known amount coverage",
                    _format_ratio(
                        metrics["known_amount_count"],
                        metrics["open_deal_count"],
                        metrics["amount_coverage_pct"],
                    ),
                ],
                ["Average health", _format_pct(metrics["avg_health_pct"])],
                [
                    "Health coverage",
                    _format_ratio(
                        metrics["assessed_health_count"],
                        metrics["open_deal_count"],
                        metrics["health_coverage_pct"],
                    ),
                ],
                ["Attention deals", str(metrics["attention_deal_count"])],
                [
                    "Objective action items",
                    str(metrics["objective_action_item_count"]),
                ],
                ["Gap observations", str(metrics["gap_observation_count"])],
                ["Overdue", str(metrics["overdue_count"])],
                ["Stuck", str(metrics["stuck_count"])],
                ["At risk", str(metrics["at_risk_count"])],
            ],
            align_right={1},
        ),
        "",
        "## Risk Deals",
        "",
        *_risk_deal_section(rows),
        "",
        "## Objective Action Items",
        "",
        *_objective_action_section(rows),
        "",
        "## Gap Observations",
        "",
        *_gap_observation_section(rows),
        "",
        "## Data Quality",
        "",
        *_table(
            ["Issue", "Count"],
            [
                ["Unassessed health", str(metrics["unassessed_health_count"])],
                [
                    "Missing expected close date",
                    str(metrics["missing_expected_close_date_count"]),
                ],
                [
                    "Invalid expected close date",
                    str(metrics["invalid_expected_close_date_count"]),
                ],
                [
                    "Missing last meeting date",
                    str(metrics["missing_last_meeting_date_count"]),
                ],
                ["Missing primary pain", str(metrics["missing_primary_pain_count"])],
                [
                    "Missing primary decision criteria",
                    str(metrics["missing_primary_decision_criteria_count"]),
                ],
                [
                    "Incomplete data quality",
                    str(metrics["incomplete_data_quality_count"]),
                ],
            ],
            align_right={1},
        ),
        "",
        _format_warning_codes(warnings),
        "",
    ]
    return "\n".join(lines)


def _risk_deal_section(rows: list[dict]) -> list[str]:
    risk_rows = [row for row in rows if row.get("attention_reasons")]
    if not risk_rows:
        return ["No risk deals."]
    return _table(
        [
            "Company",
            "Stage",
            "Amount",
            "Expected close",
            "Health",
            "Reasons",
            "Objective actions",
        ],
        [
            [
                row.get("company"),
                row.get("deal_stage"),
                _format_krw(_valid_amount(row)),
                row.get("expected_close_date") or "N/A",
                _format_health(row),
                ", ".join(str(reason) for reason in row.get("attention_reasons", [])),
                _format_action_items(row.get("objective_action_items") or []),
            ]
            for row in risk_rows
        ],
    )


def _objective_action_section(rows: list[dict]) -> list[str]:
    action_rows = [
        (row, action)
        for row in rows
        for action in row.get("objective_action_items") or []
        if isinstance(action, dict)
    ]
    if not action_rows:
        return ["No objective action items."]
    return _table(
        ["Company", "Trigger", "Recommended action", "Reason"],
        [
            [
                row.get("company"),
                action.get("label") or action.get("gap_id"),
                action.get("recommended_action") or "review",
                action.get("reason"),
            ]
            for row, action in action_rows
        ],
    )


def _gap_observation_section(rows: list[dict]) -> list[str]:
    observation_rows = [
        (row, observation)
        for row in rows
        for observation in row.get("gap_observations") or []
        if isinstance(observation, dict)
    ]
    if not observation_rows:
        return ["No gap observations."]
    return _table(
        ["Company", "Gap", "Actionability", "Reason"],
        [
            [
                row.get("company"),
                observation.get("label") or observation.get("field"),
                observation.get("actionability"),
                observation.get("reason"),
            ]
            for row, observation in observation_rows
        ],
    )


def _format_action_items(actions: list[dict]) -> str:
    values = [
        str(action.get("recommended_action") or action.get("gap_id"))
        for action in actions
        if isinstance(action, dict)
    ]
    return ", ".join(values) if values else "none"


def _valid_amount(row: dict) -> int:
    assessment = assess_deal_value(row)
    if assessment.is_valid and assessment.is_known:
        return assessment.amount_krw or 0
    return 0


def _format_health(row: dict) -> str:
    health = row.get("health_pct")
    band = str(row.get("health_band") or "unknown")
    if not isinstance(health, (int, float)) or isinstance(health, bool):
        return band
    return f"{float(health):.1f}% ({band})"


def _table(
    headers: list[str],
    rows: list[list[Any]],
    *,
    align_right: set[int] | None = None,
) -> list[str]:
    align_right = align_right or set()
    divider = [
        "---:" if index in align_right else "---" for index, _ in enumerate(headers)
    ]
    return [
        "| " + " | ".join(_md_cell(header) for header in headers) + " |",
        "| " + " | ".join(divider) + " |",
        *[
            "| " + " | ".join(_md_cell(value) for value in row) + " |"
            for row in rows
        ],
    ]


def _md_cell(value: Any) -> str:
    text = "N/A" if value is None else str(value)
    return text.replace("\r", " ").replace("\n", " ").replace("|", r"\|")


def _filter_value(value: Any) -> str:
    return str(value) if value not in (None, "") else "all"


def _format_krw(value: int | float | None) -> str:
    if value is None:
        return "N/A"
    return f"{int(value):,} KRW"


def _format_pct(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.1f}%"


def _format_ratio(count: int, total: int, pct: float | None) -> str:
    if pct is None:
        return f"{count}/{total}"
    return f"{count}/{total} ({pct:.1f}%)"


def _format_warning_codes(warnings: list[str]) -> str:
    if not warnings:
        return "Warning codes: none"
    labels = [
        f"`{warning}` ({WARNING_LABELS.get(warning, warning)})"
        for warning in warnings
    ]
    return "Warning codes: " + ", ".join(labels)
