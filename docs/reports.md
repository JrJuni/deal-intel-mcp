# Reporting Contract

This document records report-specific contracts. Metric definitions remain in
[metrics.md](metrics.md).

## Milestone 2.1 - Weekly Pipeline Rows

`deal_intel.reports.weekly_pipeline.build_weekly_pipeline_rows` builds the
in-memory table rows for the `weekly_pipeline` report.

### Scope

- Input: already-fetched deal documents, `as_of` date, metric settings, and
  optional exact `stage` / `industry` filters.
- Output: JSON-serializable dict.
- Side effects: none.
- Storage access: none.
- LLM / embedding: none.
- File writing: none.

The default population is Open deals only:

- `discovery`
- `qualification`
- `proposal`
- `negotiation`
- `stalled`

Terminal deals, `won` and `lost`, are excluded from weekly pipeline rows.

### Output Shape

```json
{
  "report_type": "weekly_pipeline",
  "filters": {"stage": null, "industry": null},
  "columns": [],
  "rows": [],
  "row_count": 0,
  "warnings": []
}
```

### Row Columns

- `deal_id`
- `company`
- `industry`
- `deal_stage`
- `deal_size_krw`
- `deal_size_status`
- `expected_close_date`
- `days_in_stage`
- `stuck_status`
- `is_stuck`
- `close_date_status`
- `is_overdue`
- `overdue_days`
- `health_pct`
- `health_band`
- `meddpicc_gaps`
- `last_meeting_date`
- `primary_pain`
- `primary_decision_criteria`
- `attention_reasons`
- `objective_action_items`
- `gap_observations`
- `data_quality`

`primary_pain` is selected from `customer_themes` where
`dimension == "identify_pain"`. `primary_decision_criteria` is selected where
`dimension == "decision_criteria"`. Selection order is highest `importance`,
then latest `meeting_date`.

`objective_action_items` contains only CTA-safe gaps such as overdue close
dates, stuck stages, and explicitly stalled deals. `gap_observations` contains
judgment-sensitive gaps such as MEDDPICC competition, champion, economic buyer,
decision criteria, and at-risk health observations. Consumers should not flatten
`gap_observations` into prescriptive next actions.

### Sorting

Rows are sorted for weekly review attention:

1. overdue
2. stuck
3. stalled
4. at risk
5. earliest valid `expected_close_date`
6. largest valid deal amount
7. company name

### Privacy

Weekly pipeline rows must not include:

- `meetings.raw_notes`
- `interactions.raw_content`
- `contacts`
- `summary_embedding`

Evidence snippets in `customer_themes` may be included because they are already
curated report evidence, not raw meeting notes or raw interaction content.

### Warnings

The row builder can return these warning codes:

- `no_open_deals`
- `unassessed_health`
- `missing_expected_close_date`
- `invalid_expected_close_date`
- `missing_last_meeting_date`
- `missing_primary_pain`
- `missing_primary_decision_criteria`
- `incomplete_data_quality`

### Out Of Scope

Milestone 2.1 does not create CSV files, Markdown summaries, Atlas Charts, or
MCP tools. Those consume this row contract in later milestones.

## Milestone 2.2 - CSV Export

`deal_intel.reports.csv_export.save_report_csv` writes report rows to a local
CSV file.

### Scope

- Input: report dict with `report_type`, `columns`, and `rows`.
- Required option: explicit `output_dir`.
- Output: structured success or structured file-write error dict.
- Side effects: creates `output_dir` if missing and writes one CSV file.
- Storage access: none.
- LLM / embedding: none.
- MongoDB access: none.

### Filename

CSV filenames use the report type plus a UTC timestamp:

```text
{report_type}_YYYYMMDD_HHMMSS.csv
```

Example:

```text
weekly_pipeline_20260609_123456.csv
```

`generated_at` must be timezone-aware. It is converted to UTC before building
the filename.

### Encoding

CSV files are written as `utf-8-sig`, which includes a UTF-8 BOM for smoother
Korean display in Excel.

### Cell Serialization

- `None` is written as an empty cell.
- Boolean values are written as `true` or `false`.
- `dict` and `list` values are written as compact JSON with `ensure_ascii=False`.
- Other values are stringified.

### Formula Injection Guard

After stringification, a cell is prefixed with a single quote when its first
non-whitespace character is one of:

```text
= + - @
```

This prevents spreadsheet apps from interpreting exported report data as a
formula.

### Success Shape

```json
{
  "ok": true,
  "report_type": "weekly_pipeline",
  "path": "C:/absolute/path/weekly_pipeline_20260609_123456.csv",
  "filename": "weekly_pipeline_20260609_123456.csv",
  "row_count": 7,
  "encoding": "utf-8-sig",
  "formula_injection_protected": true
}
```

### Error Shape

File write failures return a structured error instead of raising `OSError`:

```json
{
  "ok": false,
  "error_code": "IO_ERROR",
  "stage": "storage",
  "message": "...",
  "hint": {"output_dir": "C:/target"},
  "retryable": true
}
```

Programmer errors, such as a naive `generated_at`, may still raise a local
exception because they indicate an invalid caller contract rather than a runtime
storage failure.

## Milestone 2.3 - Markdown Summary

`deal_intel.reports.markdown_summary.build_weekly_pipeline_markdown` builds an
LLM-free Markdown summary from the `weekly_pipeline` row report.

### Scope

- Input: `weekly_pipeline` report dict from Milestone 2.1.
- Output: Markdown body plus machine-readable summary metrics.
- Side effects: none.
- File writing: none.
- Storage access: none.
- LLM / embedding: none.
- MongoDB access: none.

Markdown file persistence is intentionally out of scope for 2.3. The later
`export_report` MCP tool will be responsible for saving both CSV and Markdown
artifacts.

### Output Shape

```json
{
  "report_type": "weekly_pipeline",
  "generated_at": "2026-06-09T12:34:56+00:00",
  "metrics": {},
  "warnings": [],
  "markdown": "# Weekly Pipeline Report\n..."
}
```

`generated_at` must be timezone-aware. It is converted to UTC before rendering.

### Metric Source

Markdown metrics are computed from the same report rows that CSV export writes.
The Markdown generator does not re-read MongoDB and does not run a separate
aggregation. This keeps CSV and Markdown numbers aligned.

The fixed metric surface includes:

- `open_deal_count`
- `pipeline_value_krw`
- `known_amount_count`
- `amount_coverage_pct`
- `avg_health_pct`
- `assessed_health_count`
- `health_coverage_pct`
- `attention_deal_count`
- `objective_action_item_count`
- `gap_observation_count`
- `overdue_count`
- `stuck_count`
- `stalled_count`
- `at_risk_count`
- `unassessed_health_count`
- `incomplete_data_quality_count`
- `missing_expected_close_date_count`
- `invalid_expected_close_date_count`
- `missing_last_meeting_date_count`
- `missing_primary_pain_count`
- `missing_primary_decision_criteria_count`

### Markdown Sections

The generated body includes:

1. KPI table
2. Risk deals table, based on `attention_reasons`
3. Objective Action Items table, based only on `objective_action_items`
4. Gap Observations table, based on `gap_observations`
5. Data quality table
6. Warning code list

Risk deal tables escape Markdown table separators and newlines in cell values.
The Objective Action Items section is for objective CTA triggers. The Gap
Observations section is for judgment-sensitive gaps and includes
`actionability` so readers can decide the next move without the report
over-prescribing qualitative BD judgment.

### Non-Goals

Milestone 2.3 does not create a new MCP tool, write files, call Atlas Charts,
call an LLM, or create a polished natural-language executive narrative. It is a
deterministic report renderer.

## Milestone 2.4 - `export_report` MCP Tool

`deal_intel.tools.export_report.handle` exposes weekly pipeline reporting through
MCP.

### Scope

- First supported `report_type`: `weekly_pipeline`.
- Reads deal documents through `MongoDBClient.list_deals_for_metrics()`.
- Builds M2.1 rows, M2.2 CSV, and M2.3 Markdown from the same row surface.
- Writes CSV and Markdown files to a local output directory.
- Returns absolute artifact paths.
- LLM / embedding: none.
- MongoDB writes: none.

### Inputs

| Parameter | Required | Contract |
|---|---|---|
| `report_type` | optional | Defaults to `weekly_pipeline`; other values fail preflight |
| `output_dir` | optional | Explicit local directory. Defaults to `reporting.output_dir` or `outputs/reports` |
| `stage` | optional | Exact valid stage match |
| `industry` | optional | Exact stored industry match |
| `as_of` | optional | `YYYY-MM-DD` business date for stuck/overdue calculations |

### Success Shape

```json
{
  "ok": true,
  "report_type": "weekly_pipeline",
  "as_of": "2026-06-09",
  "timezone": "Asia/Seoul",
  "generated_at": "2026-06-09T12:34:56+00:00",
  "filters": {"stage": null, "industry": null},
  "row_count": 7,
  "warnings": [],
  "metrics": {},
  "output_dir": "C:/absolute/path/outputs/reports",
  "artifacts": {
    "csv": {
      "path": "C:/absolute/path/weekly_pipeline_20260609_123456.csv",
      "filename": "weekly_pipeline_20260609_123456.csv",
      "encoding": "utf-8-sig"
    },
    "markdown": {
      "path": "C:/absolute/path/weekly_pipeline_20260609_123456.md",
      "filename": "weekly_pipeline_20260609_123456.md",
      "encoding": "utf-8"
    }
  },
  "csv_path": "C:/absolute/path/weekly_pipeline_20260609_123456.csv",
  "markdown_path": "C:/absolute/path/weekly_pipeline_20260609_123456.md"
}
```

`csv_path` and `markdown_path` are convenience aliases for assistant-facing
answers.

### Error Behavior

- Invalid `report_type`, invalid `stage`, and invalid `as_of` fail before
  MongoDB access.
- Invalid metric/reporting config fails before MongoDB access.
- MongoDB read failure returns `STORAGE_ERROR`.
- File write failure returns `IO_ERROR` at `storage` stage.

Artifact writes are not transactional. If a later artifact write fails after an
earlier file was created, the caller receives a structured error and may retry
with a new output directory or timestamp.

### MVP Gate

With M2.4 complete, CSV Reporting MVP is functionally complete:

1. row generation
2. CSV export
3. Markdown summary
4. MCP artifact export

## Milestone 3.2 - Atlas Charts Dashboard Setup

The Atlas Charts dashboard setup path is recorded in
[atlas-charts.md](atlas-charts.md).

`deal_intel.reports.atlas_charts` owns the versioned aggregation dashboard spec
and config placeholder rendering. The CLI exposes that renderer:

```bash
~/miniconda3/envs/event-intel/python.exe -m deal_intel.cli render-atlas-dashboard --as-of 2026-06-09 --chart-id pipeline_kpis
```

The rendered chart pipeline is a JSON array suitable for the Atlas Charts Query
bar. The full dashboard spec can also be written to `outputs/atlas_charts`.

This path does not call LLMs, generate embeddings, or write to MongoDB. Atlas UI
dashboard creation remains a manual UI step because dashboard objects live in
MongoDB Atlas Charts, not in this repository.

## Milestone 3.3 - Dashboard Cross-Check

`deal_intel.reports.dashboard_crosscheck` compares the three BI surfaces that
must agree:

- `get_metrics(metric_type="pipeline_health")`
- `export_report(report_type="weekly_pipeline")` CSV/Markdown metrics
- rendered Atlas Charts aggregation pipelines

The CLI command is:

```bash
~/miniconda3/envs/event-intel/python.exe -m deal_intel.cli crosscheck-weekly-dashboard --as-of 2026-06-09 --output-dir outputs/m3_3_crosscheck
```

The command reads MongoDB, writes local CSV/Markdown report artifacts, executes
the versioned Atlas chart pipelines against the live collection, and returns a
structured `ok` result plus per-metric comparisons. It does not write to MongoDB
and does not call LLMs or embeddings.

Cross-checked fields include:

- KPI counts and values
- open pipeline value against CSV/Markdown report value
- attention, overdue, stuck, and stalled counts
- stage breakdown values
- health band counts
- attention table row count

## Milestone 5.7 - Pipeline Trend CSV

`export_report(report_type="pipeline_trend")` exports the M5.6 trend metric as
CSV and Markdown artifacts.

### Scope

- Reads `analytics_snapshots` through `MongoDBClient.list_analytics_snapshots()`.
- Reuses `build_pipeline_trend_summary()`.
- Writes a UTF-8 BOM CSV and a Markdown summary.
- LLM / embedding: none.
- MongoDB writes: none.

### Inputs

| Parameter | Required | Contract |
|---|---|---|
| `report_type` | optional | `pipeline_trend` for this report |
| `output_dir` | optional | Explicit local directory. Defaults to `reporting.output_dir` or `outputs/reports` |
| `stage` | optional | Exact valid snapshot `deal_stage` match |
| `industry` | optional | Exact stored snapshot industry match |
| `as_of` | optional | `YYYY-MM-DD` business end date |
| `lookback_days` | optional | Defaults to `7`, valid range `1..365` |

### CSV Rows

The CSV has one table with these columns:

```text
section,item,start_value,end_value,delta,count,notes
```

Rows are grouped by:

- `kpi`: start/end/delta for active deals, open deals, open pipeline value,
  average health, attention deals, won deals, and lost deals
- `stage_transition`: stage movement such as `proposal->negotiation`
- `stage_entered`: stages that appear in the end baseline but not the start
  baseline
- `stage_exited`: stages present at the start baseline but absent at the end

### Success Shape

The response follows the same artifact contract as `weekly_pipeline` and adds
trend-specific metadata:

```json
{
  "ok": true,
  "report_type": "pipeline_trend",
  "window": {
    "lookback_days": 7,
    "start_date": "2026-06-03",
    "end_date": "2026-06-10"
  },
  "snapshot_count": 12,
  "deal_count": 9,
  "csv_path": "C:/absolute/path/pipeline_trend_20260610_123456.csv",
  "markdown_path": "C:/absolute/path/pipeline_trend_20260610_123456.md"
}
```

`lookback_days` validation fails before MongoDB storage access. The report is
read-only and may return sparse-history warnings such as
`insufficient_snapshots`.
