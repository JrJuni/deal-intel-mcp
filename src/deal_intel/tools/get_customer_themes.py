from __future__ import annotations

from deal_intel.errors import ErrorCode, MCPError, Stage
from deal_intel.schema.customer_theme_insights import (
    VALID_DIMENSION_FILTERS,
    VALID_STAGE_FILTERS,
    build_customer_theme_ranking,
    validate_ranking_inputs,
)
from deal_intel.schema.customer_theme_workflow import customer_theme_workflow_step
from deal_intel.storage.mongodb import MongoDBClient


def handle(
    mongo: MongoDBClient,
    *,
    dimension: str = "all",
    stage: str = "active",
    industry: str | None = None,
    top_k: int = 5,
) -> dict:
    """Rank recurring customer themes by unique deal count."""
    top_k = max(1, min(top_k, 20))
    try:
        validate_ranking_inputs(dimension=dimension, stage=stage, top_k=top_k)
        deals = mongo.list_deals_for_metrics()
        result = build_customer_theme_ranking(
            deals,
            dimension=dimension,
            stage=stage,
            industry=industry,
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
            },
            retryable=False,
        ) from exc
    except Exception as exc:
        raise MCPError(
            error_code=ErrorCode.STORAGE_ERROR,
            stage=Stage.STORAGE,
            message=str(exc),
            retryable=True,
        ) from exc

    return {
        "ok": True,
        "workflow": customer_theme_workflow_step("ranking"),
        **result,
    }
