from __future__ import annotations

import csv
from datetime import UTC, datetime, timedelta, timezone

import pytest

from deal_intel.reports.csv_export import save_report_csv


def _report() -> dict:
    return {
        "report_type": "weekly_pipeline",
        "columns": [
            "company",
            "deal_size_amount",
            "primary_pain",
            "attention_reasons",
            "formula_like",
            "spaced_formula",
            "none_value",
            "bool_value",
        ],
        "rows": [
            {
                "company": "페이브릿지",
                "deal_size_amount": 72_000_000,
                "primary_pain": {
                    "evidence": "보고 자동화 필요",
                    "importance": 5,
                },
                "attention_reasons": ["overdue", "at_risk"],
                "formula_like": "=HYPERLINK(\"http://bad\")",
                "spaced_formula": " \t+SUM(1,1)",
                "none_value": None,
                "bool_value": True,
            }
        ],
    }


def test_save_report_csv_writes_utf8_bom_and_timestamped_filename(tmp_path) -> None:
    result = save_report_csv(
        _report(),
        output_dir=tmp_path,
        generated_at=datetime(2026, 6, 9, 12, 34, 56, tzinfo=UTC),
    )

    path = tmp_path / "weekly_pipeline_20260609_123456.csv"
    assert result == {
        "ok": True,
        "report_type": "weekly_pipeline",
        "path": str(path.resolve()),
        "filename": "weekly_pipeline_20260609_123456.csv",
        "row_count": 1,
        "encoding": "utf-8-sig",
        "formula_injection_protected": True,
    }
    data = path.read_bytes()
    assert data.startswith(b"\xef\xbb\xbf")
    decoded = data.decode("utf-8-sig")
    assert "페이브릿지" in decoded
    assert "보고 자동화 필요" in decoded


def test_save_report_csv_serializes_nested_values_and_blocks_formulas(tmp_path) -> None:
    result = save_report_csv(
        _report(),
        output_dir=tmp_path,
        generated_at=datetime(2026, 6, 9, 12, 34, 56, tzinfo=UTC),
    )

    with open(result["path"], encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))

    row = rows[0]
    assert row["primary_pain"] == '{"evidence": "보고 자동화 필요", "importance": 5}'
    assert row["attention_reasons"] == '["overdue", "at_risk"]'
    assert row["formula_like"].startswith("'=")
    assert row["spaced_formula"].startswith("' \t+")
    assert row["none_value"] == ""
    assert row["bool_value"] == "true"


def test_save_report_csv_uses_utc_timestamp_for_filename(tmp_path) -> None:
    result = save_report_csv(
        _report(),
        output_dir=tmp_path,
        generated_at=datetime(
            2026,
            6,
            9,
            21,
            34,
            56,
            tzinfo=timezone(timedelta(hours=9)),
        ),
    )

    assert result["filename"] == "weekly_pipeline_20260609_123456.csv"


def test_save_report_csv_expands_user_home(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    result = save_report_csv(
        _report(),
        output_dir="~/csv-reports",
        generated_at=datetime(2026, 6, 9, 12, 34, 56, tzinfo=UTC),
    )

    expected = tmp_path / "csv-reports" / "weekly_pipeline_20260609_123456.csv"
    assert result["ok"] is True
    assert result["path"] == str(expected.resolve())
    assert expected.exists()


def test_save_report_csv_returns_structured_error_on_write_failure(tmp_path) -> None:
    output_file = tmp_path / "not-a-directory"
    output_file.write_text("occupied", encoding="utf-8")

    result = save_report_csv(
        _report(),
        output_dir=output_file,
        generated_at=datetime(2026, 6, 9, 12, 34, 56, tzinfo=UTC),
    )

    assert result["ok"] is False
    assert result["error_code"] == "IO_ERROR"
    assert result["stage"] == "storage"
    assert result["hint"] == {"output_dir": str(output_file)}
    assert result["retryable"] is True


def test_save_report_csv_requires_timezone_aware_generated_at(tmp_path) -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        save_report_csv(
            _report(),
            output_dir=tmp_path,
            generated_at=datetime(2026, 6, 9, 12, 34, 56),
        )
