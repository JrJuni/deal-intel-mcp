from __future__ import annotations

from datetime import datetime
from typing import Any

REPORT_TYPE = "pipeline_trend"

COLUMNS = [
    "section",
    "item",
    "start_value",
    "end_value",
    "delta",
    "count",
    "notes",
]

KPI_ORDER = [
    "active_deal_count",
    "open_deal_count",
    "open_pipeline_value_krw",
    "avg_health_pct",
    "attention_deal_count",
    "won_deal_count",
    "lost_deal_count",
]

KPI_LABELS = {
    "active_deal_count": "Active deals",
    "open_deal_count": "Open deals",
    "open_pipeline_value_krw": "Open pipeline value KRW",
    "avg_health_pct": "Average health pct",
    "attention_deal_count": "Attention deals",
    "won_deal_count": "Won deals",
    "lost_deal_count": "Lost deals",
}


def build_pipeline_trend_report(summary: dict) -> dict:
    _validate_summary(summary)
    rows = _kpi_rows(summary)
    rows.extend(_stage_change_rows(summary))

    return {
        "report_type": REPORT_TYPE,
        "filters": dict(summary.get("filters") or {}),
        "window": dict(summary.get("window") or {}),
        "snapshot_count": int(summary.get("snapshot_count") or 0),
        "deal_count": int(summary.get("deal_count") or 0),
        "row_count": len(rows),
        "columns": COLUMNS,
        "rows": rows,
        "warnings": list(summary.get("warnings") or []),
        "metrics": {
            "window": dict(summary.get("window") or {}),
            "snapshot_count": int(summary.get("snapshot_count") or 0),
            "deal_count": int(summary.get("deal_count") or 0),
            "start": dict(summary.get("start") or {}),
            "end": dict(summary.get("end") or {}),
            "delta": dict(summary.get("delta") or {}),
            "stage_changes": dict(summary.get("stage_changes") or {}),
        },
    }


def build_pipeline_trend_markdown(
    report: dict,
    *,
    generated_at: datetime,
) -> dict:
    if report.get("report_type") != REPORT_TYPE:
        raise ValueError("report_type must be pipeline_trend")
    if generated_at.tzinfo is None or generated_at.utcoffset() is None:
        raise ValueError("generated_at must be timezone-aware")

    metrics = report.get("metrics") or {}
    window = metrics.get("window") or {}
    lines = [
        "# Pipeline Trend Report",
        "",
        f"- Generated at: {generated_at.isoformat()}",
        f"- Window: {window.get('start_date', '')} to {window.get('end_date', '')}",
        f"- Lookback days: {window.get('lookback_days', '')}",
        f"- Snapshot count: {metrics.get('snapshot_count', 0)}",
        f"- Deal count: {metrics.get('deal_count', 0)}",
        "",
        "## KPI Delta",
        "",
        "| Metric | Start | End | Delta |",
        "|---|---:|---:|---:|",
    ]
    start = metrics.get("start") or {}
    end = metrics.get("end") or {}
    delta = metrics.get("delta") or {}
    for key in KPI_ORDER:
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_md(KPI_LABELS[key]),
                    _format_value(start.get(key)),
                    _format_value(end.get(key)),
                    _format_value(delta.get(key)),
                ]
            )
            + " |"
        )

    stage_changes = metrics.get("stage_changes") or {}
    lines.extend(
        [
            "",
            "## Stage Changes",
            "",
            f"- Transition count: {stage_changes.get('transition_count', 0)}",
            "",
            "| Section | Item | Count |",
            "|---|---|---:|",
        ]
    )
    change_rows = [
        row for row in report.get("rows", []) if row.get("section") != "kpi"
    ]
    if change_rows:
        for row in change_rows:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _escape_md(str(row.get("section") or "")),
                        _escape_md(str(row.get("item") or "")),
                        _format_value(row.get("count")),
                    ]
                )
                + " |"
            )
    else:
        lines.append("| none | none | 0 |")

    warnings = report.get("warnings") or []
    if warnings:
        lines.extend(
            [
                "",
                "## Warnings",
                "",
                *[f"- `{_escape_md(str(warning))}`" for warning in warnings],
            ]
        )

    markdown = "\n".join(lines) + "\n"
    return {"markdown": markdown, "metrics": metrics}


def _validate_summary(summary: dict) -> None:
    for key in ("filters", "window", "start", "end", "delta", "stage_changes"):
        if not isinstance(summary.get(key), dict):
            raise ValueError(f"pipeline trend summary missing {key}")


def _kpi_rows(summary: dict) -> list[dict]:
    start = summary.get("start") or {}
    end = summary.get("end") or {}
    delta = summary.get("delta") or {}
    return [
        {
            "section": "kpi",
            "item": key,
            "start_value": start.get(key),
            "end_value": end.get(key),
            "delta": delta.get(key),
            "count": None,
            "notes": KPI_LABELS[key],
        }
        for key in KPI_ORDER
    ]


def _stage_change_rows(summary: dict) -> list[dict]:
    stage_changes = summary.get("stage_changes") or {}
    rows: list[dict] = []
    for section, values in (
        ("stage_transition", stage_changes.get("transitions") or {}),
        ("stage_entered", stage_changes.get("entered") or {}),
        ("stage_exited", stage_changes.get("exited") or {}),
    ):
        for item, count in sorted(values.items()):
            rows.append(
                {
                    "section": section,
                    "item": item,
                    "start_value": None,
                    "end_value": None,
                    "delta": None,
                    "count": int(count),
                    "notes": "",
                }
            )
    return rows


def _format_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _escape_md(value: str) -> str:
    return value.replace("|", "\\|").replace("\r", " ").replace("\n", " ")
