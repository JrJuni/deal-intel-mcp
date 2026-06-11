from __future__ import annotations

from deal_intel.providers.llm import LLMProvider
from deal_intel.storage.mongodb import MongoDBClient
from deal_intel.tools import add_interaction


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
    """Backward-compatible meeting intake backed by canonical interactions."""
    result = add_interaction.handle(
        mongo=mongo,
        llm=llm,
        cfg=cfg,
        embedding_provider=embedding_provider,
        deal_id=deal_id,
        date=date,
        interaction_type="meeting",
        direction="inbound",
        content=raw_notes,
        source_confidence="customer_stated",
        source_tool="add_meeting",
    )
    result["meeting_id"] = result["interaction_id"]
    return result
