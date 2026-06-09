from __future__ import annotations

import json
from copy import deepcopy
from datetime import date, datetime
from pathlib import Path
from typing import Any

from deal_intel.schema.metrics import (
    HealthBandThresholds,
    PipelineTimingSettings,
    ReportingContext,
)

DEFAULT_DASHBOARD_SPEC = (
    Path(__file__).resolve().parents[3]
    / "atlas"
    / "charts"
    / "weekly_pipeline_review.v1.json"
)


def load_weekly_pipeline_dashboard_spec(path: str | Path | None = None) -> dict:
    """Load the version-managed Atlas Charts dashboard spec."""
    spec_path = Path(path) if path is not None else DEFAULT_DASHBOARD_SPEC
    return json.loads(spec_path.read_text(encoding="utf-8"))


def render_weekly_pipeline_dashboard_spec(
    cfg: dict,
    *,
    as_of: str | date | None = None,
    path: str | Path | None = None,
) -> dict:
    """Render Atlas Charts placeholders using the reporting and metric config."""
    spec = load_weekly_pipeline_dashboard_spec(path)
    tokens = _render_tokens(cfg, as_of=as_of)
    rendered = _replace_tokens(spec, tokens)
    rendered["rendered_parameters"] = {
        key.strip("{}").lower(): value for key, value in tokens.items()
    }
    return rendered


def render_chart_pipeline(
    chart_id: str,
    cfg: dict,
    *,
    as_of: str | date | None = None,
    path: str | Path | None = None,
) -> list[dict]:
    """Return one rendered chart aggregation pipeline by chart id."""
    spec = render_weekly_pipeline_dashboard_spec(cfg, as_of=as_of, path=path)
    for chart in spec["charts"]:
        if chart.get("id") == chart_id:
            return deepcopy(chart["pipeline"])
    valid_ids = [chart.get("id") for chart in spec.get("charts", [])]
    raise ValueError(f"chart_id {chart_id!r} is not valid; valid ids: {valid_ids}")


def _render_tokens(cfg: dict, *, as_of: str | date | None) -> dict[str, Any]:
    reporting = ReportingContext.from_config(cfg, as_of=as_of)
    health_thresholds = HealthBandThresholds.from_config(cfg)
    timing_settings = PipelineTimingSettings.from_config(cfg)
    as_of_datetime = datetime.combine(
        reporting.as_of,
        datetime.min.time(),
        tzinfo=reporting.generated_at.tzinfo,
    )
    return {
        "{{AS_OF_DATETIME}}": as_of_datetime.isoformat().replace("+00:00", "Z"),
        "{{HEALTHY_MIN}}": health_thresholds.healthy_min,
        "{{WATCH_MIN}}": health_thresholds.watch_min,
        "{{OVERDUE_GRACE_DAYS}}": timing_settings.overdue_grace_days,
        "{{STUCK_DISCOVERY_DAYS}}": timing_settings.stuck_threshold_for("discovery"),
        "{{STUCK_QUALIFICATION_DAYS}}": timing_settings.stuck_threshold_for(
            "qualification"
        ),
        "{{STUCK_PROPOSAL_DAYS}}": timing_settings.stuck_threshold_for("proposal"),
        "{{STUCK_NEGOTIATION_DAYS}}": timing_settings.stuck_threshold_for(
            "negotiation"
        ),
    }


def _replace_tokens(value: Any, tokens: dict[str, Any]) -> Any:
    if isinstance(value, str):
        return tokens.get(value, value)
    if isinstance(value, list):
        return [_replace_tokens(item, tokens) for item in value]
    if isinstance(value, dict):
        return {key: _replace_tokens(item, tokens) for key, item in value.items()}
    return value
