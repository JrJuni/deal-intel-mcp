from __future__ import annotations

from deal_intel.errors import ErrorCode, MCPError, Stage
from deal_intel.storage.mongodb import MongoDBClient


def handle(mongo: MongoDBClient, *, deal_id: str) -> dict:
    deal = mongo.get_deal(deal_id)
    if deal is None:
        raise MCPError(
            error_code=ErrorCode.NOT_FOUND,
            stage=Stage.STORAGE,
            message=f"deal_id {deal_id!r} not found",
            retryable=False,
        )
    result = {"ok": True, "deal": deal}
    if deal.get("archived") is True:
        result["warnings"] = ["deal_archived"]
        result["archive"] = {
            "archived_at": deal.get("archived_at"),
            "archived_reason": deal.get("archived_reason"),
        }
    return result
