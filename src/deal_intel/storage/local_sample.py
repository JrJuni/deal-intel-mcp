from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from deal_intel.storage.local_personal import LocalPersonalStore
from deal_intel.storage.local_sample_fixture import (
    ZERO_CONFIG_SAMPLE_DATASET,
    ZERO_CONFIG_SAMPLE_VERSION,
    build_zero_config_sample_summary,
    load_zero_config_sample_deals,
    load_zero_config_sample_snapshots,
    validate_zero_config_sample_fixture,
)


class LocalSampleClient:
    """Read-only storage backend for MongoDB-free zero-config sample mode."""

    def __init__(
        self,
        *,
        database: str = "local_sample",
        local_data_dir: str | Path | None = None,
    ) -> None:
        self._database_name = database
        self._fixture_deals = load_zero_config_sample_deals()
        self._fixture_deal_ids = {
            str(deal.get("deal_id") or "")
            for deal in self._fixture_deals
        }
        self._snapshots = load_zero_config_sample_snapshots()
        self._personal_store = (
            LocalPersonalStore(local_data_dir) if local_data_dir is not None else None
        )
        self._local_deals = (
            self._personal_store.load_deals() if self._personal_store else []
        )
        validation = validate_zero_config_sample_fixture(
            deals=self._fixture_deals,
            snapshots=self._snapshots,
        )
        if not validation["ok"]:
            raise RuntimeError(f"invalid zero-config sample fixture: {validation['errors']}")

    @property
    def database_name(self) -> str:
        return self._database_name

    def ping(self) -> dict:
        fixture_summary = build_zero_config_sample_summary(
            deals=self._fixture_deals,
            snapshots=self._snapshots,
        )
        local_personal_active = self._local_personal_active()
        summary = build_zero_config_sample_summary(
            deals=self._active_deals(),
            snapshots=self._active_snapshots(),
        )
        payload = {
            "status": "ok",
            "storage_backend": "local_sample",
            "database": self._database_name,
            "data_mode": "local_personal" if local_personal_active else "fixture",
            "sample_dataset": (
                "local_personal" if local_personal_active else ZERO_CONFIG_SAMPLE_DATASET
            ),
            "sample_dataset_version": (
                None if local_personal_active else ZERO_CONFIG_SAMPLE_VERSION
            ),
            "deal_count": summary["deal_count"],
            "snapshot_count": summary["snapshot_count"],
            "local_deal_count": len(self._local_deals),
            "fixture_archived": local_personal_active,
            "fixture_archive": {
                "dataset": ZERO_CONFIG_SAMPLE_DATASET,
                "version": ZERO_CONFIG_SAMPLE_VERSION,
                "deal_count": fixture_summary["deal_count"],
                "snapshot_count": fixture_summary["snapshot_count"],
            },
        }
        if self._personal_store is not None:
            payload["local_data_dir"] = str(self._personal_store.data_dir)
            payload["local_deals_path"] = str(self._personal_store.deals_path)
        return payload

    def get_deal(self, deal_id: str) -> dict | None:
        for deal in self._active_deals(include_archived=True):
            if deal.get("deal_id") == deal_id:
                return deepcopy(deal)
        return None

    def list_deals(self, *, stage: str | None = None, limit: int = 50) -> list[dict]:
        deals = [
            deal
            for deal in self._active_deals()
            if stage is None or deal.get("deal_stage") == stage
        ]
        deals.sort(
            key=lambda deal: (
                str(deal.get("updated_at") or ""),
                str(deal.get("company") or ""),
            ),
            reverse=True,
        )
        if limit > 0:
            deals = deals[:limit]
        return deepcopy(deals)

    def list_deals_for_metrics(self) -> list[dict]:
        return deepcopy(self._active_deals())

    def list_analytics_snapshots(
        self,
        *,
        start_date: str,
        end_date: str,
        stage: str | None = None,
        industry: str | None = None,
    ) -> list[dict]:
        snapshots = [
            snapshot
            for snapshot in self._active_snapshots()
            if start_date <= str(snapshot.get("as_of") or "") <= end_date
            and (stage is None or snapshot.get("deal_stage") == stage)
            and (industry is None or snapshot.get("industry") == industry)
        ]
        snapshots.sort(
            key=lambda snapshot: (
                str(snapshot.get("as_of") or ""),
                str(snapshot.get("occurred_at") or snapshot.get("created_at") or ""),
                str(snapshot.get("deal_id") or ""),
            )
        )
        return deepcopy(snapshots)

    def upsert_deal(self, deal: dict) -> None:
        self._raise_if_fixture_deal(deal.get("deal_id"))
        store = self._ensure_personal_store()
        store.upsert_deal(deal)
        self._local_deals = store.load_deals()

    def insert_delete_audit_log(self, entry: dict) -> None:
        store = self._ensure_personal_store()
        store.insert_delete_audit_log(entry)

    def hard_delete_deal(self, deal_id: str) -> int:
        self._raise_if_fixture_deal(deal_id)
        store = self._ensure_personal_store()
        deleted_count = store.hard_delete_deal(deal_id)
        self._local_deals = store.load_deals()
        return deleted_count

    def local_personal_summary(self) -> dict:
        return self._ensure_personal_store().summary()

    def export_local_personal_data(self, *, output_path: str | Path | None = None) -> dict:
        return self._ensure_personal_store().export_data(output_path=output_path)

    def reset_local_personal_deals(self, *, force: bool = False) -> dict:
        store = self._ensure_personal_store()
        result = store.reset_deals(force=force)
        self._local_deals = store.load_deals()
        return result

    def _active_deals(self, *, include_archived: bool = False) -> list[dict]:
        source = self._local_deals if self._local_personal_active() else self._fixture_deals
        if include_archived:
            return source
        return [deal for deal in source if deal.get("archived") is not True]

    def _active_snapshots(self) -> list[dict]:
        if self._local_personal_active():
            return []
        return self._snapshots

    def _ensure_personal_store(self) -> LocalPersonalStore:
        if self._personal_store is None:
            self._personal_store = LocalPersonalStore()
        return self._personal_store

    def _local_personal_active(self) -> bool:
        return (
            self._personal_store is not None
            and self._personal_store.deals_path.exists()
        )

    def _raise_if_fixture_deal(self, deal_id: object) -> None:
        if str(deal_id or "") in self._fixture_deal_ids:
            raise ValueError("bundled fixture deals are read-only in local_sample")
