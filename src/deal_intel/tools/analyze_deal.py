from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime

from deal_intel.errors import ErrorCode, MCPError, Stage
from deal_intel.providers.llm import LLMProvider
from deal_intel.schema.interactions import scoring_interactions
from deal_intel.storage.mongodb import MongoDBClient

_SYSTEM = "You are a senior B2B sales strategist. Be direct, specific, and actionable."

_PROMPT = """\
Analyze this deal's MEDDPICC qualification status and provide a concrete BD strategy.

Deal: {company} | Stage: {stage} | Interactions: {interaction_count}
Industry: {industry} | Customer segment: {customer_segment}
{size_line}
MEDDPICC scores (avg across scoring-eligible interactions, 0=no data / 5=confirmed):
{meddpicc_summary}

Provide:

**1. Top 3 Gaps**
Which MEDDPICC dimensions are weakest, and why each gap is a deal risk.

**2. Next 3 Actions**
Specific, immediate steps to advance the deal (who to contact, what to ask, what to prepare).

**3. Win/Risk Assessment**
Probability estimate and the single biggest risk factor right now.

**4. GTM Positioning**
How to frame the value proposition for this specific prospect given their pain and metrics.\
"""

_DIMS = [
    "metrics", "economic_buyer", "decision_criteria",
    "decision_process", "identify_pain", "champion", "competition",
]


def _meddpicc_summary(interactions: list[dict]) -> str:
    scores: dict[str, list[int]] = defaultdict(list)
    for interaction in interactions:
        for k, v in (interaction.get("meddpicc") or {}).items():
            if isinstance(v, dict) and isinstance(v.get("score"), int):
                scores[k].append(v["score"])
    lines = []
    for d in _DIMS:
        if scores[d]:
            avg = sum(scores[d]) / len(scores[d])
            n = len(scores[d])
            lines.append(f"  {d}: {avg:.1f}/5 ({n} data point{'s' if n > 1 else ''})")
        else:
            lines.append(f"  {d}: no data")
    return "\n".join(lines)


def handle(mongo: MongoDBClient, llm: LLMProvider, *, deal_id: str) -> dict:
    deal = mongo.get_deal(deal_id)
    if deal is None:
        raise MCPError(
            error_code=ErrorCode.NOT_FOUND,
            stage=Stage.STORAGE,
            message=f"deal_id {deal_id!r} not found",
            retryable=False,
        )

    interactions = scoring_interactions(deal)
    currency = deal.get("deal_size_currency") or "KRW"
    size_line = (
        f"Deal size: {deal['deal_size_amount']:,} {currency}\n"
        if deal.get("deal_size_amount")
        else ""
    )
    prompt = _PROMPT.format(
        company=deal["company"],
        stage=deal.get("deal_stage", "unknown"),
        industry=deal.get("industry") or "unknown",
        customer_segment=deal.get("customer_segment") or "unknown",
        interaction_count=len(interactions),
        size_line=size_line,
        meddpicc_summary=_meddpicc_summary(interactions),
    )

    try:
        resp = llm.chat_once(system=_SYSTEM, user=prompt, max_tokens=2048)
    except Exception as exc:
        raise MCPError(
            error_code=ErrorCode.LLM_ERROR,
            stage=Stage.ANALYSIS,
            message=str(exc),
            retryable=True,
        ) from exc

    deal["bd_strategy"] = resp.text
    deal["updated_at"] = datetime.now(UTC).isoformat()
    try:
        mongo.upsert_deal(deal)
    except Exception:
        pass  # analysis still returned even if save fails

    return {"ok": True, "deal_id": deal_id, "analysis": resp.text, "usage": resp.usage}
