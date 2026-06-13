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
    ("mid_market", ("mid-market", "mid_market", "middle market", "중견", "중견기업")),
    ("smb", ("smb", "small business", "중소", "중소기업")),
    ("public_sector", ("public sector", "public_sector", "공공기관", "공기업", "준공기업")),
)

FUNDING_STAGE_RE = re.compile(
    r"\b(pre[-\s]?ipo|series\s*[a-f])\b|시리즈\s*([a-fA-F가-하])",
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
    issue_counts = Counter(
        issue
        for row in rows
        for issue in row["issues"]
    )
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
    industry_candidates = _industry_candidates(current_industry)
    segment_candidates = _segment_candidates(current_industry)
    issues = _issues(
        current_industry=current_industry,
        current_segment=current_segment,
        industry_candidates=industry_candidates,
        segment_candidates=segment_candidates,
    )
    suggested_industry = _suggested_industry(
        current_industry=current_industry,
        industry_candidates=industry_candidates,
        segment_candidates=segment_candidates,
    )
    suggested_segment = _suggested_segment(current_segment, segment_candidates)
    confidence = _confidence(
        issues=issues,
        industry_candidates=industry_candidates,
        segment_candidates=segment_candidates,
        suggested_industry=suggested_industry,
        suggested_segment=suggested_segment,
    )
    needs_review = confidence != "high" or "multiple_industry_candidates" in issues
    review_explanation = _review_explanation(
        issues=issues,
        confidence=confidence,
        needs_review=needs_review,
        current_industry=current_industry,
        suggested_industry=suggested_industry,
        suggested_segment=suggested_segment,
        industry_candidates=industry_candidates,
        segment_candidates=segment_candidates,
    )
    update_payload = None
    if issues:
        update_payload = {
            "deal_id": deal.get("deal_id"),
            "confirmed_by_user": True,
            "industry": suggested_industry,
            "customer_segment": suggested_segment,
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
        "suggested_industry": suggested_industry,
        "suggested_customer_segment": suggested_segment,
        "confidence": confidence,
        "needs_human_review": needs_review,
        "issues": issues,
        "issue_count": len(issues),
        "review_explanation": review_explanation,
        "context": _context_snippets(deal),
        "update_deal_payload": update_payload,
    }


def _issues(
    *,
    current_industry: str | None,
    current_segment: str | None,
    industry_candidates: list[str],
    segment_candidates: list[str],
) -> list[str]:
    issues = []
    if not current_industry:
        issues.append("missing_industry")
    if current_industry and segment_candidates:
        issues.append("mixed_segment_in_industry")
    if current_industry and _has_separator(current_industry) and len(industry_candidates) > 1:
        issues.append("multiple_industry_candidates")
    if current_industry and _has_separator(current_industry) and not segment_candidates:
        issues.append("compound_industry_needs_review")
    if segment_candidates and not current_segment:
        issues.append("missing_customer_segment")
    return issues


def _suggested_industry(
    *,
    current_industry: str | None,
    industry_candidates: list[str],
    segment_candidates: list[str],
) -> str | None:
    if industry_candidates:
        return " / ".join(industry_candidates)
    if current_industry and not segment_candidates:
        return current_industry
    return None


def _suggested_segment(
    current_segment: str | None,
    segment_candidates: list[str],
) -> str | None:
    segments = []
    if current_segment:
        segments.extend(_split_segments(current_segment))
    segments.extend(segment_candidates)
    segments = _dedupe(segments)
    return SEGMENT_SEPARATOR.join(segments) if segments else current_segment


def _confidence(
    *,
    issues: list[str],
    industry_candidates: list[str],
    segment_candidates: list[str],
    suggested_industry: str | None,
    suggested_segment: str | None,
) -> str:
    if not issues:
        return "none"
    if (
        suggested_industry
        and suggested_segment
        and len(industry_candidates) == 1
        and segment_candidates
        and "multiple_industry_candidates" not in issues
        and "compound_industry_needs_review" not in issues
    ):
        return "high"
    if suggested_industry or suggested_segment:
        return "medium"
    return "low"


def _review_explanation(
    *,
    issues: list[str],
    confidence: str,
    needs_review: bool,
    current_industry: str | None,
    suggested_industry: str | None,
    suggested_segment: str | None,
    industry_candidates: list[str],
    segment_candidates: list[str],
) -> dict:
    """Explain why a taxonomy row is safe to apply or needs human review.

    The language is intentionally product-facing. This command often runs before
    a human trusts the taxonomy cleanup flow, so it should explain the judgment
    boundary instead of only printing a machine label.
    """

    if not issues:
        return {
            "review_level": "clean",
            "mental_model": _taxonomy_mental_model(),
            "reason": "Industry and customer_segment already look separated.",
            "why_human_review": None,
            "what_to_check": [],
            "safe_next_step": "No taxonomy update is needed.",
        }

    if not needs_review:
        return {
            "review_level": "auto_apply_candidate",
            "mental_model": _taxonomy_mental_model(),
            "reason": (
                "The current industry contains one clear business vertical and "
                "one or more account-segment labels, so the split preserves both "
                "meanings without choosing between competing industries."
            ),
            "why_human_review": None,
            "what_to_check": [
                f"Industry becomes {suggested_industry!r}.",
                f"Customer segment becomes {suggested_segment!r}.",
            ],
            "safe_next_step": (
                "If the user accepts this cleanup rule, it can be applied with "
                "apply-taxonomy-cleanup."
            ),
        }

    reason = _human_review_reason(
        current_industry=current_industry,
        suggested_industry=suggested_industry,
        industry_candidates=industry_candidates,
        segment_candidates=segment_candidates,
        issues=issues,
        confidence=confidence,
    )
    return {
        "review_level": "human_review_required",
        "mental_model": _taxonomy_mental_model(),
        "reason": reason["reason"],
        "why_human_review": reason["why_human_review"],
        "what_to_check": reason["what_to_check"],
        "safe_next_step": (
            "Open the deal context, pick the single best business vertical, then "
            "use update_deal with a user-confirmed update_note."
        ),
    }


def _taxonomy_mental_model() -> str:
    return (
        "industry is the market shelf the customer belongs on; "
        "customer_segment is the sticky note about size, maturity, ownership, "
        "or funding stage."
    )


def _human_review_reason(
    *,
    current_industry: str | None,
    suggested_industry: str | None,
    industry_candidates: list[str],
    segment_candidates: list[str],
    issues: list[str],
    confidence: str,
) -> dict:
    if "multiple_industry_candidates" in issues:
        return {
            "reason": (
                "More than one plausible industry was detected, so an automatic "
                "split would be choosing a reporting taxonomy on behalf of the user."
            ),
            "why_human_review": (
                f"{current_industry!r} can be read as {suggested_industry!r}. "
                "Those choices change industry charts and customer-theme grouping, "
                "and can shift weekly reporting, so the system should not guess."
            ),
            "what_to_check": [
                "Which vertical should this account be grouped under in weekly reporting?",
                "Is the other detected label a sub-industry, business model, or just context?",
                "Would BD search for this company by the suggested industry name?",
            ],
        }
    if "compound_industry_needs_review" in issues:
        return {
            "reason": (
                "The industry has separators but no confident canonical vertical "
                "match, so the label is compound but the target industry is unclear."
            ),
            "why_human_review": (
                f"{current_industry!r} probably mixes concepts, but the configured "
                "taxonomy does not know which one should become the primary industry."
            ),
            "what_to_check": [
                "What is the buyer's actual business vertical?",
                "Should one part become customer_segment or remain industry detail?",
                "Does the taxonomy need a new industry rule for this market?",
            ],
        }
    if confidence == "medium" and suggested_industry is None and segment_candidates:
        return {
            "reason": (
                "The segment part is clear, but the industry part is not yet mapped "
                "to the canonical taxonomy."
            ),
            "why_human_review": (
                "Moving only the segment would leave the old mixed industry in place, "
                "and guessing the missing industry could distort reports."
            ),
            "what_to_check": [
                "Choose the canonical industry before applying the split.",
                "Add a taxonomy rule if this industry will appear again.",
                "Confirm the suggested segment labels are useful for BD filtering.",
            ],
        }
    return {
        "reason": (
            "The row has a taxonomy issue, but the suggestion is not strong enough "
            "to apply without a person checking the deal context."
        ),
        "why_human_review": (
            "The cleanup affects reporting groups, so uncertain rows should stay "
            "visible rather than be silently normalized."
        ),
        "what_to_check": [
            "Confirm the primary business vertical.",
            "Confirm which maturity or account-stage labels belong in customer_segment.",
            "Use update_deal only after the split is clear.",
        ],
    }


def _industry_candidates(value: str | None) -> list[str]:
    return industry_candidates(value)


def _segment_candidates(value: str | None) -> list[str]:
    if not value:
        return []
    text = value.casefold()
    candidates = [
        canonical
        for canonical, patterns in SEGMENT_RULES
        if any(pattern.casefold() in text for pattern in patterns)
    ]
    candidates.extend(_funding_stages(value))
    return _dedupe(candidates)


def _funding_stages(value: str) -> list[str]:
    stages = []
    for match in FUNDING_STAGE_RE.finditer(value):
        raw = match.group(1) or match.group(2)
        if not raw:
            continue
        cleaned = raw.strip().replace(" ", "-")
        if cleaned.casefold().replace("-", "") == "preipo":
            stages.append("Pre-IPO")
        elif cleaned.casefold().startswith("series"):
            suffix = cleaned.split("-")[-1].upper()
            stages.append(f"Series {suffix}")
        else:
            stages.append(f"Series {cleaned.upper()}")
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
    if any(row["confidence"] != "high" for row in issue_rows):
        warnings.append(
            {
                "code": "human_review_required",
                "message": (
                    "Medium/low confidence suggestions should be confirmed "
                    "against full deal context before update_deal."
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


def _has_separator(value: str) -> bool:
    return any(separator in value for separator in ("·", "/", "|", ",", ";"))


def _split_segments(value: str) -> list[str]:
    return [
        item.strip()
        for item in re.split(r"[;,/|·]+", value)
        if item.strip()
    ]


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
    return value if len(value) <= limit else f"{value[: limit - 1]}…"
