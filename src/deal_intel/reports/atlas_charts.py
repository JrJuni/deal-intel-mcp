from __future__ import annotations

import json
from copy import deepcopy
from datetime import date, datetime, timedelta
from importlib import resources
from pathlib import Path
from typing import Any

from deal_intel.schema.metrics import (
    HealthBandThresholds,
    PipelineTimingSettings,
    ReportingContext,
)
from deal_intel.schema.pipeline_trends import (
    DEFAULT_LOOKBACK_DAYS,
    validate_lookback_days,
)

WEEKLY_PIPELINE_DASHBOARD = "weekly_pipeline_review"
PIPELINE_TREND_DASHBOARD = "pipeline_trend"
CUSTOMER_THEMES_DASHBOARD = "customer_themes"

DEFAULT_WEEKLY_PIPELINE_SPEC = (
    Path(__file__).resolve().parents[3]
    / "atlas"
    / "charts"
    / "weekly_pipeline_review.v1.json"
)
DEFAULT_PIPELINE_TREND_SPEC = (
    Path(__file__).resolve().parents[3]
    / "atlas"
    / "charts"
    / "pipeline_trend.v1.json"
)
DEFAULT_CUSTOMER_THEMES_SPEC = (
    Path(__file__).resolve().parents[3]
    / "atlas"
    / "charts"
    / "customer_themes.v1.json"
)
DEFAULT_DASHBOARD_SPEC = DEFAULT_WEEKLY_PIPELINE_SPEC
DEFAULT_DASHBOARD = WEEKLY_PIPELINE_DASHBOARD
DASHBOARD_SPECS = {
    WEEKLY_PIPELINE_DASHBOARD: DEFAULT_WEEKLY_PIPELINE_SPEC,
    PIPELINE_TREND_DASHBOARD: DEFAULT_PIPELINE_TREND_SPEC,
    CUSTOMER_THEMES_DASHBOARD: DEFAULT_CUSTOMER_THEMES_SPEC,
}
RESOURCE_DASHBOARD_SPECS = {
    WEEKLY_PIPELINE_DASHBOARD: "weekly_pipeline_review.v1.json",
    PIPELINE_TREND_DASHBOARD: "pipeline_trend.v1.json",
    CUSTOMER_THEMES_DASHBOARD: "customer_themes.v1.json",
}


def load_weekly_pipeline_dashboard_spec(path: str | Path | None = None) -> dict:
    """Load the version-managed Atlas Charts dashboard spec."""
    return _load_dashboard_spec_from_path(path, WEEKLY_PIPELINE_DASHBOARD)


def load_pipeline_trend_dashboard_spec(path: str | Path | None = None) -> dict:
    """Load the version-managed Atlas Charts trend dashboard spec."""
    return _load_dashboard_spec_from_path(path, PIPELINE_TREND_DASHBOARD)


def load_customer_themes_dashboard_spec(path: str | Path | None = None) -> dict:
    """Load the version-managed Atlas Charts customer themes dashboard spec."""
    return _load_dashboard_spec_from_path(path, CUSTOMER_THEMES_DASHBOARD)


def load_dashboard_spec(
    dashboard: str = DEFAULT_DASHBOARD,
    *,
    path: str | Path | None = None,
) -> dict:
    if path is not None:
        spec_path = Path(path)
        return json.loads(spec_path.read_text(encoding="utf-8"))
    if dashboard not in DASHBOARD_SPECS:
        valid = sorted(DASHBOARD_SPECS)
        raise ValueError(
            f"dashboard {dashboard!r} is not valid; valid ids: {valid}"
        )
    spec_path = DASHBOARD_SPECS[dashboard]
    if spec_path.exists():
        return json.loads(spec_path.read_text(encoding="utf-8"))
    return json.loads(_dashboard_resource_text(dashboard))


def _dashboard_resource_text(dashboard: str) -> str:
    try:
        file_name = RESOURCE_DASHBOARD_SPECS[dashboard]
    except KeyError as exc:
        valid = sorted(RESOURCE_DASHBOARD_SPECS)
        raise ValueError(
            f"dashboard {dashboard!r} is not valid; valid ids: {valid}"
        ) from exc
    return (
        resources.files("deal_intel.resources")
        .joinpath("atlas", "charts", file_name)
        .read_text(encoding="utf-8")
    )


def _default_dashboard_path(dashboard: str) -> Path:
    try:
        return DASHBOARD_SPECS[dashboard]
    except KeyError as exc:
        valid = sorted(DASHBOARD_SPECS)
        raise ValueError(
            f"dashboard {dashboard!r} is not valid; valid ids: {valid}"
        ) from exc


def _load_default_dashboard_spec(dashboard: str) -> dict:
    spec_path = _default_dashboard_path(dashboard)
    if spec_path.exists():
        return json.loads(spec_path.read_text(encoding="utf-8"))
    return json.loads(_dashboard_resource_text(dashboard))


def _load_dashboard_spec_from_path(path: str | Path | None, dashboard: str) -> dict:
    if path is not None:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    return _load_default_dashboard_spec(dashboard)


def render_weekly_pipeline_dashboard_spec(
    cfg: dict,
    *,
    as_of: str | date | None = None,
    path: str | Path | None = None,
) -> dict:
    """Render Atlas Charts placeholders using the reporting and metric config."""
    spec = load_weekly_pipeline_dashboard_spec(path)
    tokens = _render_tokens(cfg, as_of=as_of)
    rendered = _render_spec(spec, tokens)
    return rendered


def render_pipeline_trend_dashboard_spec(
    cfg: dict,
    *,
    as_of: str | date | None = None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    path: str | Path | None = None,
) -> dict:
    """Render Atlas Charts trend placeholders using reporting config."""
    spec = load_pipeline_trend_dashboard_spec(path)
    tokens = _render_tokens(cfg, as_of=as_of, lookback_days=lookback_days)
    return _render_spec(spec, tokens)


def render_customer_themes_dashboard_spec(
    cfg: dict,
    *,
    as_of: str | date | None = None,
    path: str | Path | None = None,
) -> dict:
    """Render the customer themes dashboard spec."""
    spec = load_customer_themes_dashboard_spec(path)
    tokens = _render_tokens(cfg, as_of=as_of)
    return _render_spec(spec, tokens)


def render_dashboard_spec(
    dashboard: str,
    cfg: dict,
    *,
    as_of: str | date | None = None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    path: str | Path | None = None,
) -> dict:
    """Render one version-managed dashboard spec."""
    spec = load_dashboard_spec(dashboard, path=path)
    tokens = _render_tokens(cfg, as_of=as_of, lookback_days=lookback_days)
    return _render_spec(spec, tokens)


def _render_spec(spec: dict, tokens: dict[str, Any]) -> dict:
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
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    dashboard: str = DEFAULT_DASHBOARD,
    path: str | Path | None = None,
) -> list[dict]:
    """Return one rendered chart aggregation pipeline by chart id."""
    spec = render_dashboard_spec(
        dashboard,
        cfg,
        as_of=as_of,
        lookback_days=lookback_days,
        path=path,
    )
    for chart in spec["charts"]:
        if chart.get("id") == chart_id:
            return deepcopy(chart["pipeline"])
    valid_ids = [chart.get("id") for chart in spec.get("charts", [])]
    raise ValueError(f"chart_id {chart_id!r} is not valid; valid ids: {valid_ids}")


def _render_tokens(
    cfg: dict,
    *,
    as_of: str | date | None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> dict[str, Any]:
    reporting = ReportingContext.from_config(cfg, as_of=as_of)
    health_thresholds = HealthBandThresholds.from_config(cfg)
    timing_settings = PipelineTimingSettings.from_config(cfg)
    validate_lookback_days(lookback_days)
    as_of_datetime = datetime.combine(
        reporting.as_of,
        datetime.min.time(),
        tzinfo=reporting.generated_at.tzinfo,
    )
    start_date = reporting.as_of - timedelta(days=lookback_days)
    return {
        "{{AS_OF_DATETIME}}": as_of_datetime.isoformat().replace("+00:00", "Z"),
        "{{AS_OF_DATE}}": reporting.as_of.isoformat(),
        "{{START_DATE}}": start_date.isoformat(),
        "{{LOOKBACK_DAYS}}": lookback_days,
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
