from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

INDUSTRY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "Aviation Mobility",
        ("uam", "aviation", "air mobility", "aam", "항공", "항공모빌리티", "항공mro"),
    ),
    ("Mobility", ("mobility", "automotive", "autonomous", "자율주행", "모빌리티")),
    ("Finance", ("fintech", "finance", "financial", "금융", "핀테크")),
    ("Insurance", ("insurance", "보험", "인슈어런스")),
    ("Retail", ("retail", "commerce", "ecommerce", "e-commerce", "리테일", "이커머스", "커머스")),
    ("SaaS", ("saas", "software as a service")),
    ("IT", ("it", "software", "ai", "정보기술", "소프트웨어")),
    ("Manufacturing", ("manufacturing", "제조", "정밀")),
    ("Logistics", ("logistics", "물류", "로지스틱스")),
    ("Healthcare", ("healthcare", "medical", "clinic", "헬스케어", "헬스", "병원", "의료")),
    ("Pharma/Biotech", ("pharma", "biotech", "bio", "제약", "바이오")),
    ("Wellness", ("wellness", "웰니스")),
    ("Education", ("education", "edtech", "교육")),
    ("Gaming", ("gaming", "game", "게임")),
    ("Energy", ("energy", "에너지")),
    ("Food & Beverage", ("food", "beverage", "f&b", "식음료", "브루어리")),
    ("Consumer", ("consumer", "beauty", "cosmetic", "소비재", "뷰티", "화장품")),
    ("Government", ("government", "public sector", "공공", "정부", "공공기관")),
    ("AgTech", ("agtech", "agriculture", "smart farm", "애그테크", "스마트팜", "농업")),
)

CANONICAL_INDUSTRIES = tuple(canonical for canonical, _patterns in INDUSTRY_RULES)
_CANONICAL_BY_CASEFOLD = {
    canonical.casefold(): canonical for canonical in CANONICAL_INDUSTRIES
}
_TAG_SEPARATOR_RE = re.compile(r"[,;/|·ㆍ]+")


@dataclass(frozen=True)
class IndustryProfile:
    industry: str | None
    industry_tags: list[str]
    warnings: list[dict[str, Any]]


class IndustryTaxonomyError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        field: str,
        value: str,
        candidates: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.field = field
        self.value = value
        self.candidates = candidates or []


def industry_candidates(value: str | None) -> list[str]:
    cleaned = _clean(value)
    if not cleaned:
        return []

    exact = _CANONICAL_BY_CASEFOLD.get(cleaned.casefold())
    if exact:
        return [exact]

    text = cleaned.casefold()
    candidates = [
        canonical
        for canonical, patterns in INDUSTRY_RULES
        if any(pattern.casefold() in text for pattern in patterns)
    ]
    if "Aviation Mobility" in candidates:
        candidates = [item for item in candidates if item not in {"IT", "Mobility"}]
    if "Pharma/Biotech" in candidates:
        candidates = [item for item in candidates if item != "Healthcare"]
    if "Wellness" in candidates:
        candidates = [item for item in candidates if item != "Healthcare"]
    if "Food & Beverage" in candidates:
        candidates = [item for item in candidates if item != "Consumer"]
    return _dedupe(candidates)


def industry_filter_values(value: str | None) -> list[str]:
    """Return canonical-or-raw values suitable for read-only industry filters."""

    cleaned = _clean(value)
    if not cleaned:
        return []
    candidates = industry_candidates(cleaned)
    return candidates or [cleaned]


def deal_matches_industry_filter(deal: dict, industry: str | None) -> bool:
    """Match a read filter against primary industry or industry_tags."""

    values = industry_filter_values(industry)
    if not values:
        return True
    deal_industry = _clean(deal.get("industry"))
    deal_tags = {
        str(tag).strip()
        for tag in (deal.get("industry_tags") or [])
        if str(tag).strip()
    }
    return any(value == deal_industry or value in deal_tags for value in values)


def normalize_industry_profile(
    *,
    industry: str | None,
    industry_tags: str | list[str] | tuple[str, ...] | None = None,
    existing_industry_tags: list[str] | tuple[str, ...] | None = None,
    allow_custom: bool = True,
) -> IndustryProfile:
    """Normalize a single primary industry plus optional multi-select tags.

    The primary industry must not be ambiguous. Tags are more permissive: a
    compound tag can expand into multiple canonical tags, while unknown custom
    tags are kept with warnings so early MVP usage does not get blocked.
    """

    warnings: list[dict[str, Any]] = []
    normalized_industry = _normalize_primary_industry(
        industry,
        allow_custom=allow_custom,
        warnings=warnings,
    )

    tags_input_supplied = industry_tags is not None
    tag_values = (
        _normalize_tags(industry_tags, allow_custom=allow_custom, warnings=warnings)
        if tags_input_supplied
        else _normalize_existing_tags(existing_industry_tags, warnings=warnings)
    )
    if normalized_industry:
        tag_values = _dedupe([normalized_industry, *tag_values])
    return IndustryProfile(
        industry=normalized_industry,
        industry_tags=tag_values,
        warnings=warnings,
    )


def _normalize_primary_industry(
    value: str | None,
    *,
    allow_custom: bool,
    warnings: list[dict[str, Any]],
) -> str | None:
    cleaned = _clean(value)
    if not cleaned:
        return None

    candidates = industry_candidates(cleaned)
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        raise IndustryTaxonomyError(
            "industry is ambiguous; choose one primary industry and put the rest in industry_tags",
            field="industry",
            value=cleaned,
            candidates=candidates,
        )
    if not allow_custom:
        raise IndustryTaxonomyError(
            "industry is not in the configured taxonomy",
            field="industry",
            value=cleaned,
        )
    warnings.append(
        {
            "code": "unknown_custom_industry",
            "field": "industry",
            "value": cleaned,
            "message": "Stored as a custom primary industry outside the configured taxonomy.",
        }
    )
    return cleaned


def _normalize_tags(
    value: str | list[str] | tuple[str, ...] | None,
    *,
    allow_custom: bool,
    warnings: list[dict[str, Any]],
) -> list[str]:
    tags: list[str] = []
    for raw_tag in _tag_parts(value):
        candidates = industry_candidates(raw_tag)
        if candidates:
            if len(candidates) > 1:
                warnings.append(
                    {
                        "code": "compound_industry_tag_split",
                        "field": "industry_tags",
                        "value": raw_tag,
                        "normalized": candidates,
                        "message": "Expanded a compound industry tag into multiple canonical tags.",
                    }
                )
            tags.extend(candidates)
            continue
        if allow_custom:
            warnings.append(
                {
                    "code": "unknown_custom_industry_tag",
                    "field": "industry_tags",
                    "value": raw_tag,
                    "message": "Stored as a custom industry tag outside the configured taxonomy.",
                }
            )
            tags.append(raw_tag)
    return _dedupe(tags)


def _normalize_existing_tags(
    value: list[str] | tuple[str, ...] | None,
    *,
    warnings: list[dict[str, Any]],
) -> list[str]:
    if not value:
        return []
    return _normalize_tags(list(value), allow_custom=True, warnings=warnings)


def _tag_parts(value: str | list[str] | tuple[str, ...] | None) -> list[str]:
    if value is None:
        return []
    raw_values = [value] if isinstance(value, str) else list(value)
    parts: list[str] = []
    for raw in raw_values:
        cleaned = _clean(str(raw))
        if not cleaned:
            continue
        parts.extend(
            part.strip()
            for part in _TAG_SEPARATOR_RE.split(cleaned)
            if part and part.strip()
        )
    return parts


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _dedupe(values: list[str]) -> list[str]:
    seen = set()
    deduped = []
    for value in values:
        if value not in seen:
            deduped.append(value)
            seen.add(value)
    return deduped
