from __future__ import annotations

import uuid
from datetime import UTC, datetime

from deal_intel.errors import ErrorCode, MCPError, Stage
from deal_intel.providers.llm import LLMProvider
from deal_intel.schema.customer_themes import (
    THEME_CATALOG_PROMPT,
    parse_meeting_analysis,
    rebuild_deal_customer_themes,
)
from deal_intel.schema.meddpicc import compute_meddpicc_latest
from deal_intel.storage.mongodb import MongoDBClient
from deal_intel.tools.analytics_snapshot import (
    record_analytics_snapshot,
    snapshot_event_id,
)

_SYSTEM = "You are a B2B sales expert specializing in MEDDPICC deal qualification."

_PROMPT = """\
Extract MEDDPICC qualification signals from the meeting notes below.

For each MEDDPICC dimension present in the notes, return:
- score: 0-5  (0=absent, 1=weak mention, 3=moderate signal, 5=confirmed/strong)
- evidence: direct quote or close paraphrase from the notes

MEDDPICC dimensions:
- metrics: Quantifiable business impact, ROI, or success criteria
- economic_buyer: Decision-maker identity, authority level, and access
- decision_criteria: Formal or informal selection requirements
- decision_process: Procurement, approval, or timeline steps
- identify_pain: Core business problem, severity, and urgency
- champion: Internal advocate — name, position, commitment level
- competition: Competing vendors, alternatives, or status quo

Also extract 0-5 customer concern themes grounded only in identify_pain,
decision_criteria, or metrics evidence. Choose theme_key only from:
{theme_catalog}

For each customer theme return:
- theme_key
- dimension: identify_pain | decision_criteria | metrics
- evidence: direct quote or close paraphrase
- importance: 1-5, where 5 means explicitly critical or deal-breaking

Also detect whether the notes EXPLICITLY indicate a pipeline stage change.
Only emit "stage_signal" when there is direct evidence of a transition, e.g.:
- contract signed / PO issued / final selection won  → won
- deal rejected, lost to a competitor, or budget cut → lost
- project frozen / put on hold indefinitely          → stalled
- formal proposal or quote sent                       → proposal
- pricing/terms being negotiated                      → negotiation
When the notes do not clearly imply a transition, OMIT stage_signal entirely.
This is only a suggestion — never assume the stage has already changed.

stage_signal fields:
- suggested_stage: discovery | qualification | proposal | negotiation | won | lost | stalled
- confidence: high | medium | low
- evidence: direct quote or close paraphrase justifying the change

Omit MEDDPICC dimensions with no evidence. Do not infer unstated themes.
Return valid JSON only — no prose, no markdown fences.

Example output:
{{
  "meddpicc": {{
    "metrics": {{"score": 3, "evidence": "CFO wants 20% cost reduction by Q3"}},
    "identify_pain": {{"score": 4, "evidence": "Current system crashes weekly"}}
  }},
  "customer_themes": [
    {{
      "theme_key": "cost_reduction",
      "dimension": "metrics",
      "evidence": "CFO wants 20% cost reduction by Q3",
      "importance": 5
    }}
  ],
  "stage_signal": {{
    "suggested_stage": "won",
    "confidence": "high",
    "evidence": "Contract signed 6/13, PO issued"
  }}
}}

Meeting notes:
{notes}\
"""

_SUMMARY_SYSTEM = "You are a B2B sales assistant. Write in the same language as the input."
_SUMMARY_PROMPT = """\
Write a concise 2-3 sentence summary of this sales meeting.
Focus on: key decisions, commitments, pain points raised, and next steps.
Return ONLY the summary text — no headings, no bullet points.

Meeting notes:
{notes}\
"""


def _generate_summary(llm: LLMProvider, raw_notes: str) -> str:
    """Generate a brief meeting summary. Returns empty string on failure."""
    try:
        resp = llm.chat_once(
            system=_SUMMARY_SYSTEM,
            user=_SUMMARY_PROMPT.format(notes=raw_notes),
            max_tokens=256,
        )
        return resp.text.strip()
    except Exception:
        return ""


def _build_deal_text(deal: dict) -> str:
    """Concatenate meeting summaries (or raw_notes) for deal-level embedding."""
    parts = []
    for m in deal.get("meetings", []):
        text = m.get("summary") or (m.get("raw_notes", "")[:400])
        if text:
            date = m.get("date", "")
            parts.append(f"[{date}] {text}" if date else text)
    combined = " | ".join(parts)
    return combined[-1500:]  # fit within MiniLM's ~256-token window


def handle(
    mongo: MongoDBClient,
    llm: LLMProvider,
    cfg: dict,
    embedding_provider=None,
    *,
    deal_id: str,
    date: str,
    raw_notes: str,
) -> dict:
    deal = mongo.get_deal(deal_id)
    if deal is None:
        raise MCPError(
            error_code=ErrorCode.NOT_FOUND,
            stage=Stage.STORAGE,
            message=f"deal_id {deal_id!r} not found",
            retryable=False,
        )

    try:
        resp = llm.chat_once(
            system=_SYSTEM,
            user=_PROMPT.format(
                theme_catalog=THEME_CATALOG_PROMPT,
                notes=raw_notes,
            ),
            max_tokens=1024,
        )
    except Exception as exc:
        raise MCPError(
            error_code=ErrorCode.LLM_ERROR,
            stage=Stage.LLM,
            message=str(exc),
            retryable=True,
        ) from exc

    try:
        meddpicc_raw, customer_themes, stage_signal = parse_meeting_analysis(resp.text)
    except (TypeError, ValueError):
        meddpicc_raw = {}
        customer_themes = []
        stage_signal = None

    # Generate a brief meeting summary (graceful fallback on LLM failure).
    summary = _generate_summary(llm, raw_notes)

    meeting = {
        "meeting_id": str(uuid.uuid4()),
        "date": date,
        "raw_notes": raw_notes,
        "summary": summary,
        "meddpicc": meddpicc_raw,
        "customer_themes": customer_themes,
    }
    deal.setdefault("meetings", []).append(meeting)
    deal["customer_themes"] = rebuild_deal_customer_themes(deal)

    # Recompute deal-level MEDDPICC snapshot from all meetings (including this one).
    meddpicc_cfg = cfg.get("meddpicc", {})
    weights = meddpicc_cfg.get("weights", {})
    gap_threshold = int(meddpicc_cfg.get("gap_threshold", 2))
    deal["meddpicc_latest"] = compute_meddpicc_latest(
        deal["meetings"],
        weights=weights,
        gap_threshold=gap_threshold,
        deal_stage=deal.get("deal_stage", "discovery"),
    )

    # Generate deal-level semantic embedding from all meeting summaries.
    if embedding_provider is not None:
        deal_text = _build_deal_text(deal)
        if deal_text:
            try:
                deal["summary_embedding"] = embedding_provider.embed(deal_text)
            except Exception:
                pass  # non-critical — search_deals will skip deals without embeddings

    deal["updated_at"] = datetime.now(UTC).isoformat()

    try:
        mongo.upsert_deal(deal)
    except Exception as exc:
        raise MCPError(
            error_code=ErrorCode.STORAGE_ERROR,
            stage=Stage.STORAGE,
            message=str(exc),
            retryable=True,
        ) from exc

    # Surface a stage-change suggestion when the notes clearly imply a transition
    # away from the current stage. We DO NOT change deal_stage here — the assistant
    # must confirm with the user and then call update_stage explicitly.
    current_stage = deal.get("deal_stage", "discovery")
    stage_suggestion = None
    if stage_signal and stage_signal["suggested_stage"] != current_stage:
        stage_suggestion = {
            "current_stage": current_stage,
            "suggested_stage": stage_signal["suggested_stage"],
            "confidence": stage_signal["confidence"],
            "evidence": stage_signal["evidence"],
            "action": (
                f"These notes look like '{stage_signal['suggested_stage']}'. "
                f"Confirm with the user, then call update_stage(deal_id, "
                f"'{stage_signal['suggested_stage']}'). Stage was NOT changed automatically."
            ),
        }

    analytics_snapshot = record_analytics_snapshot(
        mongo=mongo,
        cfg=cfg,
        event_type="add_meeting",
        event_id=snapshot_event_id(
            "add_meeting",
            deal_id=deal_id,
            event_key=meeting["meeting_id"],
        ),
        deal=deal,
    )

    result = {
        "ok": True,
        "meeting_id": meeting["meeting_id"],
        "summary": summary,
        "meddpicc": meddpicc_raw,
        "meddpicc_latest": deal["meddpicc_latest"],
        "customer_themes": customer_themes,
        "stage_suggestion": stage_suggestion,
        "embedding_stored": embedding_provider is not None,
        "usage": resp.usage,
    }
    if analytics_snapshot is not None:
        result["analytics_snapshot"] = analytics_snapshot
    return result
