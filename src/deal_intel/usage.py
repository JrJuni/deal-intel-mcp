from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

TOKEN_KEYS = (
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "cached_input_tokens",
    "cache_read_input_tokens",
    "cache_creation_input_tokens",
    "reasoning_output_tokens",
)


def provider_model_from_config(cfg: dict) -> tuple[str, str]:
    llm = _mapping(cfg.get("llm"))
    provider = str(llm.get("provider") or "chatgpt_oauth")
    if provider == "openai_api":
        model = str(llm.get("openai_api_model") or "gpt-5.4-mini")
    elif provider == "anthropic":
        model = str(llm.get("draft_model") or "claude-sonnet-4-6")
    else:
        model = str(llm.get("chatgpt_oauth_model") or "gpt-5.5")
    return provider, model


def build_llm_usage_metadata(
    cfg: dict,
    *,
    source_tool: str,
    calls: list[dict],
) -> dict:
    provider, model = provider_model_from_config(cfg)
    normalized_calls = [
        {
            "operation": str(call.get("operation") or "unknown"),
            "usage": normalize_usage(call.get("usage")),
        }
        for call in calls
    ]
    totals = summarize_usage(call["usage"] for call in normalized_calls)
    cost = estimate_usage_cost(cfg, provider=provider, model=model, usage=totals)
    return {
        "provider": provider,
        "model": model,
        "source_tool": source_tool,
        "generated_at": datetime.now(UTC).isoformat(),
        "calls": normalized_calls,
        "totals": totals,
        **cost,
    }


def build_usage_report(
    *,
    deals: list[dict],
    cfg: dict,
    since: str | None = None,
    until: str | None = None,
) -> dict:
    warnings: list[str] = []
    entries: list[dict] = []
    for deal in deals:
        for interaction in deal.get("interactions") or []:
            if not isinstance(interaction, dict):
                continue
            metadata = _mapping(interaction.get("llm_usage"))
            if not metadata:
                continue
            entry_date = str(interaction.get("date") or "")[:10]
            if not _date_in_range(entry_date, since=since, until=until):
                continue
            entries.append(
                _entry_from_metadata(
                    metadata,
                    deal=deal,
                    date=entry_date or None,
                    source_kind="interaction",
                    interaction_type=interaction.get("interaction_type"),
                )
            )

        strategy_usage = _mapping(deal.get("bd_strategy_usage"))
        if strategy_usage:
            generated_at = str(strategy_usage.get("generated_at") or "")[:10]
            if _date_in_range(generated_at, since=since, until=until):
                entries.append(
                    _entry_from_metadata(
                        strategy_usage,
                        deal=deal,
                        date=generated_at or None,
                        source_kind="bd_strategy",
                        interaction_type=None,
                    )
                )

    totals = summarize_usage(entry["usage"] for entry in entries)
    summary = {
        "deal_count_scanned": len(deals),
        "usage_entries": len(entries),
        "llm_call_count": sum(int(entry.get("call_count") or 0) for entry in entries),
        "tokens": totals,
        "estimated_cost_usd": _sum_known_costs(entries),
        "unestimated_entries": sum(
            1 for entry in entries if entry.get("estimated_cost_usd") is None
        ),
    }
    if entries and summary["unestimated_entries"]:
        warnings.append("some_usage_entries_do_not_have_configured_pricing")
    if not entries:
        warnings.append("no_persisted_usage_metadata_found")

    return {
        "ok": True,
        "generated_at": datetime.now(UTC).isoformat(),
        "filters": {"since": since, "until": until},
        "summary": summary,
        "by_provider": _group_entries(entries, "provider"),
        "by_tool": _group_entries(entries, "source_tool"),
        "by_operation": _group_calls(entries),
        "entries": entries[:100],
        "pricing_policy": {
            "chatgpt_oauth": "tracked as subscription-backed with zero incremental API estimate",
            "api_providers": "estimated only when usage.pricing is configured",
        },
        "warnings": warnings,
    }


def normalize_usage(usage: Any) -> dict:
    source = usage if isinstance(usage, dict) else {}
    normalized = {key: _int(source.get(key)) for key in TOKEN_KEYS}
    if normalized["total_tokens"] <= 0:
        normalized["total_tokens"] = (
            normalized["input_tokens"] + normalized["output_tokens"]
        )
    return normalized


def summarize_usage(usages: Any) -> dict:
    total = {key: 0 for key in TOKEN_KEYS}
    for usage in usages:
        normalized = normalize_usage(usage)
        for key in TOKEN_KEYS:
            total[key] += normalized[key]
    return total


def estimate_usage_cost(
    cfg: dict,
    *,
    provider: str,
    model: str,
    usage: dict,
) -> dict:
    if provider == "chatgpt_oauth":
        return {
            "estimated_cost_usd": 0.0,
            "cost_basis": "chatgpt_oauth_subscription_no_incremental_api_bill",
        }

    pricing = _mapping(_mapping(_mapping(cfg.get("usage")).get("pricing")).get(provider))
    model_pricing = _mapping(pricing.get(model))
    if not model_pricing:
        return {
            "estimated_cost_usd": None,
            "cost_basis": "pricing_not_configured",
        }

    input_rate = _float(model_pricing.get("input_per_1m_usd"))
    output_rate = _float(model_pricing.get("output_per_1m_usd"))
    cached_rate = _float(model_pricing.get("cached_input_per_1m_usd"))
    reasoning_rate = _float(model_pricing.get("reasoning_output_per_1m_usd"))
    estimated = (
        usage.get("input_tokens", 0) / 1_000_000 * input_rate
        + usage.get("output_tokens", 0) / 1_000_000 * output_rate
        + usage.get("cached_input_tokens", 0) / 1_000_000 * cached_rate
        + usage.get("reasoning_output_tokens", 0) / 1_000_000 * reasoning_rate
    )
    return {
        "estimated_cost_usd": round(estimated, 8),
        "cost_basis": "configured_usage_pricing",
    }


def _entry_from_metadata(
    metadata: dict,
    *,
    deal: dict,
    date: str | None,
    source_kind: str,
    interaction_type: object,
) -> dict:
    calls = metadata.get("calls") if isinstance(metadata.get("calls"), list) else []
    usage = normalize_usage(metadata.get("totals"))
    if not any(usage.values()) and calls:
        usage = summarize_usage(_mapping(call).get("usage") for call in calls)
    return {
        "deal_id": deal.get("deal_id"),
        "company": deal.get("company"),
        "date": date,
        "source_kind": source_kind,
        "interaction_type": interaction_type,
        "source_tool": metadata.get("source_tool") or "unknown",
        "provider": metadata.get("provider") or "unknown",
        "model": metadata.get("model") or "unknown",
        "call_count": len(calls) or 1,
        "usage": usage,
        "estimated_cost_usd": metadata.get("estimated_cost_usd"),
        "cost_basis": metadata.get("cost_basis") or "unknown",
        "operations": [
            str(_mapping(call).get("operation") or "unknown")
            for call in calls
        ],
    }


def _group_entries(entries: list[dict], key: str) -> list[dict]:
    grouped: dict[str, dict] = {}
    for entry in entries:
        name = str(entry.get(key) or "unknown")
        bucket = grouped.setdefault(
            name,
            {
                key: name,
                "usage_entries": 0,
                "llm_call_count": 0,
                "tokens": {token_key: 0 for token_key in TOKEN_KEYS},
                "estimated_cost_usd": 0.0,
                "unestimated_entries": 0,
            },
        )
        bucket["usage_entries"] += 1
        bucket["llm_call_count"] += int(entry.get("call_count") or 0)
        for token_key in TOKEN_KEYS:
            bucket["tokens"][token_key] += int(entry["usage"].get(token_key) or 0)
        if entry.get("estimated_cost_usd") is None:
            bucket["unestimated_entries"] += 1
        else:
            bucket["estimated_cost_usd"] += float(entry["estimated_cost_usd"])

    return [_round_costs(bucket) for bucket in grouped.values()]


def _group_calls(entries: list[dict]) -> list[dict]:
    grouped: dict[str, dict] = defaultdict(
        lambda: {
            "operation": "",
            "llm_call_count": 0,
        }
    )
    for entry in entries:
        operations = entry.get("operations") or ["unknown"]
        for operation in operations:
            bucket = grouped[str(operation)]
            bucket["operation"] = str(operation)
            bucket["llm_call_count"] += 1
    return list(grouped.values())


def _date_in_range(value: str, *, since: str | None, until: str | None) -> bool:
    if since and (not value or value < since):
        return False
    if until and (not value or value > until):
        return False
    return True


def _sum_known_costs(entries: list[dict]) -> float | None:
    known = [
        entry["estimated_cost_usd"]
        for entry in entries
        if entry["estimated_cost_usd"] is not None
    ]
    if not known:
        return None
    return round(sum(float(value) for value in known), 8)


def _round_costs(bucket: dict) -> dict:
    bucket["estimated_cost_usd"] = round(float(bucket["estimated_cost_usd"]), 8)
    if bucket["unestimated_entries"] == bucket["usage_entries"]:
        bucket["estimated_cost_usd"] = None
    return bucket


def _mapping(value: object) -> dict:
    return value if isinstance(value, dict) else {}


def _int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _float(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0
