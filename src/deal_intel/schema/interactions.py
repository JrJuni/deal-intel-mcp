from __future__ import annotations

import json
import re

from deal_intel.errors import ErrorCode, MCPError, Stage

DEFAULT_INTERACTION_TYPES = frozenset({
    "meeting",
    "email_thread",
    "user_interview",
    "call_summary",
    "internal_note",
})
VALID_DIRECTIONS = frozenset({"inbound", "outbound", "mixed", "internal"})
VALID_SOURCE_CONFIDENCE = frozenset({
    "customer_stated",
    "mixed",
    "internal",
    "outbound_unconfirmed",
    "unknown",
})
NON_SCORING_SOURCE_CONFIDENCE = frozenset({"internal", "outbound_unconfirmed"})

_TYPE_RE = re.compile(r"^[a-z][a-z0-9_]{1,63}$")


def interaction_types_from_config(cfg: dict | None) -> frozenset[str]:
    """Return registered interaction types.

    Built-in types are always allowed. Custom types must be explicitly listed
    in config so downstream handling stays predictable.
    """
    config = cfg or {}
    raw_custom = (
        config.get("interactions", {}).get("custom_types")
        or config.get("interaction_types", {}).get("custom")
        or []
    )
    if isinstance(raw_custom, str):
        raw_custom = [raw_custom]
    custom: set[str] = set()
    if isinstance(raw_custom, list):
        for item in raw_custom:
            normalized = str(item or "").strip().lower()
            if not normalized:
                continue
            if not _TYPE_RE.match(normalized):
                raise MCPError(
                    error_code=ErrorCode.CONFIG_ERROR,
                    stage=Stage.PREFLIGHT,
                    message=(
                        "interactions.custom_types must contain lowercase "
                        "slug values such as 'security_review'"
                    ),
                    hint={"invalid_interaction_type": normalized},
                    retryable=False,
                )
            custom.add(normalized)
    return frozenset(DEFAULT_INTERACTION_TYPES | custom)


def normalize_required_choice(
    *,
    field_name: str,
    value: str,
    valid_values: frozenset[str],
) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in valid_values:
        expected = ", ".join(sorted(valid_values))
        raise MCPError(
            error_code=ErrorCode.INVALID_INPUT,
            stage=Stage.PREFLIGHT,
            message=f"{field_name} must be one of: {expected}",
            retryable=False,
        )
    return normalized


def normalize_interaction_type(value: str, cfg: dict | None) -> str:
    return normalize_required_choice(
        field_name="interaction_type",
        value=value,
        valid_values=interaction_types_from_config(cfg),
    )


def normalize_direction(value: str) -> str:
    return normalize_required_choice(
        field_name="direction",
        value=value,
        valid_values=VALID_DIRECTIONS,
    )


def normalize_source_confidence(value: str) -> str:
    return normalize_required_choice(
        field_name="source_confidence",
        value=value,
        valid_values=VALID_SOURCE_CONFIDENCE,
    )


def default_source_confidence(interaction_type: str, direction: str) -> str:
    if direction == "outbound":
        return "outbound_unconfirmed"
    if interaction_type == "internal_note" or direction == "internal":
        return "internal"
    if direction == "inbound":
        return "customer_stated"
    if direction == "mixed":
        return "mixed"
    return "unknown"


def resolve_source_confidence(
    interaction_type: str,
    direction: str,
    source_confidence: str | None,
) -> str:
    if source_confidence is None or str(source_confidence).strip() == "":
        return default_source_confidence(interaction_type, direction)
    return normalize_source_confidence(source_confidence)


def scoring_applies(source_confidence: str) -> bool:
    return source_confidence not in NON_SCORING_SOURCE_CONFIDENCE


def parse_participants(value: str | list[str] | None) -> list[str]:
    if value is None:
        return []
    raw_items = value if isinstance(value, list) else str(value).replace("\n", ",").split(",")
    participants = []
    seen: set[str] = set()
    for item in raw_items:
        participant = str(item or "").strip()
        if not participant or participant in seen:
            continue
        seen.add(participant)
        participants.append(participant[:120])
    return participants[:20]


def parse_custom_fields_json(value: str | None) -> dict:
    if value is None or str(value).strip() == "":
        return {}
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise MCPError(
            error_code=ErrorCode.INVALID_INPUT,
            stage=Stage.PREFLIGHT,
            message="custom_fields_json must be valid JSON object text",
            retryable=False,
        ) from exc
    if not isinstance(payload, dict):
        raise MCPError(
            error_code=ErrorCode.INVALID_INPUT,
            stage=Stage.PREFLIGHT,
            message="custom_fields_json must decode to a JSON object",
            retryable=False,
        )
    return payload


def normalize_interaction_record(interaction: dict) -> dict:
    interaction_id = str(
        interaction.get("interaction_id")
        or interaction.get("meeting_id")
        or ""
    )
    interaction_type = str(interaction.get("interaction_type") or "meeting").strip().lower()
    direction = str(interaction.get("direction") or "inbound").strip().lower()
    source_confidence = str(
        interaction.get("source_confidence")
        or default_source_confidence(interaction_type, direction)
    ).strip().lower()
    raw_content = str(
        interaction.get("raw_content")
        or interaction.get("raw_notes")
        or ""
    )
    scoring = interaction.get("scoring_applied")
    if scoring is None:
        scoring = scoring_applies(source_confidence)
    normalized = {
        "interaction_id": interaction_id,
        "meeting_id": str(interaction.get("meeting_id") or interaction_id),
        "date": str(interaction.get("date") or ""),
        "interaction_type": interaction_type,
        "direction": direction,
        "source_confidence": source_confidence,
        "participants": parse_participants(interaction.get("participants")),
        "subject": str(interaction.get("subject") or "")[:200],
        "summary": str(interaction.get("summary") or ""),
        "raw_content": raw_content,
        "meddpicc": interaction.get("meddpicc") or {},
        "customer_themes": interaction.get("customer_themes") or [],
        "unconfirmed_meddpicc": interaction.get("unconfirmed_meddpicc") or {},
        "unconfirmed_customer_themes": (
            interaction.get("unconfirmed_customer_themes") or []
        ),
        "scoring_applied": bool(scoring),
        "custom_fields": interaction.get("custom_fields") or {},
    }
    return normalized


def iter_interactions(
    deal: dict,
    *,
    include_legacy_meetings: bool = True,
) -> list[dict]:
    normalized: list[dict] = []
    seen: set[str] = set()
    interactions = deal.get("interactions")
    if isinstance(interactions, list) and interactions:
        for item in interactions:
            if not isinstance(item, dict):
                continue
            interaction = normalize_interaction_record(item)
            identity = str(
                interaction.get("interaction_id")
                or interaction.get("meeting_id")
                or ""
            )
            if identity:
                seen.add(identity)
            normalized.append(interaction)
    if not include_legacy_meetings:
        return normalized
    meetings = deal.get("meetings")
    if not isinstance(meetings, list):
        return normalized
    for meeting in meetings:
        if not isinstance(meeting, dict):
            continue
        interaction = normalize_interaction_record(meeting)
        identity = str(
            interaction.get("interaction_id")
            or interaction.get("meeting_id")
            or ""
        )
        if identity and identity in seen:
            continue
        if identity:
            seen.add(identity)
        normalized.append(interaction)
    return normalized


def scoring_interactions(deal: dict) -> list[dict]:
    return [
        interaction
        for interaction in iter_interactions(deal)
        if interaction.get("scoring_applied") is not False
    ]


def build_deal_text(deal: dict) -> str:
    """Concatenate interaction summaries/content for deal-level embedding."""
    parts = []
    for interaction in iter_interactions(deal):
        text = interaction.get("summary") or interaction.get("raw_content", "")[:400]
        if text:
            date = interaction.get("date", "")
            parts.append(f"[{date}] {text}" if date else str(text))
    combined = " | ".join(parts)
    return combined[-1500:]
