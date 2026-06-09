# Status

This file tracks the current workstream and the most recent completed
milestones. Longer roadmap items live in [backlog.md](backlog.md), and durable
contracts live in [baseline.md](baseline.md) and [metrics.md](metrics.md).

## Latest Update - 2026-06-09

### BI Reporting Milestone 5.6 pipeline_trend metric

Implemented:

- Added `get_metrics(metric_type="pipeline_trend")`.
- Added `lookback_days`, default `7`, max `365`.
- Added `MongoDBClient.list_analytics_snapshots()` with a restricted
  projection over `analytics_snapshots`.
- Added pure `build_pipeline_trend_summary()` calculator.
- Trend output compares the window start and end latest snapshots by deal.
- Trend output includes active/open counts, open pipeline value, average health,
  attention count, won/lost counts, stage transitions, and data sufficiency
  warnings.
- Duplicate `event_id` snapshots are ignored defensively by the calculator.
- No LLM, embedding, or MongoDB writes are used by the trend read path.

Verification so far:

- M5.6 targeted tests:
  `24 passed`
- Related BI regression tests:
  `21 passed`
- Full pytest with workspace-local temp:
  `216 passed`
- Ruff:
  `All checks passed`
- Live Atlas read smoke:
  `ok=true`, `metric_type=pipeline_trend`, `lookback_days=7`,
  `snapshot_count=0`, expected insufficiency warnings returned

## History

### BI Reporting Milestone 5.1-5.5 analytics snapshot foundation

Implemented:

- Added an internal `analytics_snapshots` write model for trend analysis.
- Added idempotent snapshot storage keyed by `event_id`.
- Added snapshot indexes for `event_id`, `deal_id + occurred_at`, and
  `event_type + occurred_at`.
- Connected snapshots to `create_deal`, `add_meeting`, and `update_stage`.
- Snapshot failures do not block the original deal mutation; tool responses
  include an `analytics_snapshot` warning object instead.
- Snapshot documents store only lightweight BI state:
  deal metadata, value fields, stage, health band, MEDDPICC gaps, timing, and
  attention reasons.
- Snapshot documents do not store raw meeting notes, contacts, or embeddings.

Verification so far:

- New targeted tests:
  `6 passed`
- Related regression tests:
  `58 passed`
- Full pytest with workspace-local temp:
  `203 passed`
- Ruff:
  `All checks passed`
- Live Atlas write smoke:
  first insert `true`, duplicate insert `false`, found before cleanup `1`,
  cleanup deleted `1`

### BI Reporting Milestone 4.4 onboarding/demo sample data

Implemented:

- Added MCP tools: `create_sample_data`, `delete_sample_data`.
- FastMCP registration target is now 18 tools.
- Added `mongodb.demo_database`, default `deal_intel_demo`.
- Sample tools reject any demo database equal to the primary
  `mongodb.database`.
- `create_sample_data` writes fictional `weekly_pipeline_demo` deals only to
  the resolved demo database.
- `delete_sample_data` deletes only documents matching `is_sample=true` and
  the known `sample_batch_id`.
- Both tools default to `dry_run=true`.
- Actual create/delete requires `confirmed_by_user=true`.
- No LLM, embedding, or production database writes are used by the sample-data
  workflow.

Verification so far:

- Targeted tests with workspace-local temp:
  `32 passed`
- Command:
  `pytest tests/test_sample_data.py tests/test_get_metrics.py tests/test_export_report.py tests/test_get_deal_gaps.py tests/test_deal_lifecycle.py -q --basetemp .tmp\pytest-m44-targeted`
- Full pytest with workspace-local temp:
  `197 passed`
- Ruff:
  `All checks passed`
- Live Atlas demo DB dry-run smoke:
  `create_ok=true`, `create_storage_written=false`,
  `delete_ok=true`, `delete_storage_written=false`,
  demo database `deal_intel_demo`, existing sample count `0`

### BI Reporting Milestone 4.3 deal lifecycle safety layer

Implemented:

- Added MCP tools: `archive_deal`, `restore_deal`, `delete_deal`.
- FastMCP registration target is now 16 tools.
- `archive_deal` marks a deal archived and hides it from default BI/read paths.
- `restore_deal` returns an archived deal to default BI/read paths.
- `delete_deal` defaults to `dry_run=true`.
- Actual hard delete requires:
  - `confirmed_by_user=true`
  - exact `expected_company` match after trimming whitespace
  - non-empty `delete_reason`
  - already archived deal
- Hard delete writes one `delete_audit_logs` entry before deletion.
- Delete audit snapshots exclude `_id`, `contacts`, `summary_embedding`, and
  `meetings.raw_notes`.
- `get_deal` still returns archived deals and adds `warnings=["deal_archived"]`.

Archived read-path contract:

```json
{"archived": {"$ne": true}}
```

This keeps legacy documents visible when they do not have an `archived` field.

Updated read paths:

- `MongoDBClient.list_deals`
- `MongoDBClient.list_deals_for_metrics`
- `MongoDBClient.list_deals_for_theme_backfill`
- `MongoDBClient.get_deals_for_search`
- `MongoDBClient.search_by_embedding`
- `get_insights` direct aggregation paths
- `get_customer_themes` scope queries

Verification so far:

- Targeted tests with workspace-local temp:
  `49 passed`
- Command:
  `pytest tests/test_deal_lifecycle.py tests/test_archived_read_paths.py tests/test_data_quality_reporting.py tests/test_customer_themes.py tests/test_get_metrics.py tests/test_get_deal_gaps.py tests/test_export_report.py -q --basetemp .tmp\pytest-m43-targeted`
- Full pytest with workspace-local temp:
  `189 passed`
- Ruff:
  `All checks passed`
- Live Atlas read-only dry-run smoke:
  `ok=true`, `dry_run=true`, `storage_written=false`,
  visible deal count `22`, `would_delete=false`

### BI Reporting Milestone 4.2 update_deal metadata extension

Completed before M4.3:

- Extended `update_deal` beyond value fields to selected metadata:
  `company`, `industry`, `expected_close_date`, `actual_close_date`,
  `close_reason`.
- All mutations require `confirmed_by_user=true`.
- Value updates require `deal_size_note`.
- Metadata updates require `update_note` or fallback `deal_size_note`.
- `expected_close_date` is allowed only for open deals and records
  `expected_close_date_source=user_provided`.
- `actual_close_date` is allowed only for won/lost deals.
- `close_reason` is allowed only for lost deals.
- Stage transitions remain exclusively in `update_stage`.
- Metadata changes append `deal_metadata_history`.

Verification:

- Targeted `tests/test_update_deal.py`: `16 passed`
- Full pytest at completion: `176 passed`
- Ruff: passed
- Live Atlas no-op smoke: `ok=true`, `storage_written=false`, `changed=[]`

## Next

1. M5.7 trend CSV.
2. M5.8 Atlas trend chart.
3. M6 Customer Themes expansion.
