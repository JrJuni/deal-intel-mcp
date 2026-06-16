from __future__ import annotations

from deal_intel.errors import ErrorCode, MCPError, Stage
from deal_intel.schema.customer_theme_insights import (
    VALID_DIMENSION_FILTERS,
    VALID_GROUP_BY,
    VALID_STAGE_FILTERS,
    build_customer_theme_breakdown,
    validate_breakdown_inputs,
)
from deal_intel.schema.customer_theme_workflow import customer_theme_workflow_step
from deal_intel.storage.mongodb import MongoDBClient


def handle(
    mongo: MongoDBClient,
    *,
    dimension: str = "all",
    stage: str = "active",
    industry: str | None = None,
    group_by: str = "stage",
    top_k: int = 5,
) -> dict:
    """Compare customer themes by stage, industry, or theme dimension."""
    try:
        validate_breakdown_inputs(
            dimension=dimension,
            stage=stage,
            group_by=group_by,
            top_k=top_k,
        )
    except ValueError as exc:
        raise MCPError(
            error_code=ErrorCode.INVALID_INPUT,
            stage=Stage.PREFLIGHT,
            message=str(exc),
            hint={
                "valid_dimensions": sorted(VALID_DIMENSION_FILTERS),
                "valid_stages": sorted(VALID_STAGE_FILTERS),
                "valid_group_by": sorted(VALID_GROUP_BY),
            },
            retryable=False,
        ) from exc

    try:
        deals = mongo.list_deals_for_metrics()
    except Exception as exc:
        raise MCPError(
            error_code=ErrorCode.STORAGE_ERROR,
            stage=Stage.STORAGE,
            message=str(exc),
            retryable=True,
        ) from exc

    result = build_customer_theme_breakdown(
        deals,
        dimension=dimension,
        stage=stage,
        industry=industry,
        group_by=group_by,
        top_k=top_k,
    )
    return {
        "ok": True,
        "workflow": customer_theme_workflow_step("comparison"),
        **result,
    }
