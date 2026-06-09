from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from deal_intel.errors import ErrorCode, MCPError, Stage
from deal_intel.reports.csv_export import save_report_csv
from deal_intel.reports.markdown_export import save_report_markdown
from deal_intel.reports.markdown_summary import build_weekly_pipeline_markdown
from deal_intel.reports.pipeline_trend import (
    REPORT_TYPE as REPORT_TYPE_PIPELINE_TREND,
)
from deal_intel.reports.pipeline_trend import (
    build_pipeline_trend_markdown,
    build_pipeline_trend_report,
)
from deal_intel.reports.weekly_pipeline import build_weekly_pipeline_rows
from deal_intel.schema.metrics import (
    VALID_STAGES,
    HealthBandThresholds,
    PipelineTimingSettings,
    ReportingContext,
)
from deal_intel.schema.pipeline_trends import (
    DEFAULT_LOOKBACK_DAYS,
    build_pipeline_trend_summary,
    validate_lookback_days,
)
from deal_intel.storage.mongodb import MongoDBClient

REPORT_TYPE_WEEKLY_PIPELINE = "weekly_pipeline"
VALID_REPORT_TYPES = frozenset({REPORT_TYPE_WEEKLY_PIPELINE, REPORT_TYPE_PIPELINE_TREND})
DEFAULT_OUTPUT_DIR = Path("outputs") / "reports"


def handle(
    mongo: MongoDBClient,
    cfg: dict,
    *,
    report_type: str,
    output_dir: str | None = None,
    stage: str | None = None,
    industry: str | None = None,
    as_of: str | None = None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> dict:
    if report_type not in VALID_REPORT_TYPES:
        raise MCPError(
            error_code=ErrorCode.INVALID_INPUT,
            stage=Stage.PREFLIGHT,
            message=f"report_type {report_type!r} is not valid",
            hint={"valid_report_types": sorted(VALID_REPORT_TYPES)},
            retryable=False,
        )
    if stage and stage not in VALID_STAGES:
        raise MCPError(
            error_code=ErrorCode.INVALID_INPUT,
            stage=Stage.PREFLIGHT,
            message=f"stage {stage!r} is not valid",
            hint={"valid_stages": sorted(VALID_STAGES)},
            retryable=False,
        )

    try:
        reporting = ReportingContext.from_config(cfg, as_of=as_of)
        health_thresholds = HealthBandThresholds.from_config(cfg)
        timing_settings = PipelineTimingSettings.from_config(cfg)
        if report_type == REPORT_TYPE_PIPELINE_TREND:
            validate_lookback_days(lookback_days)
        resolved_output_dir = _resolve_output_dir(cfg, output_dir)
    except ValueError as exc:
        error_code = (
            ErrorCode.INVALID_INPUT
            if str(exc).startswith(("as_of", "output_dir", "lookback_days"))
            else ErrorCode.CONFIG_ERROR
        )
        raise MCPError(
            error_code=error_code,
            stage=Stage.PREFLIGHT,
            message=str(exc),
            retryable=False,
        ) from exc

    if report_type == REPORT_TYPE_PIPELINE_TREND:
        return _handle_pipeline_trend(
            mongo=mongo,
            report_type=report_type,
            output_dir=resolved_output_dir,
            reporting=reporting,
            stage=stage,
            industry=industry,
            lookback_days=lookback_days,
        )

    return _handle_weekly_pipeline(
        mongo=mongo,
        report_type=report_type,
        output_dir=resolved_output_dir,
        reporting=reporting,
        health_thresholds=health_thresholds,
        timing_settings=timing_settings,
        stage=stage,
        industry=industry,
    )


def _handle_weekly_pipeline(
    *,
    mongo: MongoDBClient,
    report_type: str,
    output_dir: Path,
    reporting: ReportingContext,
    health_thresholds: HealthBandThresholds,
    timing_settings: PipelineTimingSettings,
    stage: str | None,
    industry: str | None,
) -> dict:
    try:
        deals = mongo.list_deals_for_metrics()
    except Exception as exc:
        raise MCPError(
            error_code=ErrorCode.STORAGE_ERROR,
            stage=Stage.STORAGE,
            message=str(exc),
            retryable=True,
        ) from exc

    report = build_weekly_pipeline_rows(
        deals,
        as_of=reporting.as_of,
        health_thresholds=health_thresholds,
        timing_settings=timing_settings,
        stage=stage,
        industry=industry,
    )
    markdown_summary = build_weekly_pipeline_markdown(
        report,
        generated_at=reporting.generated_at,
    )
    csv_result = save_report_csv(
        report,
        output_dir=output_dir,
        generated_at=reporting.generated_at,
    )
    _raise_io_error(csv_result)
    markdown_result = save_report_markdown(
        markdown_summary["markdown"],
        report_type=report_type,
        output_dir=output_dir,
        generated_at=reporting.generated_at,
    )
    _raise_io_error(markdown_result)

    return {
        "ok": True,
        "report_type": report_type,
        **reporting.to_dict(),
        "filters": report["filters"],
        "row_count": report["row_count"],
        "warnings": report["warnings"],
        "metrics": markdown_summary["metrics"],
        "output_dir": str(output_dir.resolve()),
        "artifacts": {
            "csv": _artifact(csv_result),
            "markdown": _artifact(markdown_result),
        },
        "csv_path": csv_result["path"],
        "markdown_path": markdown_result["path"],
    }


def _handle_pipeline_trend(
    *,
    mongo: MongoDBClient,
    report_type: str,
    output_dir: Path,
    reporting: ReportingContext,
    stage: str | None,
    industry: str | None,
    lookback_days: int,
) -> dict:
    start_date = reporting.as_of - timedelta(days=lookback_days)
    try:
        snapshots = mongo.list_analytics_snapshots(
            start_date=start_date.isoformat(),
            end_date=reporting.as_of.isoformat(),
            stage=stage,
            industry=industry,
        )
    except Exception as exc:
        raise MCPError(
            error_code=ErrorCode.STORAGE_ERROR,
            stage=Stage.STORAGE,
            message=str(exc),
            retryable=True,
        ) from exc

    summary = build_pipeline_trend_summary(
        snapshots,
        as_of=reporting.as_of,
        lookback_days=lookback_days,
        stage=stage,
        industry=industry,
    )
    report = build_pipeline_trend_report(summary)
    markdown_summary = build_pipeline_trend_markdown(
        report,
        generated_at=reporting.generated_at,
    )
    csv_result = save_report_csv(
        report,
        output_dir=output_dir,
        generated_at=reporting.generated_at,
    )
    _raise_io_error(csv_result)
    markdown_result = save_report_markdown(
        markdown_summary["markdown"],
        report_type=report_type,
        output_dir=output_dir,
        generated_at=reporting.generated_at,
    )
    _raise_io_error(markdown_result)

    return {
        "ok": True,
        "report_type": report_type,
        **reporting.to_dict(),
        "filters": report["filters"],
        "window": report["window"],
        "snapshot_count": report["snapshot_count"],
        "deal_count": report["deal_count"],
        "row_count": report["row_count"],
        "warnings": report["warnings"],
        "metrics": markdown_summary["metrics"],
        "output_dir": str(output_dir.resolve()),
        "artifacts": {
            "csv": _artifact(csv_result),
            "markdown": _artifact(markdown_result),
        },
        "csv_path": csv_result["path"],
        "markdown_path": markdown_result["path"],
    }


def _resolve_output_dir(cfg: dict, output_dir: str | None) -> Path:
    if output_dir not in (None, ""):
        if not isinstance(output_dir, str):
            raise ValueError("output_dir must be a string path")
        return Path(output_dir).expanduser()

    reporting = cfg.get("reporting", {})
    if not isinstance(reporting, dict):
        raise ValueError("reporting must be a mapping")
    configured = reporting.get("output_dir")
    if configured in (None, ""):
        return DEFAULT_OUTPUT_DIR
    if not isinstance(configured, str):
        raise ValueError("reporting.output_dir must be a string path")
    return Path(configured).expanduser()


def _raise_io_error(result: dict) -> None:
    if result.get("ok") is True:
        return
    raise MCPError(
        error_code=ErrorCode.IO_ERROR,
        stage=Stage.STORAGE,
        message=str(result.get("message") or "failed to write report artifact"),
        hint=result.get("hint"),
        retryable=bool(result.get("retryable")),
    )


def _artifact(result: dict) -> dict:
    return {
        "path": result["path"],
        "filename": result["filename"],
        "encoding": result["encoding"],
    }
