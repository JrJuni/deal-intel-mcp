from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import StrEnum
from typing import Any

ACTIVE_STAGES = frozenset({"discovery", "qualification", "proposal", "negotiation"})
STALLED_STAGES = frozenset({"stalled"})
OPEN_STAGES = ACTIVE_STAGES | STALLED_STAGES
TERMINAL_STAGES = frozenset({"won", "lost"})


class HealthBand(StrEnum):
    HEALTHY = "healthy"
    WATCH = "watch"
    AT_RISK = "at_risk"
    UNASSESSED = "unassessed"


class DealValueStatus(StrEnum):
    UNKNOWN = "unknown"
    ROUGH_ESTIMATE = "rough_estimate"
    CUSTOMER_BUDGET = "customer_budget"
    QUOTED = "quoted"
    STRATEGIC_ZERO = "strategic_zero"


class StuckStatus(StrEnum):
    STUCK = "stuck"
    NOT_STUCK = "not_stuck"
    UNASSESSED = "unassessed"
    NOT_APPLICABLE = "not_applicable"


class CloseDateStatus(StrEnum):
    OVERDUE = "overdue"
    ON_TRACK = "on_track"
    MISSING = "missing"
    INVALID = "invalid"
    NOT_APPLICABLE = "not_applicable"


KNOWN_VALUE_STATUSES = frozenset(
    {
        DealValueStatus.ROUGH_ESTIMATE,
        DealValueStatus.CUSTOMER_BUDGET,
        DealValueStatus.QUOTED,
    }
)
VALIDATED_VALUE_STATUSES = frozenset(
    {
        DealValueStatus.CUSTOMER_BUDGET,
        DealValueStatus.QUOTED,
    }
)


@dataclass(frozen=True)
class HealthBandThresholds:
    healthy_min: float = 70.0
    watch_min: float = 40.0

    @classmethod
    def from_config(cls, cfg: dict) -> HealthBandThresholds:
        raw = cfg.get("metrics", {}).get("health_bands", {})
        thresholds = cls(
            healthy_min=_as_finite_number(raw.get("healthy_min", cls.healthy_min)),
            watch_min=_as_finite_number(raw.get("watch_min", cls.watch_min)),
        )
        thresholds.validate()
        return thresholds

    def validate(self) -> None:
        if not 0 <= self.watch_min < self.healthy_min <= 100:
            raise ValueError(
                "metrics.health_bands must satisfy "
                "0 <= watch_min < healthy_min <= 100"
            )


@dataclass(frozen=True)
class DealValueAssessment:
    status: DealValueStatus | None
    amount_krw: int | None
    low_krw: int | None
    high_krw: int | None
    is_valid: bool
    is_known: bool
    is_classified: bool
    is_validated: bool
    is_strategic_zero: bool
    issue: str | None = None


@dataclass(frozen=True)
class PipelineTimingSettings:
    stuck_default_days: int = 14
    stuck_days_by_stage: dict[str, int] | None = None
    overdue_grace_days: int = 0

    @classmethod
    def from_config(cls, cfg: dict) -> PipelineTimingSettings:
        pipeline = _as_mapping(cfg.get("pipeline", {}), "pipeline")
        metrics = _as_mapping(cfg.get("metrics", {}), "metrics")
        raw_stuck_by_stage = _as_mapping(
            pipeline.get("stuck_threshold_days_by_stage", {}),
            "pipeline.stuck_threshold_days_by_stage",
        )
        overdue = _as_mapping(metrics.get("overdue", {}), "metrics.overdue")

        stuck_by_stage = {
            str(stage): _as_non_negative_int(
                value,
                "pipeline.stuck_threshold_days_by_stage values",
            )
            for stage, value in raw_stuck_by_stage.items()
        }
        return cls(
            stuck_default_days=_as_non_negative_int(
                pipeline.get("stuck_threshold_days", cls.stuck_default_days),
                "pipeline.stuck_threshold_days",
            ),
            stuck_days_by_stage=stuck_by_stage,
            overdue_grace_days=_as_non_negative_int(
                overdue.get(
                    "grace_days",
                    cls.overdue_grace_days,
                ),
                "metrics.overdue.grace_days",
            ),
        )

    def stuck_threshold_for(self, stage: str) -> int:
        return (self.stuck_days_by_stage or {}).get(stage, self.stuck_default_days)


@dataclass(frozen=True)
class WinRateSettings:
    minimum_closed_sample: int = 10

    @classmethod
    def from_config(cls, cfg: dict) -> WinRateSettings:
        metrics = _as_mapping(cfg.get("metrics", {}), "metrics")
        raw = _as_mapping(metrics.get("win_rate", {}), "metrics.win_rate")
        return cls(
            minimum_closed_sample=_as_positive_int(
                raw.get("minimum_closed_sample", cls.minimum_closed_sample),
                "metrics.win_rate.minimum_closed_sample",
            )
        )


@dataclass(frozen=True)
class ExpectedCloseSettings:
    default_days: int = 7
    days_by_industry: dict[str, int] | None = None

    @classmethod
    def from_config(cls, cfg: dict) -> ExpectedCloseSettings:
        pipeline = _as_mapping(cfg.get("pipeline", {}), "pipeline")
        raw = _as_mapping(
            pipeline.get("expected_close", {}),
            "pipeline.expected_close",
        )
        raw_by_industry = _as_mapping(
            raw.get("days_by_industry", {}),
            "pipeline.expected_close.days_by_industry",
        )
        days_by_industry = {
            str(industry).strip().casefold(): _as_non_negative_int(
                days,
                "pipeline.expected_close.days_by_industry values",
            )
            for industry, days in raw_by_industry.items()
            if str(industry).strip()
        }
        return cls(
            default_days=_as_non_negative_int(
                raw.get("default_days", cls.default_days),
                "pipeline.expected_close.default_days",
            ),
            days_by_industry=days_by_industry,
        )

    def days_for(self, industry: str | None) -> tuple[int, str]:
        industry_key = (industry or "").strip().casefold()
        if industry_key and industry_key in (self.days_by_industry or {}):
            return (self.days_by_industry or {})[industry_key], "config_industry"
        return self.default_days, "config_default"


@dataclass(frozen=True)
class PipelineTimingAssessment:
    days_in_stage: int | None
    stuck_threshold_days: int | None
    stuck_status: StuckStatus
    is_stuck: bool | None
    close_date_status: CloseDateStatus
    is_overdue: bool | None
    overdue_days: int | None


def _as_finite_number(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("health band thresholds must be finite numbers")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("health band thresholds must be finite numbers")
    return number


def _as_non_negative_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")
    return value


def _as_mapping(value: Any, field_name: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a mapping")
    return value


def _as_positive_int(value: Any, field_name: str) -> int:
    number = _as_non_negative_int(value, field_name)
    if number == 0:
        raise ValueError(f"{field_name} must be greater than zero")
    return number


def _is_krw_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def assess_deal_value(deal: dict) -> DealValueAssessment:
    """Validate a deal's amount classification without mutating the document."""
    raw_status = deal.get("deal_size_status")
    amount = deal.get("deal_size_krw")
    low = deal.get("deal_size_low_krw")
    high = deal.get("deal_size_high_krw")

    status = None
    if raw_status not in (None, ""):
        try:
            status = DealValueStatus(str(raw_status))
        except ValueError:
            return _invalid_value_assessment(amount, low, high, "invalid_status")

    for value in (amount, low, high):
        if value is not None and not _is_krw_integer(value):
            return _invalid_value_assessment(amount, low, high, "invalid_amount_type")

    if status == DealValueStatus.UNKNOWN:
        if any(value is not None for value in (amount, low, high)):
            return _invalid_value_assessment(
                amount,
                low,
                high,
                "unknown_status_must_not_have_amount",
                status=status,
            )
        return DealValueAssessment(
            status=status,
            amount_krw=None,
            low_krw=None,
            high_krw=None,
            is_valid=True,
            is_known=False,
            is_classified=True,
            is_validated=False,
            is_strategic_zero=False,
        )

    if status == DealValueStatus.STRATEGIC_ZERO:
        if amount != 0 or low not in (None, 0) or high not in (None, 0):
            return _invalid_value_assessment(
                amount,
                low,
                high,
                "strategic_zero_requires_zero_amount",
                status=status,
            )
        return DealValueAssessment(
            status=status,
            amount_krw=0,
            low_krw=0,
            high_krw=0,
            is_valid=True,
            is_known=True,
            is_classified=True,
            is_validated=False,
            is_strategic_zero=True,
        )

    if amount is None:
        if status in KNOWN_VALUE_STATUSES or low is not None or high is not None:
            return _invalid_value_assessment(
                amount,
                low,
                high,
                "known_status_requires_positive_amount",
                status=status,
            )
        return DealValueAssessment(
            status=None,
            amount_krw=None,
            low_krw=None,
            high_krw=None,
            is_valid=True,
            is_known=False,
            is_classified=False,
            is_validated=False,
            is_strategic_zero=False,
        )

    if amount <= 0:
        return _invalid_value_assessment(
            amount,
            low,
            high,
            "non_positive_amount_requires_strategic_zero",
            status=status,
        )

    effective_low = amount if low is None else low
    effective_high = amount if high is None else high
    if effective_low <= 0 or effective_high <= 0:
        return _invalid_value_assessment(
            amount,
            low,
            high,
            "estimated_range_must_be_positive",
            status=status,
        )
    if not effective_low <= amount <= effective_high:
        return _invalid_value_assessment(
            amount,
            low,
            high,
            "estimated_range_must_include_amount",
            status=status,
        )

    return DealValueAssessment(
        status=status,
        amount_krw=amount,
        low_krw=effective_low,
        high_krw=effective_high,
        is_valid=True,
        is_known=True,
        is_classified=status is not None,
        is_validated=status in VALIDATED_VALUE_STATUSES,
        is_strategic_zero=False,
    )


def _invalid_value_assessment(
    amount: Any,
    low: Any,
    high: Any,
    issue: str,
    *,
    status: DealValueStatus | None = None,
) -> DealValueAssessment:
    return DealValueAssessment(
        status=status,
        amount_krw=amount if _is_krw_integer(amount) else None,
        low_krw=low if _is_krw_integer(low) else None,
        high_krw=high if _is_krw_integer(high) else None,
        is_valid=False,
        is_known=False,
        is_classified=status is not None,
        is_validated=False,
        is_strategic_zero=False,
        issue=issue,
    )


def summarize_pipeline_value(
    deals: Iterable[dict],
    *,
    stages: frozenset[str] | set[str] | None = None,
) -> dict:
    """Summarize known deal values for the requested stage population."""
    population = [
        deal for deal in deals if stages is None or deal.get("deal_stage") in stages
    ]
    assessments = [assess_deal_value(deal) for deal in population]
    known = [item for item in assessments if item.is_valid and item.is_known]

    deal_count = len(population)
    known_count = len(known)
    coverage_pct = round(known_count / deal_count * 100, 1) if deal_count else None
    status_counts = {status.value: 0 for status in DealValueStatus}
    for item in assessments:
        if item.status is not None and item.is_valid:
            status_counts[item.status.value] += 1

    return {
        "deal_count": deal_count,
        "pipeline_value_krw": sum(item.amount_krw or 0 for item in known),
        "pipeline_value_low_krw": sum(item.low_krw or 0 for item in known),
        "pipeline_value_high_krw": sum(item.high_krw or 0 for item in known),
        "validated_pipeline_value_krw": sum(
            item.amount_krw or 0 for item in known if item.is_validated
        ),
        "known_amount_count": known_count,
        "missing_amount_count": sum(
            item.is_valid and not item.is_known for item in assessments
        ),
        "invalid_amount_count": sum(not item.is_valid for item in assessments),
        "unclassified_amount_count": sum(
            item.is_valid and item.is_known and not item.is_classified
            for item in assessments
        ),
        "strategic_zero_count": sum(item.is_strategic_zero for item in known),
        "amount_coverage_pct": coverage_pct,
        "status_counts": status_counts,
    }


def resolve_expected_close_date(
    *,
    provided: str | None,
    industry: str | None,
    created_on: date,
    settings: ExpectedCloseSettings,
) -> tuple[str, str]:
    """Return an ISO close date and whether it was user- or config-derived."""
    if provided is not None:
        try:
            return date.fromisoformat(provided).isoformat(), "user_provided"
        except (TypeError, ValueError) as exc:
            raise ValueError("expected_close_date must use ISO format YYYY-MM-DD") from exc

    days, source = settings.days_for(industry)
    return (created_on + timedelta(days=days)).isoformat(), source


def assess_pipeline_timing(
    deal: dict,
    *,
    as_of: date,
    settings: PipelineTimingSettings,
) -> PipelineTimingAssessment:
    stage = str(deal.get("deal_stage") or "")
    days_in_stage = _days_in_current_stage(deal, as_of=as_of)

    if stage in ACTIVE_STAGES:
        threshold = settings.stuck_threshold_for(stage)
        if days_in_stage is None:
            stuck_status = StuckStatus.UNASSESSED
            is_stuck = None
        else:
            is_stuck = threshold > 0 and days_in_stage >= threshold
            stuck_status = StuckStatus.STUCK if is_stuck else StuckStatus.NOT_STUCK
    else:
        threshold = None
        stuck_status = StuckStatus.NOT_APPLICABLE
        is_stuck = False

    raw_close_date = deal.get("expected_close_date")
    if stage not in OPEN_STAGES:
        close_date_status = CloseDateStatus.NOT_APPLICABLE
        is_overdue = False
        overdue_days = None
    elif raw_close_date in (None, ""):
        close_date_status = CloseDateStatus.MISSING
        is_overdue = None
        overdue_days = None
    else:
        try:
            expected = date.fromisoformat(str(raw_close_date))
        except ValueError:
            close_date_status = CloseDateStatus.INVALID
            is_overdue = None
            overdue_days = None
        else:
            days_past = (as_of - expected).days
            is_overdue = days_past > settings.overdue_grace_days
            close_date_status = (
                CloseDateStatus.OVERDUE if is_overdue else CloseDateStatus.ON_TRACK
            )
            overdue_days = max(days_past, 0) if is_overdue else 0

    return PipelineTimingAssessment(
        days_in_stage=days_in_stage,
        stuck_threshold_days=threshold,
        stuck_status=stuck_status,
        is_stuck=is_stuck,
        close_date_status=close_date_status,
        is_overdue=is_overdue,
        overdue_days=overdue_days,
    )


def _days_in_current_stage(deal: dict, *, as_of: date) -> int | None:
    history = deal.get("stage_history")
    if not isinstance(history, list) or not history:
        return None
    last = history[-1]
    if not isinstance(last, dict) or last.get("stage") != deal.get("deal_stage"):
        return None
    try:
        entered_on = datetime.fromisoformat(str(last["entered_at"])).date()
    except (KeyError, TypeError, ValueError):
        return None
    days = (as_of - entered_on).days
    return days if days >= 0 else None


def build_attention_reasons(
    *,
    stage: str | None,
    health_band: HealthBand,
    timing: PipelineTimingAssessment,
) -> list[str]:
    reasons = []
    if stage in STALLED_STAGES:
        reasons.append("stalled")
    if timing.is_overdue:
        reasons.append("overdue")
    if timing.is_stuck:
        reasons.append("stuck")
    if health_band == HealthBand.AT_RISK:
        reasons.append("at_risk")
    return reasons


def summarize_win_rate(
    deals: Iterable[dict],
    *,
    settings: WinRateSettings,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    if start_date and end_date and start_date > end_date:
        raise ValueError("start_date must be on or before end_date")

    period_filtering = start_date is not None or end_date is not None
    terminal = [deal for deal in deals if deal.get("deal_stage") in TERMINAL_STAGES]
    included = []
    missing_close_date_count = 0
    invalid_close_date_count = 0
    for deal in terminal:
        if not period_filtering:
            included.append(deal)
            continue
        raw_close_date = deal.get("actual_close_date")
        if raw_close_date in (None, ""):
            missing_close_date_count += 1
            continue
        try:
            actual_close = date.fromisoformat(str(raw_close_date))
        except ValueError:
            invalid_close_date_count += 1
            continue
        if start_date and actual_close < start_date:
            continue
        if end_date and actual_close > end_date:
            continue
        included.append(deal)

    won_count = sum(deal.get("deal_stage") == "won" for deal in included)
    lost_count = sum(deal.get("deal_stage") == "lost" for deal in included)
    closed_count = won_count + lost_count
    warnings = []
    if closed_count < settings.minimum_closed_sample:
        warnings.append("insufficient_closed_sample")
    if missing_close_date_count:
        warnings.append("missing_actual_close_date")
    if invalid_close_date_count:
        warnings.append("invalid_actual_close_date")

    return {
        "win_rate_pct": (
            round(won_count / closed_count * 100, 1) if closed_count else None
        ),
        "won_count": won_count,
        "lost_count": lost_count,
        "closed_count": closed_count,
        "minimum_closed_sample": settings.minimum_closed_sample,
        "insufficient_sample": closed_count < settings.minimum_closed_sample,
        "missing_actual_close_date_count": missing_close_date_count,
        "invalid_actual_close_date_count": invalid_close_date_count,
        "warnings": warnings,
    }


def is_active_stage(stage: str | None) -> bool:
    return stage in ACTIVE_STAGES


def is_open_stage(stage: str | None) -> bool:
    return stage in OPEN_STAGES


def is_health_assessed(meddpicc_latest: dict | None) -> bool:
    snapshot = meddpicc_latest or {}
    filled_count = snapshot.get("filled_count")
    health_pct = snapshot.get("health_pct")
    return (
        isinstance(filled_count, int)
        and not isinstance(filled_count, bool)
        and filled_count >= 1
        and isinstance(health_pct, (int, float))
        and not isinstance(health_pct, bool)
        and math.isfinite(float(health_pct))
    )


def classify_health(
    meddpicc_latest: dict | None,
    thresholds: HealthBandThresholds,
) -> HealthBand:
    if not is_health_assessed(meddpicc_latest):
        return HealthBand.UNASSESSED

    health_pct = float((meddpicc_latest or {})["health_pct"])
    if health_pct >= thresholds.healthy_min:
        return HealthBand.HEALTHY
    if health_pct >= thresholds.watch_min:
        return HealthBand.WATCH
    return HealthBand.AT_RISK
