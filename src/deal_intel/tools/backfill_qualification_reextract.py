from __future__ import annotations

from datetime import UTC, datetime

from deal_intel.errors import ErrorCode, MCPError, Stage
from deal_intel.providers.llm import LLMProvider
from deal_intel.qualification_config import resolve_active_qualification_framework
from deal_intel.schema.customer_themes import load_json_response
from deal_intel.schema.interactions import (
    normalize_interaction_record,
    scoring_applies,
)
from deal_intel.schema.qualification_extraction import (
    normalize_qualification_extraction,
    render_qualification_extraction_prompt_block,
)
from deal_intel.schema.qualification_framework import (
    QualificationFramework,
    qualification_framework_fingerprint,
)
from deal_intel.storage.mongodb import MongoDBClient
from deal_intel.tools.qualification_snapshot import rebuild_latest_snapshots
from deal_intel.usage import build_llm_usage_metadata, summarize_usage

DEFAULT_MAX_LLM_CALLS = 30

_SYSTEM = "You are a precise B2B deal qualification extraction engine."

_PROMPT = """\
Re-extract qualification evidence from this historical customer interaction.

Source metadata:
- interaction_type: {interaction_type}
- direction: {direction}
- source_confidence: {source_confidence}

Evidence rules:
- Use only evidence present in the interaction content.
- Do not invent scores for missing dimensions.
- Omit dimensions when evidence is absent.
- Keep evidence short and paraphrased.
- Return JSON only, with a top-level `qualification` object.

{qualification_framework_prompt}

Interaction content:
{content}\
"""


def build_qualification_reextract_plan(
    deals: list[dict],
    cfg: dict,
    *,
    limit: int = 0,
    max_llm_calls: int = DEFAULT_MAX_LLM_CALLS,
    include_unconfirmed: bool = False,
    include_unhashed: bool = False,
) -> dict:
    if limit < 0:
        raise ValueError("limit must be greater than or equal to 0.")
    if max_llm_calls < 1:
        raise ValueError("max_llm_calls must be greater than or equal to 1.")

    framework = resolve_active_qualification_framework(cfg)
    framework_hash = qualification_framework_fingerprint(framework)
    scoped_deals = deals[:limit] if limit > 0 else deals
    rows: list[dict] = []
    for deal in scoped_deals:
        interactions = deal.get("interactions")
        if not isinstance(interactions, list):
            rows.append(_deal_skip_row(deal, "no_interactions"))
            continue
        for index, interaction in enumerate(interactions):
            if not isinstance(interaction, dict):
                rows.append(_interaction_skip_row(deal, index, "invalid_interaction"))
                continue
            rows.append(
                _classify_interaction(
                    deal,
                    interaction,
                    index=index,
                    framework=framework,
                    framework_hash=framework_hash,
                    include_unconfirmed=include_unconfirmed,
                    include_unhashed=include_unhashed,
                )
            )

    candidates = [row for row in rows if row["action"] == "reextract"]
    skipped = [row for row in rows if row["action"] == "skipped"]
    clean = [row for row in rows if row["action"] == "clean"]
    selected = candidates[:max_llm_calls]
    return {
        "framework": {
            "key": framework.key,
            "display_name": framework.display_name,
            "fingerprint": framework_hash,
        },
        "summary": {
            "deals_scanned": len(scoped_deals),
            "interactions_scanned": len(rows),
            "candidate_count": len(candidates),
            "selected_count": len(selected),
            "clean_count": len(clean),
            "skipped_count": len(skipped),
            "max_llm_calls": max_llm_calls,
            "include_unconfirmed": include_unconfirmed,
            "include_unhashed": include_unhashed,
            "estimated_llm_calls": len(selected),
            "estimated_input_chars": sum(int(row.get("content_chars") or 0) for row in selected),
            "issue_counts": _issue_counts(rows),
        },
        "candidates": candidates,
        "selected_candidates": selected,
        "skipped": skipped,
        "clean": clean,
        "warnings": _plan_warnings(candidates, selected, include_unconfirmed),
    }


def handle(
    mongo: MongoDBClient,
    llm: LLMProvider | None,
    cfg: dict,
    *,
    limit: int = 0,
    max_llm_calls: int = DEFAULT_MAX_LLM_CALLS,
    include_unconfirmed: bool = False,
    include_unhashed: bool = False,
    dry_run: bool = True,
    confirmed_by_user: bool = False,
) -> dict:
    if not dry_run and not confirmed_by_user:
        raise MCPError(
            error_code=ErrorCode.INVALID_INPUT,
            stage=Stage.PREFLIGHT,
            message=(
                "backfill-qualification-reextract requires confirmed_by_user=true "
                "when dry_run=false."
            ),
            hint=(
                "Run a dry-run first, then retry with "
                "--apply --confirmed-by-user after reviewing LLM call counts."
            ),
            retryable=False,
        )
    if not dry_run and llm is None:
        raise MCPError(
            error_code=ErrorCode.CONFIG_ERROR,
            stage=Stage.PREFLIGHT,
            message="LLM provider is required when dry_run=false.",
            retryable=False,
        )

    try:
        deals = mongo.list_deals_for_qualification_reextract(limit=limit)
    except Exception as exc:
        raise MCPError(
            error_code=ErrorCode.STORAGE_ERROR,
            stage=Stage.STORAGE,
            message=str(exc),
            retryable=True,
        ) from exc

    try:
        plan = build_qualification_reextract_plan(
            deals,
            cfg,
            limit=0,
            max_llm_calls=max_llm_calls,
            include_unconfirmed=include_unconfirmed,
            include_unhashed=include_unhashed,
        )
    except ValueError as exc:
        raise MCPError(
            error_code=ErrorCode.CONFIG_ERROR,
            stage=Stage.PREFLIGHT,
            message=str(exc),
            retryable=False,
        ) from exc

    results: list[dict] = []
    errors: list[dict] = []
    updated_deal_ids: set[str] = set()
    deals_by_id = {
        str(deal.get("deal_id") or ""): deal
        for deal in deals
        if str(deal.get("deal_id") or "")
    }

    if not dry_run:
        framework = resolve_active_qualification_framework(cfg)
        framework_hash = qualification_framework_fingerprint(framework)
        for row in plan["selected_candidates"]:
            deal_id = str(row.get("deal_id") or "")
            deal = deals_by_id.get(deal_id)
            if deal is None:
                errors.append(_error_row(row, "deal_not_found_in_backfill_input"))
                continue
            interaction_index = int(row.get("interaction_index") or -1)
            interactions = deal.get("interactions")
            if not isinstance(interactions, list) or interaction_index >= len(interactions):
                errors.append(_error_row(row, "interaction_not_found_in_backfill_input"))
                continue
            try:
                result = _reextract_interaction(
                    llm,
                    cfg,
                    framework=framework,
                    framework_hash=framework_hash,
                    row=row,
                    interaction=interactions[interaction_index],
                )
                results.append(result)
                updated_deal_ids.add(deal_id)
            except Exception as exc:  # pragma: no cover - defensive per-row envelope
                errors.append(_error_row(row, _safe_error(exc)))

        now = datetime.now(UTC).isoformat()
        for deal_id in sorted(updated_deal_ids):
            deal = deals_by_id[deal_id]
            try:
                snapshots = rebuild_latest_snapshots(deal, cfg)
                updated = mongo.update_deal_qualification_reextraction(
                    deal_id,
                    interactions=deal.get("interactions") or [],
                    meddpicc_latest=snapshots["meddpicc_latest"],
                    qualification_latest=snapshots["qualification_latest"],
                    updated_at=now,
                )
                for result in results:
                    if result.get("deal_id") == deal_id:
                        result["storage_written"] = bool(updated)
            except Exception as exc:  # pragma: no cover - defensive storage envelope
                errors.append(
                    {
                        "deal_id": deal_id,
                        "company": deal.get("company"),
                        "error": _safe_error(exc),
                    }
                )

    summary = dict(plan["summary"])
    summary["applied_count"] = len(results)
    summary["error_count"] = len(errors)
    return {
        "ok": not errors,
        "dry_run": dry_run,
        "mode": "llm_reextract",
        "llm_calls": not dry_run,
        "storage_written": any(bool(row.get("storage_written")) for row in results),
        "framework": plan["framework"],
        "summary": summary,
        "candidates": plan["candidates"],
        "selected_candidates": plan["selected_candidates"],
        "skipped": plan["skipped"],
        "results": results,
        "errors": errors,
        "warnings": plan["warnings"],
    }


def _classify_interaction(
    deal: dict,
    interaction: dict,
    *,
    index: int,
    framework: QualificationFramework,
    framework_hash: str,
    include_unconfirmed: bool,
    include_unhashed: bool,
) -> dict:
    normalized = normalize_interaction_record(interaction)
    base = _interaction_base(deal, normalized, index)
    raw_content = str(normalized.get("raw_content") or "").strip()
    if not raw_content:
        return {**base, "action": "skipped", "reason": "missing_raw_content"}

    scoring = scoring_applies(str(normalized.get("source_confidence") or ""))
    if not scoring and not include_unconfirmed:
        return {**base, "action": "skipped", "reason": "non_scoring_source"}

    target_field = _target_field(framework.key, scoring=scoring)
    existing = interaction.get(target_field)
    if framework.key != "meddpicc" and target_field == "qualification":
        stored_framework = str(interaction.get("qualification_framework") or "")
        if isinstance(existing, dict) and existing and stored_framework != framework.key:
            return {
                **base,
                "action": "reextract",
                "reason": "different_framework_evidence",
                "target_field": target_field,
                "content_chars": len(raw_content),
            }

    if isinstance(existing, dict) and existing:
        stored_hash = str(interaction.get("qualification_framework_hash") or "")
        if stored_hash and stored_hash != framework_hash:
            return {
                **base,
                "action": "reextract",
                "reason": "stale_framework_hash",
                "target_field": target_field,
                "stored_framework_hash": stored_hash,
                "current_framework_hash": framework_hash,
                "content_chars": len(raw_content),
            }
        if not stored_hash and include_unhashed:
            return {
                **base,
                "action": "reextract",
                "reason": "missing_framework_hash",
                "target_field": target_field,
                "current_framework_hash": framework_hash,
                "content_chars": len(raw_content),
            }
        return {
            **base,
            "action": "clean",
            "reason": "active_framework_evidence_present",
            "target_field": target_field,
        }

    return {
        **base,
        "action": "reextract",
        "reason": "missing_active_framework_evidence",
        "target_field": target_field,
        "content_chars": len(raw_content),
    }


def _reextract_interaction(
    llm: LLMProvider,
    cfg: dict,
    *,
    framework: QualificationFramework,
    framework_hash: str,
    row: dict,
    interaction: dict,
) -> dict:
    normalized = normalize_interaction_record(interaction)
    content = str(normalized.get("raw_content") or "").strip()
    if not content:
        raise ValueError("missing_raw_content")
    resp = llm.chat_once(
        system=_SYSTEM,
        user=_PROMPT.format(
            interaction_type=normalized.get("interaction_type"),
            direction=normalized.get("direction"),
            source_confidence=normalized.get("source_confidence"),
            qualification_framework_prompt=render_qualification_extraction_prompt_block(
                framework
            ),
            content=content,
        ),
        max_tokens=768,
    )
    payload = load_json_response(resp.text)
    normalized_result = normalize_qualification_extraction(payload, framework=framework)
    qualification = normalized_result["qualification"]
    if not qualification:
        raise ValueError("no_qualification_extracted")

    target_field = str(row.get("target_field") or _target_field(framework.key, scoring=True))
    interaction[target_field] = qualification
    interaction["qualification_framework"] = framework.key
    interaction["qualification_framework_hash"] = framework_hash
    warnings = normalized_result.get("warnings") or []
    if warnings:
        interaction["qualification_extraction_warnings"] = warnings
    else:
        interaction.pop("qualification_extraction_warnings", None)
    usage = build_llm_usage_metadata(
        cfg,
        source_tool="backfill_qualification_reextract",
        calls=[{"operation": "reextract_qualification", "usage": resp.usage}],
    )
    interaction["qualification_backfill_usage"] = usage
    return {
        "deal_id": row.get("deal_id"),
        "company": row.get("company"),
        "interaction_id": row.get("interaction_id"),
        "interaction_index": row.get("interaction_index"),
        "reason": row.get("reason"),
        "target_field": target_field,
        "dimension_count": len(qualification),
        "warning_count": len(warnings),
        "usage_summary": {
            "calls": usage["calls"],
            "totals": summarize_usage([resp.usage]),
            "estimated_cost_usd": usage["estimated_cost_usd"],
            "cost_basis": usage["cost_basis"],
        },
        "storage_written": False,
    }


def _target_field(framework_key: str, *, scoring: bool) -> str:
    if framework_key == "meddpicc":
        return "meddpicc" if scoring else "unconfirmed_meddpicc"
    return "qualification" if scoring else "unconfirmed_qualification"


def _interaction_base(deal: dict, interaction: dict, index: int) -> dict:
    return {
        "deal_id": deal.get("deal_id"),
        "company": deal.get("company"),
        "deal_stage": deal.get("deal_stage"),
        "interaction_index": index,
        "interaction_id": interaction.get("interaction_id") or interaction.get("meeting_id"),
        "date": interaction.get("date"),
        "interaction_type": interaction.get("interaction_type"),
        "direction": interaction.get("direction"),
        "source_confidence": interaction.get("source_confidence"),
    }


def _interaction_skip_row(deal: dict, index: int, reason: str) -> dict:
    return {
        "deal_id": deal.get("deal_id"),
        "company": deal.get("company"),
        "deal_stage": deal.get("deal_stage"),
        "interaction_index": index,
        "action": "skipped",
        "reason": reason,
    }


def _deal_skip_row(deal: dict, reason: str) -> dict:
    return {
        "deal_id": deal.get("deal_id"),
        "company": deal.get("company"),
        "deal_stage": deal.get("deal_stage"),
        "interaction_index": None,
        "action": "skipped",
        "reason": reason,
    }


def _issue_counts(rows: list[dict]) -> dict:
    counts: dict[str, int] = {}
    for row in rows:
        key = str(row.get("reason") or row.get("action") or "unknown")
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _plan_warnings(
    candidates: list[dict],
    selected: list[dict],
    include_unconfirmed: bool,
) -> list[dict]:
    warnings: list[dict] = [
        {
            "code": "llm_cost_possible",
            "message": (
                "Apply mode calls the configured LLM once per selected interaction. "
                "Dry-run first and review selected_count/max_llm_calls."
            ),
        }
    ]
    if len(candidates) > len(selected):
        warnings.append(
            {
                "code": "candidate_limit_applied",
                "message": (
                    f"{len(candidates) - len(selected)} candidate interaction(s) "
                    "are beyond max_llm_calls and will not be processed in one apply run."
                ),
            }
        )
    if not include_unconfirmed:
        warnings.append(
            {
                "code": "unconfirmed_sources_excluded",
                "message": (
                    "Internal and outbound-unconfirmed interactions are skipped by "
                    "default. Use include_unconfirmed only when you intentionally "
                    "want unconfirmed context re-extracted."
                ),
            }
        )
    return warnings


def _error_row(row: dict, error: str) -> dict:
    return {
        "deal_id": row.get("deal_id"),
        "company": row.get("company"),
        "interaction_id": row.get("interaction_id"),
        "interaction_index": row.get("interaction_index"),
        "error": error,
    }


def _safe_error(exc: Exception) -> str:
    return f"{type(exc).__name__}: {str(exc)[:160]}"
