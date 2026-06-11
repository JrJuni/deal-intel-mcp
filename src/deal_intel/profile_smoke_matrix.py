from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, cast

from deal_intel.config_profiles import ConfigProfileName, get_config_profile, profile_names

SmokeWritePolicy = Literal["read_only", "read_check_only"]


@dataclass(frozen=True)
class ProfileSmokeContract:
    """Expected first-run smoke behavior for one config profile.

    The matrix is intentionally diagnostic-only. It documents what should pass,
    warn, fail, or be deferred before future commands such as
    `deal-intel smoke-profile` automate the checks.
    """

    profile: ConfigProfileName
    storage_backend: str
    vector_search: str
    llm_provider: str
    bi_smoke_required_setup: tuple[str, ...]
    llm_tool_required_setup: tuple[str, ...]
    unconfigured_offline_fail_checks: tuple[str, ...]
    unconfigured_offline_warning_checks: tuple[str, ...]
    no_live_calls: tuple[str, ...]
    write_policy: SmokeWritePolicy
    deferred_checks: tuple[str, ...]

    def profile_values(self) -> dict[str, str]:
        return {
            "storage.backend": self.storage_backend,
            "mongodb.vector_search": self.vector_search,
            "llm.provider": self.llm_provider,
        }

    def to_dict(self) -> dict:
        profile = get_config_profile(self.profile)
        return {
            "profile": self.profile,
            "profile_values": self.profile_values(),
            "bi_smoke_required_setup": list(self.bi_smoke_required_setup),
            "llm_tool_required_setup": list(self.llm_tool_required_setup),
            "unconfigured_offline_fail_checks": list(
                self.unconfigured_offline_fail_checks
            ),
            "unconfigured_offline_warning_checks": list(
                self.unconfigured_offline_warning_checks
            ),
            "no_live_calls": list(self.no_live_calls),
            "write_policy": self.write_policy,
            "deferred_checks": list(self.deferred_checks),
            "first_run_commands": list(profile.first_run_commands),
        }


_CONTRACTS: dict[ConfigProfileName, ProfileSmokeContract] = {
    "sample": ProfileSmokeContract(
        profile="sample",
        storage_backend="local_sample",
        vector_search="python_cosine",
        llm_provider="chatgpt_oauth",
        bi_smoke_required_setup=(),
        llm_tool_required_setup=("ChatGPT OAuth login for LLM-only tools",),
        unconfigured_offline_fail_checks=(),
        unconfigured_offline_warning_checks=("llm_provider",),
        no_live_calls=(
            "MongoDB",
            "LLM completions",
            "embeddings",
            "Atlas admin APIs",
        ),
        write_policy="read_only",
        deferred_checks=(
            "real create/update/delete persistence",
            "semantic search over real embeddings",
        ),
    ),
    "full": ProfileSmokeContract(
        profile="full",
        storage_backend="mongo",
        vector_search="python_cosine",
        llm_provider="chatgpt_oauth",
        bi_smoke_required_setup=("MONGODB_URI",),
        llm_tool_required_setup=("ChatGPT OAuth login or API-key LLM provider",),
        unconfigured_offline_fail_checks=("mongodb_uri",),
        unconfigured_offline_warning_checks=("llm_provider",),
        no_live_calls=(
            "LLM completions",
            "embeddings",
            "MongoDB writes",
            "Atlas admin APIs",
        ),
        write_policy="read_check_only",
        deferred_checks=("live Atlas write smoke",),
    ),
    "pro": ProfileSmokeContract(
        profile="pro",
        storage_backend="mongo",
        vector_search="atlas",
        llm_provider="openai_api",
        bi_smoke_required_setup=(
            "MONGODB_URI",
            "Atlas M10+ cluster",
            "Atlas Vector Search index",
        ),
        llm_tool_required_setup=("OPENAI_API_KEY",),
        unconfigured_offline_fail_checks=("mongodb_uri", "llm_provider"),
        unconfigured_offline_warning_checks=("vector_search",),
        no_live_calls=(
            "LLM completions",
            "MongoDB writes",
            "Atlas admin APIs",
        ),
        write_policy="read_check_only",
        deferred_checks=(
            "live OpenAI API smoke",
            "live Atlas Vector Search query",
            "Atlas admin M10+ validation",
        ),
    ),
}


def get_profile_smoke_contract(profile_name: str) -> ProfileSmokeContract:
    normalized = profile_name.strip().lower()
    if normalized not in _CONTRACTS:
        raise ValueError("profile must be one of: sample, full, pro")
    return _CONTRACTS[cast(ConfigProfileName, normalized)]


def list_profile_smoke_contracts() -> list[ProfileSmokeContract]:
    return [_CONTRACTS[name] for name in profile_names()]


def build_profile_smoke_matrix() -> dict:
    return {
        "ok": True,
        "matrix_version": 1,
        "profiles": [contract.to_dict() for contract in list_profile_smoke_contracts()],
    }
