from __future__ import annotations

from typing import Any

from deal_intel.errors import ErrorCode, MCPError, Stage
from deal_intel.schema.taxonomy_audit import infer_industry_metadata
from deal_intel.storage.mongodb import MongoDBClient
from deal_intel.tools import update_deal

BACKFILL_UPDATE_NOTE = (
    "User confirmed automatic industry metadata backfill from existing labels."
)


def build_industry_tag_backfill_plan(
    deals: list[dict],
    *,
    limit: int = 0,
) -> dict:
    scoped_deals = deals[:limit] if limit > 0 else deals
    rows = [_classify_deal(deal) for deal in scoped_deals]
    candidates = [row for row in rows if row["action"] in _WRITE_ACTIONS]
    research = [row for row in rows if row["action"] in _RESEARCH_ACTIONS]
    skipped = [row for row in rows if row["action"] == "skipped"]
    clean = [row for row in rows if row["action"] == "clean"]
    return {
        "summary": {
            "deals_scanned": len(scoped_deals),
            "candidate_count": len(candidates),
            "research_count": len(research),
            "clean_count": len(clean),
            "skipped_count": len(skipped),
            "issue_counts": _issue_counts(rows),
        },
        "candidates": candidates,
        "research": research,
        "skipped": skipped,
        "clean": clean,
    }


def handle(
    mongo: MongoDBClient,
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
                "backfill-industry-tags requires confirmed_by_user=true "
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

    plan = build_industry_tag_backfill_plan(deals, limit=limit)
    results = []
    errors = []

    if not dry_run:
        for row in plan["candidates"]:
            try:
                result = update_deal.handle(
                    mongo=mongo,
                    deal_id=row["deal_id"],
                    industry=row["suggested_industry"],
                    industry_tags=row["suggested_industry_tags"],
                    customer_segment=row["suggested_customer_segment"],
                    update_note=BACKFILL_UPDATE_NOTE,
                    confirmed_by_user=True,
                )
                results.append(
                    {
                        "deal_id": result["deal_id"],
                        "company": result["company"],
                        "changed_fields": result["changed_metadata_fields"],
                        "storage_written": result["storage_written"],
                    }
                )
            except Exception as exc:  # pragma: no cover - defensive CLI envelope
                errors.append(
                    {
                        "deal_id": row.get("deal_id"),
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
        "storage_written": (not dry_run and bool(results)),
        "summary": summary,
        "candidates": plan["candidates"],
        "research": plan["research"],
        "skipped": plan["skipped"],
        "results": results,
        "errors": errors,
    }


_WRITE_ACTIONS = frozenset(
    {
        "backfill_missing_tags",
        "repair_primary_tag",
        "normalize_existing_tags",
        "normalize_primary_industry",
        "normalize_industry_and_segment",
        "normalize_customer_segment",
        "infer_missing_industry_from_company",
        "custom_industry_draft",
    }
)

_RESEARCH_ACTIONS = frozenset({"research_missing_industry"})


def _classify_deal(deal: dict) -> dict:
    industry = _clean(deal.get("industry"))
    current_tags = _clean_tags(deal.get("industry_tags"))
    current_segment = _clean(deal.get("customer_segment"))
    base = {
        "deal_id": deal.get("deal_id"),
        "company": deal.get("company"),
        "industry": industry,
        "current_industry_tags": current_tags,
        "current_customer_segment": current_segment,
    }

    inference = infer_industry_metadata(
        current_industry=industry,
        current_segment=current_segment,
        current_industry_tags=current_tags,
        company=deal.get("company"),
    )
    suggested_industry = inference["suggested_industry"]
    suggested_tags = inference["suggested_industry_tags"]
    suggested_segment = inference["suggested_customer_segment"]
    if not suggested_industry:
        if industry:
            return {
                **base,
                "action": "custom_industry_draft",
                "reason": None,
                "suggested_industry": industry,
                "suggested_industry_tags": [industry],
                "suggested_customer_segment": current_segment,
                "taxonomy_warnings": [
                    {
                        "code": "low_confidence_custom_industry_draft",
                        "field": "industry",
                        "value": industry,
                        "message": (
                            "Stored label was not in taxonomy; using it as a draft "
                            "custom industry so the record is not left unclassified."
                        ),
                    }
                ],
                "unmapped_parts": inference["unmapped_parts"],
                "confidence": "low",
                "recommended_action": (
                    "Research the company or add a taxonomy rule, then update "
                    "industry metadata if the draft is wrong."
                ),
                "research_query": inference.get("research_query"),
            }
        return {
            **base,
            "action": "research_missing_industry",
            "reason": None,
            "suggested_industry_tags": [],
            "suggested_industry": None,
            "suggested_customer_segment": current_segment,
            "taxonomy_warnings": [
                {
                    "code": "online_research_needed",
                    "field": "industry",
                    "value": None,
                    "message": (
                        "No industry label exists. Ask the AI client to research "
                        "the company and call update_deal with a draft."
                    ),
                }
            ],
            "unmapped_parts": inference["unmapped_parts"],
            "confidence": "unknown",
            "recommended_action": (
                "Search the web for the company industry, then call update_deal "
                "with industry, industry_tags, customer_segment, and update_note."
            ),
            "research_query": inference.get("research_query"),
        }

    if (
        suggested_industry == industry
        and suggested_tags == current_tags
        and suggested_segment == current_segment
    ):
        return {
            **base,
            "action": "clean",
            "reason": None,
            "suggested_industry": suggested_industry,
            "suggested_industry_tags": suggested_tags,
            "suggested_customer_segment": suggested_segment,
            "taxonomy_warnings": [],
            "confidence": "none",
        }

    if not industry and inference.get("inference_source") == "company_name":
        action = "infer_missing_industry_from_company"
    elif suggested_industry != industry and suggested_segment != current_segment:
        action = "normalize_industry_and_segment"
    elif suggested_industry != industry:
        action = "normalize_primary_industry"
    elif suggested_segment != current_segment:
        action = "normalize_customer_segment"
    elif not current_tags:
        action = "backfill_missing_tags"
    elif industry not in current_tags:
        action = "repair_primary_tag"
    else:
        action = "normalize_existing_tags"
    return {
        **base,
        "action": action,
        "reason": None,
        "suggested_industry": suggested_industry,
        "suggested_industry_tags": suggested_tags,
        "suggested_customer_segment": suggested_segment,
        "taxonomy_warnings": [],
        "unmapped_parts": inference["unmapped_parts"],
        "confidence": "medium"
        if inference.get("inference_source") == "company_name"
        else "high",
        "inference_source": inference.get("inference_source"),
        "research_query": inference.get("research_query"),
    }


def _issue_counts(rows: list[dict]) -> dict:
    counts: dict[str, int] = {}
    for row in rows:
        key = row["action"] if row["action"] != "skipped" else row.get("reason")
        key = str(key or "unknown")
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    stripped = str(value).strip()
    return stripped or None


def _clean_tags(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]
