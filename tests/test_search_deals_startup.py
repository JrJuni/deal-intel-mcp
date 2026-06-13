from __future__ import annotations

import pytest

from deal_intel import _context, mcp_server
from deal_intel.errors import MCPError
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


def test_search_deals_atlas_mode_does_not_silently_fallback() -> None:
    class Embedding:
        def embed(self, _query: str) -> list[float]:
            return [0.1, 0.2]

    class Mongo:
        def get_deals_for_search(self):
            raise AssertionError("python cosine fallback must not be used")

        def search_by_embedding(self, _embedding, *, limit):
            raise RuntimeError("index not found")

    with pytest.raises(MCPError) as exc_info:
        search_tool.handle(
            Mongo(),
            Embedding(),
            cfg={"mongodb": {"vector_search": "atlas"}},
            query="cost reduction",
        )

    error = exc_info.value
    assert error.error_code == "STORAGE_ERROR"
    assert error.retryable is False
    assert error.hint["policy"] == "No silent fallback in pro/atlas mode."
    assert error.hint["record_failures_in"] == "docs/pro-fallback-errors.md"


def test_search_deals_returns_industry_tags_from_python_cosine() -> None:
    class Embedding:
        def embed(self, _query: str) -> list[float]:
            return [1.0, 0.0]

    class Mongo:
        def get_deals_for_search(self) -> list[dict]:
            return [
                {
                    "deal_id": "d1",
                    "company": "Cross Industry Co",
                    "deal_stage": "proposal",
                    "industry": "SaaS",
                    "industry_tags": ["SaaS", "Insurance"],
                    "summary_embedding": [1.0, 0.0],
                    "meddpicc_latest": {"health_pct": 88.88, "gaps": []},
                }
            ]

    result = search_tool.handle(
        Mongo(),
        Embedding(),
        cfg={"mongodb": {"vector_search": "python_cosine"}},
        query="insurance workflow",
    )

    assert result["results"][0]["industry_tags"] == ["SaaS", "Insurance"]
    assert result["results"][0]["health_pct"] == 88.9


def test_search_deals_normalizes_missing_industry_tags_from_atlas() -> None:
    class Embedding:
        def embed(self, _query: str) -> list[float]:
            return [0.1, 0.2]

    class Mongo:
        def search_by_embedding(self, _embedding, *, limit):
            assert limit == 1
            return [
                {
                    "deal_id": "d1",
                    "company": "No Tag Co",
                    "score": 0.98765,
                    "health_pct": 81.23,
                }
            ]

    result = search_tool.handle(
        Mongo(),
        Embedding(),
        cfg={"mongodb": {"vector_search": "atlas"}},
        query="insurance workflow",
        limit=1,
    )

    assert result["results"][0]["industry_tags"] == []
    assert result["results"][0]["score"] == 0.9877


def test_search_deals_rejects_invalid_vector_search_mode() -> None:
    class Embedding:
        def embed(self, _query: str) -> list[float]:
            return [0.1, 0.2]

    with pytest.raises(MCPError) as exc_info:
        search_tool.handle(
            object(),
            Embedding(),
            cfg={"mongodb": {"vector_search": "surprise"}},
            query="cost reduction",
        )

    assert exc_info.value.error_code == "INVALID_INPUT"


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
