from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

StorageBackendKind = Literal["local_sample_mvp", "mongo_full"]
StorageMethodMode = Literal["read", "write", "admin"]


@dataclass(frozen=True)
class StorageMethodContract:
    name: str
    mode: StorageMethodMode
    local_sample_mvp: bool
    consumers: tuple[str, ...]
    notes: str = ""


@runtime_checkable
class SampleReadStorageBackend(Protocol):
    """Minimum read contract for the zero-config local sample MVP."""

    @property
    def database_name(self) -> str: ...

    def ping(self) -> dict: ...

    def get_deal(self, deal_id: str) -> dict | None: ...

    def list_deals(self, *, stage: str | None = None, limit: int = 50) -> list[dict]: ...

    def list_deals_for_metrics(self) -> list[dict]: ...

    def list_deals_for_qualification_reextract(
        self,
        *,
        limit: int = 0,
    ) -> list[dict]: ...

    def list_analytics_snapshots(
        self,
        *,
        start_date: str,
        end_date: str,
        stage: str | None = None,
        industry: str | None = None,
    ) -> list[dict]: ...


STORAGE_METHOD_CONTRACTS: tuple[StorageMethodContract, ...] = (
    StorageMethodContract(
        name="ping",
        mode="read",
        local_sample_mvp=True,
        consumers=("startup diagnostics", "zero-config smoke"),
        notes="Local sample backend should return a non-network diagnostic response.",
    ),
    StorageMethodContract(
        name="get_deal",
        mode="read",
        local_sample_mvp=True,
        consumers=("get_deal",),
        notes="Returns a single deal without raw notes/contact/vector exposure changes.",
    ),
    StorageMethodContract(
        name="list_deals",
        mode="read",
        local_sample_mvp=True,
        consumers=("list_deals",),
        notes="Supports stage filter and limit for the user-facing list view.",
    ),
    StorageMethodContract(
        name="list_deals_for_metrics",
        mode="read",
        local_sample_mvp=True,
        consumers=(
            "get_metrics:pipeline_health",
            "get_deal_gaps",
            "get_deal_review",
            "get_customer_theme_breakdown",
            "get_customer_theme_evidence",
            "export_report:weekly_pipeline",
            "get_insights:pipeline_overview",
            "smoke-natural-questions",
        ),
        notes="Primary LLM-free BI/reporting read path; excludes raw notes, contacts, vectors.",
    ),
    StorageMethodContract(
        name="list_analytics_snapshots",
        mode="read",
        local_sample_mvp=True,
        consumers=("get_metrics:pipeline_trend", "export_report:pipeline_trend"),
        notes="May return an empty list for fixture-only sample mode.",
    ),
    StorageMethodContract(
        name="count_deals",
        mode="read",
        local_sample_mvp=False,
        consumers=("get_customer_themes", "create_sample_data", "delete_sample_data"),
        notes="Legacy/customer-theme aggregate path; not required for local sample MVP.",
    ),
    StorageMethodContract(
        name="aggregate_deals",
        mode="read",
        local_sample_mvp=False,
        consumers=(
            "get_customer_themes",
            "crosscheck-weekly-dashboard",
            "Atlas chart smoke",
        ),
        notes="Mongo aggregation compatibility is deferred for local sample mode.",
    ),
    StorageMethodContract(
        name="aggregate_analytics_snapshots",
        mode="read",
        local_sample_mvp=False,
        consumers=("Atlas trend chart smoke",),
        notes="Atlas-specific smoke helper; not part of MongoDB-free sample mode.",
    ),
    StorageMethodContract(
        name="get_deals_for_search",
        mode="read",
        local_sample_mvp=False,
        consumers=("search_deals:python_cosine",),
        notes="Deferred because search still requires an embedding provider.",
    ),
    StorageMethodContract(
        name="search_by_embedding",
        mode="read",
        local_sample_mvp=False,
        consumers=("search_deals:atlas",),
        notes="Atlas Vector Search path; not part of MongoDB-free sample mode.",
    ),
    StorageMethodContract(
        name="list_deals_for_theme_backfill",
        mode="read",
        local_sample_mvp=False,
        consumers=("backfill-customer-themes",),
        notes="Backfill is a maintainer workflow, not a zero-config sample workflow.",
    ),
    StorageMethodContract(
        name="list_deals_for_qualification_reextract",
        mode="read",
        local_sample_mvp=False,
        consumers=("backfill-qualification-reextract",),
        notes=(
            "Maintenance LLM path that intentionally reads interactions.raw_content "
            "for historical qualification extraction; keep out of BI/reporting paths."
        ),
    ),
    StorageMethodContract(
        name="upsert_deal",
        mode="write",
        local_sample_mvp=False,
        consumers=(
            "create_deal",
            "add_interaction",
            "update_stage",
            "update_deal",
            "archive_deal",
            "restore_deal",
            "analyze_deal",
            "backfill-customer-themes",
        ),
        notes="Local write support is deferred to the local personal sample target.",
    ),
    StorageMethodContract(
        name="update_deal_qualification_snapshots",
        mode="write",
        local_sample_mvp=False,
        consumers=("backfill-qualification",),
        notes=(
            "Patch-only recompute path for meddpicc_latest and "
            "qualification_latest; avoids replacing restricted deal projections."
        ),
    ),
    StorageMethodContract(
        name="update_deal_qualification_reextraction",
        mode="write",
        local_sample_mvp=False,
        consumers=("backfill-qualification-reextract",),
        notes=(
            "Patch-only historical re-extraction path for interactions and "
            "qualification snapshots; avoids replacing unrelated deal fields."
        ),
    ),
    StorageMethodContract(
        name="upsert_analytics_snapshot",
        mode="write",
        local_sample_mvp=False,
        consumers=("create_deal", "add_interaction", "update_stage"),
        notes="Trend snapshot write path is deferred for local sample mode.",
    ),
    StorageMethodContract(
        name="upsert_deals",
        mode="write",
        local_sample_mvp=False,
        consumers=("create_sample_data",),
        notes="Atlas demo database sample management is distinct from local sample mode.",
    ),
    StorageMethodContract(
        name="list_sample_deals",
        mode="read",
        local_sample_mvp=False,
        consumers=("delete_sample_data",),
        notes="Atlas demo database sample management is distinct from local sample mode.",
    ),
    StorageMethodContract(
        name="delete_sample_deals",
        mode="write",
        local_sample_mvp=False,
        consumers=("create_sample_data", "delete_sample_data"),
        notes="Atlas demo database sample management is distinct from local sample mode.",
    ),
    StorageMethodContract(
        name="insert_delete_audit_log",
        mode="write",
        local_sample_mvp=False,
        consumers=("delete_deal",),
        notes="Hard delete audit logging belongs to the local personal sample target.",
    ),
    StorageMethodContract(
        name="hard_delete_deal",
        mode="write",
        local_sample_mvp=False,
        consumers=("delete_deal",),
        notes="Hard delete belongs to the local personal sample target.",
    ),
    StorageMethodContract(
        name="ensure_indexes",
        mode="admin",
        local_sample_mvp=False,
        consumers=("MCP startup",),
        notes="MongoDB index creation should be skipped by local sample backends.",
    ),
    StorageMethodContract(
        name="ensure_vector_index",
        mode="admin",
        local_sample_mvp=False,
        consumers=("M10+ setup",),
        notes="Atlas Vector Search setup is out of scope for local sample mode.",
    ),
)

LOCAL_SAMPLE_MVP_METHODS: tuple[str, ...] = tuple(
    contract.name
    for contract in STORAGE_METHOD_CONTRACTS
    if contract.local_sample_mvp
)

MONGO_FULL_METHODS: tuple[str, ...] = tuple(
    contract.name for contract in STORAGE_METHOD_CONTRACTS
)


def required_methods_for_backend(kind: StorageBackendKind) -> tuple[str, ...]:
    if kind == "local_sample_mvp":
        return LOCAL_SAMPLE_MVP_METHODS
    if kind == "mongo_full":
        return MONGO_FULL_METHODS
    raise ValueError(f"unknown storage backend kind: {kind!r}")


def backend_capability_report(
    backend: object,
    *,
    kind: StorageBackendKind = "local_sample_mvp",
) -> dict:
    required = required_methods_for_backend(kind)
    present = [name for name in required if _has_callable(backend, name)]
    missing = [name for name in required if name not in present]
    return {
        "ok": not missing,
        "backend_kind": kind,
        "required_methods": list(required),
        "present_methods": present,
        "missing_methods": missing,
    }


def validate_backend_capabilities(
    backend: object,
    *,
    kind: StorageBackendKind = "local_sample_mvp",
) -> None:
    report = backend_capability_report(backend, kind=kind)
    if report["ok"]:
        return
    missing = ", ".join(report["missing_methods"])
    raise TypeError(f"{kind} storage backend missing required methods: {missing}")


def storage_contracts_by_name() -> dict[str, StorageMethodContract]:
    return {contract.name: contract for contract in STORAGE_METHOD_CONTRACTS}


def _has_callable(backend: object, name: str) -> bool:
    candidate = getattr(backend, name, None)
    return isinstance(candidate, Callable)
