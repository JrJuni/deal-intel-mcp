from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

import deal_intel.atlas_vector_indexes as vector_indexes
from deal_intel.atlas_vector_indexes import (
    DEAL_SUMMARY_VECTOR_INDEX,
    build_create_search_index_command,
    deal_summary_vector_index_name,
    deal_summary_vector_search_settings,
    load_deal_summary_vector_index_spec,
)

ROOT = Path(__file__).resolve().parents[1]


def test_deal_summary_vector_index_spec_is_versioned_and_complete() -> None:
    spec = load_deal_summary_vector_index_spec()

    assert spec["id"] == DEAL_SUMMARY_VECTOR_INDEX
    assert spec["version"] == 1
    assert spec["collection"] == "deals"
    assert spec["minimum_cluster_tier"] == "M10"
    assert spec["embedding"] == {
        "path": "summary_embedding",
        "numDimensions": 384,
        "similarity": "cosine",
        "source_config": "embedding.model",
    }
    assert spec["create_search_index"]["name"] == "deal_summary_vector"
    assert spec["create_search_index"]["type"] == "vectorSearch"


def test_packaged_vector_index_spec_matches_repo_spec() -> None:
    packaged = (
        resources.files("deal_intel.resources")
        .joinpath("atlas", "vector_indexes", "deal_summary_vector.v1.json")
        .read_text(encoding="utf-8")
    )
    repo = (
        ROOT / "atlas" / "vector_indexes" / "deal_summary_vector.v1.json"
    ).read_text(encoding="utf-8")

    assert packaged == repo


def test_vector_index_spec_falls_back_to_packaged_resource(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        vector_indexes,
        "DEFAULT_DEAL_SUMMARY_VECTOR_INDEX_SPEC",
        tmp_path / "missing.json",
    )

    spec = load_deal_summary_vector_index_spec()

    assert spec["id"] == DEAL_SUMMARY_VECTOR_INDEX


def test_create_search_index_command_uses_versioned_spec() -> None:
    command = build_create_search_index_command()

    assert command["createSearchIndexes"] == "deals"
    assert command["indexes"][0]["name"] == deal_summary_vector_index_name()
    assert command["indexes"][0]["definition"]["fields"] == [
        {
            "type": "vector",
            "path": "summary_embedding",
            "numDimensions": 384,
            "similarity": "cosine",
        }
    ]


def test_create_search_index_command_can_override_dimensions() -> None:
    command = build_create_search_index_command(dimensions=768)

    assert command["indexes"][0]["definition"]["fields"][0]["numDimensions"] == 768


def test_vector_search_settings_are_stable() -> None:
    assert deal_summary_vector_search_settings() == {
        "num_candidates_multiplier": 10,
        "minimum_num_candidates": 50,
        "max_limit": 20,
    }


def test_vector_index_spec_is_valid_json_without_bom() -> None:
    path = ROOT / "atlas" / "vector_indexes" / "deal_summary_vector.v1.json"
    raw = path.read_bytes()

    assert not raw.startswith(b"\xef\xbb\xbf")
    assert json.loads(raw.decode("utf-8"))["id"] == DEAL_SUMMARY_VECTOR_INDEX
