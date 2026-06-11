from __future__ import annotations

import csv
import json
from datetime import UTC, date, datetime

import pytest

from deal_intel.reports.csv_export import save_report_csv
from deal_intel.reports.markdown_summary import build_weekly_pipeline_markdown
from deal_intel.reports.weekly_pipeline import build_weekly_pipeline_rows

AS_OF = date(2026, 6, 10)
GENERATED_AT = datetime(2026, 6, 10, 1, 2, 3, tzinfo=UTC)


def _deal(
    deal_id: str,
    *,
    company: str,
    stage: str = "proposal",
    amount: int | None = 10_000_000,
    currency: str = "KRW",
    amount_status: str | None = "quoted",
    health_pct: float | None = 80,
    entered_at: str = "2026-06-01T00:00:00+00:00",
    expected_close_date: str | None = "2026-06-30",
    meetings: list[dict] | None = None,
    customer_themes: list[dict] | None = None,
    meddpicc_gaps: list[str] | None = None,
) -> dict:
    return {
        "deal_id": deal_id,
        "company": company,
        "industry": "IT",
        "deal_stage": stage,
        "deal_size_amount": amount,
        "deal_size_currency": currency,
        "deal_size_status": amount_status,
        "stage_history": [{"stage": stage, "entered_at": entered_at}],
        "expected_close_date": expected_close_date,
        "expected_close_date_source": "user_provided",
        "meetings": (
            meetings
            if meetings is not None
            else [{"meeting_id": f"m-{deal_id}", "date": "2026-06-01"}]
        ),
        "customer_themes": customer_themes if customer_themes is not None else _themes(),
        "meddpicc_latest": (
            {
                "filled_count": 1,
                "health_pct": health_pct,
                "gaps": meddpicc_gaps if meddpicc_gaps is not None else ["economic_buyer"],
            }
            if health_pct is not None
            else {}
        ),
    }


def _themes() -> list[dict]:
    return [
        {
            "theme_key": "operational_efficiency",
            "label": "Operational efficiency",
            "dimension": "identify_pain",
            "evidence": "manual report takes too long",
            "importance": 4,
            "meeting_id": "m-theme",
            "meeting_date": "2026-06-01",
            "interaction_id": "i-email-theme",
            "interaction_date": "2026-06-01",
            "interaction_type": "email_thread",
            "source_confidence": "customer_stated",
            "subject": "Re: reporting workflow",
        },
        {
            "theme_key": "integration_migration",
            "label": "Integration and migration",
            "dimension": "decision_criteria",
            "evidence": "GitHub and Jira integration required",
            "importance": 5,
            "meeting_id": "m-theme",
            "meeting_date": "2026-06-01",
            "interaction_id": "i-interview-theme",
            "interaction_date": "2026-06-01",
            "interaction_type": "user_interview",
            "source_confidence": "customer_stated",
            "subject": "Ops lead interview",
        },
    ]


def test_weekly_pipeline_markdown_summarizes_kpis_and_matches_csv(tmp_path) -> None:
    report = build_weekly_pipeline_rows(
        [
            _deal(
                "overdue",
                company="PayBridge",
                amount=72_000_000,
                health_pct=85,
                expected_close_date="2026-06-01",
            ),
            _deal(
                "stuck-risk",
                company="LuminoAI",
                amount=26_000_000,
                amount_status="rough_estimate",
                health_pct=35,
                entered_at="2026-05-01T00:00:00+00:00",
            ),
            _deal(
                "missing",
                company="MissingCo",
                amount=None,
                amount_status="unknown",
                health_pct=None,
                expected_close_date=None,
                meetings=[],
                customer_themes=[],
            ),
            _deal(
                "strategic-zero",
                company="ReferenceCo",
                stage="stalled",
                amount=0,
                amount_status="strategic_zero",
                health_pct=75,
            ),
        ],
        as_of=AS_OF,
    )

    csv_result = save_report_csv(
        report,
        output_dir=tmp_path,
        generated_at=GENERATED_AT,
    )
    markdown_result = build_weekly_pipeline_markdown(
        report,
        generated_at=GENERATED_AT,
    )

    csv_metrics = _csv_metrics(csv_result["path"])
    metrics = markdown_result["metrics"]
    assert metrics["open_deal_count"] == csv_metrics["open_deal_count"] == 4
    assert metrics["pipeline_value_amount"] == csv_metrics["pipeline_value_amount"]
    assert metrics["pipeline_value_amount"] == 98_000_000
    assert metrics["pipeline_value_currency"] == "KRW"
    assert metrics["mixed_pipeline_value_currency"] is False
    assert metrics["attention_deal_count"] == csv_metrics["attention_deal_count"]
    assert metrics["attention_deal_count"] == 3
    assert metrics["avg_health_pct"] == 65.0
    assert metrics["health_coverage_pct"] == 75.0
    assert metrics["incomplete_data_quality_count"] == 1

    markdown = markdown_result["markdown"]
    assert "| Open deals | 4 |" in markdown
    assert "| Pipeline value | 98,000,000 KRW |" in markdown
    assert "| Attention deals | 3 |" in markdown
    assert "| Average health | 65.0% |" in markdown
    assert "| Health coverage | 3/4 (75.0%) |" in markdown
    assert "PayBridge" in markdown
    assert "LuminoAI" in markdown
    assert "`missing_expected_close_date`" in markdown
    assert "## Objective Action Items" in markdown
    assert "## Gap Observations" in markdown
    assert "## Customer Evidence" in markdown
    assert "Email thread (customer-stated)" in markdown
    assert "User interview (customer-stated)" in markdown


def test_weekly_pipeline_markdown_breaks_down_mixed_currencies() -> None:
    report = build_weekly_pipeline_rows(
        [
            _deal("krw", company="Korea Co", amount=100, currency="KRW"),
            _deal("usd", company="US Co", amount=20, currency="USD"),
        ],
        as_of=AS_OF,
    )

    result = build_weekly_pipeline_markdown(report, generated_at=GENERATED_AT)

    assert result["metrics"]["pipeline_value_amount"] is None
    assert result["metrics"]["pipeline_value_currency"] is None
    assert result["metrics"]["pipeline_value_currencies"] == ["KRW", "USD"]
    assert result["metrics"]["mixed_pipeline_value_currency"] is True
    assert result["metrics"]["pipeline_value_by_currency"] == {"KRW": 100, "USD": 20}
    assert "| Pipeline value | 100 KRW, 20 USD |" in result["markdown"]


def test_weekly_pipeline_markdown_handles_empty_report() -> None:
    report = build_weekly_pipeline_rows([], as_of=AS_OF)

    result = build_weekly_pipeline_markdown(report, generated_at=GENERATED_AT)

    assert result["metrics"]["open_deal_count"] == 0
    assert result["metrics"]["pipeline_value_amount"] == 0
    assert result["metrics"]["avg_health_pct"] is None
    assert "| Open deals | 0 |" in result["markdown"]
    assert "| Average health | N/A |" in result["markdown"]
    assert "No risk deals." in result["markdown"]
    assert "`no_open_deals`" in result["markdown"]


def test_weekly_pipeline_markdown_escapes_table_cells() -> None:
    report = build_weekly_pipeline_rows(
        [
            _deal(
                "escape",
                company="Pipe | Newline\nCo",
                stage="stalled",
                amount=1,
                amount_status="quoted",
            )
        ],
        as_of=AS_OF,
    )

    markdown = build_weekly_pipeline_markdown(
        report,
        generated_at=GENERATED_AT,
    )["markdown"]

    assert "Pipe \\| Newline Co" in markdown


def test_weekly_pipeline_markdown_keeps_judgment_gaps_out_of_ctas() -> None:
    report = build_weekly_pipeline_rows(
        [
            _deal(
                "competition",
                company="GreenLogistics",
                stage="negotiation",
                health_pct=82,
                expected_close_date="2026-06-01",
                meddpicc_gaps=["competition"],
            )
        ],
        as_of=AS_OF,
    )

    markdown = build_weekly_pipeline_markdown(
        report,
        generated_at=GENERATED_AT,
    )["markdown"]

    assert "| GreenLogistics | Overdue close date | review_close_plan |" in markdown
    assert "| GreenLogistics | Competition | needs_human_judgment |" in markdown
    assert "ask_in_next_meeting" not in markdown


def test_weekly_pipeline_markdown_validates_input_contract() -> None:
    with pytest.raises(ValueError, match="weekly_pipeline"):
        build_weekly_pipeline_markdown({"report_type": "other"})
    with pytest.raises(ValueError, match="timezone-aware"):
        build_weekly_pipeline_markdown(
            {"report_type": "weekly_pipeline", "rows": []},
            generated_at=datetime(2026, 6, 10, 1, 2, 3),
        )


def _csv_metrics(path: str) -> dict:
    with open(path, encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    return {
        "open_deal_count": len(rows),
        "pipeline_value_amount": sum(_csv_amount(row) for row in rows),
        "attention_deal_count": sum(
            bool(json.loads(row["attention_reasons"] or "[]")) for row in rows
        ),
    }


def _csv_amount(row: dict) -> int:
    if row["deal_size_status"] not in {
        "rough_estimate",
        "customer_budget",
        "quoted",
        "strategic_zero",
    }:
        return 0
    return int(row["deal_size_amount"] or 0)
