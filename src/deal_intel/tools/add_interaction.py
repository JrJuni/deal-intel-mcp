from __future__ import annotations

import uuid
from datetime import UTC, datetime

from deal_intel.errors import ErrorCode, MCPError, Stage
from deal_intel.providers.llm import LLMProvider
from deal_intel.qualification_config import resolve_active_qualification_framework
from deal_intel.schema.customer_themes import (
    THEME_CATALOG_PROMPT,
    load_json_response,
    parse_meeting_analysis_payload,
    rebuild_deal_customer_themes,
)
from deal_intel.schema.interactions import (
    build_deal_text,
    normalize_direction,
    normalize_interaction_type,
    parse_custom_fields_json,
    parse_participants,
    resolve_source_confidence,
    scoring_applies,
    source_policy_summary,
)
from deal_intel.schema.qualification_extraction import (
    normalize_qualification_extraction,
    render_qualification_extraction_prompt_block,
)
from deal_intel.schema.qualification_framework import (
    qualification_framework_fingerprint,
)
from deal_intel.storage.mongodb import MongoDBClient
from deal_intel.tools.analytics_snapshot import (
    record_analytics_snapshot,
    snapshot_event_id,
)
from deal_intel.tools.qualification_snapshot import rebuild_latest_snapshots
from deal_intel.usage import build_llm_usage_metadata, summarize_usage

_SYSTEM = "You are a B2B sales expert specializing in deal qualification."

_PROMPT = """\
Extract deal qualification signals from this customer interaction.

Source metadata:
- interaction_type: {interaction_type}
- direction: {direction}
- source_confidence: {source_confidence}

Evidence rules:
- Customer-stated evidence is strongest: meetings, direct user interviews,
  inbound customer emails, and explicit customer replies inside mixed threads.
- For outbound-only or internal-only content, do NOT treat seller claims,
  hypotheses, or proposed benefits as confirmed customer evidence.
- If outbound/internal-only content includes no explicit customer reply or quote,
  omit MEDDPICC dimensions rather than inventing strength.
- Call summaries are acceptable only when they describe what the customer said
  or committed to, not just what the seller pitched.
- User interviews can be treated like direct customer evidence when they contain
  clear statements from the user or prospect.

For each MEDDPICC dimension present in the interaction, return:
- score: 0-5 (0=absent, 1=weak mention, 3=moderate signal, 5=confirmed/strong)
- evidence: direct quote or close paraphrase from the interaction

MEDDPICC dimensions:
- metrics: Quantifiable business impact, ROI, or success criteria
- economic_buyer: Decision-maker identity, authority level, and access
- decision_criteria: Formal or informal selection requirements
- decision_process: Procurement, approval, or timeline steps
- identify_pain: Core business problem, severity, and urgency
- champion: Internal advocate — name, position, commitment level
- competition: Competing vendors, alternatives, or status quo

{qualification_framework_prompt}

Also extract 0-5 customer concern themes grounded only in identify_pain,
decision_criteria, or metrics evidence. Choose theme_key only from:
{theme_catalog}

For each customer theme return:
- theme_key
- dimension: identify_pain | decision_criteria | metrics
- evidence: direct quote or close paraphrase
- importance: 1-5, where 5 means explicitly critical or deal-breaking

Also detect whether the interaction EXPLICITLY indicates a pipeline stage change.
Only emit "stage_signal" when there is direct evidence of a transition, e.g.:
- contract signed / PO issued / final selection won  -> won
- deal rejected, lost to a competitor, or budget cut -> lost
- project frozen / put on hold indefinitely          -> stalled
- formal proposal or quote sent                       -> proposal
- pricing/terms being negotiated                      -> negotiation
When the interaction does not clearly imply a transition, OMIT stage_signal.
This is only a suggestion — never assume the stage has already changed.

stage_signal fields:
- suggested_stage: discovery | qualification | proposal | negotiation | won | lost | stalled
- confidence: high | medium | low
- evidence: direct quote or close paraphrase justifying the change

Omit MEDDPICC dimensions with no evidence. Do not infer unstated themes.
Return valid JSON only — no prose, no markdown fences.

Interaction content:
{content}\
"""

_SUMMARY_SYSTEM = "You are a B2B sales assistant. Write in the same language as the input."
_SUMMARY_PROMPT = """\
Write a concise 2-3 sentence summary of this customer interaction.
Focus on: customer-stated facts, commitments, pain points raised, and next steps.
For outbound-only or internal-only content, clearly keep it as unconfirmed unless
the content includes a customer reply or quote.
Return ONLY the summary text — no headings, no bullet points.

Interaction content:
{content}\
"""


def _generate_summary(llm: LLMProvider, content: str) -> tuple[str, dict]:
    try:
        resp = llm.chat_once(
            system=_SUMMARY_SYSTEM,
            user=_SUMMARY_PROMPT.format(content=content),
            max_tokens=256,
        )
        return resp.text.strip(), resp.usage
    except Exception:
        return "", {}


def _stage_suggestion_from_signal(
    *,
    deal: dict,
    stage_signal: dict | None,
) -> dict | None:
    current_stage = deal.get("deal_stage", "discovery")
    if not stage_signal or stage_signal["suggested_stage"] == current_stage:
        return None
    return {
        "current_stage": current_stage,
        "suggested_stage": stage_signal["suggested_stage"],
        "confidence": stage_signal["confidence"],
        "evidence": stage_signal["evidence"],
        "action": (
            f"This interaction looks like '{stage_signal['suggested_stage']}'. "
            f"Confirm with the user, then call update_stage(deal_id, "
            f"'{stage_signal['suggested_stage']}'). Stage was NOT changed automatically."
        ),
    }


def _qualification_framework_prompt(framework) -> str:
    if framework.key == "meddpicc":
        return (
            "Active qualification framework: MEDDPICC. The top-level `meddpicc` "
            "object is the framework evidence. Omit the top-level `qualification` "
            "object unless a custom framework is active."
        )
    return (
        "Also extract the active custom qualification framework below. Return its "
        "signals in a separate top-level `qualification` object while keeping "
        "legacy MEDDPICC, customer_themes, and stage_signal separate.\n\n"
        + render_qualification_extraction_prompt_block(framework)
    )


def handle(
    mongo: MongoDBClient,
    llm: LLMProvider,
    cfg: dict,
    embedding_provider=None,
    *,
    deal_id: str,
    date: str,
    interaction_type: str,
    direction: str,
    content: str,
    participants: str | list[str] | None = None,
    subject: str | None = None,
    source_confidence: str | None = None,
    custom_fields_json: str | None = None,
    source_tool: str = "add_interaction",
) -> dict:
    normalized_type = normalize_interaction_type(interaction_type, cfg)
    normalized_direction = normalize_direction(direction)
    normalized_content = str(content or "").strip()
    if not normalized_content:
        raise MCPError(
            error_code=ErrorCode.INVALID_INPUT,
            stage=Stage.PREFLIGHT,
            message="content is required",
            retryable=False,
        )
    resolved_confidence = resolve_source_confidence(
        normalized_type,
        normalized_direction,
        source_confidence,
    )
    normalized_participants = parse_participants(participants)
    normalized_subject = str(subject or "").strip()[:200]
    custom_fields = parse_custom_fields_json(custom_fields_json)

    deal = mongo.get_deal(deal_id)
    if deal is None:
        raise MCPError(
            error_code=ErrorCode.NOT_FOUND,
            stage=Stage.STORAGE,
            message=f"deal_id {deal_id!r} not found",
            retryable=False,
        )

    try:
        active_framework = resolve_active_qualification_framework(cfg)
    except ValueError as exc:
        raise MCPError(
            error_code=ErrorCode.CONFIG_ERROR,
            stage=Stage.PREFLIGHT,
            message=str(exc),
            retryable=False,
        ) from exc
    active_framework_hash = qualification_framework_fingerprint(active_framework)

    try:
        resp = llm.chat_once(
            system=_SYSTEM,
            user=_PROMPT.format(
                interaction_type=normalized_type,
                direction=normalized_direction,
                source_confidence=resolved_confidence,
                qualification_framework_prompt=_qualification_framework_prompt(
                    active_framework
                ),
                theme_catalog=THEME_CATALOG_PROMPT,
                content=normalized_content,
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
        analysis_payload = load_json_response(resp.text)
        meddpicc_raw, customer_themes, stage_signal = parse_meeting_analysis_payload(
            analysis_payload
        )
    except (TypeError, ValueError):
        analysis_payload = {}
        meddpicc_raw = {}
        customer_themes = []
        stage_signal = None

    qualification_raw: dict = {}
    qualification_warnings: list[dict] = []
    if active_framework.key != "meddpicc":
        qualification_result = normalize_qualification_extraction(
            analysis_payload,
            framework=active_framework,
        )
        qualification_raw = qualification_result["qualification"]
        qualification_warnings = qualification_result["warnings"]

    scoring_applied = scoring_applies(resolved_confidence)
    source_policy = source_policy_summary(
        interaction_type=normalized_type,
        direction=normalized_direction,
        source_confidence=resolved_confidence,
    )
    scored_meddpicc = meddpicc_raw if scoring_applied else {}
    scored_qualification = qualification_raw if scoring_applied else {}
    scored_customer_themes = customer_themes if scoring_applied else []

    summary, summary_usage = _generate_summary(llm, normalized_content)
    interaction_id = str(uuid.uuid4())
    llm_usage = build_llm_usage_metadata(
        cfg,
        source_tool=source_tool,
        calls=[
            {"operation": "extract_signals", "usage": resp.usage},
            {"operation": "summarize_interaction", "usage": summary_usage},
        ],
    )
    source_metadata = {
        "source": source_tool,
        "interaction_id": interaction_id,
        "meeting_id": interaction_id,
        "interaction_type": normalized_type,
        "direction": normalized_direction,
        "source_confidence": resolved_confidence,
        "participants": normalized_participants,
        "subject": normalized_subject,
    }
    interaction_record = {
        "date": date,
        "raw_content": normalized_content,
        "summary": summary,
        "meddpicc": scored_meddpicc,
        "qualification": scored_qualification,
        "qualification_framework": active_framework.key,
        "qualification_framework_hash": active_framework_hash,
        "customer_themes": scored_customer_themes,
        "scoring_applied": scoring_applied,
        "llm_usage": llm_usage,
        "custom_fields": custom_fields,
        **source_metadata,
    }
    if not scoring_applied and meddpicc_raw:
        interaction_record["unconfirmed_meddpicc"] = meddpicc_raw
    if not scoring_applied and qualification_raw:
        interaction_record["unconfirmed_qualification"] = qualification_raw
    if not scoring_applied and customer_themes:
        interaction_record["unconfirmed_customer_themes"] = customer_themes
    if qualification_warnings:
        interaction_record["qualification_extraction_warnings"] = qualification_warnings

    deal.setdefault("interactions", []).append(interaction_record)
    deal["customer_themes"] = rebuild_deal_customer_themes(deal)

    try:
        snapshots = rebuild_latest_snapshots(deal, cfg)
    except ValueError as exc:
        raise MCPError(
            error_code=ErrorCode.CONFIG_ERROR,
            stage=Stage.PREFLIGHT,
            message=str(exc),
            retryable=False,
        ) from exc
    deal["meddpicc_latest"] = snapshots["meddpicc_latest"]
    deal["qualification_latest"] = snapshots["qualification_latest"]

    if embedding_provider is not None:
        deal_text = build_deal_text(deal)
        if deal_text:
            try:
                deal["summary_embedding"] = embedding_provider.embed(deal_text)
            except Exception:
                pass

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

    stage_suggestion = _stage_suggestion_from_signal(
        deal=deal,
        stage_signal=stage_signal,
    )
    analytics_snapshot = record_analytics_snapshot(
        mongo=mongo,
        cfg=cfg,
        event_type=source_tool,
        event_id=snapshot_event_id(
            source_tool,
            deal_id=deal_id,
            event_key=interaction_id,
        ),
        deal=deal,
    )

    result = {
        "ok": True,
        "interaction_id": interaction_id,
        "meeting_id": interaction_id,
        "interaction_type": normalized_type,
        "direction": normalized_direction,
        "source_confidence": resolved_confidence,
        "source_policy": source_policy,
        "participants": normalized_participants,
        "subject": normalized_subject,
        "summary": summary,
        "meddpicc": scored_meddpicc,
        "unconfirmed_meddpicc": meddpicc_raw if not scoring_applied else {},
        "active_qualification_framework": active_framework.key,
        "active_qualification_framework_hash": active_framework_hash,
        "qualification": scored_qualification,
        "unconfirmed_qualification": qualification_raw if not scoring_applied else {},
        "qualification_extraction_warnings": qualification_warnings,
        "meddpicc_latest": deal["meddpicc_latest"],
        "qualification_latest": deal["qualification_latest"],
        "customer_themes": scored_customer_themes,
        "unconfirmed_customer_themes": customer_themes if not scoring_applied else [],
        "scoring_applied": scoring_applied,
        "stage_suggestion": stage_suggestion,
        "embedding_stored": embedding_provider is not None,
        "usage": resp.usage,
        "usage_summary": {
            "calls": llm_usage["calls"],
            "totals": summarize_usage([resp.usage, summary_usage]),
            "estimated_cost_usd": llm_usage["estimated_cost_usd"],
            "cost_basis": llm_usage["cost_basis"],
        },
    }
    if analytics_snapshot is not None:
        result["analytics_snapshot"] = analytics_snapshot
    return result
