from __future__ import annotations

from deal_intel.errors import ErrorCode, MCPError, Stage
from deal_intel.schema.customer_theme_insights import (
    VALID_DIMENSION_FILTERS,
    VALID_SOURCE_CONFIDENCE_FILTERS,
    VALID_STAGE_FILTERS,
    build_customer_theme_evidence,
    validate_evidence_inputs,
)
from deal_intel.schema.customer_themes import THEME_TAXONOMY
from deal_intel.schema.interactions import interaction_types_from_config
from deal_intel.storage.mongodb import MongoDBClient


def handle(
    mongo: MongoDBClient,
    *,
    cfg: dict | None = None,
    theme_key: str,
    dimension: str = "all",
    stage: str = "active",
    industry: str | None = None,
    limit: int = 10,
    min_importance: int = 1,
    interaction_type: str = "all",
    source_confidence: str = "all",
) -> dict:
    """Return curated customer-theme evidence without raw meeting notes."""
    try:
        valid_interaction_types = interaction_types_from_config(cfg)
        validate_evidence_inputs(
            theme_key=theme_key,
            dimension=dimension,
            stage=stage,
            limit=limit,
            min_importance=min_importance,
            interaction_type=interaction_type,
            source_confidence=source_confidence,
            valid_interaction_types=valid_interaction_types,
        )
    except ValueError as exc:
        raise MCPError(
            error_code=ErrorCode.INVALID_INPUT,
            stage=Stage.PREFLIGHT,
            message=str(exc),
            hint={
                "valid_theme_keys": sorted(THEME_TAXONOMY),
                "valid_dimensions": sorted(VALID_DIMENSION_FILTERS),
                "valid_stages": sorted(VALID_STAGE_FILTERS),
                "valid_interaction_types": sorted(
                    interaction_types_from_config(cfg)
                ),
                "valid_source_confidence": sorted(
                    VALID_SOURCE_CONFIDENCE_FILTERS
                ),
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

    result = build_customer_theme_evidence(
        deals,
        theme_key=theme_key,
        dimension=dimension,
        stage=stage,
        industry=industry,
        limit=limit,
        min_importance=min_importance,
        interaction_type=interaction_type,
        source_confidence=source_confidence,
        valid_interaction_types=interaction_types_from_config(cfg),
    )
    return {"ok": True, **result}
