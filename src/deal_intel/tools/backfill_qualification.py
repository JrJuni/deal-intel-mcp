from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from deal_intel.errors import ErrorCode, MCPError, Stage
from deal_intel.qualification_config import resolve_active_qualification_framework
from deal_intel.schema.interactions import scoring_interactions
from deal_intel.storage.mongodb import MongoDBClient
from deal_intel.tools.qualification_snapshot import rebuild_latest_snapshots


def build_qualification_backfill_plan(
    deals: list[dict],
    cfg: dict,
    *,
    limit: int = 0,
) -> dict:
    if limit < 0:
        raise ValueError("limit must be greater than or equal to 0.")

    framework = resolve_active_qualification_framework(cfg)
    scoped_deals = deals[:limit] if limit > 0 else deals
    rows = [
        _classify_deal_for_recompute(deal, cfg, framework_key=framework.key)
        for deal in scoped_deals
    ]
    candidates = [row for row in rows if row["action"] == "update_snapshots"]
    reextraction = [row for row in rows if row["action"] == "needs_reextraction"]
    skipped = [row for row in rows if row["action"] == "skipped"]
    clean = [row for row in rows if row["action"] == "clean"]
    return {
        "framework": {
            "key": framework.key,
            "display_name": framework.display_name,
        },
        "summary": {
            "deals_scanned": len(scoped_deals),
            "candidate_count": len(candidates),
            "needs_reextraction_count": len(reextraction),
            "clean_count": len(clean),
            "skipped_count": len(skipped),
            "issue_counts": _issue_counts(rows),
        },
        "candidates": candidates,
        "needs_reextraction": reextraction,
        "skipped": skipped,
        "clean": clean,
    }


def handle(
    mongo: MongoDBClient,
    cfg: dict,
    *,
    limit: int = 0,
    dry_run: bool = True,
    confirmed_by_user: bool = False,
) -> dict:
    if limit < 0:
        raise MCPError(
            error_code=ErrorCode.INVALID_INPUT,
            stage=Stage.PREFLIGHT,
            message="limit must be greater than or equal to 0.",
            retryable=False,
        )
    if not dry_run and not confirmed_by_user:
        raise MCPError(
            error_code=ErrorCode.INVALID_INPUT,
            stage=Stage.PREFLIGHT,
            message=(
                "backfill-qualification requires confirmed_by_user=true "
                "when dry_run=false."
            ),
            hint="Run a dry-run first, then retry with --apply --confirmed-by-user.",
            retryable=False,
        )

    try:
        deals = mongo.list_deals_for_metrics()
    except Exception as exc:
        raise MCPError(
            error_code=ErrorCode.STORAGE_ERROR,
            stage=Stage.STORAGE,
            message=str(exc),
            retryable=True,
        ) from exc

    try:
        plan = build_qualification_backfill_plan(deals, cfg, limit=limit)
    except ValueError as exc:
        raise MCPError(
            error_code=ErrorCode.CONFIG_ERROR,
            stage=Stage.PREFLIGHT,
            message=str(exc),
            retryable=False,
        ) from exc

    results: list[dict] = []
    errors: list[dict] = []
    scoped_by_id = {
        str(deal.get("deal_id") or ""): deal
        for deal in (deals[:limit] if limit > 0 else deals)
        if str(deal.get("deal_id") or "")
    }

    if not dry_run:
        now = datetime.now(UTC).isoformat()
        for row in plan["candidates"]:
            deal_id = str(row.get("deal_id") or "")
            deal = scoped_by_id.get(deal_id)
            if deal is None:
                errors.append(
                    {
                        "deal_id": deal_id,
                        "company": row.get("company"),
                        "error": "deal disappeared from scoped backfill input",
                    }
                )
                continue
            try:
                snapshots = rebuild_latest_snapshots(deal, cfg)
                updated = mongo.update_deal_qualification_snapshots(
                    deal_id,
                    meddpicc_latest=snapshots["meddpicc_latest"],
                    qualification_latest=snapshots["qualification_latest"],
                    updated_at=now,
                )
                results.append(
                    {
                        "deal_id": deal_id,
                        "company": row.get("company"),
                        "changed_fields": row["changed_fields"],
                        "storage_written": bool(updated),
                    }
                )
            except Exception as exc:  # pragma: no cover - defensive CLI envelope
                errors.append(
                    {
                        "deal_id": deal_id,
                        "company": row.get("company"),
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )

    summary = dict(plan["summary"])
    summary["applied_count"] = len(results)
    summary["error_count"] = len(errors)
    return {
        "ok": not errors,
        "dry_run": dry_run,
        "mode": "recompute_only",
        "llm_calls": False,
        "storage_written": (not dry_run and any(row["storage_written"] for row in results)),
        "framework": plan["framework"],
        "summary": summary,
        "candidates": plan["candidates"],
        "needs_reextraction": plan["needs_reextraction"],
        "skipped": plan["skipped"],
        "results": results,
        "errors": errors,
        "warnings": _warnings(plan),
    }


def _classify_deal_for_recompute(
    deal: dict,
    cfg: dict,
    *,
    framework_key: str,
) -> dict:
    base = {
        "deal_id": deal.get("deal_id"),
        "company": deal.get("company"),
        "deal_stage": deal.get("deal_stage"),
    }
    evidence = scoring_interactions(deal)
    if not evidence:
        return {
            **base,
            "action": "skipped",
            "reason": "no_scoring_evidence",
            "message": (
                "No scoring-eligible interaction evidence exists; leaving "
                "qualification_latest unassessed instead of writing a zero-score snapshot."
            ),
        }
    if not _has_active_framework_evidence(evidence, framework_key):
        return {
            **base,
            "action": "needs_reextraction",
            "reason": "missing_active_framework_evidence",
            "message": (
                "Stored interactions do not contain evidence for the active "
                "qualification framework. Use the later LLM re-extraction path "
                "if raw content is available."
            ),
            "current_qualification": _snapshot_summary(
                _mapping(deal.get("qualification_latest"))
            ),
        }

    snapshots = rebuild_latest_snapshots(deal, cfg)
    changed_fields = _changed_snapshot_fields(deal, snapshots)
    if not changed_fields:
        return {
            **base,
            "action": "clean",
            "reason": None,
            "current_qualification": _snapshot_summary(
                _mapping(deal.get("qualification_latest"))
            ),
        }
    return {
        **base,
        "action": "update_snapshots",
        "reason": "snapshot_diff",
        "changed_fields": changed_fields,
        "current_meddpicc": _snapshot_summary(_mapping(deal.get("meddpicc_latest"))),
        "recomputed_meddpicc": _snapshot_summary(snapshots["meddpicc_latest"]),
        "current_qualification": _snapshot_summary(
            _mapping(deal.get("qualification_latest"))
        ),
        "recomputed_qualification": _snapshot_summary(
            snapshots["qualification_latest"]
        ),
    }


def _changed_snapshot_fields(deal: dict, snapshots: dict[str, dict]) -> list[str]:
    changed = []
    if _mapping(deal.get("meddpicc_latest")) != snapshots["meddpicc_latest"]:
        changed.append("meddpicc_latest")
    if _mapping(deal.get("qualification_latest")) != snapshots["qualification_latest"]:
        changed.append("qualification_latest")
    return changed


def _has_active_framework_evidence(
    evidence: list[dict],
    framework_key: str,
) -> bool:
    field = "meddpicc" if framework_key == "meddpicc" else "qualification"
    for item in evidence:
        signals = item.get(field)
        if isinstance(signals, dict) and signals:
            return True
    return False


def _snapshot_summary(snapshot: dict[str, Any]) -> dict:
    if not snapshot:
        return {"present": False}
    gaps = snapshot.get("gaps")
    if not isinstance(gaps, list):
        gaps = []
    return {
        "present": True,
        "framework_key": snapshot.get("framework_key"),
        "framework_display_name": snapshot.get("framework_display_name"),
        "health_pct": snapshot.get("health_pct"),
        "quality_pct": snapshot.get("quality_pct"),
        "coverage_pct": snapshot.get("coverage_pct"),
        "filled_count": snapshot.get("filled_count"),
        "total_count": snapshot.get("total_count"),
        "gap_count": len(gaps),
        "gaps": deepcopy(gaps[:10]),
    }


def _issue_counts(rows: list[dict]) -> dict:
    counts: dict[str, int] = {}
    for row in rows:
        key = str(row.get("reason") or row.get("action") or "unknown")
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _warnings(plan: dict) -> list[dict]:
    warnings: list[dict] = []
    if plan["summary"]["needs_reextraction_count"]:
        warnings.append(
            {
                "code": "llm_reextraction_needed",
                "message": (
                    "Some deals do not have stored evidence for the active "
                    "framework. Recompute-only backfill cannot infer new "
                    "dimension evidence from old MEDDPICC fields."
                ),
            }
        )
    if plan["summary"]["skipped_count"]:
        warnings.append(
            {
                "code": "unassessed_deals_skipped",
                "message": (
                    "Deals without scoring evidence were skipped so missing "
                    "information is not converted into a false low-health signal."
                ),
            }
        )
    return warnings


def _mapping(value: object) -> dict:
    return value if isinstance(value, dict) else {}
