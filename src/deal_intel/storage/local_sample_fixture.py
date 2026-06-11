from __future__ import annotations

from copy import deepcopy
from typing import Any

ZERO_CONFIG_SAMPLE_DATASET = "zero_config_sample"
ZERO_CONFIG_SAMPLE_VERSION = "2026-06-10.v1"
ZERO_CONFIG_SAMPLE_AS_OF = "2026-06-10"
ZERO_CONFIG_SAMPLE_WINDOW_START = "2026-06-03"

SENSITIVE_FIELD_NAMES = frozenset({"raw_notes", "contacts", "summary_embedding"})
FIXTURE_SENSITIVE_FIELD_NAMES = SENSITIVE_FIELD_NAMES | {"raw_content"}


def load_zero_config_sample_deals() -> list[dict]:
    """Return safe bundled sample deals for MongoDB-free demos and smoke tests."""
    return deepcopy(_DEALS)


def load_zero_config_sample_snapshots() -> list[dict]:
    """Return bundled analytics snapshots that pair with the sample deals."""
    return deepcopy(_SNAPSHOTS)


def build_zero_config_sample_summary(
    *,
    deals: list[dict] | None = None,
    snapshots: list[dict] | None = None,
) -> dict:
    """Summarize fixture coverage without depending on BI modules."""
    source_deals = deals if deals is not None else _DEALS
    source_snapshots = snapshots if snapshots is not None else _SNAPSHOTS
    return {
        "dataset": ZERO_CONFIG_SAMPLE_DATASET,
        "version": ZERO_CONFIG_SAMPLE_VERSION,
        "as_of": ZERO_CONFIG_SAMPLE_AS_OF,
        "window_start": ZERO_CONFIG_SAMPLE_WINDOW_START,
        "deal_count": len(source_deals),
        "snapshot_count": len(source_snapshots),
        "stage_counts": _count_values(source_deals, "deal_stage"),
        "deal_size_status_counts": _count_values(source_deals, "deal_size_status"),
        "industry_counts": _count_values(source_deals, "industry"),
    }


def validate_zero_config_sample_fixture(
    *,
    deals: list[dict] | None = None,
    snapshots: list[dict] | None = None,
) -> dict:
    """Return fixture integrity errors for tests and future CLI diagnostics."""
    source_deals = deals if deals is not None else _DEALS
    source_snapshots = snapshots if snapshots is not None else _SNAPSHOTS
    errors = []

    sensitive_paths = sorted(_sensitive_paths(source_deals, prefix="deals"))
    sensitive_paths.extend(sorted(_sensitive_paths(source_snapshots, prefix="snapshots")))
    if sensitive_paths:
        errors.append(
            {
                "code": "sensitive_fields_present",
                "paths": sensitive_paths,
            }
        )

    deal_ids = [
        str(deal.get("deal_id") or "")
        for deal in source_deals
        if isinstance(deal, dict)
    ]
    if len(deal_ids) != len(set(deal_ids)):
        errors.append({"code": "duplicate_deal_ids"})
    if any(not deal_id for deal_id in deal_ids):
        errors.append({"code": "missing_deal_id"})

    snapshot_deal_ids = {
        str(snapshot.get("deal_id") or "")
        for snapshot in source_snapshots
        if isinstance(snapshot, dict)
    }
    unknown_snapshot_deal_ids = sorted(snapshot_deal_ids - set(deal_ids))
    if unknown_snapshot_deal_ids:
        errors.append(
            {
                "code": "snapshot_references_unknown_deal",
                "deal_ids": unknown_snapshot_deal_ids,
            }
        )

    return {
        "ok": not errors,
        "errors": errors,
        "summary": build_zero_config_sample_summary(
            deals=source_deals,
            snapshots=source_snapshots,
        ),
    }


def _deal(
    *,
    deal_id: str,
    company: str,
    industry: str,
    stage: str,
    amount: int | None,
    amount_status: str,
    amount_low: int | None,
    amount_high: int | None,
    expected_close_date: str | None,
    expected_close_date_source: str | None = "user_provided",
    actual_close_date: str | None = None,
    close_reason: str | None = None,
    health_pct: float | None,
    meddpicc_scores: dict[str, float],
    gaps: list[str],
    entered_at: str,
    meeting_date: str,
    pain_theme: tuple[str, str, int],
    decision_theme: tuple[str, str, int],
    metric_theme: tuple[str, str, int],
    extra_interactions: list[dict] | None = None,
) -> dict:
    meeting_id = f"{deal_id}-m1"
    meeting_subject = f"{company} customer meeting"
    themes = _themes(
        meeting_id=meeting_id,
        meeting_date=meeting_date,
        interaction_id=meeting_id,
        interaction_date=meeting_date,
        interaction_type="meeting",
        source_confidence="customer_stated",
        subject=meeting_subject,
        pain_theme=pain_theme,
        decision_theme=decision_theme,
        metric_theme=metric_theme,
    )
    meddpicc = _meeting_meddpicc(
        metric=metric_theme[1],
        pain=pain_theme[1],
        decision=decision_theme[1],
    )
    extra_interactions = extra_interactions or []
    extra_themes = [
        theme
        for interaction in extra_interactions
        for theme in interaction.get("customer_themes", [])
        if isinstance(theme, dict)
    ]
    all_themes = [*themes, *extra_themes]
    return {
        "deal_id": deal_id,
        "company": company,
        "industry": industry,
        "deal_size_amount": amount,
        "deal_size_low_amount": amount_low,
        "deal_size_high_amount": amount_high,
        "deal_size_currency": "KRW",
        "deal_size_status": amount_status,
        "deal_size_note": "Bundled fictional amount for zero-config demos.",
        "deal_value_history": [
            {
                "updated_at": "2026-06-10T00:00:00+00:00",
                "source": "zero_config_sample",
                "deal_size_amount": amount,
                "deal_size_currency": "KRW",
                "deal_size_status": amount_status,
                "deal_size_note": "Bundled fictional amount for zero-config demos.",
            }
        ],
        "meetings": [
            {
                "meeting_id": meeting_id,
                "date": meeting_date,
                "summary": (
                    f"{company} discussed {pain_theme[1]} and will evaluate "
                    f"{decision_theme[1]}."
                ),
                "meddpicc": meddpicc,
                "customer_themes": themes,
            }
        ],
        "interactions": [
            _interaction(
                interaction_id=meeting_id,
                date=meeting_date,
                interaction_type="meeting",
                direction="inbound",
                source_confidence="customer_stated",
                subject=meeting_subject,
                summary=(
                    f"{company} discussed {pain_theme[1]} and will evaluate "
                    f"{decision_theme[1]}."
                ),
                meddpicc=meddpicc,
                themes=themes,
                scoring_applied=True,
            ),
            *extra_interactions,
        ],
        "customer_themes": all_themes,
        "meddpicc_latest": _meddpicc_latest(
            health_pct=health_pct,
            scores=meddpicc_scores,
            gaps=gaps,
        ),
        "stage_history": [{"stage": stage, "entered_at": entered_at}],
        "deal_stage": stage,
        "expected_close_date": expected_close_date,
        "expected_close_date_source": (
            expected_close_date_source if expected_close_date is not None else None
        ),
        "actual_close_date": actual_close_date,
        "close_reason": close_reason,
        "bd_strategy": "",
        "gtm_notes": "Bundled fictional sample data for zero-config demos.",
        "prospect_id": None,
        "created_at": "2026-06-01T00:00:00+00:00",
        "updated_at": "2026-06-10T00:00:00+00:00",
        "is_sample": True,
        "sample_dataset": ZERO_CONFIG_SAMPLE_DATASET,
        "sample_dataset_version": ZERO_CONFIG_SAMPLE_VERSION,
    }


def _meddpicc_latest(
    *,
    health_pct: float | None,
    scores: dict[str, float],
    gaps: list[str],
) -> dict:
    if health_pct is None:
        return {"filled_count": 0, "gaps": gaps}
    weighted_score = round(float(health_pct) / 100 * 42.5, 2)
    return {
        **{
            dimension: {"score": score, "trend": "flat"}
            for dimension, score in scores.items()
        },
        "total_weighted_score": weighted_score,
        "health_pct": health_pct,
        "filled_count": len(scores),
        "gaps": gaps,
    }


def _meeting_meddpicc(*, metric: str, pain: str, decision: str) -> dict:
    return {
        "metrics": {"score": 4, "evidence": metric},
        "decision_criteria": {"score": 4, "evidence": decision},
        "identify_pain": {"score": 4, "evidence": pain},
    }


def _themes(
    *,
    meeting_id: str,
    meeting_date: str,
    interaction_id: str | None = None,
    interaction_date: str | None = None,
    interaction_type: str | None = None,
    source_confidence: str | None = None,
    subject: str | None = None,
    pain_theme: tuple[str, str, int],
    decision_theme: tuple[str, str, int],
    metric_theme: tuple[str, str, int],
) -> list[dict]:
    return [
        _theme(
            theme_key=pain_theme[0],
            label=_label(pain_theme[0]),
            dimension="identify_pain",
            evidence=pain_theme[1],
            importance=pain_theme[2],
            meeting_id=meeting_id,
            meeting_date=meeting_date,
            interaction_id=interaction_id,
            interaction_date=interaction_date,
            interaction_type=interaction_type,
            source_confidence=source_confidence,
            subject=subject,
        ),
        _theme(
            theme_key=decision_theme[0],
            label=_label(decision_theme[0]),
            dimension="decision_criteria",
            evidence=decision_theme[1],
            importance=decision_theme[2],
            meeting_id=meeting_id,
            meeting_date=meeting_date,
            interaction_id=interaction_id,
            interaction_date=interaction_date,
            interaction_type=interaction_type,
            source_confidence=source_confidence,
            subject=subject,
        ),
        _theme(
            theme_key=metric_theme[0],
            label=_label(metric_theme[0]),
            dimension="metrics",
            evidence=metric_theme[1],
            importance=metric_theme[2],
            meeting_id=meeting_id,
            meeting_date=meeting_date,
            interaction_id=interaction_id,
            interaction_date=interaction_date,
            interaction_type=interaction_type,
            source_confidence=source_confidence,
            subject=subject,
        ),
    ]


def _theme(
    *,
    theme_key: str,
    label: str,
    dimension: str,
    evidence: str,
    importance: int,
    meeting_id: str,
    meeting_date: str,
    interaction_id: str | None = None,
    interaction_date: str | None = None,
    interaction_type: str | None = None,
    source_confidence: str | None = None,
    subject: str | None = None,
) -> dict:
    theme = {
        "theme_key": theme_key,
        "label": label,
        "dimension": dimension,
        "evidence": evidence,
        "importance": importance,
        "meeting_id": meeting_id,
        "meeting_date": meeting_date,
    }
    if interaction_id:
        theme["interaction_id"] = interaction_id
    if interaction_date:
        theme["interaction_date"] = interaction_date
    if interaction_type:
        theme["interaction_type"] = interaction_type
    if source_confidence:
        theme["source_confidence"] = source_confidence
    if subject:
        theme["subject"] = subject
    return theme


def _interaction(
    *,
    interaction_id: str,
    date: str,
    interaction_type: str,
    direction: str,
    source_confidence: str,
    subject: str,
    summary: str,
    meddpicc: dict,
    themes: list[dict],
    scoring_applied: bool,
) -> dict:
    return {
        "interaction_id": interaction_id,
        "meeting_id": interaction_id if interaction_type == "meeting" else None,
        "date": date,
        "interaction_type": interaction_type,
        "direction": direction,
        "source_confidence": source_confidence,
        "participants": [],
        "subject": subject,
        "summary": summary,
        "meddpicc": meddpicc,
        "customer_themes": themes,
        "unconfirmed_meddpicc": {},
        "unconfirmed_customer_themes": [],
        "scoring_applied": scoring_applied,
        "custom_fields": {},
    }


def _source_interaction(
    *,
    deal_id: str,
    suffix: str,
    date: str,
    interaction_type: str,
    direction: str,
    source_confidence: str,
    subject: str,
    summary: str,
    theme_specs: list[tuple[str, str, str, int]],
) -> dict:
    interaction_id = f"{deal_id}-{suffix}"
    themes = [
        _theme(
            theme_key=theme_key,
            label=_label(theme_key),
            dimension=dimension,
            evidence=evidence,
            importance=importance,
            meeting_id=interaction_id,
            meeting_date=date,
            interaction_id=interaction_id,
            interaction_date=date,
            interaction_type=interaction_type,
            source_confidence=source_confidence,
            subject=subject,
        )
        for theme_key, dimension, evidence, importance in theme_specs
    ]
    return _interaction(
        interaction_id=interaction_id,
        date=date,
        interaction_type=interaction_type,
        direction=direction,
        source_confidence=source_confidence,
        subject=subject,
        summary=summary,
        meddpicc=_meddpicc_from_theme_specs(theme_specs),
        themes=themes,
        scoring_applied=source_confidence in {"customer_stated", "mixed"},
    )


def _meddpicc_from_theme_specs(
    theme_specs: list[tuple[str, str, str, int]],
) -> dict:
    meddpicc: dict[str, dict] = {}
    for _theme_key, dimension, evidence, importance in theme_specs:
        if dimension not in {"metrics", "decision_criteria", "identify_pain"}:
            continue
        meddpicc.setdefault(
            dimension,
            {
                "score": max(1, min(int(importance), 5)),
                "evidence": evidence,
            },
        )
    return meddpicc


def _label(theme_key: str) -> str:
    return {
        "adoption_change_management": "Adoption and change management",
        "compliance_security": "Compliance and security",
        "cost_reduction": "Cost reduction",
        "customization_flexibility": "Customization and flexibility",
        "data_quality_governance": "Data quality and governance",
        "integration_migration": "Integration and migration",
        "operational_efficiency": "Operational efficiency",
        "reporting_visibility": "Reporting and visibility",
        "scalability": "Scalability",
        "usability_accessibility": "Usability and accessibility",
    }.get(theme_key, theme_key)


_FULL_SCORES = {
    "metrics": 4,
    "economic_buyer": 4,
    "decision_criteria": 4,
    "decision_process": 4,
    "identify_pain": 4,
    "champion": 4,
    "competition": 4,
}


_DEALS = [
    _deal(
        deal_id="sample-northstar-ai",
        company="Northstar AI",
        industry="SaaS",
        stage="discovery",
        amount=None,
        amount_status="unknown",
        amount_low=None,
        amount_high=None,
        expected_close_date="2026-07-08",
        health_pct=None,
        meddpicc_scores={},
        gaps=[],
        entered_at="2026-06-08T00:00:00+00:00",
        meeting_date="2026-06-08",
        pain_theme=(
            "reporting_visibility",
            "weekly executive reporting is slow and hard to trust",
            4,
        ),
        decision_theme=(
            "integration_migration",
            "Slack, GitHub, and Jira integration quality",
            4,
        ),
        metric_theme=("operational_efficiency", "reduce report prep time by 60%", 3),
        extra_interactions=[
            _source_interaction(
                deal_id="sample-northstar-ai",
                suffix="u1",
                date="2026-06-09",
                interaction_type="user_interview",
                direction="inbound",
                source_confidence="customer_stated",
                subject="Ops lead user interview",
                summary=(
                    "Ops lead described weekly reporting prep as a recurring "
                    "manual burden and asked for source links in executive summaries."
                ),
                theme_specs=[
                    (
                        "reporting_visibility",
                        "identify_pain",
                        "weekly reporting takes most of Monday morning and lacks source links",
                        5,
                    ),
                    (
                        "operational_efficiency",
                        "metrics",
                        "save three to four hours per reporting cycle",
                        4,
                    ),
                ],
            )
        ],
    ),
    _deal(
        deal_id="sample-pavebridge",
        company="페이브릿지",
        industry="Fintech",
        stage="negotiation",
        amount=92_000_000,
        amount_status="quoted",
        amount_low=None,
        amount_high=None,
        expected_close_date="2026-06-14",
        health_pct=88.5,
        meddpicc_scores=_FULL_SCORES,
        gaps=[],
        entered_at="2026-05-20T00:00:00+00:00",
        meeting_date="2026-06-06",
        pain_theme=(
            "compliance_security",
            "audit evidence gathering still depends on manual screenshots",
            5,
        ),
        decision_theme=("compliance_security", "audit log export and SSO policy fit", 5),
        metric_theme=(
            "operational_efficiency",
            "cut audit package preparation from five days to one day",
            4,
        ),
    ),
    _deal(
        deal_id="sample-shopnext",
        company="ShopNext",
        industry="Retail",
        stage="proposal",
        amount=156_000_000,
        amount_status="quoted",
        amount_low=None,
        amount_high=None,
        expected_close_date="2026-06-30",
        health_pct=86.1,
        meddpicc_scores={
            key: value for key, value in _FULL_SCORES.items() if key != "economic_buyer"
        },
        gaps=["economic_buyer"],
        entered_at="2026-05-25T00:00:00+00:00",
        meeting_date="2026-06-05",
        pain_theme=(
            "operational_efficiency",
            "handoff between logistics and sales still happens in spreadsheets",
            5,
        ),
        decision_theme=("adoption_change_management", "frontline team adoption rate", 4),
        metric_theme=("cost_reduction", "replace 12 spreadsheet workflows", 4),
    ),
    _deal(
        deal_id="sample-greenlogistics",
        company="GreenLogistics",
        industry="Logistics",
        stage="negotiation",
        amount=210_000_000,
        amount_status="customer_budget",
        amount_low=180_000_000,
        amount_high=230_000_000,
        expected_close_date="2026-06-20",
        health_pct=78.0,
        meddpicc_scores={
            key: value for key, value in _FULL_SCORES.items() if key != "competition"
        },
        gaps=["competition"],
        entered_at="2026-05-22T00:00:00+00:00",
        meeting_date="2026-06-04",
        pain_theme=(
            "data_quality_governance",
            "delivery SLA reporting is fragmented across regions",
            4,
        ),
        decision_theme=("scalability", "regional rollout without custom services", 4),
        metric_theme=("reporting_visibility", "weekly SLA report by region", 4),
        extra_interactions=[
            _source_interaction(
                deal_id="sample-greenlogistics",
                suffix="e1",
                date="2026-06-07",
                interaction_type="email_thread",
                direction="inbound",
                source_confidence="customer_stated",
                subject="Re: Regional SLA dashboard rollout",
                summary=(
                    "Operations director confirmed that regional SLA dashboards "
                    "must reconcile warehouse and carrier data before rollout."
                ),
                theme_specs=[
                    (
                        "data_quality_governance",
                        "identify_pain",
                        "warehouse and carrier SLA data disagree by region",
                        5,
                    ),
                    (
                        "reporting_visibility",
                        "metrics",
                        "regional SLA report must refresh every Friday",
                        4,
                    ),
                    (
                        "scalability",
                        "decision_criteria",
                        "rollout must cover five regions without custom services",
                        4,
                    ),
                ],
            )
        ],
    ),
    _deal(
        deal_id="sample-civicgov",
        company="CivicGov Reference",
        industry="Public Sector",
        stage="proposal",
        amount=0,
        amount_status="strategic_zero",
        amount_low=0,
        amount_high=0,
        expected_close_date="2026-07-15",
        expected_close_date_source="config_industry",
        health_pct=72.0,
        meddpicc_scores={
            key: value for key, value in _FULL_SCORES.items() if key != "champion"
        },
        gaps=["champion"],
        entered_at="2026-06-01T00:00:00+00:00",
        meeting_date="2026-06-03",
        pain_theme=(
            "compliance_security",
            "reference program needs clear public-sector security evidence",
            4,
        ),
        decision_theme=("vendor_support", "implementation support responsiveness", 4),
        metric_theme=("reporting_visibility", "publish a reference case in Q3", 3),
    ),
    _deal(
        deal_id="sample-edulink",
        company="EduLink Korea",
        industry="Education",
        stage="stalled",
        amount=58_000_000,
        amount_status="rough_estimate",
        amount_low=40_000_000,
        amount_high=80_000_000,
        expected_close_date="2026-09-30",
        health_pct=62.9,
        meddpicc_scores={
            "metrics": 3,
            "decision_criteria": 3,
            "identify_pain": 4,
            "competition": 2,
        },
        gaps=["economic_buyer", "champion", "decision_process"],
        entered_at="2026-05-10T00:00:00+00:00",
        meeting_date="2026-05-28",
        pain_theme=(
            "operational_efficiency",
            "content approval cycles are slow across departments",
            3,
        ),
        decision_theme=("timeline_procurement", "board review timing is unclear", 4),
        metric_theme=("cost_reduction", "avoid two external reporting contractors", 3),
    ),
    _deal(
        deal_id="sample-hyundai-precision",
        company="Hyundai Precision",
        industry="Manufacturing",
        stage="qualification",
        amount=48_000_000,
        amount_status="quoted",
        amount_low=None,
        amount_high=None,
        expected_close_date="2026-08-31",
        health_pct=74.0,
        meddpicc_scores={
            key: value
            for key, value in _FULL_SCORES.items()
            if key not in {"economic_buyer", "competition"}
        },
        gaps=["economic_buyer", "competition"],
        entered_at="2026-06-04T00:00:00+00:00",
        meeting_date="2026-06-07",
        pain_theme=(
            "data_quality_governance",
            "factory knowledge base ownership is unclear",
            4,
        ),
        decision_theme=("integration_migration", "migration from Confluence and SharePoint", 4),
        metric_theme=("operational_efficiency", "reduce operator support tickets by 20%", 3),
    ),
    _deal(
        deal_id="sample-orion-insurance",
        company="Orion Insurance",
        industry="Insurance",
        stage="negotiation",
        amount=62_000_000,
        amount_status="quoted",
        amount_low=None,
        amount_high=None,
        expected_close_date="2026-06-05",
        health_pct=38.0,
        meddpicc_scores={
            "metrics": 2,
            "economic_buyer": 2,
            "decision_criteria": 4,
            "decision_process": 3,
            "identify_pain": 4,
            "champion": 1,
            "competition": 2,
        },
        gaps=[],
        entered_at="2026-05-15T00:00:00+00:00",
        meeting_date="2026-06-02",
        pain_theme=(
            "compliance_security",
            "risk team rejected prior tools after audit concerns",
            5,
        ),
        decision_theme=("compliance_security", "security exception path must be documented", 5),
        metric_theme=("cost_reduction", "avoid duplicate compliance tooling", 3),
    ),
    _deal(
        deal_id="sample-clear-skin",
        company="ClearSkin Lab",
        industry="Healthcare",
        stage="won",
        amount=1_890_000,
        amount_status="quoted",
        amount_low=None,
        amount_high=None,
        expected_close_date=None,
        actual_close_date="2026-06-02",
        health_pct=93.0,
        meddpicc_scores=_FULL_SCORES,
        gaps=[],
        entered_at="2026-06-02T00:00:00+00:00",
        meeting_date="2026-06-02",
        pain_theme=("usability_accessibility", "clinic staff needed faster onboarding", 4),
        decision_theme=("usability_accessibility", "simple setup and Korean support", 4),
        metric_theme=("operational_efficiency", "launch first team in one day", 4),
    ),
    _deal(
        deal_id="sample-medihub",
        company="MediHub Group",
        industry="Healthcare",
        stage="won",
        amount=110_500_000,
        amount_status="quoted",
        amount_low=None,
        amount_high=None,
        expected_close_date=None,
        actual_close_date="2026-06-06",
        health_pct=91.0,
        meddpicc_scores=_FULL_SCORES,
        gaps=[],
        entered_at="2026-06-06T00:00:00+00:00",
        meeting_date="2026-06-06",
        pain_theme=("data_quality_governance", "clinical policy documents drift by team", 5),
        decision_theme=("compliance_security", "HIPAA-style audit evidence and SSO", 5),
        metric_theme=("reporting_visibility", "monthly compliance package in under one hour", 4),
    ),
    _deal(
        deal_id="sample-arcana-games",
        company="Arcana Games",
        industry="Gaming",
        stage="won",
        amount=18_000_000,
        amount_status="quoted",
        amount_low=None,
        amount_high=None,
        expected_close_date=None,
        actual_close_date="2026-06-07",
        health_pct=98.2,
        meddpicc_scores=_FULL_SCORES,
        gaps=[],
        entered_at="2026-06-07T00:00:00+00:00",
        meeting_date="2026-06-07",
        pain_theme=("operational_efficiency", "live-ops incident notes were scattered", 4),
        decision_theme=("integration_migration", "Discord and Jira workflow fit", 4),
        metric_theme=("operational_efficiency", "incident review in 30 minutes", 4),
    ),
    _deal(
        deal_id="sample-hanul-energy",
        company="Hanul Energy",
        industry="Energy",
        stage="lost",
        amount=95_000_000,
        amount_status="rough_estimate",
        amount_low=70_000_000,
        amount_high=120_000_000,
        expected_close_date=None,
        actual_close_date="2026-06-04",
        close_reason="Customer policy did not allow cloud SaaS for this workload.",
        health_pct=61.0,
        meddpicc_scores={
            "metrics": 3,
            "economic_buyer": 3,
            "decision_criteria": 3,
            "identify_pain": 4,
            "competition": 2,
        },
        gaps=["champion", "decision_process"],
        entered_at="2026-06-04T00:00:00+00:00",
        meeting_date="2026-06-04",
        pain_theme=("compliance_security", "cloud policy blocked the deployment model", 5),
        decision_theme=("compliance_security", "private deployment was required", 5),
        metric_theme=("cost_reduction", "avoid custom on-premise support cost", 3),
    ),
]


def _snapshot(
    *,
    deal_id: str,
    company: str,
    industry: str,
    as_of: str,
    stage: str,
    amount: int | None,
    amount_status: str,
    health_pct: float | None,
    attention_reasons: list[str],
) -> dict:
    return {
        "event_id": f"sample-snapshot:{deal_id}:{as_of}",
        "event_type": "sample_snapshot",
        "occurred_at": f"{as_of}T00:00:00+00:00",
        "created_at": f"{as_of}T00:00:00+00:00",
        "as_of": as_of,
        "timezone": "Asia/Seoul",
        "deal_id": deal_id,
        "company": company,
        "industry": industry,
        "deal_stage": stage,
        "deal_size_amount": amount,
        "deal_size_currency": "KRW",
        "deal_size_status": amount_status,
        "health_pct": health_pct,
        "attention_reasons": attention_reasons,
        "sample_dataset": ZERO_CONFIG_SAMPLE_DATASET,
        "sample_dataset_version": ZERO_CONFIG_SAMPLE_VERSION,
    }


_SNAPSHOT_START_STAGES = {
    "sample-pavebridge": "proposal",
    "sample-shopnext": "qualification",
    "sample-greenlogistics": "proposal",
    "sample-edulink": "qualification",
    "sample-hyundai-precision": "discovery",
    "sample-orion-insurance": "proposal",
    "sample-clear-skin": "proposal",
    "sample-medihub": "negotiation",
    "sample-arcana-games": "proposal",
    "sample-hanul-energy": "negotiation",
}


def _build_snapshots() -> list[dict]:
    snapshots = []
    for deal in _DEALS:
        deal_id = str(deal["deal_id"])
        start_stage = _SNAPSHOT_START_STAGES.get(deal_id, str(deal["deal_stage"]))
        amount = deal.get("deal_size_amount")
        start_amount = (
            None
            if amount is None
            else int(round(int(amount) * 0.85))
            if int(amount) > 0
            else 0
        )
        start_health = (deal.get("meddpicc_latest") or {}).get("health_pct")
        if isinstance(start_health, (int, float)):
            start_health = max(0.0, round(float(start_health) - 5.0, 1))
        snapshots.append(
            _snapshot(
                deal_id=deal_id,
                company=str(deal["company"]),
                industry=str(deal["industry"]),
                as_of=ZERO_CONFIG_SAMPLE_WINDOW_START,
                stage=start_stage,
                amount=start_amount,
                amount_status=str(deal["deal_size_status"]),
                health_pct=start_health,
                attention_reasons=[],
            )
        )
        current_health = (deal.get("meddpicc_latest") or {}).get("health_pct")
        snapshots.append(
            _snapshot(
                deal_id=deal_id,
                company=str(deal["company"]),
                industry=str(deal["industry"]),
                as_of=ZERO_CONFIG_SAMPLE_AS_OF,
                stage=str(deal["deal_stage"]),
                amount=amount if isinstance(amount, int) else None,
                amount_status=str(deal["deal_size_status"]),
                health_pct=(
                    float(current_health)
                    if isinstance(current_health, (int, float))
                    else None
                ),
                attention_reasons=_sample_attention_reasons(deal),
            )
        )
    return snapshots


def _sample_attention_reasons(deal: dict) -> list[str]:
    if deal["deal_stage"] == "stalled":
        return ["stalled"]
    if deal["deal_id"] == "sample-orion-insurance":
        return ["overdue", "stuck", "at_risk"]
    return []


def _count_values(rows: list[dict], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(field) or "null")
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _sensitive_paths(value: Any, *, prefix: str) -> list[str]:
    paths = []
    if isinstance(value, dict):
        for key, item in value.items():
            path = f"{prefix}.{key}"
            if key in FIXTURE_SENSITIVE_FIELD_NAMES:
                paths.append(path)
            paths.extend(_sensitive_paths(item, prefix=path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            paths.extend(_sensitive_paths(item, prefix=f"{prefix}[{index}]"))
    return paths


_SNAPSHOTS = _build_snapshots()
