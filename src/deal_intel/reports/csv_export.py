from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from deal_intel.errors import ErrorCode, Stage

FORMULA_PREFIXES = ("=", "+", "-", "@")


def save_report_csv(
    report: dict,
    *,
    output_dir: str | Path,
    generated_at: datetime | None = None,
) -> dict:
    """Write a report table to UTF-8 BOM CSV with spreadsheet safety guards."""
    report_type = str(report.get("report_type") or "report")
    rows = report.get("rows") if isinstance(report.get("rows"), list) else []
    columns = _columns(report, rows)
    generated = _generated_at(generated_at)
    filename = f"{_safe_filename_part(report_type)}_{generated:%Y%m%d_%H%M%S}.csv"
    directory = Path(output_dir).expanduser()
    path = directory / filename

    try:
        directory.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            for row in rows:
                writer.writerow({column: _cell(row.get(column)) for column in columns})
    except OSError as exc:
        return {
            "ok": False,
            "error_code": ErrorCode.IO_ERROR.value,
            "stage": Stage.STORAGE.value,
            "message": str(exc),
            "hint": {"output_dir": str(directory)},
            "retryable": True,
        }

    return {
        "ok": True,
        "report_type": report_type,
        "path": str(path.resolve()),
        "filename": filename,
        "row_count": len(rows),
        "encoding": "utf-8-sig",
        "formula_injection_protected": True,
    }


def _columns(report: dict, rows: list[dict]) -> list[str]:
    raw_columns = report.get("columns")
    if isinstance(raw_columns, list) and all(isinstance(item, str) for item in raw_columns):
        return raw_columns
    if not rows:
        return []
    return list(rows[0])


def _generated_at(value: datetime | None) -> datetime:
    generated = value or datetime.now(UTC)
    if generated.tzinfo is None or generated.utcoffset() is None:
        raise ValueError("generated_at must be timezone-aware")
    return generated.astimezone(UTC)


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    else:
        text = str(value)
    return _escape_formula(text)


def _escape_formula(text: str) -> str:
    stripped = text.lstrip(" \t\r\n")
    if stripped.startswith(FORMULA_PREFIXES):
        return "'" + text
    return text


def _safe_filename_part(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value)
    return cleaned.strip("_") or "report"
