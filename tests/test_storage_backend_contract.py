from __future__ import annotations

import pytest

from deal_intel.storage.backend import (
    LOCAL_SAMPLE_MVP_METHODS,
    MONGO_FULL_METHODS,
    SampleReadStorageBackend,
    backend_capability_report,
    required_methods_for_backend,
    storage_contracts_by_name,
    validate_backend_capabilities,
)
from deal_intel.storage.mongodb import MongoDBClient


class PartialBackend:
    @property
    def database_name(self) -> str:
        return "partial"

    def list_deals_for_metrics(self) -> list[dict]:
        return []


def test_local_sample_mvp_contract_is_read_only_and_minimal() -> None:
    assert required_methods_for_backend("local_sample_mvp") == LOCAL_SAMPLE_MVP_METHODS
    assert LOCAL_SAMPLE_MVP_METHODS == (
        "ping",
        "get_deal",
        "list_deals",
        "list_deals_for_metrics",
        "list_analytics_snapshots",
    )

    contracts = storage_contracts_by_name()
    assert all(contracts[name].mode == "read" for name in LOCAL_SAMPLE_MVP_METHODS)
    assert "upsert_deal" not in LOCAL_SAMPLE_MVP_METHODS
    assert "hard_delete_deal" not in LOCAL_SAMPLE_MVP_METHODS


def test_mongo_full_contract_includes_write_and_admin_methods() -> None:
    assert required_methods_for_backend("mongo_full") == MONGO_FULL_METHODS
    contracts = storage_contracts_by_name()

    assert "upsert_deal" in MONGO_FULL_METHODS
    assert "ensure_indexes" in MONGO_FULL_METHODS
    assert contracts["upsert_deal"].mode == "write"
    assert contracts["ensure_indexes"].mode == "admin"


def test_mongodb_client_satisfies_local_sample_read_contract() -> None:
    client = MongoDBClient(uri="mongodb://example.invalid", database="deal_intel")

    assert isinstance(client, SampleReadStorageBackend)
    validate_backend_capabilities(client, kind="local_sample_mvp")


def test_capability_report_lists_missing_methods() -> None:
    report = backend_capability_report(PartialBackend(), kind="local_sample_mvp")

    assert report["ok"] is False
    assert report["present_methods"] == ["list_deals_for_metrics"]
    assert report["missing_methods"] == [
        "ping",
        "get_deal",
        "list_deals",
        "list_analytics_snapshots",
    ]
    with pytest.raises(TypeError, match="missing required methods"):
        validate_backend_capabilities(PartialBackend(), kind="local_sample_mvp")


def test_contract_records_zero_config_consumers_and_deferred_paths() -> None:
    contracts = storage_contracts_by_name()

    assert "smoke-natural-questions" in contracts["list_deals_for_metrics"].consumers
    assert "get_deal_review" in contracts["list_deals_for_metrics"].consumers
    assert contracts["aggregate_deals"].local_sample_mvp is False
    assert "Mongo aggregation compatibility is deferred" in contracts["aggregate_deals"].notes


def test_unknown_backend_kind_fails_fast() -> None:
    with pytest.raises(ValueError, match="unknown storage backend kind"):
        required_methods_for_backend("bad")  # type: ignore[arg-type]
