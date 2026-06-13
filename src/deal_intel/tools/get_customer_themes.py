from __future__ import annotations

from deal_intel.errors import ErrorCode, MCPError, Stage
from deal_intel.schema.customer_themes import THEME_DIMENSIONS
from deal_intel.schema.industry_taxonomy import industry_filter_values
from deal_intel.schema.meddpicc import VALID_STAGES
from deal_intel.storage.mongodb import MongoDBClient, with_unarchived_deal_filter

_TERMINAL_STAGES = ["won", "lost"]
_VALID_STAGE_FILTERS = VALID_STAGES | {"active", "all"}
_VALID_DIMENSIONS = THEME_DIMENSIONS | {"all"}


def build_scope_query(*, stage: str, industry: str | None) -> dict:
    if stage not in _VALID_STAGE_FILTERS:
        raise MCPError(
            error_code=ErrorCode.INVALID_INPUT,
            stage=Stage.PREFLIGHT,
            message=f"stage {stage!r} is not valid",
            hint={"valid_stages": sorted(_VALID_STAGE_FILTERS)},
            retryable=False,
        )

    query = with_unarchived_deal_filter()
    if stage == "active":
        query["deal_stage"] = {"$nin": _TERMINAL_STAGES}
    elif stage != "all":
        query["deal_stage"] = stage
    industry_values = industry_filter_values(industry)
    if industry_values:
        query["$or"] = [
            {"industry": {"$in": industry_values}},
            {"industry_tags": {"$in": industry_values}},
        ]
    return query


def build_theme_pipeline(
    *,
    dimension: str,
    stage: str,
    industry: str | None,
    top_k: int,
) -> list[dict]:
    if dimension not in _VALID_DIMENSIONS:
        raise MCPError(
            error_code=ErrorCode.INVALID_INPUT,
            stage=Stage.PREFLIGHT,
            message=f"dimension {dimension!r} is not valid",
            hint={"valid_dimensions": sorted(_VALID_DIMENSIONS)},
            retryable=False,
        )

    scope = build_scope_query(stage=stage, industry=industry)
    scope["customer_themes.0"] = {"$exists": True}
    pipeline: list[dict] = [
        {"$match": scope},
        {"$unwind": "$customer_themes"},
    ]
    if dimension != "all":
        pipeline.append({"$match": {"customer_themes.dimension": dimension}})

    pipeline.extend(
        [
            {
                "$group": {
                    "_id": {
                        "theme_key": "$customer_themes.theme_key",
                        "deal_id": "$deal_id",
                    },
                    "label": {"$first": "$customer_themes.label"},
                    "company": {"$first": "$company"},
                    "dimension": {"$first": "$customer_themes.dimension"},
                    "importance": {"$max": "$customer_themes.importance"},
                    "evidence": {"$first": "$customer_themes.evidence"},
                }
            },
            {
                "$group": {
                    "_id": "$_id.theme_key",
                    "label": {"$first": "$label"},
                    "deal_count": {"$sum": 1},
                    "avg_importance": {"$avg": "$importance"},
                    "companies": {"$addToSet": "$company"},
                    "evidence_samples": {
                        "$push": {
                            "company": "$company",
                            "dimension": "$dimension",
                            "evidence": "$evidence",
                            "importance": "$importance",
                        }
                    },
                }
            },
            {"$sort": {"deal_count": -1, "avg_importance": -1, "_id": 1}},
            {"$limit": top_k},
            {
                "$project": {
                    "_id": 0,
                    "theme_key": "$_id",
                    "label": 1,
                    "deal_count": 1,
                    "avg_importance": {"$round": ["$avg_importance", 1]},
                    "companies": {"$slice": ["$companies", 5]},
                    "evidence_samples": {"$slice": ["$evidence_samples", 3]},
                }
            },
        ]
    )
    return pipeline


def handle(
    mongo: MongoDBClient,
    *,
    dimension: str = "all",
    stage: str = "active",
    industry: str | None = None,
    top_k: int = 5,
) -> dict:
    top_k = max(1, min(top_k, 20))
    scope = build_scope_query(stage=stage, industry=industry)
    pipeline = build_theme_pipeline(
        dimension=dimension,
        stage=stage,
        industry=industry,
        top_k=top_k,
    )

    evidence_query = dict(scope)
    if dimension == "all":
        evidence_query["customer_themes.0"] = {"$exists": True}
    elif dimension in _VALID_DIMENSIONS:
        evidence_query["customer_themes"] = {"$elemMatch": {"dimension": dimension}}
    else:
        # build_theme_pipeline produces the structured validation error.
        raise AssertionError("unreachable")

    try:
        deals_analyzed = mongo.count_deals(scope)
        deals_with_evidence = mongo.count_deals(evidence_query)
        themes = mongo.aggregate_deals(pipeline)
    except Exception as exc:
        raise MCPError(
            error_code=ErrorCode.STORAGE_ERROR,
            stage=Stage.STORAGE,
            message=str(exc),
            retryable=True,
        ) from exc

    for theme in themes:
        deal_count = theme.get("deal_count", 0)
        theme["share_of_evidenced_pct"] = (
            round(deal_count / deals_with_evidence * 100, 1) if deals_with_evidence else 0.0
        )
        theme["share_of_all_deals_pct"] = (
            round(deal_count / deals_analyzed * 100, 1) if deals_analyzed else 0.0
        )

    coverage_pct = (
        round(deals_with_evidence / deals_analyzed * 100, 1) if deals_analyzed else 0.0
    )
    return {
        "ok": True,
        "filters": {
            "dimension": dimension,
            "stage": stage,
            "industry": industry,
        },
        "coverage": {
            "deals_analyzed": deals_analyzed,
            "deals_with_evidence": deals_with_evidence,
            "coverage_pct": coverage_pct,
        },
        "themes": themes,
    }
