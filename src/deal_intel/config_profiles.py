from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Literal, cast

ConfigProfileName = Literal["sample", "full", "pro"]


@dataclass(frozen=True)
class ConfigProfile:
    name: ConfigProfileName
    title: str
    description: str
    config_patch: dict[str, Any]
    requirements: tuple[str, ...]
    limitations: tuple[str, ...]
    first_run_commands: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "config_patch": deepcopy(self.config_patch),
            "requirements": list(self.requirements),
            "limitations": list(self.limitations),
            "first_run_commands": list(self.first_run_commands),
        }


_PROFILES: dict[ConfigProfileName, ConfigProfile] = {
    "sample": ConfigProfile(
        name="sample",
        title="Sample",
        description=(
            "Zero-config feature-test mode with bundled fictional data, intended "
            "to grow into lightweight local personal use before MongoDB setup."
        ),
        config_patch={
            "storage": {"backend": "local_sample"},
            "mongodb": {"vector_search": "python_cosine"},
            "llm": {"provider": "chatgpt_oauth"},
        },
        requirements=(
            "No MongoDB Atlas project required for sample testing.",
            "No API key required for LLM-free BI/reporting smoke paths.",
            "ChatGPT OAuth is only needed for LLM tools such as analyze_deal.",
        ),
        limitations=(
            "Feature-test surface with some tools intentionally unavailable.",
            "Bundled fictional data is read-only in the current MVP.",
            "Local personal create/update/delete persistence is planned next.",
            "Team/shared operation assumes MongoDB-backed full mode.",
            "No semantic search in the local sample MVP.",
        ),
        first_run_commands=(
            "deal-intel config show",
            "deal-intel storage-status",
            "deal-intel smoke-natural-questions --as-of 2026-06-10",
        ),
    ),
    "full": ConfigProfile(
        name="full",
        title="Full",
        description=(
            "Atlas-backed operating mode for real team data on a free or paid "
            "MongoDB cluster."
        ),
        config_patch={
            "storage": {"backend": "mongo"},
            "mongodb": {"vector_search": "python_cosine"},
            "llm": {"provider": "chatgpt_oauth"},
        },
        requirements=(
            "MONGODB_URI configured in .env or the MCP package settings.",
            "ChatGPT OAuth, Anthropic API key, or OpenAI API key for LLM tools.",
            "Python cosine similarity is used for search by default.",
        ),
        limitations=(
            "Atlas Vector Search is not enabled by default.",
            "Large-scale search performance is bounded by Python-side cosine.",
        ),
        first_run_commands=(
            "deal-intel config show",
            "deal-intel storage-status",
        ),
    ),
    "pro": ConfigProfile(
        name="pro",
        title="Pro",
        description=(
            "Paid-infrastructure profile for M10+ Atlas clusters, Atlas Vector "
            "Search, and API-key LLM providers."
        ),
        config_patch={
            "storage": {"backend": "mongo"},
            "mongodb": {"vector_search": "atlas"},
            "llm": {"provider": "openai_api"},
        },
        requirements=(
            "MONGODB_URI for an Atlas M10+ cluster.",
            "Atlas Vector Search index configured for deal summaries.",
            "OPENAI_API_KEY by default, or switch llm.provider to anthropic.",
        ),
        limitations=(
            "Requires paid external infrastructure.",
            "OpenAI API live verification remains pending until billing is enabled.",
            "Should be treated as an upgrade path, not the first-run default.",
        ),
        first_run_commands=(
            "deal-intel config show",
            "deal-intel storage-status",
        ),
    ),
}


def profile_names() -> tuple[ConfigProfileName, ...]:
    return ("sample", "full", "pro")


def list_config_profiles() -> list[ConfigProfile]:
    return [_PROFILES[name] for name in profile_names()]


def get_config_profile(name: str) -> ConfigProfile:
    normalized = name.strip().lower()
    if normalized not in _PROFILES:
        raise ValueError("profile must be one of: sample, full, pro")
    return _PROFILES[cast(ConfigProfileName, normalized)]


def build_profile_config_patch(name: str) -> dict[str, Any]:
    return deepcopy(get_config_profile(name).config_patch)


def infer_config_profile(cfg: dict[str, Any]) -> ConfigProfileName:
    storage = _mapping(cfg.get("storage"))
    mongodb = _mapping(cfg.get("mongodb"))
    backend = storage.get("backend", "mongo")
    vector_search = mongodb.get("vector_search", "python_cosine")

    if backend == "local_sample":
        return "sample"
    if backend == "mongo" and vector_search == "atlas":
        return "pro"
    return "full"


def merge_profile_patch(
    base: dict[str, Any],
    profile_name: str,
) -> dict[str, Any]:
    merged = deepcopy(base)
    _deep_merge(merged, build_profile_config_patch(profile_name))
    return merged


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> None:
    for key, value in override.items():
        if isinstance(base.get(key), dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = deepcopy(value)
