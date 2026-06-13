from __future__ import annotations

from pydantic import BaseModel, Field

VALID_STAGES = frozenset({
    "discovery", "qualification", "proposal", "negotiation", "won", "lost", "stalled",
})

_DIMS = [
    "metrics", "economic_buyer", "decision_criteria",
    "decision_process", "identify_pain", "champion", "competition",
]


# ---------- sub-models (for doc / validation; stored as plain dicts in Mongo) ----------

class MeddpiccField(BaseModel):
    score: int = Field(default=0, ge=0, le=5)
    evidence: str = ""


class Meddpicc(BaseModel):
    metrics: MeddpiccField | None = None
    economic_buyer: MeddpiccField | None = None
    decision_criteria: MeddpiccField | None = None
    decision_process: MeddpiccField | None = None
    identify_pain: MeddpiccField | None = None
    champion: MeddpiccField | None = None
    competition: MeddpiccField | None = None


class Contact(BaseModel):
    """Flexible contact entry on a deal.

    `role` is required so BI queries can find champions, economic buyers, etc.
    All other fields are optional — fill what's known.
    """
    role: str  # champion | economic_buyer | user | blocker | unknown
    name: str | None = None
    title: str | None = None
    company: str | None = None
    memo: str = ""


class StageHistoryEntry(BaseModel):
    stage: str
    entered_at: str  # ISO-8601 UTC


class Meeting(BaseModel):
    meeting_id: str
    date: str
    raw_notes: str
    summary: str = ""
    meddpicc: dict | None = None
    customer_themes: list[dict] = Field(default_factory=list)


# ---------- deal-level MEDDPICC snapshot ----------

# Stage-aware gap logic constants.
# identify_pain declining in late active stages = pain being resolved = positive signal.
_LATE_ACTIVE_STAGES = {"proposal", "negotiation"}
_PAIN_LATE_THRESHOLD = 1  # score >= 1 is OK in late stages (0 = completely lost urgency)

# won = terminal success; gap list is meaningless for a closed deal.
# lost = terminal failure; keep gaps for post-mortem / pattern analysis.
_NO_GAP_STAGES = {"won"}


def compute_meddpicc_latest(
    meetings: list[dict],
    weights: dict[str, float],
    gap_threshold: int = 2,
    deal_stage: str = "discovery",
) -> dict:
    """Compute aggregated MEDDPICC snapshot from all meetings.

    `weights` keys match _DIMS; missing keys default to 1.0.
    `deal_stage` drives stage-aware gap classification:
      - won              → gaps = []  (closed deal, no open gaps)
      - proposal/negotiation → identify_pain threshold relaxed to 1
                              (declining pain = resolution, not a risk)
      - all others       → gap_threshold applies to all dims

    health_pct formula:
        sum(avg_score_i * weight_i for filled dims) / sum(5 * weight_i for ALL dims) * 100
    Unfilled dimensions count as 0 in the denominator — missing info is a real risk signal.
    """
    dim_scores: dict[str, list[int]] = {d: [] for d in _DIMS}

    for m in meetings:
        meddpicc = m.get("meddpicc") or {}
        for dim in _DIMS:
            val = meddpicc.get(dim)
            if isinstance(val, dict):
                raw = val.get("score")
                if isinstance(raw, (int, float)):
                    dim_scores[dim].append(int(raw))

    dims_out: dict = {}
    for dim in _DIMS:
        scores = dim_scores[dim]
        if not scores:
            continue
        avg = sum(scores) / len(scores)
        trend: str | None = None
        if len(scores) >= 2:
            if scores[-1] > scores[-2]:
                trend = "up"
            elif scores[-1] < scores[-2]:
                trend = "down"
            else:
                trend = "flat"
        dims_out[dim] = {"score": round(avg, 2), "trend": trend}

    total_weight = sum(weights.get(d, 1.0) for d in _DIMS)
    weighted_score = sum(
        dims_out[d]["score"] * weights.get(d, 1.0) for d in _DIMS if d in dims_out
    )
    max_possible = 5.0 * total_weight
    health_pct = round(weighted_score / max_possible * 100, 1) if max_possible > 0 else 0.0

    # Stage-aware gap classification.
    if deal_stage in _NO_GAP_STAGES:
        gaps: list[str] = []
    else:
        late = deal_stage in _LATE_ACTIVE_STAGES
        gaps = []
        for dim in _DIMS:
            if dim not in dims_out:
                gaps.append(dim)
            elif dim == "identify_pain" and late:
                if dims_out[dim]["score"] < _PAIN_LATE_THRESHOLD:
                    gaps.append(dim)
            elif dims_out[dim]["score"] < gap_threshold:
                gaps.append(dim)

    return {
        **dims_out,
        "total_weighted_score": round(weighted_score, 2),
        "health_pct": health_pct,
        "filled_count": len(dims_out),
        "gaps": gaps,
    }


# ---------- top-level Deal document ----------

class Deal(BaseModel):
    deal_id: str
    company: str
    industry: str | None = None
    customer_segment: str | None = None
    deal_size_amount: int | None = None
    deal_size_low_amount: int | None = None
    deal_size_high_amount: int | None = None
    deal_size_currency: str = "KRW"
    deal_size_status: str | None = None
    deal_size_note: str | None = None
    deal_value_history: list[dict] = Field(default_factory=list)
    contacts: list[dict] = Field(default_factory=list)   # Contact dicts
    interactions: list[dict] = Field(default_factory=list)
    meetings: list[dict] = Field(default_factory=list)
    customer_themes: list[dict] = Field(default_factory=list)
    meddpicc_latest: dict = Field(default_factory=dict)  # compute_meddpicc_latest output
    stage_history: list[dict] = Field(default_factory=list)  # StageHistoryEntry dicts
    deal_stage: str = "discovery"
    expected_close_date: str | None = None  # ISO-8601 date
    expected_close_date_source: str | None = None
    actual_close_date: str | None = None  # ISO-8601 date; won/lost only
    close_reason: str | None = None
    bd_strategy: str = ""
    gtm_notes: str = ""
    prospect_id: str | None = None
    created_at: str = ""
    updated_at: str = ""
