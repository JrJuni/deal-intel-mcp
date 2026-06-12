from __future__ import annotations

import json
from copy import deepcopy
from importlib import resources
from pathlib import Path
from typing import Any

DEAL_SUMMARY_VECTOR_INDEX = "deal_summary_vector"
DEAL_SUMMARY_VECTOR_INDEX_FILE = "deal_summary_vector.v1.json"
DEFAULT_DEAL_SUMMARY_VECTOR_INDEX_SPEC = (
    Path(__file__).resolve().parents[2]
    / "atlas"
    / "vector_indexes"
    / DEAL_SUMMARY_VECTOR_INDEX_FILE
)


def load_deal_summary_vector_index_spec(path: str | Path | None = None) -> dict[str, Any]:
    """Load the version-managed Atlas Vector Search index spec."""
    if path is not None:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    if DEFAULT_DEAL_SUMMARY_VECTOR_INDEX_SPEC.exists():
        return json.loads(
            DEFAULT_DEAL_SUMMARY_VECTOR_INDEX_SPEC.read_text(encoding="utf-8")
        )
    return json.loads(_vector_index_resource_text())


def deal_summary_vector_index_name() -> str:
    return str(load_deal_summary_vector_index_spec()["create_search_index"]["name"])


def deal_summary_vector_search_settings() -> dict[str, int]:
    settings = load_deal_summary_vector_index_spec()["search"]
    return {
        "num_candidates_multiplier": int(settings["numCandidatesMultiplier"]),
        "minimum_num_candidates": int(settings["minimumNumCandidates"]),
        "max_limit": int(settings["maxLimit"]),
    }


def build_create_search_index_command(
    *,
    dimensions: int | None = None,
) -> dict[str, Any]:
    spec = load_deal_summary_vector_index_spec()
    index = deepcopy(spec["create_search_index"])
    if dimensions is not None:
        for field in index["definition"]["fields"]:
            if field.get("path") == spec["embedding"]["path"]:
                field["numDimensions"] = dimensions
    return {
        "createSearchIndexes": spec["collection"],
        "indexes": [index],
    }


def _vector_index_resource_text() -> str:
    return (
        resources.files("deal_intel.resources")
        .joinpath("atlas", "vector_indexes", DEAL_SUMMARY_VECTOR_INDEX_FILE)
        .read_text(encoding="utf-8")
    )
