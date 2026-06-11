"""Process-level lazy singletons. All tool handlers go through here."""
from __future__ import annotations

import threading

from deal_intel import _env
from deal_intel.providers import llm as _llm
from deal_intel.providers.embedding import EmbeddingProvider, make_embedding_provider
from deal_intel.storage.local_sample import LocalSampleClient
from deal_intel.storage.mongodb import MongoDBClient

_config: dict | None = None
_llm_provider: _llm.LLMProvider | None = None
_mongo: MongoDBClient | LocalSampleClient | None = None
_embedding_provider: EmbeddingProvider | None = None
_embedding_initialized: bool = False
_mongo_lock = threading.Lock()
_embedding_lock = threading.Lock()

_VALID_STORAGE_BACKENDS = {"mongo", "local_sample"}


def config() -> dict:
    global _config
    if _config is None:
        _config = _env.load_config()
    return _config


def llm_provider() -> _llm.LLMProvider:
    global _llm_provider
    if _llm_provider is None:
        _llm_provider = _llm.make_llm_provider(config())
    return _llm_provider


def embedding_provider() -> EmbeddingProvider | None:
    global _embedding_provider, _embedding_initialized
    if not _embedding_initialized:
        with _embedding_lock:
            if not _embedding_initialized:
                _embedding_provider = make_embedding_provider(config())
                _embedding_initialized = True
    return _embedding_provider


def storage_backend_name() -> str:
    storage = config().get("storage", {})
    if not isinstance(storage, dict):
        raise ValueError("storage must be a mapping")
    backend = storage.get("backend", "mongo")
    if not isinstance(backend, str) or not backend.strip():
        raise ValueError("storage.backend must be 'mongo' or 'local_sample'")
    backend = backend.strip()
    if backend not in _VALID_STORAGE_BACKENDS:
        raise ValueError("storage.backend must be 'mongo' or 'local_sample'")
    return backend


def mongo() -> MongoDBClient | LocalSampleClient:
    global _mongo
    if _mongo is None:
        with _mongo_lock:
            if _mongo is None:
                cfg = config()
                backend = storage_backend_name()
                if backend == "local_sample":
                    storage_cfg = cfg.get("storage", {})
                    local_data_dir = (
                        storage_cfg.get("local_data_dir")
                        if isinstance(storage_cfg, dict)
                        else None
                    )
                    _mongo = LocalSampleClient(local_data_dir=local_data_dir)
                else:
                    db_name = cfg.get("mongodb", {}).get("database", "deal_intel")
                    _mongo = MongoDBClient(database=db_name)
    return _mongo
