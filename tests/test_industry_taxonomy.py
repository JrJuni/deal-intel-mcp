from __future__ import annotations

import pytest

from deal_intel.schema.industry_taxonomy import (
    IndustryTaxonomyError,
    industry_candidates,
    normalize_industry_profile,
)


def test_industry_candidates_normalizes_korean_single_vertical() -> None:
    assert industry_candidates("제조") == ["Manufacturing"]
    assert industry_candidates("핀테크") == ["Finance"]
    assert industry_candidates("애그테크") == ["AgTech"]


def test_primary_industry_rejects_ambiguous_compound_value() -> None:
    with pytest.raises(IndustryTaxonomyError) as exc_info:
        normalize_industry_profile(industry="보험·금융")

    assert exc_info.value.field == "industry"
    assert exc_info.value.candidates == ["Finance", "Insurance"]


def test_profile_defaults_tags_to_primary_industry() -> None:
    result = normalize_industry_profile(industry="제조")

    assert result.industry == "Manufacturing"
    assert result.industry_tags == ["Manufacturing"]
    assert result.warnings == []


def test_profile_splits_compound_tags_and_forces_primary() -> None:
    result = normalize_industry_profile(
        industry="Finance",
        industry_tags="보험/SaaS",
    )

    assert result.industry == "Finance"
    assert result.industry_tags == ["Finance", "Insurance", "SaaS"]


def test_profile_keeps_custom_industry_with_warning() -> None:
    result = normalize_industry_profile(industry="Space Mining")

    assert result.industry == "Space Mining"
    assert result.industry_tags == ["Space Mining"]
    assert result.warnings[0]["code"] == "unknown_custom_industry"


def test_profile_preserves_existing_tags_when_primary_changes() -> None:
    result = normalize_industry_profile(
        industry="제조",
        existing_industry_tags=["Finance", "Custom Vertical"],
    )

    assert result.industry == "Manufacturing"
    assert result.industry_tags == ["Manufacturing", "Finance", "Custom Vertical"]
    assert any(
        warning["code"] == "unknown_custom_industry_tag"
        for warning in result.warnings
    )
