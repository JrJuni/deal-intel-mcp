from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta
from typing import Any

from deal_intel.schema.metrics import (
    ACTIVE_STAGES,
    DEFAULT_DEAL_CURRENCY,
    OPEN_STAGES,
    normalize_currency,
)

DEFAULT_LOOKBACK_DAYS = 7
MAX_LOOKBACK_DAYS = 365


def build_pipeline_trend_summary(
    snapshots: list[dict],
    *,
    as_of: date,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    stage: str | None = None,
    industry: str | None = None,
) -> dict:
    if not isinstance(as_of, date) or isinstance(as_of, datetime):
        raise ValueError("as_of must be a date")
    validate_lookback_days(lookback_days)

    window_start = as_of - timedelta(days=lookback_days)
    filtered = _filter_snapshots(
        _dedupe_event_snapshots(snapshots),
        stage=stage,
        industry=industry,
    )
    in_window = [
        snapshot
        for snapshot in filtered
        if _parse_as_of(snapshot) is not None
        and window_start <= _parse_as_of(snapshot) <= as_of
    ]

    start_snapshots = _latest_by_deal(
        [snapshot for snapshot in filtered if _is_on_or_before(snapshot, window_start)]
    )
    end_snapshots = _latest_by_deal(
        [snapshot for snapshot in filtered if _is_on_or_before(snapshot, as_of)]
    )

    start_kpis = _kpis(start_snapshots.values())
    end_kpis = _kpis(end_snapshots.values())
    deltas = _deltas(start_kpis, end_kpis)
    stage_changes = _stage_changes(start_snapshots, end_snapshots)

    return {
        "filters": {"stage": stage or None, "industry": industry or None},
        "window": {
            "lookback_days": lookback_days,
            "start_date": window_start.isoformat(),
            "end_date": as_of.isoformat(),
        },
        "snapshot_count": len(in_window),
        "deal_count": len(end_snapshots),
        "start": start_kpis,
        "end": end_kpis,
        "delta": deltas,
        "stage_changes": stage_changes,
        "warnings": _warnings(
            in_window=in_window,
            start_snapshots=start_snapshots,
            end_snapshots=end_snapshots,
        ),
    }


def validate_lookback_days(lookback_days: int) -> None:
    if isinstance(lookback_days, bool) or not isinstance(lookback_days, int):
        raise ValueError("lookback_days must be an integer")
    if lookback_days < 1 or lookback_days > MAX_LOOKBACK_DAYS:
        raise ValueError(f"lookback_days must be between 1 and {MAX_LOOKBACK_DAYS}")


def _dedupe_event_snapshots(snapshots: list[dict]) -> list[dict]:
    seen = set()
    unique = []
    for snapshot in snapshots:
        event_id = snapshot.get("event_id")
        if event_id is not None:
            if event_id in seen:
                continue
            seen.add(event_id)
        unique.append(snapshot)
    return unique


def _filter_snapshots(
    snapshots: list[dict],
    *,
    stage: str | None,
    industry: str | None,
) -> list[dict]:
    filtered = []
    for snapshot in snapshots:
        if stage is not None and snapshot.get("deal_stage") != stage:
            continue
        if industry is not None and snapshot.get("industry") != industry:
            continue
        filtered.append(snapshot)
    return filtered


def _latest_by_deal(snapshots: list[dict]) -> dict[str, dict]:
    latest: dict[str, dict] = {}
    for snapshot in sorted(snapshots, key=_sort_key):
        deal_id = snapshot.get("deal_id")
        if not isinstance(deal_id, str) or not deal_id:
            continue
        latest[deal_id] = snapshot
    return latest


def _kpis(snapshots: Any) -> dict:
    rows = list(snapshots)
    active = [row for row in rows if row.get("deal_stage") in ACTIVE_STAGES]
    open_rows = [row for row in rows if row.get("deal_stage") in OPEN_STAGES]
    assessed_health = [
        float(row["health_pct"])
        for row in active
        if isinstance(row.get("health_pct"), (int, float))
        and not isinstance(row.get("health_pct"), bool)
    ]
    attention = [row for row in rows if row.get("attention_reasons")]
    won = [row for row in rows if row.get("deal_stage") == "won"]
    lost = [row for row in rows if row.get("deal_stage") == "lost"]
    open_value = _open_pipeline_value(open_rows)

    return {
        "active_deal_count": len(active),
        "open_deal_count": len(open_rows),
        "open_pipeline_value_amount": open_value["amount"],
        "open_pipeline_value_currency": open_value["currency"],
        "open_pipeline_value_currencies": open_value["currencies"],
        "mixed_open_pipeline_value_currency": open_value["mixed_currency"],
        "open_pipeline_value_by_currency": open_value["amount_by_currency"],
        "avg_health_pct": (
            round(sum(assessed_health) / len(assessed_health), 1)
            if assessed_health
            else None
        ),
        "health_assessed_count": len(assessed_health),
        "attention_deal_count": len(attention),
        "won_deal_count": len(won),
        "lost_deal_count": len(lost),
    }


def _open_pipeline_value(rows: list[dict]) -> dict:
    amount_by_currency: dict[str, int] = {}
    for row in rows:
        amount = row.get("deal_size_amount")
        if amount is None or isinstance(amount, bool):
            continue
        if not isinstance(amount, (int, float)):
            continue
        currency = _row_currency(row)
        amount_by_currency[currency] = amount_by_currency.get(currency, 0) + int(amount)

    currencies = sorted(amount_by_currency) or [DEFAULT_DEAL_CURRENCY]
    mixed_currency = len(amount_by_currency) > 1
    currency = None if mixed_currency else currencies[0]
    amount = None if mixed_currency else amount_by_currency.get(currencies[0], 0)
    return {
        "amount": amount,
        "currency": currency,
        "currencies": currencies,
        "mixed_currency": mixed_currency,
        "amount_by_currency": dict(sorted(amount_by_currency.items())),
    }


def _row_currency(row: dict) -> str:
    try:
        return normalize_currency(
            row.get("deal_size_currency"),
            default=DEFAULT_DEAL_CURRENCY,
        )
    except ValueError:
        return DEFAULT_DEAL_CURRENCY


def _deltas(start: dict, end: dict) -> dict:
    return {
        key: _delta_value(start.get(key), end.get(key))
        for key in (
            "active_deal_count",
            "open_deal_count",
            "open_pipeline_value_amount",
            "avg_health_pct",
            "attention_deal_count",
            "won_deal_count",
            "lost_deal_count",
        )
    }


def _delta_value(start_value, end_value):
    if start_value is None or end_value is None:
        return None
    if (
        isinstance(start_value, int)
        and not isinstance(start_value, bool)
        and isinstance(end_value, int)
        and not isinstance(end_value, bool)
    ):
        return end_value - start_value
    return round(float(end_value) - float(start_value), 1)


def _stage_changes(start: dict[str, dict], end: dict[str, dict]) -> dict:
    transitions = Counter()
    entered = Counter()
    exited = Counter()
    for deal_id, end_snapshot in end.items():
        end_stage = end_snapshot.get("deal_stage")
        start_snapshot = start.get(deal_id)
        if start_snapshot is None:
            entered[str(end_stage)] += 1
            continue
        start_stage = start_snapshot.get("deal_stage")
        if start_stage != end_stage:
            transitions[f"{start_stage}->{end_stage}"] += 1
    for deal_id, start_snapshot in start.items():
        if deal_id not in end:
            exited[str(start_snapshot.get("deal_stage"))] += 1
    return {
        "transition_count": sum(transitions.values()),
        "transitions": dict(sorted(transitions.items())),
        "entered": dict(sorted(entered.items())),
        "exited": dict(sorted(exited.items())),
    }


def _warnings(
    *,
    in_window: list[dict],
    start_snapshots: dict[str, dict],
    end_snapshots: dict[str, dict],
) -> list[str]:
    warnings = []
    if not in_window:
        warnings.append("no_snapshots_in_window")
    if not start_snapshots:
        warnings.append("missing_start_baseline")
    if not end_snapshots:
        warnings.append("missing_end_baseline")
    if len(in_window) < 2:
        warnings.append("insufficient_snapshots")
    start_mixed = (
        start_snapshots
        and _kpis(start_snapshots.values())["mixed_open_pipeline_value_currency"]
    )
    end_mixed = (
        end_snapshots
        and _kpis(end_snapshots.values())["mixed_open_pipeline_value_currency"]
    )
    if start_mixed or end_mixed:
        warnings.append("mixed_currency")
    return warnings


def _is_on_or_before(snapshot: dict, target: date) -> bool:
    snapshot_date = _parse_as_of(snapshot)
    return snapshot_date is not None and snapshot_date <= target


def _parse_as_of(snapshot: dict) -> date | None:
    raw = snapshot.get("as_of")
    if isinstance(raw, date) and not isinstance(raw, datetime):
        return raw
    if isinstance(raw, str):
        try:
            return date.fromisoformat(raw)
        except ValueError:
            return None
    return None


def _sort_key(snapshot: dict) -> tuple[str, str]:
    return (
        str(snapshot.get("as_of") or ""),
        str(snapshot.get("occurred_at") or snapshot.get("created_at") or ""),
    )
