from __future__ import annotations

import os
from importlib import resources
from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parents[2]  # src/deal_intel → src → repo root
load_dotenv(_ROOT / ".env", override=False)

_USER_CONFIG_PATH = Path.home() / ".deal-intel" / "config.yaml"
_VALID_STORAGE_BACKENDS = {"mongo", "local_sample"}
_VALID_TOOL_SURFACES = {"auto", "sample", "standard", "developer"}


def user_config_path() -> Path:
    return _USER_CONFIG_PATH


def load_config() -> dict:
    import yaml

    config: dict = {}
    defaults_path = _ROOT / "config" / "defaults.yaml"
    if defaults_path.exists():
        with open(defaults_path, encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
    else:
        defaults_text = (
            resources.files("deal_intel.resources")
            .joinpath("defaults.yaml")
            .read_text(encoding="utf-8")
        )
        config = yaml.safe_load(defaults_text) or {}

    if _USER_CONFIG_PATH.exists():
        with open(_USER_CONFIG_PATH, encoding="utf-8") as f:
            user = yaml.safe_load(f) or {}
        _deep_merge(config, user)

    # mcpb user_config env override. DEAL_INTEL_LLM_PROVIDER is the explicit
    # provider selector; DEAL_INTEL_USE_CHATGPT_OAUTH remains for older bundles.
    provider_env = os.environ.get("DEAL_INTEL_LLM_PROVIDER", "").strip()
    if provider_env in {"chatgpt_oauth", "anthropic", "openai_api"}:
        config.setdefault("llm", {})["provider"] = provider_env
    else:
        # "true"/"1" -> chatgpt_oauth, "false"/"0" -> anthropic.
        _oauth_env = os.environ.get("DEAL_INTEL_USE_CHATGPT_OAUTH", "").lower()
        if _oauth_env in ("true", "1"):
            config.setdefault("llm", {})["provider"] = "chatgpt_oauth"
        elif _oauth_env in ("false", "0"):
            config.setdefault("llm", {})["provider"] = "anthropic"

    storage_backend_env = os.environ.get("DEAL_INTEL_STORAGE_BACKEND", "").strip()
    if storage_backend_env in _VALID_STORAGE_BACKENDS:
        config.setdefault("storage", {})["backend"] = storage_backend_env

    tool_surface_env = os.environ.get("DEAL_INTEL_TOOLS_SURFACE", "").strip()
    if tool_surface_env in _VALID_TOOL_SURFACES:
        config.setdefault("tools", {})["surface"] = tool_surface_env

    return config


def _deep_merge(base: dict, override: dict) -> None:
    for k, v in override.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
