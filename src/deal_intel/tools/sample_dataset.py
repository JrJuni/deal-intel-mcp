from __future__ import annotations

import json
from copy import deepcopy
from importlib import resources

DATASET_WEEKLY_PIPELINE = "weekly_pipeline_demo"
DATASET_VERSION = "2026-06-14.v2"
SAMPLE_BATCH_ID = f"{DATASET_WEEKLY_PIPELINE}:{DATASET_VERSION}"
SUPPORTED_DATASETS = frozenset({DATASET_WEEKLY_PIPELINE})

_RESOURCE_PACKAGE = "deal_intel.resources.sample_datasets"
_WEEKLY_PIPELINE_RESOURCE = "weekly_pipeline_demo.v2.json"


def build_sample_deals(*, loaded_at: str) -> list[dict]:
    """Return public fictional demo deals for Atlas demo-database seeding.

    This dataset is richer than the zero-config local fixture and is intended
    for `full`/MongoDB demos. It is still opt-in only: callers must use
    `create_sample_data`, which writes to a separate demo database by default.
    """

    deals = _load_dataset()
    for deal in deals:
        deal["updated_at"] = loaded_at
        deal["sample_loaded_at"] = loaded_at
        deal["is_sample"] = True
        deal["sample_batch_id"] = SAMPLE_BATCH_ID
        deal["sample_dataset"] = DATASET_WEEKLY_PIPELINE
        deal["sample_dataset_version"] = DATASET_VERSION
        deal["sample_label"] = "Full Pipeline Review demo"
    return deepcopy(deals)


def sample_preview(deals: list[dict], *, limit: int = 3) -> list[dict]:
    return [
        {
            "deal_id": deal["deal_id"],
            "company": deal["company"],
            "deal_stage": deal["deal_stage"],
            "industry": deal["industry"],
            "industry_tags": deal.get("industry_tags") or [],
            "customer_segment": deal.get("customer_segment"),
            "deal_size_amount": deal["deal_size_amount"],
            "deal_size_currency": deal["deal_size_currency"],
            "health_pct": deal["meddpicc_latest"].get("health_pct"),
        }
        for deal in deals[:limit]
    ]


def _load_dataset() -> list[dict]:
    resource = resources.files(_RESOURCE_PACKAGE).joinpath(_WEEKLY_PIPELINE_RESOURCE)
    with resource.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError(f"{_WEEKLY_PIPELINE_RESOURCE} must contain a JSON array")
    return data
