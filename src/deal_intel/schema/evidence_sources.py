from __future__ import annotations

from collections.abc import Mapping
from typing import Any

INTERACTION_TYPE_LABELS = {
    "meeting": "Meeting",
    "email_thread": "Email thread",
    "user_interview": "User interview",
    "call_summary": "Call summary",
    "internal_note": "Internal note",
    "unknown": "Unknown source",
}

SOURCE_CONFIDENCE_LABELS = {
    "customer_stated": "customer-stated",
    "mixed": "mixed",
    "internal": "internal",
    "outbound_unconfirmed": "outbound-unconfirmed",
    "unknown": "unknown",
}


def evidence_source_label(evidence: Mapping[str, Any] | None) -> str:
    """Return a human-readable source label for curated evidence rows."""
    evidence = evidence or {}
    interaction_type = evidence_interaction_type(evidence)
    confidence = evidence_source_confidence(evidence)
    type_label = interaction_type_label(interaction_type)
    if confidence == "unknown":
        return type_label
    return f"{type_label} ({source_confidence_label(confidence)})"


def evidence_interaction_type(evidence: Mapping[str, Any] | None) -> str:
    evidence = evidence or {}
    raw_value = str(evidence.get("interaction_type") or "").strip().lower()
    if raw_value:
        return raw_value
    if evidence.get("meeting_id"):
        return "meeting"
    return "unknown"


def evidence_source_confidence(evidence: Mapping[str, Any] | None) -> str:
    evidence = evidence or {}
    raw_value = str(evidence.get("source_confidence") or "").strip().lower()
    return raw_value or "unknown"


def interaction_type_label(value: str | None) -> str:
    normalized = str(value or "unknown").strip().lower()
    if normalized in INTERACTION_TYPE_LABELS:
        return INTERACTION_TYPE_LABELS[normalized]
    return normalized.replace("_", " ").title()


def source_confidence_label(value: str | None) -> str:
    normalized = str(value or "unknown").strip().lower()
    return SOURCE_CONFIDENCE_LABELS.get(normalized, normalized.replace("_", "-"))
