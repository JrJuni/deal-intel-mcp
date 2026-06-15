from __future__ import annotations

from typing import Any

from deal_intel.qualification_config import resolve_active_qualification_framework
from deal_intel.schema.interactions import scoring_interactions
from deal_intel.schema.meddpicc import compute_meddpicc_latest
from deal_intel.schema.qualification import compute_qualification_latest


def rebuild_latest_snapshots(deal: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    """Rebuild legacy and canonical qualification snapshots for a deal.

    The legacy `meddpicc_latest` remains the read-path compatibility contract.
    `qualification_latest` is the new canonical framework-aware snapshot.
    """
    evidence = scoring_interactions(deal)
    deal_stage = deal.get("deal_stage", "discovery")
    raw_meddpicc_cfg = cfg.get("meddpicc", {})
    meddpicc_cfg = raw_meddpicc_cfg if isinstance(raw_meddpicc_cfg, dict) else {}
    framework = resolve_active_qualification_framework(cfg)

    snapshots: dict[str, Any] = {
        "qualification_latest": compute_qualification_latest(
            evidence,
            framework=framework,
            evidence_fields=_qualification_evidence_fields(framework.key),
            deal_stage=deal_stage,
        )
    }
    snapshots["meddpicc_latest"] = compute_meddpicc_latest(
        evidence,
        weights=meddpicc_cfg.get("weights", {}),
        gap_threshold=int(meddpicc_cfg.get("gap_threshold", 2)),
        deal_stage=deal_stage,
    )
    return snapshots


def _qualification_evidence_fields(framework_key: str) -> tuple[str, ...]:
    if framework_key == "meddpicc":
        return ("meddpicc",)
    return ("qualification",)
