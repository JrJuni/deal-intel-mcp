# Status

This file tracks the current workstream and the most recent completed
milestones. Longer roadmap items live in [backlog.md](backlog.md), and durable
contracts live in [baseline.md](baseline.md) and [metrics.md](metrics.md).

## Latest Update - 2026-06-10

### Natural question smoke CLI

Implemented:

- Added `deal-intel smoke-natural-questions`.
- The command runs a deterministic pack of eight realistic natural-language
  questions without requiring Claude Desktop or another MCP client.
- The pack combines existing read-only payloads from pipeline metrics, deal
  review, deal gaps, and customer-theme evidence.
- It writes `summary.md`, `summary.json`, and per-question JSON files under
  `outputs/smoke/...`.
- It is a developer/QA CLI, not a user-facing MCP tool.
- Raw meeting notes, contacts, and embeddings remain excluded from the saved
  artifacts.

Verification:

- CLI targeted tests:
  `12 passed`
- Full pytest with workspace-local temp:
  `269 passed`
- Ruff:
  `All checks passed`
- Live Atlas read-only smoke:
  `smoke-natural-questions --as-of 2026-06-10` returned `OK: True`,
  `derived=3`, `direct=5`, `Sensitive failures: none`, and
  `Blocked questions: none`
- Live smoke artifacts saved locally:
  `outputs/smoke/natural-question-pack-20260610_200827/summary.md`

### Deal review Calibration v2

Implemented:

- Tightened `verified_healthy`.
  - It now requires high evidence coverage, no missing information, no
    confirmed risk rows, and confirmed data quality.
  - Healthy-looking deals with open questions are downgraded to
    `promising_but_unproven`.
  - Healthy-looking deals with confirmed risk rows are downgraded to
    `watch_with_evidence`.
- Tightened `low` uncertainty.
  - Missing information, rough estimates, invalid value classification, or
    unconfirmed data quality now prevent `low` uncertainty.
- Added `forecast_confidence` to deal review interpretation.
  - Values include `quoted`, `strategic_zero`, `customer_indicated`,
    `estimated`, `unknown`, and `invalid`.
- Extended the audit smoke rules so `verified_healthy` and `low` uncertainty
  cannot hide open gaps, risk rows, or unconfirmed data.

Verification:

- Calibration targeted tests:
  `22 passed`
- Full pytest with workspace-local temp:
  `267 passed`
- Ruff:
  `All checks passed`
- Live Atlas read-only audit smoke:
  `smoke-deal-review-audit --as-of 2026-06-10 --limit 50` reviewed `22`
  deals and returned `Sensitive field check: passed`, `Quality rules: passed`
- 10-set live smoke artifacts saved locally:
  `outputs/smoke/deal-review-calibration-v2-20260610_175009/summary.md`

Observed calibration delta:

- Before v2:
  `verified_healthy=19`, `watch_with_evidence=2`, `low uncertainty=21`,
  `medium uncertainty=0`, `watch alert=8`
- After v2:
  `verified_healthy=10`, `watch_with_evidence=8`,
  `promising_but_unproven=3`, `low uncertainty=12`,
  `medium uncertainty=9`, `watch alert=11`

### Deal review audit smoke pack

Implemented:

- Added `deal-intel smoke-deal-review-audit`.
- The command audits selected deal reviews through the restricted metrics read
  path without requiring Claude Desktop or another MCP client.
- Supports `--company`, `--stage`, `--industry`, `--limit`, `--as-of`,
  `--json`, and `--fail-on-issues`.
- Summarizes alert levels, uncertainty levels, review bands, warnings, quality
  issue counts, and top review targets.
- Added deterministic quality rules for:
  - win-probability suppression
  - low-evidence healthy overconfidence
  - confirmed risk alert consistency
  - missing information follow-up questions
  - confirmed risk follow-up actions
  - closed-deal postmortem gap reporting
  - accidental percentage estimates in guidance
  - sensitive field exposure
- Fixed deal review alert interpretation so any confirmed risk row raises the
  review to at least `watch`.

Verification:

- Deal review audit CLI targeted tests:
  `10 passed`
- Related deal review regression tests:
  `21 passed`
- Full pytest with workspace-local temp:
  `266 passed`
- Ruff:
  `All checks passed`
- Live Atlas read-only audit smoke:
  `smoke-deal-review-audit --as-of 2026-06-10 --limit 50` reviewed `22`
  deals, returned `Sensitive field check: passed`, `Quality rules: passed`,
  and moved confirmed-risk rows from `alert=none` to `watch`

### Deal review local smoke CLI

Implemented:

- Added `deal-intel smoke-deal-review`.
- The command exercises the same read-only `get_deal_review` handler path
  without requiring Claude Desktop or another MCP client.
- Supports exact `--deal-id`, company substring `--company`, `--limit`,
  `--as-of`, and `--json`.
- Text output summarizes review band, alert level, uncertainty, evidence
  coverage, missing information, confirmed risks, recommended questions, and
  warnings.
- JSON output returns the full structured tool response for repeatable local
  smoke checks.
- Successful smoke output omits raw notes, contacts, embeddings, and even the
  restricted field names themselves.

Verification:

- New CLI targeted tests:
  `5 passed`
- Related deal review regression tests:
  `15 passed`
- Full pytest with workspace-local temp:
  `260 passed`
- Ruff:
  `All checks passed`
- Live Atlas read-only smoke:
  `smoke-deal-review --as-of 2026-06-10 --limit 2` returned two deal reviews
  and `Sensitive field check: passed`

### Deal review quality hardening

Implemented:

- Added `get_deal_review` MCP tool.
- Added deterministic `deal_review` calculation module.
- Separated legacy `health_pct` from MEDDPICC evidence coverage.
- Added `uncertainty_level`, `review_band`, and `alert_level`.
- Added explicit `missing_information`, `confirmed_risks`,
  `known_signals`, `recommended_questions`, and `recommended_actions`.
- Suppressed uncalibrated win-probability numbers in review responses.
- Kept the read path free of LLM calls, embedding calls, and MongoDB writes.
- Used the restricted metrics projection so raw notes, contacts, and
  embeddings remain excluded.

Verification:

- `tests/test_deal_review.py`:
  `10 passed`
- Related MCP/read-path regression tests:
  `54 passed`
- Full pytest with workspace-local temp:
  `255 passed`
- Ruff:
  `All checks passed`
- FastMCP registration smoke:
  `21` tools, `get_deal_review` registered
- Live Atlas read-only smoke:
  `deal_count=22`, `ok=true`, first reviewed deal returned
  `review_band=verified_healthy`, `alert_level=none`,
  `warnings=win_probability_suppressed`

### BI Reporting Milestone 6.1-M6.3 Customer Themes expansion

Implemented:

- Added `get_customer_theme_breakdown` MCP tool.
  - Compares curated customer themes by `stage`, `industry`, or `dimension`.
  - Supports `dimension`, `stage`, `industry`, `group_by`, and `top_k`.
- Added `get_customer_theme_evidence` MCP tool.
  - Returns curated evidence snippets for one `theme_key`.
  - Supports `dimension`, `stage`, `industry`, `limit`, and `min_importance`.
- Added pure `customer_theme_insights` calculation module for breakdown and
  drill-down behavior.
- Added versioned Atlas Charts spec:
  `atlas/charts/customer_themes.v1.json`.
- Added `Customer Themes Review` dashboard source over `deals`.
- Extended `render-atlas-dashboard` with `--dashboard customer_themes`.
- Kept the M6 read paths free of LLM calls, embedding calls, and MongoDB
  writes.
- Raw meeting notes, contacts, and embeddings remain excluded from the new
  read paths.

Verification:

- M6.1-M6.2 targeted tests:
  `18 passed`
- M6.3 Atlas chart targeted tests:
  `15 passed`
- M6 related regression tests:
  `69 passed`
- Full pytest with workspace-local temp:
  `245 passed`
- Ruff:
  `All checks passed`
- CLI render smoke:
  `render-atlas-dashboard --dashboard customer_themes --chart-id theme_overview`
  printed a rendered Atlas aggregation pipeline
- Live Atlas read-only smoke:
  `get_customer_theme_breakdown` returned `deals_analyzed=13`,
  `deals_with_evidence=13`, `group_count=4`; `get_customer_theme_evidence`
  returned `unique_deal_count=10`, `evidence_count=21`; Customer Themes Atlas
  aggregations returned rows for all 4 charts

### BI Reporting Milestone 5.8 Atlas trend chart

Implemented:

- Added versioned Atlas Charts spec:
  `atlas/charts/pipeline_trend.v1.json`.
- Added `Pipeline Trend Review` dashboard source over
  `analytics_snapshots`.
- Added chart pipelines:
  `trend_kpis` and `trend_delta_bars`.
- Extended `render-atlas-dashboard` with:
  `--dashboard pipeline_trend` and `--lookback-days`.
- Added `MongoDBClient.aggregate_analytics_snapshots()` for read-only Atlas
  pipeline smoke tests.
- No LLM, embedding, or MongoDB writes are used by the trend chart path.

Verification:

- M5.8 targeted tests:
  `20 passed`
- Related Atlas/report/trend regression tests:
  `34 passed`
- Full pytest with workspace-local temp:
  `234 passed`
- Ruff:
  `All checks passed`
- CLI render smoke:
  `render-atlas-dashboard --dashboard pipeline_trend --chart-id trend_kpis`
  wrote rendered JSON with no unresolved placeholders
- Live Atlas aggregation smoke:
  `trend_kpis=1 row`, `trend_delta_bars=3 rows`

Manual follow-up:

- Create or update the Atlas Charts dashboard named `Pipeline Trend Review`
  using [atlas-charts.md](atlas-charts.md). This is a manual Atlas UI step.

## History

### BI Reporting Milestone 5.7 trend CSV

Implemented:

- Added `export_report(report_type="pipeline_trend")`.
- Added `lookback_days`, default `7`, max `365`, for trend reports.
- Added pipeline trend CSV rows for KPI start/end/delta and stage movement.
- Added LLM-free Markdown summary for pipeline trend reports.
- Reused the M5.6 `build_pipeline_trend_summary()` calculator.
- Trend report reads only `analytics_snapshots` through
  `list_analytics_snapshots()` and does not read deal raw notes.
- No LLM, embedding, or MongoDB writes are used by the trend export path.

Verification:

- M5.7 targeted tests:
  `17 passed`
- Related report/trend regression tests:
  `33 passed`
- Full pytest with workspace-local temp:
  `228 passed`
- Ruff:
  `All checks passed`
- Live Atlas read-only smoke:
  `ok=true`, `report_type=pipeline_trend`, `snapshot_count=0`, `row_count=7`,
  expected sparse-history warnings returned, CSV/Markdown artifacts created

### OpenAI API LLM provider support

Implemented:

- Added `OpenAIAPIProvider` using the official OpenAI Responses API.
- Added `llm.provider: openai_api`.
- Added `llm.openai_api_model` and `llm.openai_api_reasoning_effort`.
- Added `OPENAI_API_KEY` support through `.env` and MCP bundle user config.
- Added `DEAL_INTEL_LLM_PROVIDER` as the explicit provider override while
  preserving legacy `DEAL_INTEL_USE_CHATGPT_OAUTH` behavior.
- Bumped the MCP bundle manifest to `0.1.8`.
- Kept the MCP tool surface unchanged at 18 tools.

Verification:

- OpenAI provider targeted tests:
  `10 passed`
- Related LLM/provider regression tests:
  `27 passed`
- Full pytest with workspace-local temp:
  `226 passed`
- Ruff:
  `All checks passed`
- MCP bundle manifest JSON:
  valid
- Live OpenAI API smoke:
  not run because this environment does not currently have API credits/key;
  provider behavior is covered with mock HTTP tests.

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

1. M6 Customer Themes expansion.
