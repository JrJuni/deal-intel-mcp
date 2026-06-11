from __future__ import annotations

from deal_intel.errors import ErrorCode, MCPError, Stage
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
        meddpicc = deal.get("meddpicc_latest") or {}
        result: dict = {
            "deal_id": deal["deal_id"],
            "company": deal["company"],
            "deal_stage": deal.get("deal_stage"),
            "industry": deal.get("industry"),
            "deal_size_amount": deal.get("deal_size_amount"),
            "deal_size_currency": deal.get("deal_size_currency") or "KRW",
            "score": round(score, 4),
        }
        hp = meddpicc.get("health_pct")
        if hp is not None:
            result["health_pct"] = round(hp, 1)
        gaps = meddpicc.get("gaps")
        if gaps is not None:
            result["gaps"] = gaps
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
            message=str(exc),
            retryable=True,
        ) from exc

    for r in results:
        if r.get("score") is not None:
            r["score"] = round(r["score"], 4)
        if r.get("health_pct") is not None:
            r["health_pct"] = round(r["health_pct"], 1)

    return {"ok": True, "query": query, "result_count": len(results), "results": results}
