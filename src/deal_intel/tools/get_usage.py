from __future__ import annotations

from deal_intel.errors import ErrorCode, MCPError, Stage
from deal_intel.storage.mongodb import MongoDBClient
from deal_intel.usage import build_usage_report


def handle(
    mongo: MongoDBClient,
    cfg: dict,
    *,
    since: str | None = None,
    until: str | None = None,
) -> dict:
    _validate_date("since", since)
    _validate_date("until", until)
    if since and until and since > until:
        raise MCPError(
            error_code=ErrorCode.INVALID_INPUT,
            stage=Stage.PREFLIGHT,
            message="since must be before or equal to until",
            retryable=False,
        )
    deals = mongo.list_deals_for_metrics()
    return build_usage_report(deals=deals, cfg=cfg, since=since, until=until)


def _validate_date(name: str, value: str | None) -> None:
    if value is None:
        return
    if len(value) != 10 or value[4] != "-" or value[7] != "-":
        raise MCPError(
            error_code=ErrorCode.INVALID_INPUT,
            stage=Stage.PREFLIGHT,
            message=f"{name} must use YYYY-MM-DD format",
            retryable=False,
        )
