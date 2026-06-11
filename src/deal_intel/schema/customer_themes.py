from __future__ import annotations

import json
from typing import Any

from deal_intel.schema.meddpicc import VALID_STAGES

THEME_TAXONOMY = {
    "cost_reduction": "비용 절감",
    "operational_efficiency": "운영 효율·자동화",
    "compliance_security": "규제·보안·컴플라이언스",
    "integration_migration": "연동·마이그레이션",
    "adoption_change_management": "사용자 채택·변화관리",
    "data_quality_governance": "데이터 품질·거버넌스",
    "reliability_performance": "안정성·성능",
    "reporting_visibility": "보고·가시성",
    "scalability": "확장성",
    "usability_accessibility": "사용성·접근성",
    "vendor_support": "공급사 지원·서비스",
    "customization_flexibility": "커스터마이징·유연성",
    "timeline_procurement": "도입 일정·구매 절차",
    "other": "기타",
}

THEME_DIMENSIONS = frozenset({"identify_pain", "decision_criteria", "metrics"})

STAGE_SIGNAL_CONFIDENCE = frozenset({"high", "medium", "low"})

THEME_CATALOG_PROMPT = "\n".join(
    f"- {key}: {label}" for key, label in THEME_TAXONOMY.items()
)


def load_json_response(text: str) -> Any:
    """Parse a JSON response, tolerating a single Markdown code fence."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    return json.loads(cleaned)


def normalize_customer_themes(raw: Any) -> list[dict]:
    """Validate LLM theme output and map it to the controlled taxonomy."""
    if not isinstance(raw, list):
        return []

    normalized = []
    seen: set[tuple[str, str, str]] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue

        evidence = str(item.get("evidence") or "").strip()
        dimension = str(item.get("dimension") or "").strip()
        if not evidence or dimension not in THEME_DIMENSIONS:
            continue

        theme_key = str(item.get("theme_key") or "").strip().lower()
        if theme_key not in THEME_TAXONOMY:
            theme_key = "other"

        try:
            importance = int(round(float(item.get("importance", 3))))
        except (TypeError, ValueError):
            importance = 3
        importance = max(1, min(importance, 5))
        evidence = evidence[:500]

        identity = (theme_key, dimension, evidence)
        if identity in seen:
            continue
        seen.add(identity)
        normalized.append(
            {
                "theme_key": theme_key,
                "label": THEME_TAXONOMY[theme_key],
                "dimension": dimension,
                "evidence": evidence,
                "importance": importance,
            }
        )
    return normalized[:5]


def normalize_stage_signal(raw: Any) -> dict | None:
    """Validate an optional stage-change signal from the LLM.

    Returns None unless the notes clearly point at a valid pipeline stage.
    This is only ever surfaced to the user as a suggestion — add_meeting never
    changes deal_stage automatically; the user must confirm via update_stage.
    """
    if not isinstance(raw, dict):
        return None
    suggested = str(raw.get("suggested_stage") or "").strip().lower()
    if suggested not in VALID_STAGES:
        return None
    confidence = str(raw.get("confidence") or "").strip().lower()
    if confidence not in STAGE_SIGNAL_CONFIDENCE:
        confidence = "low"
    evidence = str(raw.get("evidence") or "").strip()[:500]
    return {
        "suggested_stage": suggested,
        "confidence": confidence,
        "evidence": evidence,
    }


def parse_meeting_analysis(text: str) -> tuple[dict, list[dict], dict | None]:
    """Parse the combined MEDDPICC, customer-theme, and stage-signal response.

    Returns (meddpicc, customer_themes, stage_signal). stage_signal is None
    unless the notes clearly indicate a pipeline stage transition; it is a
    suggestion only and never mutates the deal.
    """
    payload = load_json_response(text)
    if not isinstance(payload, dict):
        return {}, [], None

    if isinstance(payload.get("meddpicc"), dict):
        meddpicc = payload["meddpicc"]
        themes = normalize_customer_themes(payload.get("customer_themes"))
        stage_signal = normalize_stage_signal(payload.get("stage_signal"))
        return meddpicc, themes, stage_signal

    # Backward compatibility if a provider returns the legacy MEDDPICC-only shape.
    return payload, [], None


def rebuild_deal_customer_themes(deal: dict) -> list[dict]:
    """Flatten interaction themes onto the deal for M0 aggregation and Atlas Charts."""
    from deal_intel.schema.interactions import iter_interactions

    flattened = []
    seen: set[tuple[str, str, str, str]] = set()
    for interaction in iter_interactions(deal):
        themes = normalize_customer_themes(interaction.get("customer_themes"))
        interaction_id = str(interaction.get("interaction_id") or "")
        interaction_date = str(interaction.get("date") or "")
        meeting_id = str(interaction.get("meeting_id") or interaction_id)
        for theme in themes:
            identity = (
                interaction_id,
                theme["theme_key"],
                theme["dimension"],
                theme["evidence"],
            )
            if identity in seen:
                continue
            seen.add(identity)
            flattened.append(
                {
                    **theme,
                    "interaction_id": interaction_id,
                    "interaction_date": interaction_date,
                    "interaction_type": interaction.get("interaction_type"),
                    "meeting_id": meeting_id,
                    "meeting_date": interaction_date,
                }
            )
    return flattened
