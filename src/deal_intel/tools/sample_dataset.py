from __future__ import annotations

from copy import deepcopy

DATASET_WEEKLY_PIPELINE = "weekly_pipeline_demo"
DATASET_VERSION = "2026-06-09.v1"
SAMPLE_BATCH_ID = f"{DATASET_WEEKLY_PIPELINE}:{DATASET_VERSION}"
SUPPORTED_DATASETS = frozenset({DATASET_WEEKLY_PIPELINE})

_BASE_CREATED_AT = "2026-06-09T00:00:00+00:00"


def build_sample_deals(*, loaded_at: str) -> list[dict]:
    deals = [_build_deal(index=index, loaded_at=loaded_at, **row) for index, row in enumerate(
        _SAMPLE_ROWS,
        start=1,
    )]
    return deepcopy(deals)


def sample_preview(deals: list[dict], *, limit: int = 3) -> list[dict]:
    return [
        {
            "deal_id": deal["deal_id"],
            "company": deal["company"],
            "deal_stage": deal["deal_stage"],
            "industry": deal["industry"],
            "deal_size_krw": deal["deal_size_krw"],
            "health_pct": deal["meddpicc_latest"].get("health_pct"),
        }
        for deal in deals[:limit]
    ]


def _build_deal(
    *,
    index: int,
    loaded_at: str,
    company: str,
    industry: str,
    stage: str,
    amount: int | None,
    amount_status: str,
    expected_close_date: str | None,
    actual_close_date: str | None,
    close_reason: str | None,
    health_pct: float,
    filled_count: int,
    gaps: list[str],
    entered_at: str,
    pain: str,
    decision: str,
    metric: str,
) -> dict:
    deal_id = f"sample-{DATASET_WEEKLY_PIPELINE}-{index:02d}"
    meddpicc_latest = _meddpicc_latest(
        health_pct=health_pct,
        filled_count=filled_count,
        gaps=gaps,
    )
    return {
        "deal_id": deal_id,
        "company": company,
        "industry": industry,
        "deal_size_krw": amount,
        "deal_size_low_krw": None,
        "deal_size_high_krw": None,
        "deal_size_status": amount_status,
        "deal_size_note": "Fictional demo amount for onboarding.",
        "deal_value_history": [
            {
                "updated_at": _BASE_CREATED_AT,
                "source": "sample_data",
                "deal_size_krw": amount,
                "deal_size_status": amount_status,
                "deal_size_note": "Fictional demo amount for onboarding.",
            }
        ],
        "contacts": [],
        "meetings": [
            {
                "meeting_id": f"{deal_id}-meeting-01",
                "date": "2026-06-03",
                "raw_notes": (
                    f"Fictional onboarding note. Pain: {pain}. "
                    f"Decision criteria: {decision}. Metric: {metric}."
                ),
                "summary": (
                    f"{company} is evaluating the platform for {pain.lower()} "
                    f"with decision criteria around {decision.lower()}."
                ),
                "meddpicc": _meeting_meddpicc(
                    pain=pain,
                    decision=decision,
                    metric=metric,
                ),
                "customer_themes": _customer_themes(
                    deal_id=deal_id,
                    pain=pain,
                    decision=decision,
                    metric=metric,
                ),
            }
        ],
        "customer_themes": _customer_themes(
            deal_id=deal_id,
            pain=pain,
            decision=decision,
            metric=metric,
        ),
        "meddpicc_latest": meddpicc_latest,
        "stage_history": [{"stage": stage, "entered_at": entered_at}],
        "deal_stage": stage,
        "expected_close_date": expected_close_date,
        "expected_close_date_source": (
            "user_provided" if expected_close_date is not None else None
        ),
        "actual_close_date": actual_close_date,
        "close_reason": close_reason,
        "bd_strategy": "",
        "gtm_notes": "Fictional sample data for onboarding demos.",
        "prospect_id": None,
        "created_at": _BASE_CREATED_AT,
        "updated_at": loaded_at,
        "is_sample": True,
        "sample_batch_id": SAMPLE_BATCH_ID,
        "sample_dataset": DATASET_WEEKLY_PIPELINE,
        "sample_dataset_version": DATASET_VERSION,
        "sample_label": "Weekly Pipeline Review demo",
        "sample_loaded_at": loaded_at,
    }


def _meddpicc_latest(
    *,
    health_pct: float,
    filled_count: int,
    gaps: list[str],
) -> dict:
    dimensions = {
        "metrics": 4,
        "economic_buyer": 3,
        "decision_criteria": 4,
        "decision_process": 3,
        "identify_pain": 4,
        "champion": 3,
        "competition": 2,
    }
    for gap in gaps:
        dimensions[gap] = 0
    return {
        **{
            dimension: {"score": score, "trend": "flat"}
            for dimension, score in dimensions.items()
            if score > 0
        },
        "total_weighted_score": round(health_pct / 100 * 42.5, 2),
        "health_pct": health_pct,
        "filled_count": filled_count,
        "gaps": gaps,
    }


def _meeting_meddpicc(*, pain: str, decision: str, metric: str) -> dict:
    return {
        "metrics": {"score": 4, "evidence": metric},
        "decision_criteria": {"score": 4, "evidence": decision},
        "identify_pain": {"score": 4, "evidence": pain},
        "champion": {"score": 3, "evidence": "Business owner is engaged."},
    }


def _customer_themes(
    *,
    deal_id: str,
    pain: str,
    decision: str,
    metric: str,
) -> list[dict]:
    return [
        {
            "theme_key": "operational_efficiency",
            "label": "Operational efficiency",
            "dimension": "identify_pain",
            "evidence": pain,
            "importance": 4,
            "meeting_id": f"{deal_id}-meeting-01",
            "meeting_date": "2026-06-03",
        },
        {
            "theme_key": "integration_migration",
            "label": "Integration and migration",
            "dimension": "decision_criteria",
            "evidence": decision,
            "importance": 4,
            "meeting_id": f"{deal_id}-meeting-01",
            "meeting_date": "2026-06-03",
        },
        {
            "theme_key": "cost_reduction",
            "label": "Cost reduction",
            "dimension": "metrics",
            "evidence": metric,
            "importance": 3,
            "meeting_id": f"{deal_id}-meeting-01",
            "meeting_date": "2026-06-03",
        },
    ]


_SAMPLE_ROWS = [
    {
        "company": "Northstar AI",
        "industry": "SaaS",
        "stage": "discovery",
        "amount": 26_000_000,
        "amount_status": "rough_estimate",
        "expected_close_date": "2026-06-23",
        "actual_close_date": None,
        "close_reason": None,
        "health_pct": 82.0,
        "filled_count": 5,
        "gaps": ["economic_buyer", "competition"],
        "entered_at": "2026-06-01T00:00:00+00:00",
        "pain": "manual weekly reporting is slow",
        "decision": "Slack, GitHub, and Jira integration quality",
        "metric": "reduce reporting time by 60 percent",
    },
    {
        "company": "PaveBridge",
        "industry": "Finance",
        "stage": "negotiation",
        "amount": 92_000_000,
        "amount_status": "quoted",
        "expected_close_date": "2026-06-14",
        "actual_close_date": None,
        "close_reason": None,
        "health_pct": 88.5,
        "filled_count": 7,
        "gaps": [],
        "entered_at": "2026-05-20T00:00:00+00:00",
        "pain": "audit preparation requires too much manual evidence gathering",
        "decision": "audit log export and SSO policy fit",
        "metric": "cut audit package preparation from five days to one day",
    },
    {
        "company": "ShopNext",
        "industry": "Commerce",
        "stage": "proposal",
        "amount": 156_000_000,
        "amount_status": "quoted",
        "expected_close_date": "2026-06-30",
        "actual_close_date": None,
        "close_reason": None,
        "health_pct": 86.1,
        "filled_count": 6,
        "gaps": ["economic_buyer"],
        "entered_at": "2026-05-25T00:00:00+00:00",
        "pain": "Excel handoff between logistics and sales creates errors",
        "decision": "Excel replacement and mobile adoption",
        "metric": "raise weekly active adoption above 70 percent",
    },
    {
        "company": "Hanul Energy",
        "industry": "Energy",
        "stage": "lost",
        "amount": 95_000_000,
        "amount_status": "rough_estimate",
        "expected_close_date": None,
        "actual_close_date": "2026-06-04",
        "close_reason": "cloud SaaS policy conflict",
        "health_pct": 61.0,
        "filled_count": 5,
        "gaps": ["champion", "decision_process"],
        "entered_at": "2026-05-10T00:00:00+00:00",
        "pain": "distributed field teams lack a shared knowledge base",
        "decision": "on-premise policy exception and security review",
        "metric": "reduce repeated support escalations by 30 percent",
    },
    {
        "company": "Arcana Games",
        "industry": "Gaming",
        "stage": "won",
        "amount": 18_000_000,
        "amount_status": "quoted",
        "expected_close_date": None,
        "actual_close_date": "2026-06-07",
        "close_reason": None,
        "health_pct": 98.2,
        "filled_count": 7,
        "gaps": [],
        "entered_at": "2026-05-31T00:00:00+00:00",
        "pain": "launch checklist ownership is scattered across tools",
        "decision": "fast onboarding and low admin burden",
        "metric": "ship localization tasks two days faster",
    },
    {
        "company": "MediHub Group",
        "industry": "Healthcare",
        "stage": "won",
        "amount": 110_500_000,
        "amount_status": "quoted",
        "expected_close_date": None,
        "actual_close_date": "2026-06-06",
        "close_reason": None,
        "health_pct": 91.0,
        "filled_count": 7,
        "gaps": [],
        "entered_at": "2026-05-18T00:00:00+00:00",
        "pain": "clinical policy updates are hard to distribute reliably",
        "decision": "permission model and audit history",
        "metric": "reduce policy acknowledgement lag by 50 percent",
    },
    {
        "company": "GreenLogistics",
        "industry": "Logistics",
        "stage": "negotiation",
        "amount": 210_000_000,
        "amount_status": "customer_budget",
        "expected_close_date": "2026-06-20",
        "actual_close_date": None,
        "close_reason": None,
        "health_pct": 78.0,
        "filled_count": 6,
        "gaps": ["competition"],
        "entered_at": "2026-05-15T00:00:00+00:00",
        "pain": "warehouse SOP changes do not reach night-shift teams",
        "decision": "migration from Confluence and offline cache behavior",
        "metric": "reduce SOP lookup time from ten minutes to two minutes",
    },
    {
        "company": "ClearSkin Lab",
        "industry": "Consumer",
        "stage": "won",
        "amount": 1_890_000,
        "amount_status": "quoted",
        "expected_close_date": None,
        "actual_close_date": "2026-06-02",
        "close_reason": None,
        "health_pct": 93.0,
        "filled_count": 6,
        "gaps": [],
        "entered_at": "2026-05-28T00:00:00+00:00",
        "pain": "campaign learnings disappear after each launch",
        "decision": "easy template reuse and low setup time",
        "metric": "save three hours per campaign retro",
    },
    {
        "company": "EduContent Korea",
        "industry": "Education",
        "stage": "stalled",
        "amount": 58_000_000,
        "amount_status": "rough_estimate",
        "expected_close_date": "2026-09-30",
        "actual_close_date": None,
        "close_reason": None,
        "health_pct": 62.9,
        "filled_count": 4,
        "gaps": ["economic_buyer", "champion", "decision_process"],
        "entered_at": "2026-05-01T00:00:00+00:00",
        "pain": "content approvals take too long across departments",
        "decision": "budget owner confirmation and procurement path",
        "metric": "cut approval cycle from three weeks to one week",
    },
    {
        "company": "Hyundai Precision Demo",
        "industry": "Manufacturing",
        "stage": "qualification",
        "amount": 48_000_000,
        "amount_status": "quoted",
        "expected_close_date": "2026-08-31",
        "actual_close_date": None,
        "close_reason": None,
        "health_pct": 74.0,
        "filled_count": 5,
        "gaps": ["economic_buyer", "competition"],
        "entered_at": "2026-05-09T00:00:00+00:00",
        "pain": "quality issue knowledge is trapped in local spreadsheets",
        "decision": "API import from ERP and shop-floor accessibility",
        "metric": "reduce recurring defect investigation time by 25 percent",
    },
]
