from __future__ import annotations

from typing import Any

ACTIONABILITY_CTA_ALLOWED = "cta_allowed"
ACTIONABILITY_NEEDS_HUMAN_JUDGMENT = "needs_human_judgment"
CTA_POLICY_ALLOWED = "cta_allowed"
CTA_POLICY_OBSERVATION_ONLY = "observation_only"

OBJECTIVE_ATTENTION_GAP_IDS = {
    "attention:overdue",
    "attention:stuck",
    "attention:stalled",
}

OBJECTIVE_FIELDS = {
    "actual_close_date",
    "close_reason",
    "expected_close_date",
    "deal_value",
    "stage_history",
    "meetings",
    "health_assessment",
}


def annotate_gap_actionability(gap: dict[str, Any]) -> dict[str, Any]:
    """Add actionability metadata without mutating the source gap row."""
    annotated = dict(gap)
    actionability = classify_gap_actionability(annotated)
    annotated["actionability"] = actionability
    annotated["cta_policy"] = (
        CTA_POLICY_ALLOWED
        if actionability == ACTIONABILITY_CTA_ALLOWED
        else CTA_POLICY_OBSERVATION_ONLY
    )
    return annotated


def classify_gap_actionability(gap: dict[str, Any]) -> str:
    """Classify whether a gap is objective enough to become a CTA."""
    gap_id = str(gap.get("gap_id") or "")
    field = str(gap.get("field") or "")

    if gap_id.startswith("meddpicc:") or field.startswith("meddpicc."):
        return ACTIONABILITY_NEEDS_HUMAN_JUDGMENT
    if gap_id == "attention:at_risk":
        return ACTIONABILITY_NEEDS_HUMAN_JUDGMENT
    if gap_id in OBJECTIVE_ATTENTION_GAP_IDS:
        return ACTIONABILITY_CTA_ALLOWED
    if field in OBJECTIVE_FIELDS:
        return ACTIONABILITY_CTA_ALLOWED
    if gap.get("status") in {"invalid", "attention"}:
        return ACTIONABILITY_CTA_ALLOWED
    return ACTIONABILITY_NEEDS_HUMAN_JUDGMENT
