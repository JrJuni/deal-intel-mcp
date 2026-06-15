from __future__ import annotations

from pydantic import BaseModel, Field

from deal_intel.schema.qualification import compute_qualification_latest
from deal_intel.schema.qualification_framework import get_qualification_template
from deal_intel.schema.stages import VALID_STAGES as VALID_STAGES

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

# Stage-aware gap logic now lives in the bundled MEDDPICC qualification
# framework template and is interpreted by compute_qualification_latest().


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
    qualification = compute_meddpicc_qualification_latest(
        meetings,
        weights=weights,
        gap_threshold=gap_threshold,
        deal_stage=deal_stage,
    )
    dims_out = {
        dim: {
            "score": qualification["dimensions"][dim]["score"],
            "trend": qualification["dimensions"][dim]["trend"],
        }
        for dim in _DIMS
        if dim in qualification["dimensions"]
    }
    return {
        **dims_out,
        "total_weighted_score": qualification["total_weighted_score"],
        "health_pct": qualification["health_pct"],
        "filled_count": len(dims_out),
        "gaps": qualification["gaps"],
    }


def compute_meddpicc_qualification_latest(
    meetings: list[dict],
    weights: dict[str, float],
    gap_threshold: int = 2,
    deal_stage: str = "discovery",
) -> dict:
    """Compute the canonical qualification snapshot for MEDDPICC evidence."""
    return compute_qualification_latest(
        meetings,
        framework=_meddpicc_framework_for_legacy_compute(weights, gap_threshold),
        evidence_fields=("meddpicc",),
        deal_stage=deal_stage,
    )


def _meddpicc_framework_for_legacy_compute(
    weights: dict[str, float],
    gap_threshold: int,
):
    framework = get_qualification_template("meddpicc").model_copy(deep=True)
    for dim in _DIMS:
        dimension = framework.dimensions[dim]
        # Preserve the historical function contract: missing weight keys
        # default to 1.0 even though the bundled MEDDPICC template carries the
        # product's default configured weights.
        dimension.weight = float(weights.get(dim, 1.0))
        dimension.gap_threshold = int(gap_threshold)
    return framework


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
    qualification_latest: dict = Field(default_factory=dict)
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
