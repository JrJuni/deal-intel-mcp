from __future__ import annotations

from copy import deepcopy
from typing import Any

from deal_intel.errors import ErrorCode, MCPError, Stage
from deal_intel.storage.mongodb import MongoDBClient

SENSITIVE_SNAPSHOT_FIELDS = ("_id", "contacts", "summary_embedding")


def clean_required_text(value: str | None, field_name: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        raise MCPError(
            error_code=ErrorCode.INVALID_INPUT,
            stage=Stage.PREFLIGHT,
            message=f"{field_name} is required",
            retryable=False,
        )
    return cleaned


def require_confirmation(*, confirmed_by_user: bool, action: str) -> None:
    if not confirmed_by_user:
        raise MCPError(
            error_code=ErrorCode.INVALID_INPUT,
            stage=Stage.PREFLIGHT,
            message=f"{action} requires explicit user confirmation",
            hint={"required": "confirmed_by_user=true"},
            retryable=False,
        )


def get_deal_or_raise(mongo: MongoDBClient, deal_id: str) -> dict:
    try:
        deal = mongo.get_deal(deal_id)
    except Exception as exc:
        raise MCPError(
            error_code=ErrorCode.STORAGE_ERROR,
            stage=Stage.STORAGE,
            message=str(exc),
            retryable=True,
        ) from exc
    if deal is None:
        raise MCPError(
            error_code=ErrorCode.NOT_FOUND,
            stage=Stage.STORAGE,
            message=f"deal_id {deal_id!r} not found",
            retryable=False,
        )
    return deal


def validate_expected_company(deal: dict, expected_company: str) -> str:
    expected = clean_required_text(expected_company, "expected_company")
    actual = str(deal.get("company") or "").strip()
    if actual != expected:
        raise MCPError(
            error_code=ErrorCode.INVALID_INPUT,
            stage=Stage.PREFLIGHT,
            message="expected_company does not match the stored deal company",
            hint={"expected_company": expected, "stored_company": actual},
            retryable=False,
        )
    return expected


def safe_deal_snapshot(deal: dict) -> dict[str, Any]:
    """Return an audit-safe snapshot with raw notes, contacts, and vectors removed."""
    snapshot = deepcopy(deal)
    for field in SENSITIVE_SNAPSHOT_FIELDS:
        snapshot.pop(field, None)
    meetings = snapshot.get("meetings")
    if isinstance(meetings, list):
        for meeting in meetings:
            if isinstance(meeting, dict):
                meeting.pop("raw_notes", None)
    interactions = snapshot.get("interactions")
    if isinstance(interactions, list):
        for interaction in interactions:
            if isinstance(interaction, dict):
                interaction.pop("raw_content", None)
    return snapshot


def lifecycle_summary(deal: dict) -> dict[str, Any]:
    return {
        "deal_id": deal.get("deal_id"),
        "company": deal.get("company"),
        "industry": deal.get("industry"),
        "customer_segment": deal.get("customer_segment"),
        "deal_stage": deal.get("deal_stage"),
        "archived": deal.get("archived") is True,
        "archived_at": deal.get("archived_at"),
        "archived_reason": deal.get("archived_reason"),
        "restored_at": deal.get("restored_at"),
        "updated_at": deal.get("updated_at"),
    }


def write_deal_or_raise(mongo: MongoDBClient, deal: dict) -> None:
    try:
        mongo.upsert_deal(deal)
    except Exception as exc:
        raise MCPError(
            error_code=ErrorCode.STORAGE_ERROR,
            stage=Stage.STORAGE,
            message=str(exc),
            retryable=True,
        ) from exc
