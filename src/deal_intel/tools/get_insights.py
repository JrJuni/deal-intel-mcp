from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from deal_intel.errors import ErrorCode, MCPError, Stage
from deal_intel.schema.metrics import (
    HealthBandThresholds,
    PipelineTimingSettings,
    ReportingContext,
    WinRateSettings,
)
from deal_intel.schema.pipeline_metrics import build_pipeline_health_summary
from deal_intel.storage.mongodb import MongoDBClient, with_unarchived_deal_filter

_DIMS = [
    "metrics", "economic_buyer", "decision_criteria",
    "decision_process", "identify_pain", "champion", "competition",
]

VALID_QUERY_TYPES = frozenset({
    "pipeline_overview",
    "win_patterns",
    "loss_patterns",
    "compare_won_lost",
    "gap_frequency",
    "industry_benchmark",
    "stage_velocity",
})

_TERMINAL_STAGES = ["won", "lost"]
_ACTIVE_STAGES = {"$nin": _TERMINAL_STAGES}


def _clean(doc: dict) -> dict:
    doc.pop("_id", None)
    return doc


def _round_dict(d: dict, keys: list[str], ndigits: int = 1) -> dict:
    for k in keys:
        if d.get(k) is not None:
            d[k] = round(d[k], ndigits)
    return d


# ── aggregation helpers ────────────────────────────────────────────────────────

def _dim_avg_accumulators() -> dict:
    return {d: {"$avg": f"$meddpicc_latest.{d}.score"} for d in _DIMS}


def _meddpicc_profile(col, stage: str) -> dict:
    """Average MEDDPICC scores for a given stage."""
    pipeline = [
        {"$match": with_unarchived_deal_filter({"deal_stage": stage})},
        {"$group": {
            "_id": None,
            "count": {"$sum": 1},
            "avg_health_pct": {"$avg": "$meddpicc_latest.health_pct"},
            **_dim_avg_accumulators(),
        }},
    ]
    results = list(col.aggregate(pipeline))
    if not results:
        return {"count": 0}
    r = _clean(results[0])
    _round_dict(r, ["avg_health_pct"] + _DIMS)
    return r


# ── query implementations ──────────────────────────────────────────────────────

def _pipeline_overview(
    deals: list[dict],
    *,
    reporting: ReportingContext,
    health_thresholds: HealthBandThresholds,
    timing_settings: PipelineTimingSettings,
    win_rate_settings: WinRateSettings,
) -> dict:
    summary = build_pipeline_health_summary(
        deals,
        as_of=reporting.as_of,
        health_thresholds=health_thresholds,
        timing_settings=timing_settings,
        win_rate_settings=win_rate_settings,
    )
    stages = [
        {
            "stage": row["stage"],
            "count": row["count"],
            "avg_health_pct": row["avg_health_pct"],
            "total_size_krw": row["pipeline_value_krw"],
        }
        for row in summary["stage_breakdown"]
        if row["count"]
    ]
    return {
        **summary,
        "stages": stages,
        "total_deals": summary["kpis"]["deal_count"],
        "total_size_krw": summary["pipeline_values"]["open"]["pipeline_value_krw"],
    }


def _win_patterns(col) -> dict:
    r = _meddpicc_profile(col, "won")
    return {"query": "win_patterns", **r}


def _loss_patterns(col) -> dict:
    r = _meddpicc_profile(col, "lost")
    return {"query": "loss_patterns", **r}


def _compare_won_lost(col) -> dict:
    won = _meddpicc_profile(col, "won")
    lost = _meddpicc_profile(col, "lost")

    comparison = {}
    for dim in _DIMS:
        won_avg = won.get(dim)
        lost_avg = lost.get(dim)
        comparison[dim] = {
            "won_avg": won_avg,
            "lost_avg": lost_avg,
            "delta": (
                round(won_avg - lost_avg, 2)
                if (won_avg is not None and lost_avg is not None)
                else None
            ),
        }

    return {
        "won_count": won.get("count", 0),
        "lost_count": lost.get("count", 0),
        "won_avg_health_pct": won.get("avg_health_pct"),
        "lost_avg_health_pct": lost.get("avg_health_pct"),
        "dimensions": comparison,
    }


def _gap_frequency(col) -> dict:
    active_query = with_unarchived_deal_filter({"deal_stage": _ACTIVE_STAGES})
    pipeline = [
        {"$match": active_query},
        {"$project": {"gaps": "$meddpicc_latest.gaps", "deal_stage": 1}},
        {"$unwind": "$gaps"},
        {"$group": {"_id": "$gaps", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    rows = [{"dimension": r["_id"], "gap_count": r["count"]} for r in col.aggregate(pipeline)]
    active_count_pipeline = [
        {"$match": active_query},
        {"$count": "n"},
    ]
    active_res = list(col.aggregate(active_count_pipeline))
    active_deals = active_res[0]["n"] if active_res else 0
    return {"active_deal_count": active_deals, "gap_frequency": rows}


def _industry_benchmark(
    col,
    settings: WinRateSettings | None = None,
) -> dict:
    settings = settings or WinRateSettings()
    pipeline = [
        {"$match": with_unarchived_deal_filter({"industry": {"$ne": None}})},
        {"$group": {
            "_id": "$industry",
            "deal_count": {"$sum": 1},
            "avg_health_pct": {"$avg": "$meddpicc_latest.health_pct"},
            "won_count": {"$sum": {"$cond": [{"$eq": ["$deal_stage", "won"]}, 1, 0]}},
            "lost_count": {"$sum": {"$cond": [{"$eq": ["$deal_stage", "lost"]}, 1, 0]}},
            "closed_count": {
                "$sum": {
                    "$cond": [
                        {"$in": ["$deal_stage", _TERMINAL_STAGES]},
                        1,
                        0,
                    ]
                }
            },
            "total_size_krw": {"$sum": {"$ifNull": ["$deal_size_krw", 0]}},
        }},
        {"$addFields": {
            "win_rate_pct": {
                "$cond": [
                    {"$gt": ["$closed_count", 0]},
                    {
                        "$round": [
                            {
                                "$multiply": [
                                    {"$divide": ["$won_count", "$closed_count"]},
                                    100,
                                ]
                            },
                            1,
                        ]
                    },
                    None,
                ]
            }
        }},
        {"$sort": {"avg_health_pct": -1}},
    ]
    rows = []
    for r in col.aggregate(pipeline):
        rows.append({
            "industry": r["_id"],
            "deal_count": r["deal_count"],
            "avg_health_pct": round(r["avg_health_pct"], 1) if r["avg_health_pct"] else None,
            "won_count": r["won_count"],
            "lost_count": r["lost_count"],
            "closed_count": r["closed_count"],
            "win_rate_pct": r["win_rate_pct"],
            "minimum_closed_sample": settings.minimum_closed_sample,
            "insufficient_sample": (
                r["closed_count"] < settings.minimum_closed_sample
            ),
            "warnings": (
                ["insufficient_closed_sample"]
                if r["closed_count"] < settings.minimum_closed_sample
                else []
            ),
            "total_size_krw": r["total_size_krw"],
        })
    return {"industries": rows}


def _stage_velocity(col) -> dict:
    """Compute average days spent per stage from stage_history entries."""
    deals = list(col.find(
        with_unarchived_deal_filter(
            {"stage_history.1": {"$exists": True}}
        ),  # at least 2 history entries
        {"_id": 0, "stage_history": 1},
    ))

    stage_days: dict[str, list[float]] = defaultdict(list)
    for deal in deals:
        history = deal.get("stage_history", [])
        for i in range(len(history) - 1):
            try:
                t0 = datetime.fromisoformat(history[i]["entered_at"])
                t1 = datetime.fromisoformat(history[i + 1]["entered_at"])
                days = (t1 - t0).total_seconds() / 86400
                if days >= 0:
                    stage_days[history[i]["stage"]].append(days)
            except Exception:
                pass

    rows = []
    for stage, days_list in sorted(stage_days.items()):
        rows.append({
            "stage": stage,
            "avg_days": round(sum(days_list) / len(days_list), 1),
            "min_days": round(min(days_list), 1),
            "max_days": round(max(days_list), 1),
            "sample_count": len(days_list),
        })
    return {"stage_velocity": rows}


# ── public entry point ─────────────────────────────────────────────────────────

_HANDLERS = {
    "win_patterns": _win_patterns,
    "loss_patterns": _loss_patterns,
    "compare_won_lost": _compare_won_lost,
    "gap_frequency": _gap_frequency,
    "industry_benchmark": _industry_benchmark,
    "stage_velocity": _stage_velocity,
}


def handle(
    mongo: MongoDBClient,
    cfg: dict,
    *,
    query_type: str,
    as_of: str | None = None,
) -> dict:
    if query_type not in VALID_QUERY_TYPES:
        raise MCPError(
            error_code=ErrorCode.INVALID_INPUT,
            stage=Stage.PREFLIGHT,
            message=f"query_type {query_type!r} is not valid",
            hint={"valid_query_types": sorted(VALID_QUERY_TYPES)},
            retryable=False,
        )
    try:
        reporting = ReportingContext.from_config(cfg, as_of=as_of)
        win_rate_settings = (
            WinRateSettings.from_config(cfg)
            if query_type in {"industry_benchmark", "pipeline_overview"}
            else None
        )
        if query_type == "pipeline_overview":
            health_thresholds = HealthBandThresholds.from_config(cfg)
            timing_settings = PipelineTimingSettings.from_config(cfg)
    except ValueError as exc:
        error_code = (
            ErrorCode.INVALID_INPUT
            if str(exc).startswith("as_of")
            else ErrorCode.CONFIG_ERROR
        )
        raise MCPError(
            error_code=error_code,
            stage=Stage.PREFLIGHT,
            message=str(exc),
            retryable=False,
        ) from exc
    try:
        if query_type == "pipeline_overview":
            deals = mongo.list_deals_for_metrics()
            result = _pipeline_overview(
                deals,
                reporting=reporting,
                health_thresholds=health_thresholds,
                timing_settings=timing_settings,
                win_rate_settings=win_rate_settings,
            )
        else:
            col = mongo._get_db().deals
            if query_type == "industry_benchmark":
                result = _industry_benchmark(col, win_rate_settings)
            else:
                result = _HANDLERS[query_type](col)
        return {
            "ok": True,
            "query_type": query_type,
            **reporting.to_dict(),
            **result,
        }
    except MCPError:
        raise
    except Exception as exc:
        raise MCPError(
            error_code=ErrorCode.STORAGE_ERROR,
            stage=Stage.STORAGE,
            message=str(exc),
            retryable=True,
        ) from exc
