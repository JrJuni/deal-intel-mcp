from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable
from typing import Any

from deal_intel.schema.industry_taxonomy import industry_candidates

SEGMENT_SEPARATOR = "; "

SEGMENT_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("startup", ("startup", "start-up", "스타트업")),
    ("enterprise", ("enterprise", "large enterprise", "대기업", "엔터프라이즈")),
    (
        "mid_market",
        ("mid-market", "mid_market", "middle market", "중견", "중견기업", "준대기업"),
    ),
    ("smb", ("smb", "small business", "중소", "중소기업")),
    (
        "public_sector",
        ("public sector", "public_sector", "공공기관", "공기업", "준공기업", "정부", "공공"),
    ),
    ("deeptech", ("deeptech", "deep tech", "딥테크")),
)

FUNDING_STAGE_RE = re.compile(
    r"\b(pre[-\s]?ipo|series\s*[a-f])\b",
    re.IGNORECASE,
)


def build_taxonomy_audit(
    deals: Iterable[dict],
    *,
    include_all: bool = False,
    limit: int = 50,
) -> dict:
    """Audit industry/customer_segment hygiene without storage writes or LLM calls."""

    rows = [_build_row(deal) for deal in deals]
    issue_rows = [row for row in rows if row["issue_count"] > 0]
    output_rows = rows if include_all else issue_rows
    output_rows.sort(key=_sort_key)
    limited_rows = output_rows[:limit]
    issue_counts = Counter(issue for row in rows for issue in row["issues"])
    confidence_counts = Counter(row["confidence"] for row in issue_rows)
    total_returnable_count = len(output_rows)
    return {
        "ok": True,
        "include_all": include_all,
        "limit": limit,
        "summary": {
            "deal_count": len(rows),
            "issue_deal_count": len(issue_rows),
            "returned_count": len(limited_rows),
            "issue_counts": dict(sorted(issue_counts.items())),
            "confidence_counts": dict(sorted(confidence_counts.items())),
            "needs_human_review_count": sum(
                1 for row in issue_rows if row["needs_human_review"]
            ),
        },
        "deals": limited_rows,
        "warnings": _warnings(
            issue_rows=issue_rows,
            returned_count=len(limited_rows),
            total_returnable_count=total_returnable_count,
        ),
    }


def _build_row(deal: dict) -> dict:
    current_industry = _clean(deal.get("industry"))
    current_segment = _clean(deal.get("customer_segment"))
    inference = infer_industry_metadata(
        current_industry=current_industry,
        current_segment=current_segment,
        company=deal.get("company"),
    )
    issues = _issues(
        current_industry=current_industry,
        current_segment=current_segment,
        inference=inference,
    )
    confidence = _confidence(issues=issues, inference=inference)
    needs_review = confidence == "low"
    review_explanation = _review_explanation(
        issues=issues,
        confidence=confidence,
        needs_review=needs_review,
        current_industry=current_industry,
        inference=inference,
    )
    update_payload = None
    if issues and inference["suggested_industry"]:
        update_payload = {
            "deal_id": deal.get("deal_id"),
            "confirmed_by_user": True,
            "industry": inference["suggested_industry"],
            "industry_tags": inference["suggested_industry_tags"],
            "customer_segment": inference["suggested_customer_segment"],
            "update_note": (
                "User confirmed taxonomy cleanup after reviewing deal context."
            ),
        }
    return {
        "deal_id": deal.get("deal_id"),
        "company": deal.get("company"),
        "deal_stage": deal.get("deal_stage"),
        "current_industry": current_industry,
        "current_customer_segment": current_segment,
        "suggested_industry": inference["suggested_industry"],
        "suggested_industry_tags": inference["suggested_industry_tags"],
        "suggested_customer_segment": inference["suggested_customer_segment"],
        "confidence": confidence,
        "needs_human_review": needs_review,
        "issues": issues,
        "issue_count": len(issues),
        "review_explanation": review_explanation,
        "context": _context_snippets(deal),
        "update_deal_payload": update_payload,
    }


def infer_industry_metadata(
    *,
    current_industry: str | None,
    current_segment: str | None = None,
    current_industry_tags: list[str] | None = None,
    company: str | None = None,
) -> dict:
    """Infer primary industry, tags, and customer segment from a stored label.

    This is intentionally deterministic. It is not trying to be a perfect BD
    classifier; it gives the product a sane default so operators only review the
    genuinely weird rows.
    """

    industry_parts = _split_parts(current_industry)
    detected_industries: list[str] = []
    detected_segments: list[str] = []
    unmapped_parts: list[str] = []

    for part in industry_parts:
        candidates = industry_candidates(part)
        segments = _segment_candidates(part)
        if candidates:
            detected_industries.extend(candidates)
        if segments:
            detected_segments.extend(segments)
        if not candidates and not segments:
            unmapped_parts.append(part)

    source = "industry"
    if not detected_industries:
        detected_industries.extend(industry_candidates(current_industry))
    if not detected_industries:
        company_candidates = industry_candidates(company)
        if company_candidates:
            detected_industries.extend(company_candidates)
            source = "company_name"

    normalized_current_tags: list[str] = []
    for tag in current_industry_tags or []:
        candidates = industry_candidates(tag)
        normalized_current_tags.extend(candidates or [tag])

    suggested_industry = detected_industries[0] if detected_industries else None
    suggested_tags = _dedupe([*detected_industries, *normalized_current_tags])
    suggested_segment = _merge_segment(current_segment, detected_segments)
    return {
        "suggested_industry": suggested_industry,
        "suggested_industry_tags": suggested_tags,
        "suggested_customer_segment": suggested_segment,
        "detected_industries": _dedupe(detected_industries),
        "detected_segments": _dedupe(detected_segments),
        "unmapped_parts": unmapped_parts,
        "inference_source": source if detected_industries else None,
        "research_query": _research_query(company, current_industry)
        if not detected_industries
        else None,
    }


def _research_query(company: str | None, current_industry: str | None) -> str | None:
    company = _clean(company)
    if not company:
        return None
    if current_industry:
        return f"{company} company industry business model"
    return f"{company} company industry"


def _issues(
    *,
    current_industry: str | None,
    current_segment: str | None,
    inference: dict,
) -> list[str]:
    issues = []
    suggested_industry = inference["suggested_industry"]
    suggested_segment = inference["suggested_customer_segment"]
    detected_industries = inference["detected_industries"]
    detected_segments = inference["detected_segments"]

    if not current_industry and suggested_industry:
        issues.append("inferred_missing_industry_from_company")
    elif not current_industry:
        issues.append("missing_industry")
    elif not suggested_industry:
        issues.append("unmapped_industry")
    if current_industry and suggested_industry and suggested_industry != current_industry:
        issues.append("normalized_primary_industry")
    if current_industry and len(detected_industries) > 1:
        issues.append("cross_industry_tags_detected")
    if detected_segments:
        issues.append("mixed_segment_in_industry")
    if suggested_segment and suggested_segment != current_segment:
        issues.append("missing_or_updated_customer_segment")
    return issues


def _confidence(*, issues: list[str], inference: dict) -> str:
    if not issues:
        return "none"
    if inference.get("inference_source") == "company_name":
        return "medium"
    if inference["suggested_industry"]:
        return "high"
    return "low"


def _review_explanation(
    *,
    issues: list[str],
    confidence: str,
    needs_review: bool,
    current_industry: str | None,
    inference: dict,
) -> dict:
    if not issues:
        return {
            "review_level": "clean",
            "mental_model": _taxonomy_mental_model(),
            "reason": "Industry, tags, and customer_segment already look separated.",
            "why_human_review": None,
            "what_to_check": [],
            "safe_next_step": "No taxonomy update is needed.",
        }

    if not needs_review:
        return {
            "review_level": "auto_apply_candidate",
            "mental_model": _taxonomy_mental_model(),
            "reason": (
                "The stored label contains recognizable industry and segment "
                "signals, so the system can normalize it into primary industry, "
                "industry_tags, and customer_segment without dropping meaning."
            ),
            "why_human_review": None,
            "what_to_check": [
                f"Industry becomes {inference['suggested_industry']!r}.",
                f"Tags become {inference['suggested_industry_tags']!r}.",
                f"Customer segment becomes {inference['suggested_customer_segment']!r}.",
            ],
            "safe_next_step": (
                "Apply the cleanup after reviewing the dry-run candidate list."
            ),
        }

    return {
        "review_level": "human_review_required",
        "mental_model": _taxonomy_mental_model(),
        "reason": (
            "The stored label does not match the configured taxonomy strongly "
            "enough for automatic normalization."
        ),
        "why_human_review": (
            f"{current_industry!r} has no confident industry match. Add a taxonomy "
            "rule or update the deal with the desired primary industry."
        ),
        "what_to_check": [
            "What is the buyer's actual business vertical?",
            "Should this become a new canonical industry rule?",
            "Which labels belong in customer_segment instead of industry?",
        ],
        "safe_next_step": "Use update_deal after choosing the target taxonomy.",
    }


def _taxonomy_mental_model() -> str:
    return (
        "industry is the market shelf the customer belongs on; "
        "industry_tags are extra shelves for cross-industry accounts; "
        "customer_segment is the sticky note about size, maturity, ownership, "
        "or funding stage."
    )


def _segment_candidates(value: str | None) -> list[str]:
    if not value:
        return []
    text = value.casefold()
    candidates = [
        canonical
        for canonical, patterns in SEGMENT_RULES
        if any(pattern.casefold() in text for pattern in patterns)
    ]
    if "mid_market" in candidates and ("준대기업" in text or "중견" in text):
        candidates = [candidate for candidate in candidates if candidate != "enterprise"]
    candidates.extend(_funding_stages(value))
    return _dedupe(candidates)


def _funding_stages(value: str) -> list[str]:
    stages = []
    for match in FUNDING_STAGE_RE.finditer(value):
        raw = match.group(1)
        if not raw:
            continue
        compact = re.sub(r"[-\s]+", "", raw).casefold()
        if compact == "preipo":
            stages.append("Pre-IPO")
        elif compact.startswith("series"):
            stages.append(f"Series {compact.removeprefix('series').upper()}")
    return stages


def _context_snippets(deal: dict) -> list[dict]:
    snippets = []
    for theme in deal.get("customer_themes") or []:
        if not isinstance(theme, dict):
            continue
        evidence = _clean(theme.get("evidence"))
        if not evidence:
            continue
        snippets.append(
            {
                "source": "customer_theme",
                "dimension": theme.get("dimension"),
                "label": theme.get("label"),
                "evidence": _truncate(evidence),
            }
        )
        if len(snippets) >= 3:
            return snippets
    for interaction in deal.get("interactions") or []:
        if not isinstance(interaction, dict):
            continue
        summary = _clean(interaction.get("summary"))
        if not summary:
            continue
        snippets.append(
            {
                "source": "interaction_summary",
                "interaction_type": interaction.get("interaction_type"),
                "summary": _truncate(summary),
            }
        )
        if len(snippets) >= 3:
            return snippets
    for meeting in deal.get("meetings") or []:
        if not isinstance(meeting, dict):
            continue
        summary = _clean(meeting.get("summary"))
        if not summary:
            continue
        snippets.append({"source": "meeting_summary", "summary": _truncate(summary)})
        if len(snippets) >= 3:
            return snippets
    return snippets


def _warnings(
    *,
    issue_rows: list[dict],
    returned_count: int,
    total_returnable_count: int,
) -> list[dict]:
    warnings = []
    if returned_count < total_returnable_count:
        warnings.append(
            {
                "code": "results_limited",
                "message": "Increase --limit or use --json to inspect every returned row.",
            }
        )
    if any(row["confidence"] == "low" for row in issue_rows):
        warnings.append(
            {
                "code": "taxonomy_rule_needed",
                "message": (
                    "Some rows could not be mapped automatically. Add a taxonomy "
                    "rule or update those deals explicitly."
                ),
            }
        )
    return warnings


def _sort_key(row: dict) -> tuple[int, int, str]:
    confidence_rank = {"high": 0, "medium": 1, "low": 2, "none": 3}
    return (
        confidence_rank.get(str(row.get("confidence")), 9),
        -int(row.get("issue_count") or 0),
        str(row.get("company") or ""),
    )


def _split_parts(value: str | None) -> list[str]:
    if not value:
        return []
    return [
        item.strip()
        for item in re.split(r"[,;/|·ㆍ]+", value)
        if item.strip()
    ]


def _merge_segment(current_segment: str | None, detected_segments: list[str]) -> str | None:
    segments = []
    if current_segment:
        segments.extend(_split_parts(current_segment))
    segments.extend(detected_segments)
    segments = _dedupe(segments)
    return SEGMENT_SEPARATOR.join(segments) if segments else current_segment


def _dedupe(values: Iterable[str]) -> list[str]:
    deduped = []
    for value in values:
        if value and value not in deduped:
            deduped.append(value)
    return deduped


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _truncate(value: str, *, limit: int = 180) -> str:
    value = " ".join(value.split())
    return value if len(value) <= limit else f"{value[: limit - 3]}..."
