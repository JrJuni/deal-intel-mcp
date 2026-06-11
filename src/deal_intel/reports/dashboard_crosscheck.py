from __future__ import annotations

from collections.abc import Mapping
from typing import Any

KPI_CHECKS = (
    {
        "metric": "deal_count",
        "sources": {"get_metrics": "deal_count", "atlas": "deal_count"},
    },
    {
        "metric": "active_deal_count",
        "sources": {"get_metrics": "active_deal_count", "atlas": "active_deal_count"},
    },
    {
        "metric": "open_deal_count",
        "sources": {
            "get_metrics": "open_deal_count",
            "csv_markdown": "open_deal_count",
            "atlas": "open_deal_count",
        },
    },
    {
        "metric": "stalled_deal_count",
        "sources": {
            "get_metrics": "stalled_deal_count",
            "csv_markdown": "stalled_count",
            "atlas": "stalled_deal_count",
        },
    },
    {
        "metric": "terminal_deal_count",
        "sources": {
            "get_metrics": "terminal_deal_count",
            "atlas": "terminal_deal_count",
        },
    },
    {
        "metric": "active_pipeline_value_amount",
        "sources": {
            "get_metrics": "active_pipeline_value_amount",
            "atlas": "active_pipeline_value_amount",
        },
    },
    {
        "metric": "open_pipeline_value_amount",
        "sources": {
            "get_metrics": "open_pipeline_value_amount",
            "csv_markdown": "pipeline_value_amount",
            "atlas": "open_pipeline_value_amount",
        },
    },
    {
        "metric": "avg_health_pct",
        "sources": {"get_metrics": "avg_health_pct", "atlas": "avg_health_pct"},
    },
    {
        "metric": "health_coverage_pct",
        "sources": {
            "get_metrics": "health_coverage_pct",
            "atlas": "health_coverage_pct",
        },
    },
    {
        "metric": "health_assessed_count",
        "sources": {
            "get_metrics": "health_assessed_count",
            "atlas": "health_assessed_count",
        },
    },
    {
        "metric": "stuck_deal_count",
        "sources": {
            "get_metrics": "stuck_deal_count",
            "csv_markdown": "stuck_count",
            "atlas": "stuck_deal_count",
        },
    },
    {
        "metric": "overdue_deal_count",
        "sources": {
            "get_metrics": "overdue_deal_count",
            "csv_markdown": "overdue_count",
            "atlas": "overdue_deal_count",
        },
    },
    {
        "metric": "attention_deal_count",
        "sources": {
            "get_metrics": "attention_deal_count",
            "csv_markdown": "attention_deal_count",
            "atlas": "attention_deal_count",
        },
    },
)

STAGE_FIELDS = (
    "count",
    "pipeline_value_amount",
    "avg_health_pct",
    "health_coverage_pct",
    "stuck_count",
    "overdue_count",
)

HEALTH_BANDS = ("healthy", "watch", "at_risk", "unassessed")


def build_weekly_pipeline_dashboard_crosscheck(
    *,
    metrics_result: Mapping[str, Any],
    report_result: Mapping[str, Any],
    atlas_results: Mapping[str, list[dict]],
) -> dict:
    """Compare get_metrics, weekly report, and Atlas Charts aggregation output."""
    metric_kpis = _mapping(metrics_result.get("kpis"))
    report_metrics = _mapping(report_result.get("metrics"))
    atlas_kpis = _singleton(atlas_results.get("pipeline_kpis"))

    kpi_checks = [
        _build_check(
            check["metric"],
            {
                source_name: _field_value(
                    _source_mapping(
                        source_name,
                        metric_kpis=metric_kpis,
                        report_metrics=report_metrics,
                        atlas_kpis=atlas_kpis,
                    ),
                    source_field,
                )
                for source_name, source_field in check["sources"].items()
            },
        )
        for check in KPI_CHECKS
    ]
    stage_checks = _stage_checks(
        metrics_result.get("stage_breakdown"),
        atlas_results.get("stage_breakdown"),
    )
    health_band_checks = _health_band_checks(
        metrics_result.get("health_bands"),
        atlas_results.get("health_bands"),
    )
    attention_row_check = _build_check(
        "attention_deals_row_count",
        {
            "get_metrics": metric_kpis.get("attention_deal_count"),
            "atlas_attention_deals": len(atlas_results.get("attention_deals") or []),
        },
    )
    checks = [
        *kpi_checks,
        *stage_checks,
        *health_band_checks,
        attention_row_check,
    ]
    mismatches = [
        mismatch
        for check in checks
        for mismatch in check["mismatches"]
    ]
    return {
        "ok": not mismatches,
        "as_of": metrics_result.get("as_of") or report_result.get("as_of"),
        "checks": checks,
        "mismatches": mismatches,
        "artifacts": report_result.get("artifacts"),
        "csv_path": report_result.get("csv_path"),
        "markdown_path": report_result.get("markdown_path"),
    }


def _source_mapping(
    source_name: str,
    *,
    metric_kpis: Mapping[str, Any],
    report_metrics: Mapping[str, Any],
    atlas_kpis: Mapping[str, Any],
) -> Mapping[str, Any]:
    if source_name == "get_metrics":
        return metric_kpis
    if source_name == "csv_markdown":
        return report_metrics
    if source_name == "atlas":
        return atlas_kpis
    return {}


def _stage_checks(metric_stage_rows: Any, atlas_stage_rows: Any) -> list[dict]:
    metric_by_stage = {
        str(row.get("stage")): _mapping(row)
        for row in _list_of_mappings(metric_stage_rows)
    }
    atlas_by_stage = {
        str(row.get("stage")): _mapping(row)
        for row in _list_of_mappings(atlas_stage_rows)
    }
    stages = sorted(set(metric_by_stage) | set(atlas_by_stage))
    return [
        _build_check(
            f"stage_breakdown.{stage}.{field}",
            {
                "get_metrics": _stage_field_value(metric_by_stage.get(stage), field),
                "atlas": _stage_field_value(atlas_by_stage.get(stage), field),
            },
        )
        for stage in stages
        for field in STAGE_FIELDS
    ]


def _health_band_checks(metric_bands: Any, atlas_band_rows: Any) -> list[dict]:
    metric_mapping = _mapping(metric_bands)
    atlas_mapping = {
        str(row.get("health_band")): row.get("count", 0)
        for row in _list_of_mappings(atlas_band_rows)
    }
    return [
        _build_check(
            f"health_bands.{band}",
            {
                "get_metrics": metric_mapping.get(band, 0),
                "atlas": atlas_mapping.get(band, 0),
            },
        )
        for band in HEALTH_BANDS
    ]


def _build_check(metric: str, values: Mapping[str, Any]) -> dict:
    normalized = {source: _normalize(value) for source, value in values.items()}
    first_source, first_value = next(iter(normalized.items()))
    mismatches = [
        {
            "metric": metric,
            "expected_source": first_source,
            "expected": first_value,
            "actual_source": source,
            "actual": value,
            "values": normalized,
        }
        for source, value in list(normalized.items())[1:]
        if not _same_value(first_value, value)
    ]
    return {
        "metric": metric,
        "ok": not mismatches,
        "values": normalized,
        "mismatches": mismatches,
    }


def _same_value(left: Any, right: Any) -> bool:
    if left is None or right is None:
        return left is None and right is None
    if isinstance(left, float) or isinstance(right, float):
        try:
            return abs(float(left) - float(right)) <= 0.05
        except (TypeError, ValueError):
            return False
    return left == right


def _normalize(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return round(value, 2)
    if isinstance(value, str):
        stripped = value.strip()
        if stripped == "":
            return None
        try:
            number = float(stripped.replace(",", ""))
        except ValueError:
            return stripped
        if number.is_integer():
            return int(number)
        return round(number, 2)
    return value


def _singleton(rows: list[dict] | None) -> Mapping[str, Any]:
    if not rows:
        return {}
    return _mapping(rows[0])


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _list_of_mappings(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _field_value(value: Mapping[str, Any] | None, field: str) -> Any:
    return value.get(field) if isinstance(value, Mapping) else None


def _stage_field_value(value: Mapping[str, Any] | None, field: str) -> Any:
    if isinstance(value, Mapping):
        return value.get(field)
    if field in {"count", "pipeline_value_amount", "stuck_count", "overdue_count"}:
        return 0
    return None
