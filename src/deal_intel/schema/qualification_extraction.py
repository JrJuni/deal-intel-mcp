from __future__ import annotations

import re
from math import isfinite
from typing import Any

from deal_intel.schema.qualification_framework import QualificationFramework
from deal_intel.user_memory import detect_secret_patterns

CONFIDENCE_LEVELS = {"low", "medium", "high"}
MAX_EVIDENCE_CHARS = 240
MAX_REASON_CHARS = 240


def build_qualification_extraction_contract(
    framework: QualificationFramework,
) -> dict[str, Any]:
    """Return the LLM-facing extraction contract for a qualification framework.

    The contract is intentionally serializable and side-effect free so the
    prompt layer can evolve without changing the evidence shape consumed by the
    metric engine.
    """
    dimensions = [
        {
            "key": key,
            "label": dimension.label,
            "description": dimension.description,
            "extraction_hint": dimension.extraction_hint,
            "score": "integer 0-5; omit this dimension when evidence is absent",
            "suggested_question": dimension.suggested_question,
        }
        for key, dimension in framework.dimensions.items()
        if dimension.enabled
    ]
    return {
        "framework_key": framework.key,
        "framework_display_name": framework.display_name,
        "score_scale": framework.score_scale.model_dump(mode="json"),
        "dimensions": dimensions,
        "output_schema": {
            "qualification": {
                "<dimension_key>": {
                    "score": "integer 0-5",
                    "evidence": "short paraphrased evidence, not full raw notes",
                    "reason": "short explanation for the score",
                    "confidence": "low | medium | high",
                }
            }
        },
        "rules": [
            "Use only dimension keys listed in this contract.",
            "Do not invent scores when the interaction has no evidence.",
            "Omit missing dimensions instead of assigning a neutral score.",
            "Keep evidence short and paraphrased; do not copy full raw content.",
            "Never include API keys, OAuth tokens, MongoDB URIs, or private keys.",
        ],
    }


def render_qualification_extraction_prompt_block(
    framework: QualificationFramework,
) -> str:
    """Render a compact text block that can be embedded into an LLM prompt."""
    contract = build_qualification_extraction_contract(framework)
    lines = [
        f"Active qualification framework: {contract['framework_display_name']} "
        f"({contract['framework_key']})",
        "Return JSON with a top-level `qualification` object.",
        "Dimensions:",
    ]
    for dimension in contract["dimensions"]:
        lines.append(
            "- {key}: {label}. {description} Evidence hint: {hint}".format(
                key=dimension["key"],
                label=dimension["label"],
                description=dimension["description"],
                hint=dimension["extraction_hint"],
            )
        )
    lines.extend(["Rules:", *[f"- {rule}" for rule in contract["rules"]]])
    return "\n".join(lines)


def normalize_qualification_extraction(
    payload: Any,
    *,
    framework: QualificationFramework,
) -> dict[str, Any]:
    """Normalize LLM-produced qualification evidence for storage.

    The function is permissive at the boundary and strict at the storage
    contract. Bad or ambiguous dimensions are dropped with warnings; valid
    scores remain usable by `compute_qualification_latest`.
    """
    warnings: list[dict[str, Any]] = []
    if not isinstance(payload, dict):
        return {
            "ok": True,
            "qualification": {},
            "warnings": [
                {
                    "code": "invalid_payload",
                    "message": "qualification extraction payload must be an object",
                }
            ],
        }

    signals = _extract_signal_mapping(payload)
    enabled_dimensions = {
        key: dimension
        for key, dimension in framework.dimensions.items()
        if dimension.enabled
    }
    disabled_dimensions = {
        key for key, dimension in framework.dimensions.items() if not dimension.enabled
    }
    normalized: dict[str, dict[str, Any]] = {}

    for key, value in signals.items():
        key_text = str(key)
        if key_text in disabled_dimensions:
            warnings.append(
                _warning(
                    "disabled_dimension",
                    key_text,
                    "dimension is disabled in the active framework",
                )
            )
            continue
        if key_text not in enabled_dimensions:
            warnings.append(
                _warning(
                    "unknown_dimension",
                    key_text,
                    "dimension is not part of the active framework",
                )
            )
            continue

        raw_dimension = value if isinstance(value, dict) else {"score": value}
        score, score_warning = _normalize_score(raw_dimension.get("score"))
        if score_warning:
            warnings.append(_warning(score_warning, key_text, "invalid score ignored"))
            continue

        dimension_out: dict[str, Any] = {"score": score}
        for field, limit in (("evidence", MAX_EVIDENCE_CHARS), ("reason", MAX_REASON_CHARS)):
            text, text_warning = _safe_text(raw_dimension.get(field), limit=limit)
            if text_warning:
                warnings.append(_warning(text_warning, key_text, f"{field} redacted"))
            if text:
                dimension_out[field] = text

        confidence = str(raw_dimension.get("confidence") or "").strip().lower()
        if confidence:
            if confidence in CONFIDENCE_LEVELS:
                dimension_out["confidence"] = confidence
            else:
                warnings.append(
                    _warning(
                        "invalid_confidence",
                        key_text,
                        "confidence must be low, medium, or high",
                    )
                )
        normalized[key_text] = dimension_out

    return {
        "ok": True,
        "qualification": normalized,
        "warnings": warnings,
    }


def _extract_signal_mapping(payload: dict[str, Any]) -> dict[str, Any]:
    qualification = payload.get("qualification")
    if isinstance(qualification, dict):
        return qualification
    return payload


def _normalize_score(value: Any) -> tuple[int | None, str | None]:
    if isinstance(value, bool) or value is None:
        return None, "invalid_score"
    if not isinstance(value, (int, float)):
        return None, "invalid_score"
    number = float(value)
    if not isfinite(number) or number < 0 or number > 5:
        return None, "score_out_of_range"
    if number != int(number):
        return None, "fractional_score"
    return int(number), None


def _safe_text(value: Any, *, limit: int) -> tuple[str, str | None]:
    text = _normalize_whitespace(str(value or ""))
    if not text:
        return "", None
    if detect_secret_patterns(text):
        return "", "secret_like_text"
    if len(text) > limit:
        return text[: max(limit - 3, 0)].rstrip() + "...", "text_truncated"
    return text, None


def _normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _warning(code: str, dimension: str, message: str) -> dict[str, Any]:
    return {
        "code": code,
        "dimension": dimension,
        "message": message,
    }
