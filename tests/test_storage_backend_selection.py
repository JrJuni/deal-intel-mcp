from __future__ import annotations

import pytest

from deal_intel import _context, _env
from deal_intel.storage.local_sample import LocalSampleClient


class FakeMongo:
    def __init__(self, *, database: str) -> None:
        self.database_name = database


def test_env_can_select_local_sample_backend(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(_env, "_USER_CONFIG_PATH", tmp_path / "missing.yaml")
    monkeypatch.setenv("DEAL_INTEL_STORAGE_BACKEND", "local_sample")

    cfg = _env.load_config()

    assert cfg["storage"]["backend"] == "local_sample"


def test_storage_env_override_survives_llm_provider_override(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(_env, "_USER_CONFIG_PATH", tmp_path / "missing.yaml")
    monkeypatch.setenv("DEAL_INTEL_LLM_PROVIDER", "openai_api")
    monkeypatch.setenv("DEAL_INTEL_STORAGE_BACKEND", "local_sample")

    cfg = _env.load_config()

    assert cfg["llm"]["provider"] == "openai_api"
    assert cfg["storage"]["backend"] == "local_sample"


def test_context_uses_local_sample_backend(monkeypatch) -> None:
    monkeypatch.setattr(_context, "_mongo", None)
    monkeypatch.setattr(
        _context,
        "config",
        lambda: {"storage": {"backend": "local_sample"}},
    )

    backend = _context.mongo()

    assert isinstance(backend, LocalSampleClient)
    assert backend.ping()["storage_backend"] == "local_sample"


def test_context_uses_mongo_backend_by_default(monkeypatch) -> None:
    monkeypatch.setattr(_context, "_mongo", None)
    monkeypatch.setattr(_context, "MongoDBClient", FakeMongo)
    monkeypatch.setattr(
        _context,
        "config",
        lambda: {"mongodb": {"database": "selected_db"}},
    )

    backend = _context.mongo()

    assert isinstance(backend, FakeMongo)
    assert backend.database_name == "selected_db"


@pytest.mark.parametrize("backend", ["", "sample", "mongodb", "bad"])
def test_context_rejects_invalid_storage_backend(monkeypatch, backend: str) -> None:
    monkeypatch.setattr(_context, "_mongo", None)
    monkeypatch.setattr(
        _context,
        "config",
        lambda: {"storage": {"backend": backend}},
    )

    with pytest.raises(ValueError, match="storage.backend"):
        _context.mongo()
