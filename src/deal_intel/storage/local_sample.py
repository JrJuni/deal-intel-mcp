from __future__ import annotations

from copy import deepcopy

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

    def __init__(self, *, database: str = "local_sample") -> None:
        self._database_name = database
        self._deals = load_zero_config_sample_deals()
        self._snapshots = load_zero_config_sample_snapshots()
        validation = validate_zero_config_sample_fixture(
            deals=self._deals,
            snapshots=self._snapshots,
        )
        if not validation["ok"]:
            raise RuntimeError(f"invalid zero-config sample fixture: {validation['errors']}")

    @property
    def database_name(self) -> str:
        return self._database_name

    def ping(self) -> dict:
        summary = build_zero_config_sample_summary(
            deals=self._deals,
            snapshots=self._snapshots,
        )
        return {
            "status": "ok",
            "storage_backend": "local_sample",
            "database": self._database_name,
            "sample_dataset": ZERO_CONFIG_SAMPLE_DATASET,
            "sample_dataset_version": ZERO_CONFIG_SAMPLE_VERSION,
            "deal_count": summary["deal_count"],
            "snapshot_count": summary["snapshot_count"],
        }

    def get_deal(self, deal_id: str) -> dict | None:
        for deal in self._deals:
            if deal.get("deal_id") == deal_id:
                return deepcopy(deal)
        return None

    def list_deals(self, *, stage: str | None = None, limit: int = 50) -> list[dict]:
        deals = [
            deal
            for deal in self._deals
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
        return deepcopy(self._deals)

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
            for snapshot in self._snapshots
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
