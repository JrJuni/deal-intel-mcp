# Reporting Contract

This document records report-specific contracts. Metric definitions remain in
[metrics.md](metrics.md).

## Product Contract - Reports vs Data Exports

The export layer has two different jobs:

- `export_report` creates human-facing artifacts for manager updates, team
  meetings, and narrative pipeline reviews. The output should read like a
  briefing: KPI summary, key deal movements, risks/opportunities, and next-week
  focus. The deterministic metric/data pack is the source of truth; host-app
  LLMs may help turn that pack into polished prose. The MCP response includes a
  compact `briefing`, structured `briefing_sections`, and a safe
  `host_report_prompt` for that host-app polishing step.
- `export_data` creates spreadsheet-ready CSV ledgers for Excel, Sheets, BI
  cleanup, or downstream analysis. It is deterministic, LLM-free, and should
  not try to be a narrative report.

This split replaces the early MVP assumption that a weekly pipeline "report"
should primarily be CSV plus a thin Markdown summary. CSV remains useful, but
CSV is now treated as data export, not the user-facing weekly report surface.

## Data Export Datasets

`deal_intel.reports.data_export.build_data_export` builds deterministic CSV
datasets without storage access, file IO, LLM calls, embeddings, or Atlas admin
APIs.

Supported datasets:

- `open_deals`: active/stalled pipeline ledger with health, timing, attention,
  gap, and primary pain / decision-criteria fields.
- `all_deals`: full safe deal ledger for recordkeeping and spreadsheet
  filtering.
- `closed_deals`: won/lost postmortem ledger with close metadata.

`export_data` reads through the restricted metrics projection
(`list_deals_for_metrics()`), writes UTF-8 BOM CSV with formula-injection
protection, and excludes:

- `meetings.raw_notes`
- `interactions.raw_content`
- `contacts`
- `summary_embedding`

The MCP response includes absolute CSV path, row count, column list, warnings,
and a small safe preview. It does not write to MongoDB and does not call an LLM.

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
- `customer_segment`
- `deal_stage`
- `deal_size_amount`
- `deal_size_currency`
- `deal_size_status`
- `expected_close_date`
- `days_in_stage`
- `stuck_status`
- `is_stuck`
- `close_date_status`
- `is_overdue`
- `overdue_days`
- `qualification_framework`
- `qualification_framework_display_name`
- `qualification_source_field`
- `qualification_health_pct`
- `qualification_quality_pct`
- `qualification_coverage_pct`
- `qualification_gaps`
- `health_pct`
- `health_band`
- `meddpicc_gaps` (legacy alias; populated only for MEDDPICC-backed rows)
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

Primary theme objects include safe source metadata when available:

- `interaction_id`
- `interaction_date`
- `interaction_type`
- `source_confidence`
- `source_label`
- `subject`
- legacy `meeting_id` / `meeting_date`

`source_label` is a human-readable label such as
`Email thread (customer-stated)` or `User interview (customer-stated)`. It is
derived from structured source metadata and does not require exposing raw
interaction content.

`qualification_*` fields are the canonical framework-aware report fields.
`health_pct` and `health_band` remain stable compatibility aliases so existing
CSV/Markdown consumers do not need to change immediately.

`objective_action_items` contains only CTA-safe gaps such as overdue close
dates, stuck stages, and explicitly stalled deals. `gap_observations` contains
judgment-sensitive qualification gaps such as competition, champion, buyer
owner, business need, or framework-specific decision criteria, plus at-risk
health observations. Consumers should not flatten `gap_observations` into
prescriptive next actions.

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

`deal_intel.reports.markdown_summary.build_weekly_pipeline_markdown` currently
builds a deterministic Markdown briefing from the `weekly_pipeline` row report.
It is the compatibility local report renderer and host-app source pack, not the
final limit of the human-report product surface.

### Scope

- Input: `weekly_pipeline` report dict from Milestone 2.1.
- Output: Markdown body, machine-readable summary metrics, compact briefing
  text, structured briefing sections, and a safe host-app polish prompt.
- Side effects: none.
- File writing: none.
- Storage access: none.
- LLM / embedding: none in this deterministic local renderer.
- MongoDB access: none.

Markdown file persistence is intentionally out of scope for 2.3. The later
`export_report` MCP tool will be responsible for saving both CSV and Markdown
artifacts.

Markdown artifacts are written by `markdown_export` as `utf-8-sig` so Korean
reports open more reliably in Windows desktop apps. Markdown readers that
understand normal UTF-8 should also accept the BOM.

### Output Shape

```json
{
  "report_type": "weekly_pipeline",
  "generated_at": "2026-06-09T12:34:56+00:00",
  "metrics": {},
  "warnings": [],
  "briefing": "...",
  "briefing_sections": {
    "executive_summary": [],
    "meeting_agenda": [],
    "priority_deals": []
  },
  "host_report_prompt": "## Host-App Report Polish Prompt\n...",
  "markdown": "# Weekly Pipeline Report\n..."
}
```

`generated_at` must be timezone-aware. It is converted to UTC before rendering.

### Metric Source

Markdown metrics are computed from the same report rows that compatibility CSV
export writes.
The Markdown generator does not re-read MongoDB and does not run a separate
aggregation. This keeps CSV and Markdown numbers aligned.

The fixed metric surface includes:

- `open_deal_count`
- `pipeline_value_amount`
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

The generated body is designed for a weekly pipeline review meeting. It should
read differently from the CSV table and Atlas dashboard: CSV preserves rows,
Atlas visualizes current state, and Markdown gives the meeting narrative.

The generated body includes:

1. Executive summary explaining how to use the report.
2. Meeting agenda for a manager/team weekly review.
3. Core KPI table.
4. Key deal watchlist, using the weekly row sort order and limited to the first
   five deals.
5. Stage breakdown table.
6. Issues to watch, split into:
   - Objective Action Items, based only on `objective_action_items`.
   - Gap Observations, based on `gap_observations`.
7. Next Week Actions, generated deterministically from action, attention,
   observation, and data-quality counts.
8. Customer Evidence table, based on primary curated pain / decision criteria
   snippets and their `source_label`
9. Data quality table.
10. Warning code list.

The key deal watchlist and issue tables escape Markdown table separators and
newlines in cell values. The Objective Action Items section is for objective CTA
triggers. The Gap Observations section is for judgment-sensitive gaps and
includes `actionability` so readers can decide the next move without the report
over-prescribing qualitative BD judgment.

The Customer Evidence section renders only curated `customer_themes` snippets
plus safe source labels. It must not render `meetings.raw_notes`,
`interactions.raw_content`, contacts, or embeddings.

### Non-Goals

Milestone 2.3 does not create a new MCP tool, write files, call Atlas Charts, or
call an LLM. It may render deterministic narrative prose, but must not infer new
facts beyond the row report and Markdown summary metrics. Host-assisted report
polish can happen above this deterministic data pack; any future server-side LLM
report mode must keep deterministic metrics as the source of truth.

`host_report_prompt` is designed for Claude/Codex/ChatGPT host apps that can
write better prose than the MCP server should. It explicitly instructs the host
not to change deterministic numbers, company names, stages, amounts, health
scores, or warning codes. It also keeps objective action items separate from
judgment-sensitive gap observations so reports do not over-prescribe BD actions.

## Milestone 2.4 - `export_report` MCP Tool

`deal_intel.tools.export_report.handle` exposes weekly pipeline reporting through
MCP.

### Scope

- First supported `report_type`: `weekly_pipeline`.
- Reads deal documents through `MongoDBClient.list_deals_for_metrics()`.
- Builds M2.1 rows and M2.3 Markdown from the same row surface.
- Writes Markdown plus a compatibility CSV artifact to a local output directory.
- Returns absolute artifact paths plus a compact briefing and host-app report
  polish prompt.
- LLM / embedding: none.
- MongoDB writes: none.

For spreadsheet-first CSV ledgers, use `export_data` instead of
`export_report`.

### Inputs

| Parameter | Required | Contract |
|---|---|---|
| `report_type` | optional | Defaults to `weekly_pipeline`; other values fail preflight |
| `output_dir` | optional | Explicit local directory. Defaults to `reporting.output_dir` or `~/.deal-intel/reports`; relative paths are scoped under `~/.deal-intel/` |
| `stage` | optional | Exact valid stage match |
| `industry` | optional | Exact stored industry match |
| `as_of` | optional | `YYYY-MM-DD` business date for stuck/overdue calculations |

Markdown report language is controlled by config:

```yaml
reporting:
  language: en  # en | ko
```

Use `update_config(reporting_language="ko")` to switch generated Markdown
reports to Korean from Claude/Codex App. CSV field names and stored customer
evidence stay contract/data-oriented; only the human-facing Markdown labels and
section text are localized.

### Success Shape

```json
{
  "ok": true,
  "report_type": "weekly_pipeline",
  "as_of": "2026-06-09",
  "timezone": "Asia/Seoul",
  "generated_at": "2026-06-09T12:34:56+00:00",
  "language": "en",
  "filters": {"stage": null, "industry": null},
  "row_count": 7,
  "warnings": [],
  "metrics": {},
  "briefing": "...",
  "briefing_sections": {
    "executive_summary": [],
    "meeting_agenda": [],
    "priority_deals": []
  },
  "host_report_prompt": "## Host-App Report Polish Prompt\n...",
  "output_dir": "<user-home>/.deal-intel/reports",
  "artifacts": {
    "csv": {
      "path": "C:/absolute/path/weekly_pipeline_20260609_123456.csv",
      "filename": "weekly_pipeline_20260609_123456.csv",
      "encoding": "utf-8-sig"
    },
    "markdown": {
      "path": "C:/absolute/path/weekly_pipeline_20260609_123456.md",
      "filename": "weekly_pipeline_20260609_123456.md",
      "encoding": "utf-8-sig"
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
~/miniconda3/envs/deal-intel/python.exe -m deal_intel.cli render-atlas-dashboard --as-of 2026-06-09 --chart-id pipeline_kpis
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
~/miniconda3/envs/deal-intel/python.exe -m deal_intel.cli crosscheck-weekly-dashboard --as-of 2026-06-09 --output-dir outputs/m3_3_crosscheck
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
| `output_dir` | optional | Explicit local directory. Defaults to `reporting.output_dir` or `~/.deal-intel/reports`; relative paths are scoped under `~/.deal-intel/` |
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
