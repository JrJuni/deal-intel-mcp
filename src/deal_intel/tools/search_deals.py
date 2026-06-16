from __future__ import annotations

from deal_intel.atlas_vector_indexes import deal_summary_vector_index_name
from deal_intel.errors import ErrorCode, MCPError, Stage
from deal_intel.schema.qualification_read import select_qualification_snapshot
from deal_intel.storage.mongodb import MongoDBClient


def handle(
    mongo: MongoDBClient,
    embedding_provider,
    *,
    cfg: dict,
    query: str,
    limit: int = 5,
) -> dict:
    """Semantic search over deals.

    Routing controlled by config mongodb.vector_search:
    - "python_cosine" (default): fetch all embeddings from MongoDB, rank in Python.
      Works on any tier (M0/M10+). O(n) scan — sufficient for thousands of deals.
    - "atlas": uses $vectorSearch ANN index. Requires M10+ cluster.
      Switch by setting mongodb.vector_search: atlas in ~/.deal-intel/config.yaml.
    """
    if embedding_provider is None:
        raise MCPError(
            error_code=ErrorCode.INVALID_INPUT,
            stage=Stage.PREFLIGHT,
            message="Embedding provider not available.",
            hint={"fix": "pip install sentence-transformers"},
            retryable=False,
        )

    if not query.strip():
        raise MCPError(
            error_code=ErrorCode.INVALID_INPUT,
            stage=Stage.PREFLIGHT,
            message="query must not be empty.",
            retryable=False,
        )

    limit = max(1, min(limit, 20))

    try:
        query_embedding = embedding_provider.embed(query)
    except Exception as exc:
        raise MCPError(
            error_code=ErrorCode.LLM_ERROR,
            stage=Stage.LLM,
            message=f"Embedding generation failed: {exc}",
            retryable=True,
        ) from exc

    mode = cfg.get("mongodb", {}).get("vector_search", "python_cosine")

    if mode == "atlas":
        return _search_atlas(mongo, query_embedding, query=query, limit=limit)
    if mode != "python_cosine":
        raise MCPError(
            error_code=ErrorCode.INVALID_INPUT,
            stage=Stage.PREFLIGHT,
            message="mongodb.vector_search must be 'python_cosine' or 'atlas'.",
            hint={"fix": "Set mongodb.vector_search to python_cosine or atlas."},
            retryable=False,
        )
    return _search_python_cosine(mongo, query_embedding, query=query, limit=limit)


def _search_python_cosine(
    mongo: MongoDBClient,
    query_embedding: list[float],
    *,
    query: str,
    limit: int,
) -> dict:
    try:
        deals = mongo.get_deals_for_search()
    except Exception as exc:
        raise MCPError(
            error_code=ErrorCode.STORAGE_ERROR,
            stage=Stage.STORAGE,
            message=str(exc),
            retryable=True,
        ) from exc

    if not deals:
        return {"ok": True, "query": query, "result_count": 0, "results": []}

    # Vectors are L2-normalized at write time (normalize_embeddings=True),
    # so cosine similarity = dot product.
    scored: list[tuple[float, dict]] = []
    for deal in deals:
        emb = deal.get("summary_embedding")
        if not emb:
            continue
        score = sum(q * d for q, d in zip(query_embedding, emb))
        scored.append((score, deal))

    scored.sort(key=lambda x: -x[0])

    results = []
    for score, deal in scored[:limit]:
        qualification = select_qualification_snapshot(deal)
        qualification_gaps = _safe_gap_list(qualification.gaps)
        result: dict = {
            "deal_id": deal["deal_id"],
            "company": deal["company"],
            "deal_stage": deal.get("deal_stage"),
            "industry": deal.get("industry"),
            "industry_tags": deal.get("industry_tags") or [],
            "customer_segment": deal.get("customer_segment"),
            "deal_size_amount": deal.get("deal_size_amount"),
            "deal_size_currency": deal.get("deal_size_currency") or "KRW",
            "score": round(score, 4),
            "qualification_framework": qualification.framework_key,
            "qualification_framework_display_name": (
                qualification.framework_display_name
            ),
            "qualification_source_field": qualification.source_field,
            "qualification_gaps": qualification_gaps,
            "gaps": qualification_gaps,
        }
        hp = qualification.snapshot.get("health_pct")
        if hp is not None:
            rounded_health = round(hp, 1)
            result["qualification_health_pct"] = rounded_health
            result["health_pct"] = rounded_health
        results.append(result)

    return {"ok": True, "query": query, "result_count": len(results), "results": results}


def _search_atlas(
    mongo: MongoDBClient,
    query_embedding: list[float],
    *,
    query: str,
    limit: int,
) -> dict:
    try:
        results = mongo.search_by_embedding(query_embedding, limit=limit)
    except Exception as exc:
        raise MCPError(
            error_code=ErrorCode.STORAGE_ERROR,
            stage=Stage.STORAGE,
            message=f"Atlas Vector Search failed: {exc}",
            hint={
                "policy": "No silent fallback in pro/atlas mode.",
                "index": deal_summary_vector_index_name(),
                "fix": (
                    "Verify Atlas M10+, create the vector index, or temporarily set "
                    "mongodb.vector_search to python_cosine."
                ),
                "record_failures_in": "docs/pro-fallback-errors.md",
            },
            retryable=False,
        ) from exc

    for r in results:
        if r.get("score") is not None:
            r["score"] = round(r["score"], 4)
        if r.get("health_pct") is not None:
            r["health_pct"] = round(r["health_pct"], 1)
        if r.get("qualification_health_pct") is not None:
            r["qualification_health_pct"] = round(
                r["qualification_health_pct"],
                1,
            )
        r["qualification_gaps"] = _safe_gap_list(r.get("qualification_gaps"))
        r["gaps"] = _safe_gap_list(r.get("gaps"))
        r["industry_tags"] = r.get("industry_tags") or []

    return {"ok": True, "query": query, "result_count": len(results), "results": results}


def _safe_gap_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]
