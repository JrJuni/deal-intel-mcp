from __future__ import annotations

import pytest

from deal_intel import _context, mcp_server
from deal_intel.providers.embedding import SentenceTransformerProvider
from deal_intel.tools import search_deals as search_tool


class _Embedding:
    def __init__(
        self,
        *,
        ready: bool,
        error: str | None = None,
        elapsed_seconds: float = 1.0,
    ) -> None:
        self.is_ready = ready
        self.load_error = error
        self.warmup_status = {
            "phase": "importing_sentence_transformers",
            "elapsed_seconds": elapsed_seconds,
        }


@pytest.fixture(autouse=True)
def _use_mongo_backend(monkeypatch) -> None:
    monkeypatch.setattr(_context, "storage_backend_name", lambda: "mongo")


def test_search_deals_returns_immediately_while_embedding_warms(monkeypatch) -> None:
    monkeypatch.setattr(_context, "embedding_provider", lambda: _Embedding(ready=False))
    monkeypatch.setattr(
        _context,
        "mongo",
        lambda: (_ for _ in ()).throw(AssertionError("MongoDB must not be touched")),
    )

    result = mcp_server.search_deals("cost reduction")

    assert result["ok"] is False
    assert result["warming_up"] is True
    assert result["retryable"] is True


def test_search_deals_local_sample_mode_skips_embedding(monkeypatch) -> None:
    monkeypatch.setattr(_context, "storage_backend_name", lambda: "local_sample")
    monkeypatch.setattr(
        _context,
        "embedding_provider",
        lambda: (_ for _ in ()).throw(
            AssertionError("embedding must not be touched")
        ),
    )
    monkeypatch.setattr(
        _context,
        "mongo",
        lambda: (_ for _ in ()).throw(AssertionError("MongoDB must not be touched")),
    )

    result = mcp_server.search_deals("cost reduction")

    assert result["ok"] is False
    assert result["error_code"] == "CONFIG_ERROR"
    assert result["warming_up"] is False
    assert "local_sample" in result["message"]


def test_search_deals_reports_background_load_failure(monkeypatch) -> None:
    monkeypatch.setattr(
        _context,
        "embedding_provider",
        lambda: _Embedding(ready=False, error="RuntimeError: model cache missing"),
    )
    monkeypatch.setattr(
        _context,
        "mongo",
        lambda: (_ for _ in ()).throw(AssertionError("MongoDB must not be touched")),
    )

    result = mcp_server.search_deals("cost reduction")

    assert result["ok"] is False
    assert result["warming_up"] is False
    assert result["hint"]["detail"] == "RuntimeError: model cache missing"


def test_search_deals_reports_missing_embedding_dependency(monkeypatch) -> None:
    monkeypatch.setattr(_context, "embedding_provider", lambda: None)
    monkeypatch.setattr(
        _context,
        "mongo",
        lambda: (_ for _ in ()).throw(AssertionError("MongoDB must not be touched")),
    )

    result = mcp_server.search_deals("cost reduction")

    assert result["ok"] is False
    assert result["error_code"] == "CONFIG_ERROR"
    assert result["warming_up"] is False


def test_search_deals_reports_stalled_warmup(monkeypatch) -> None:
    monkeypatch.setattr(
        _context,
        "embedding_provider",
        lambda: _Embedding(ready=False, elapsed_seconds=31.0),
    )
    monkeypatch.setattr(
        _context,
        "mongo",
        lambda: (_ for _ in ()).throw(AssertionError("MongoDB must not be touched")),
    )

    result = mcp_server.search_deals("cost reduction")

    assert result["ok"] is False
    assert result["warming_up"] is False
    assert result["retryable"] is False
    assert result["message"].endswith("warmup is stalled.")


def test_search_deals_calls_tool_only_after_embedding_is_ready(monkeypatch) -> None:
    embedding = _Embedding(ready=True)
    mongo = object()
    captured = {}

    monkeypatch.setattr(_context, "embedding_provider", lambda: embedding)
    monkeypatch.setattr(_context, "mongo", lambda: mongo)
    monkeypatch.setattr(_context, "config", lambda: {"mongodb": {}})

    def fake_handle(**kwargs):
        captured.update(kwargs)
        return {"ok": True, "results": []}

    monkeypatch.setattr(search_tool, "handle", fake_handle)

    result = mcp_server.search_deals("cost reduction", limit=3)

    assert result["ok"] is True
    assert captured["mongo"] is mongo
    assert captured["embedding_provider"] is embedding
    assert captured["query"] == "cost reduction"
    assert captured["limit"] == 3


def test_mongo_singleton_does_not_create_indexes_inline(monkeypatch) -> None:
    class FakeMongo:
        def __init__(self, *, database: str) -> None:
            self.database = database

        def ensure_indexes(self) -> None:
            raise AssertionError("Index creation must not run in the first tool call")

    monkeypatch.setattr(_context, "_mongo", None)
    monkeypatch.setattr(_context, "MongoDBClient", FakeMongo)
    monkeypatch.setattr(_context, "config", lambda: {"mongodb": {"database": "test_db"}})

    mongo = _context.mongo()

    assert mongo.database == "test_db"


def test_embedding_warmup_records_load_error(monkeypatch) -> None:
    provider = SentenceTransformerProvider()

    def fail_embed(text: str) -> list[float]:
        raise RuntimeError(f"failed for {text}")

    monkeypatch.setattr(provider, "embed", fail_embed)

    try:
        provider.warmup()
    except RuntimeError:
        pass

    assert provider.load_error == "RuntimeError: failed for warmup"
