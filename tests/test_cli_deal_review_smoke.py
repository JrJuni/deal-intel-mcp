from __future__ import annotations

import json
from copy import deepcopy

from typer.testing import CliRunner

from deal_intel import _context
from deal_intel.cli import _audit_deal_review_quality, _contains_sensitive_result_key, app

MEDDPICC_DIMS = (
    "metrics",
    "economic_buyer",
    "decision_criteria",
    "decision_process",
    "identify_pain",
    "champion",
    "competition",
)


class FakeMongo:
    def __init__(self, deals: list[dict]) -> None:
        self.deals = deepcopy(deals)
        self.read_count = 0
        self.write_count = 0

    def list_deals_for_metrics(self) -> list[dict]:
        self.read_count += 1
        return deepcopy(self.deals)

    def upsert_deal(self, deal: dict) -> None:
        self.write_count += 1
        raise AssertionError("smoke-deal-review must be read-only")


def _deal(
    deal_id: str,
    *,
    company: str,
    stage: str = "proposal",
    health_pct: float = 86.5,
    filled_count: int = 7,
    actual_close_date: str | None = None,
    close_reason: str | None = None,
) -> dict:
    scores = {
        dim: {"score": 4.5, "trend": None}
        for dim in MEDDPICC_DIMS[:filled_count]
    }
    return {
        "deal_id": deal_id,
        "company": company,
        "industry": "IT",
        "deal_stage": stage,
        "deal_size_krw": 72_000_000,
        "deal_size_status": "quoted",
        "expected_close_date": "2026-06-30",
        "expected_close_date_source": "user_provided",
        "stage_history": [
            {"stage": stage, "entered_at": "2026-06-01T00:00:00+00:00"}
        ],
        "actual_close_date": actual_close_date,
        "close_reason": close_reason,
        "meddpicc_latest": {
            **scores,
            "filled_count": filled_count,
            "health_pct": health_pct,
            "gaps": [
                dim for dim in MEDDPICC_DIMS if dim not in scores
            ],
        },
        "meetings": [{"raw_notes": "secret raw note"}],
        "contacts": [{"name": "secret contact"}],
        "summary_embedding": [0.1, 0.2],
        "customer_themes": [
            {
                "theme_key": "compliance_security",
                "label": "규제·보안·컴플라이언스",
                "dimension": "decision_criteria",
                "evidence": "audit log export is mandatory",
                "importance": 5,
                "meeting_id": "m1",
                "meeting_date": "2026-06-01",
            }
        ],
    }


def test_smoke_deal_review_text_outputs_human_summary(monkeypatch) -> None:
    mongo = FakeMongo([_deal("deal-1", company="페이브릿지")])
    monkeypatch.setattr(_context, "mongo", lambda: mongo)
    monkeypatch.setattr(_context, "config", lambda: {})

    result = CliRunner().invoke(
        app,
        ["smoke-deal-review", "--deal-id", "deal-1", "--as-of", "2026-06-10"],
    )

    assert result.exit_code == 0
    assert "Deal Review Smoke (as_of=2026-06-10, count=1)" in result.output
    assert "[페이브릿지] deal-1" in result.output
    assert "Band:" in result.output
    assert "Evidence coverage:" in result.output
    assert "Warnings: win_probability_suppressed" in result.output
    assert "Sensitive field check: passed" in result.output
    assert "raw_notes" not in result.output
    assert "secret raw note" not in result.output
    assert "contacts" not in result.output
    assert "summary_embedding" not in result.output
    assert mongo.write_count == 0


def test_smoke_deal_review_json_outputs_full_payload(monkeypatch) -> None:
    mongo = FakeMongo(
        [
            _deal("deal-1", company="Alpha Labs"),
            _deal("deal-2", company="Beta Works"),
        ]
    )
    monkeypatch.setattr(_context, "mongo", lambda: mongo)
    monkeypatch.setattr(_context, "config", lambda: {})

    result = CliRunner().invoke(
        app,
        [
            "smoke-deal-review",
            "--company",
            "alpha",
            "--as-of",
            "2026-06-10",
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert payload["count"] == 1
    assert payload["sensitive_field_check"]["ok"] is True
    assert payload["results"][0]["review"]["deal_id"] == "deal-1"
    encoded = json.dumps(payload, ensure_ascii=False)
    assert "raw_notes" not in encoded
    assert "secret raw note" not in encoded
    assert "contacts" not in encoded
    assert "summary_embedding" not in encoded
    assert mongo.write_count == 0


def test_smoke_deal_review_limit_selects_multiple_deals(monkeypatch) -> None:
    mongo = FakeMongo(
        [
            _deal("deal-1", company="Alpha Labs"),
            _deal("deal-2", company="Beta Works"),
            _deal("deal-3", company="Gamma Works"),
        ]
    )
    monkeypatch.setattr(_context, "mongo", lambda: mongo)
    monkeypatch.setattr(_context, "config", lambda: {})

    result = CliRunner().invoke(
        app,
        ["smoke-deal-review", "--limit", "2", "--as-of", "2026-06-10", "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["count"] == 2
    assert [item["review"]["deal_id"] for item in payload["results"]] == [
        "deal-1",
        "deal-2",
    ]


def test_smoke_deal_review_not_found_returns_cli_error(monkeypatch) -> None:
    mongo = FakeMongo([_deal("deal-1", company="Alpha Labs")])
    monkeypatch.setattr(_context, "mongo", lambda: mongo)
    monkeypatch.setattr(_context, "config", lambda: {})

    result = CliRunner().invoke(
        app,
        ["smoke-deal-review", "--deal-id", "missing", "--as-of", "2026-06-10"],
    )

    assert result.exit_code == 1
    assert "Smoke failed: INVALID_INPUT (preflight)" in result.output
    assert "deal_id 'missing' not found" in result.output
    assert mongo.write_count == 0


def test_sensitive_key_detector_checks_keys_not_values() -> None:
    assert _contains_sensitive_result_key({"safe": "raw_notes"}) is False
    assert _contains_sensitive_result_key({"nested": [{"raw_notes": "secret"}]}) is True


def test_smoke_deal_review_audit_text_outputs_quality_summary(monkeypatch) -> None:
    mongo = FakeMongo(
        [
            _deal("deal-1", company="Alpha Labs"),
            _deal("deal-2", company="Beta Works", filled_count=2),
        ]
    )
    monkeypatch.setattr(_context, "mongo", lambda: mongo)
    monkeypatch.setattr(_context, "config", lambda: {})

    result = CliRunner().invoke(
        app,
        ["smoke-deal-review-audit", "--as-of", "2026-06-10", "--limit", "10"],
    )

    assert result.exit_code == 0
    assert "Deal Review Audit (as_of=2026-06-10, reviewed=2)" in result.output
    assert "Sensitive field check: passed" in result.output
    assert "Quality rules: passed" in result.output
    assert "Alert levels:" in result.output
    assert "Uncertainty:" in result.output
    assert "Top review targets:" in result.output
    assert "raw_notes" not in result.output
    assert "secret raw note" not in result.output
    assert "contacts" not in result.output
    assert "summary_embedding" not in result.output
    assert mongo.write_count == 0


def test_smoke_deal_review_audit_json_filters_and_counts(monkeypatch) -> None:
    mongo = FakeMongo(
        [
            _deal("deal-1", company="Alpha Labs", stage="proposal"),
            _deal("deal-2", company="Beta Works", stage="discovery"),
            _deal(
                "deal-3",
                company="Closed Lost",
                stage="lost",
                actual_close_date="2026-06-05",
                close_reason="No budget",
            ),
        ]
    )
    monkeypatch.setattr(_context, "mongo", lambda: mongo)
    monkeypatch.setattr(_context, "config", lambda: {})

    result = CliRunner().invoke(
        app,
        [
            "smoke-deal-review-audit",
            "--stage",
            "proposal",
            "--as-of",
            "2026-06-10",
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert payload["filters"]["stage"] == "proposal"
    assert payload["summary"]["reviewed_count"] == 1
    assert payload["summary"]["quality_issue_count"] == 0
    assert payload["deals"][0]["deal_id"] == "deal-1"
    encoded = json.dumps(payload, ensure_ascii=False)
    assert "raw_notes" not in encoded
    assert "contacts" not in encoded
    assert "summary_embedding" not in encoded
    assert mongo.write_count == 0


def test_smoke_deal_review_audit_invalid_stage_fails_before_storage(monkeypatch) -> None:
    mongo = FakeMongo([_deal("deal-1", company="Alpha Labs")])
    monkeypatch.setattr(_context, "mongo", lambda: mongo)
    monkeypatch.setattr(_context, "config", lambda: {})

    result = CliRunner().invoke(
        app,
        ["smoke-deal-review-audit", "--stage", "bad-stage", "--as-of", "2026-06-10"],
    )

    assert result.exit_code == 1
    assert "Smoke failed: INVALID_INPUT (preflight)" in result.output
    assert mongo.read_count == 0
    assert mongo.write_count == 0


def test_deal_review_audit_quality_rules_detect_broken_review_payload() -> None:
    review = {
        "deal_stage": "proposal",
        "health_interpretation": {
            "health_band": "healthy",
            "evidence_coverage_pct": 25.0,
            "review_band": "verified_healthy",
            "alert_level": "none",
            "uncertainty_level": "low",
        },
        "warnings": [],
        "missing_information": [],
        "confirmed_risks": [
            {"risk_id": "forecast:rough_estimate", "severity": "watch"}
        ],
        "recommended_questions": ["이 딜의 수주 확률은 80%인가요?"],
        "recommended_actions": ["review_forecast_basis"],
    }

    issue_ids = {
        issue["issue_id"] for issue in _audit_deal_review_quality(review)
    }

    assert "missing_win_probability_suppression" in issue_ids
    assert "overconfidence_warning_missing" in issue_ids
    assert "verified_healthy_with_low_coverage" in issue_ids
    assert "risk_rows_without_attention_level" in issue_ids
    assert "percent_estimate_in_guidance" in issue_ids


def test_deal_review_audit_quality_rules_require_closed_gap_reporting() -> None:
    review = {
        "deal_stage": "lost",
        "health_interpretation": {
            "health_band": "unassessed",
            "evidence_coverage_pct": 0.0,
            "review_band": "insufficient_evidence",
            "alert_level": "info",
            "uncertainty_level": "high",
        },
        "warnings": ["win_probability_suppressed", "insufficient_evidence"],
        "missing_information": [],
        "confirmed_risks": [],
        "recommended_questions": [],
        "recommended_actions": [],
    }

    issue_ids = {
        issue["issue_id"] for issue in _audit_deal_review_quality(review)
    }

    assert "closed_actual_close_gap_not_reported" in issue_ids
    assert "lost_close_reason_gap_not_reported" in issue_ids


def test_smoke_natural_questions_writes_pack(monkeypatch, tmp_path) -> None:
    mongo = FakeMongo(
        [
            _deal("deal-1", company="페이브릿지", stage="proposal"),
            _deal("deal-2", company="Beta Works", stage="discovery", filled_count=4),
            _deal("deal-3", company="Closed Lost", stage="lost"),
        ]
    )
    monkeypatch.setattr(_context, "mongo", lambda: mongo)
    monkeypatch.setattr(_context, "config", lambda: {})
    output_dir = tmp_path / "natural-pack"

    result = CliRunner().invoke(
        app,
        [
            "smoke-natural-questions",
            "--as-of",
            "2026-06-10",
            "--output-dir",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0
    assert "Natural Question Smoke (as_of=2026-06-10, questions=9)" in result.output
    assert "OK: True" in result.output
    assert "Sensitive failures: none" in result.output
    assert (output_dir / "summary.md").exists()
    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["ok"] is True
    assert summary["question_count"] == 9
    assert summary["answerability_counts"] == {"derived": 4, "direct": 5}
    assert (output_dir / "q01_pipeline_health.json").exists()
    assert (output_dir / "q08_theme_evidence_drilldown.json").exists()
    assert (output_dir / "q09_interaction_source_evidence.json").exists()
    encoded = json.dumps(summary, ensure_ascii=False)
    assert "raw_notes" not in encoded
    assert "secret raw note" not in encoded
    assert "contacts" not in encoded
    assert "summary_embedding" not in encoded
    assert mongo.write_count == 0


def test_smoke_natural_questions_json_outputs_artifact_path(monkeypatch, tmp_path) -> None:
    mongo = FakeMongo([_deal("deal-1", company="페이브릿지")])
    monkeypatch.setattr(_context, "mongo", lambda: mongo)
    monkeypatch.setattr(_context, "config", lambda: {})
    output_dir = tmp_path / "natural-pack"

    result = CliRunner().invoke(
        app,
        [
            "smoke-natural-questions",
            "--as-of",
            "2026-06-10",
            "--output-dir",
            str(output_dir),
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert payload["output_dir"] == str(output_dir.resolve())
    assert [row["id"] for row in payload["questions"]][-1] == (
        "q09_interaction_source_evidence"
    )
    assert (output_dir / "summary.md").exists()
    assert mongo.write_count == 0
