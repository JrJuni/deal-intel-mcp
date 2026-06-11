from __future__ import annotations

import pytest

from deal_intel.config_profiles import (
    build_profile_config_patch,
    get_config_profile,
    infer_config_profile,
    list_config_profiles,
    merge_profile_patch,
    profile_names,
)


def test_profile_names_are_stable_and_ordered() -> None:
    assert profile_names() == ("sample", "full", "pro")
    assert [profile.name for profile in list_config_profiles()] == [
        "sample",
        "full",
        "pro",
    ]


def test_sample_profile_is_zero_config_read_only_default() -> None:
    profile = get_config_profile("sample")

    assert profile.config_patch["storage"]["backend"] == "local_sample"
    assert profile.config_patch["mongodb"]["vector_search"] == "python_cosine"
    assert "feature-test" in profile.description
    assert any("No MongoDB" in item for item in profile.requirements)
    assert any("sample testing" in item for item in profile.requirements)
    assert any("intentionally unavailable" in item for item in profile.limitations)
    assert any("read-only" in item for item in profile.limitations)
    assert any("Local personal" in item for item in profile.limitations)
    assert any("MongoDB-backed full mode" in item for item in profile.limitations)


def test_full_profile_uses_mongo_without_atlas_vector_search() -> None:
    profile = get_config_profile("full")

    assert profile.config_patch["storage"]["backend"] == "mongo"
    assert profile.config_patch["mongodb"]["vector_search"] == "python_cosine"
    assert any("MONGODB_URI" in item for item in profile.requirements)


def test_pro_profile_enables_paid_infrastructure_defaults() -> None:
    profile = get_config_profile("pro")

    assert profile.config_patch["storage"]["backend"] == "mongo"
    assert profile.config_patch["mongodb"]["vector_search"] == "atlas"
    assert profile.config_patch["llm"]["provider"] == "openai_api"
    assert any("M10+" in item for item in profile.requirements)


def test_build_profile_config_patch_returns_deep_copy() -> None:
    first = build_profile_config_patch("sample")
    second = build_profile_config_patch("sample")

    first["storage"]["backend"] = "mutated"

    assert second["storage"]["backend"] == "local_sample"


@pytest.mark.parametrize(
    ("cfg", "expected"),
    [
        ({"storage": {"backend": "local_sample"}}, "sample"),
        ({"storage": {"backend": "mongo"}}, "full"),
        (
            {
                "storage": {"backend": "mongo"},
                "mongodb": {"vector_search": "python_cosine"},
            },
            "full",
        ),
        (
            {
                "storage": {"backend": "mongo"},
                "mongodb": {"vector_search": "atlas"},
            },
            "pro",
        ),
        ({}, "full"),
    ],
)
def test_infer_config_profile(cfg: dict, expected: str) -> None:
    assert infer_config_profile(cfg) == expected


def test_merge_profile_patch_preserves_unrelated_config() -> None:
    base = {
        "llm": {"provider": "anthropic", "draft_model": "claude-sonnet-4-6"},
        "reporting": {"timezone": "Asia/Seoul"},
    }

    merged = merge_profile_patch(base, "sample")

    assert merged["storage"]["backend"] == "local_sample"
    assert merged["llm"]["provider"] == "chatgpt_oauth"
    assert merged["llm"]["draft_model"] == "claude-sonnet-4-6"
    assert merged["reporting"]["timezone"] == "Asia/Seoul"
    assert "storage" not in base


def test_get_config_profile_rejects_unknown_profile() -> None:
    with pytest.raises(ValueError, match="sample, full, pro"):
        get_config_profile("enterprise")
