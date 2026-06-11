# Verification Baseline

BI and reporting work must compare its behavior against this baseline before
changing shared deal or MCP behavior.

## 2026-06-08 - Milestone 0.1

### Runtime

- Python: 3.11.15 (`event-intel` conda environment)
- FastMCP runtime registration: 9 tools
- MongoDB database: `deal_intel`
- Atlas read smoke: passed
- Deal count at smoke time: 10

The Atlas smoke performed only:

1. `ping`
2. `count_documents({})`
3. One deal read with a restricted projection

It did not write or update MongoDB data.

### Common Error Contract

All MCP boundaries return structured errors with:

```json
{
  "ok": false,
  "error_code": "INVALID_INPUT | NOT_FOUND | CONFIG_ERROR | RATE_LIMITED | UPSTREAM_ERROR | IO_ERROR | INTERNAL | STORAGE_ERROR | LLM_ERROR | LOGIN_REQUIRED",
  "stage": "preflight | storage | llm | analysis",
  "message": "human-readable message",
  "hint": null,
  "retryable": false
}
```

### LLM Provider Contract

Valid `llm.provider` values:

- `chatgpt_oauth` - default; uses ChatGPT Plus/Pro OAuth tokens from the local
  `login-chatgpt` flow.
- `openai_api` - uses the official OpenAI Responses API with `OPENAI_API_KEY`.
- `anthropic` - uses `ANTHROPIC_API_KEY` through the Anthropic SDK.

`DEAL_INTEL_LLM_PROVIDER` is the explicit install/bundle override and accepts
the same values. `DEAL_INTEL_USE_CHATGPT_OAUTH` remains a legacy boolean
override for older bundles. When both are present, `DEAL_INTEL_LLM_PROVIDER`
wins.

OpenAI API live smoke is not part of the current baseline because this local
environment may not have API credits. The provider is covered by mock HTTP
tests and should be live-smoked only when a disposable `OPENAI_API_KEY` is
available.

### MCP Tool Contracts

The Python server keeps all 23 handler functions available internally, but MCP
clients see a config-filtered tool surface:

- `tools.surface: auto` resolves from the effective profile.
- `sample` exposes 16 tools for bundled/local personal sample mode.
- `standard` exposes 21 tools for normal MongoDB-backed operation.
- `developer` exposes all 23 tools, including demo database seed/cleanup.
- Invalid `tools.surface` config exposes only `config_doctor` so setup can be
  diagnosed.

| Tool | Required inputs | Optional inputs | Success response | Persistence or external effects |
|---|---|---|---|---|
| `config_doctor` | None | `offline` | `ok`, `profile`, `generated_at`, `summary`, `checks`, `next_actions` | Read only; checks config, storage readiness, vector-search mode, and LLM provider readiness without LLM calls, embeddings, or writes. The default path may perform a bounded storage ping; `offline=true` skips it |
| `create_deal` | `company` | `industry`, `deal_size_krw`, `deal_size_status`, `deal_size_low_krw`, `deal_size_high_krw`, `deal_size_note`, `expected_close_date` | `ok`, `deal_id`, `company`, deal value fields, `expected_close_date`, `expected_close_date_source`, optional `analytics_snapshot` | Validates the initial deal-value classification, applies the configured close-date default when omitted, upserts one deal, initializes `discovery` stage history, and attempts a non-blocking analytics snapshot |
| `add_meeting` | `deal_id`, `date`, `raw_notes` | None | `ok`, `meeting_id`, `summary`, `meddpicc`, `meddpicc_latest`, `customer_themes`, `stage_suggestion`, `embedding_stored`, `usage`, optional `analytics_snapshot` | Calls LLM, appends a meeting, recalculates deal signals, optionally stores an embedding, upserts the deal, and attempts a non-blocking analytics snapshot |
| `update_stage` | `deal_id`, `new_stage` | `actual_close_date` | `ok`, `deal_id`, `old_stage`, `new_stage`, `actual_close_date`, `days_in_previous_stage`, `stuck_threshold_days`, optional `analytics_snapshot` | Appends stage history, records the actual terminal date, recalculates stage-aware MEDDPICC gaps, upserts the deal, and attempts a non-blocking analytics snapshot |
| `update_deal` | `deal_id` | `confirmed_by_user`, value fields, `company`, `industry`, `expected_close_date`, `actual_close_date`, `close_reason`, `update_note` | `ok`, `deal_id`, `company`, old/new value snapshots, old/new metadata snapshots, `changed_fields`, `changed_value_fields`, `changed_metadata_fields`, `storage_written` | Requires explicit user confirmation, updates confirmed value/metadata fields only, appends value/metadata history entries, and upserts the deal |
| `archive_deal` | `deal_id`, `expected_company`, `archive_reason` | `confirmed_by_user` | `ok`, `deal_id`, `company`, `already_archived`, `old_deal`, `new_deal`, `storage_written` | Requires explicit confirmation and exact company match, marks the deal archived, appends archive history, and hides it from default BI/read paths |
| `restore_deal` | `deal_id`, `expected_company`, `restore_reason` | `confirmed_by_user` | `ok`, `deal_id`, `company`, `already_active`, `old_deal`, `new_deal`, `storage_written` | Requires explicit confirmation and exact company match, clears archived state, appends restore history, and returns the deal to default BI/read paths |
| `delete_deal` | `deal_id`, `expected_company`, `delete_reason` | `confirmed_by_user`, `dry_run` | `ok`, `deal_id`, `company`, `dry_run`, `can_delete`, `would_delete`, `blocked_reason`, `storage_written` or `deleted_count`, `audit_id`, `deleted_at` | Defaults to dry-run. Real hard delete requires confirmation, exact company match, a non-empty reason, and an already archived deal. Writes a safe delete audit snapshot before deleting |
| `migrate_local_data` | None | `target_database`, `confirmed_by_user`, `dry_run`, `overwrite` | `ok`, `migration_type`, `dry_run`, `storage_written`, `source`, `target`, `options`, `counts`, `deals`, `warnings` | Migrates only user-created local personal deals from `storage.local_data_dir` to MongoDB. Defaults to dry-run, requires confirmation for writes, skips existing target deal ids unless `overwrite=true`, and never migrates bundled fixture records or local delete audit logs |
| `create_sample_data` | None | `dataset`, `demo_database`, `confirmed_by_user`, `dry_run`, `overwrite` | `ok`, `dataset`, `sample_batch_id`, `primary_database`, `demo_database`, `dry_run`, `existing_count`, `deal_count`, `preview`, `storage_written` | Defaults to dry-run. Actual writes require confirmation and write only to a demo database different from the primary database |
| `delete_sample_data` | None | `dataset`, `demo_database`, `confirmed_by_user`, `dry_run` | `ok`, `dataset`, `sample_batch_id`, `primary_database`, `demo_database`, `dry_run`, `existing_count`, `sample_deals`, `storage_written` | Defaults to dry-run. Actual deletes require confirmation and delete only records with the known sample batch marker in the demo database |
| `get_deal` | `deal_id` | None | `ok`, `deal` | Read only; includes full meeting history and raw notes |
| `list_deals` | None | `stage`, `limit`, `as_of` | `ok`, `as_of`, `timezone`, `generated_at`, `deals`, `count`, `data_quality` | Read only; returns health, timing, attention, and field-quality results while excluding meeting raw notes |
| `get_metrics` | None | `metric_type`, `stage`, `industry`, `as_of`, `lookback_days` | `ok`, `metric_type`, `as_of`, `timezone`, `generated_at`, `filters`, metric-specific summary fields, `warnings` | Read only; `pipeline_health` uses the shared deal metric calculator and restricted deal projection; `pipeline_trend` uses `analytics_snapshots` and a restricted snapshot projection |
| `get_deal_gaps` | None | `as_of`, `stage`, `industry`, `deal_id`, `min_priority`, `limit` | `ok`, `as_of`, `timezone`, `generated_at`, `filters`, `summary`, `deals`, `warnings` | Read only; uses the restricted metric projection, prioritizes sales follow-up gaps, and excludes raw notes, contacts, and embeddings |
| `get_deal_review` | `deal_id` | `as_of` | `ok`, `as_of`, `timezone`, `generated_at`, `review` | Read only; uses the restricted metric projection, separates health quality from evidence coverage, returns v2 `assessment`, `actionable_gaps`, and `gap_observations`, suppresses uncalibrated win probability numbers, and excludes raw notes, contacts, and embeddings |
| `export_report` | None | `report_type`, `output_dir`, `stage`, `industry`, `as_of`, `lookback_days` | `ok`, `report_type`, `as_of`, `timezone`, `generated_at`, `filters`, `row_count`, `warnings`, `metrics`, `output_dir`, `artifacts`, `csv_path`, `markdown_path` | Reads through the report-specific restricted projection and writes local CSV/Markdown report artifacts |
| `get_insights` | `query_type` | `as_of` | `ok`, `query_type`, `as_of`, `timezone`, `generated_at`, query-specific aggregate fields | Read only over the current collection snapshot |
| `get_customer_themes` | None | `dimension`, `stage`, `industry`, `top_k` | `ok`, `filters`, `coverage`, `themes` | Read-only MongoDB counts and aggregation |
| `get_customer_theme_breakdown` | None | `dimension`, `stage`, `industry`, `group_by`, `top_k` | `ok`, `filters`, `summary`, `groups`, `warnings` | Read only; compares curated customer themes by stage, industry, or dimension using the restricted metric projection |
| `get_customer_theme_evidence` | `theme_key` | `dimension`, `stage`, `industry`, `limit`, `min_importance` | `ok`, `filters`, `summary`, `evidence`, `warnings` | Read only; returns curated customer-theme evidence snippets and excludes raw notes, contacts, and embeddings |
| `search_deals` | `query` | `limit` | `ok`, `query`, `result_count`, `results` | Generates a local query embedding and reads deal embeddings; may return a structured warmup response before search |
| `analyze_deal` | `deal_id` | None | `ok`, `deal_id`, `analysis`, `usage` | Calls LLM and attempts to persist `bd_strategy`; analysis still returns if that save fails |

`get_metrics.metric_type` currently supports:

- `pipeline_health`
- `pipeline_trend`

`create_deal` validates initial deal-value fields with the shared Part B metric
contract before storage. Valid `deal_size_status` values are `unknown`,
`rough_estimate`, `customer_budget`, `quoted`, and `strategic_zero`; zero is
valid only with `strategic_zero`. A bare `deal_size_krw: 0` returns a
preflight clarification error with retry options instead of saving. Explicit
`deal_size_status: unknown` with zero amount fields is normalized to a missing
amount before storage. A positive `deal_size_krw` without `deal_size_status`
also returns a preflight clarification error so new records do not enter BI as
unclassified amounts.

`update_deal` supports confirmed deal value fields plus selected metadata:
`company`, `industry`, `expected_close_date`, `actual_close_date`, and
`close_reason`. It requires `confirmed_by_user: true`. Value updates require a
non-empty `deal_size_note`; metadata updates require `update_note` or a
fallback `deal_size_note`. `expected_close_date` is allowed only on open deals
and sets `expected_close_date_source: user_provided`; `actual_close_date` is
allowed only on won/lost deals; `close_reason` is allowed only on lost deals.
It does not update `deal_stage`, meetings, contacts, or notes.

`archive_deal`, `restore_deal`, and `delete_deal` form the M4.3 lifecycle
safety layer. All three require exact `expected_company` matching after
trimming whitespace. `delete_deal` defaults to `dry_run: true`; actual hard
delete is allowed only after `archive_deal` has marked the deal archived and
`confirmed_by_user: true` is provided. The delete audit snapshot excludes
`_id`, `contacts`, `summary_embedding`, and `meetings.raw_notes`.

Default BI/read paths exclude archived deals with:

```json
{"archived": {"$ne": true}}
```

This is intentionally not `{"archived": false}` because legacy documents may
not have an `archived` field and must remain visible.

`create_sample_data` and `delete_sample_data` form the M4.4 onboarding/demo
sample-data layer. They use `mongodb.demo_database` by default
(`deal_intel_demo`) and reject any demo database equal to the primary
`mongodb.database`. Both tools default to `dry_run: true`; actual writes or
deletes require `confirmed_by_user: true`. `delete_sample_data` only deletes
documents matching both `is_sample: true` and the known `sample_batch_id`.
The first supported dataset is `weekly_pipeline_demo`.

`analytics_snapshots` form the M5.1-M5.5 trend foundation. `create_deal`,
`add_meeting`, and `update_stage` attempt to write one lightweight snapshot
after the source deal mutation succeeds. Snapshot writes are idempotent by
`event_id`; a duplicate event returns `inserted: false` and `duplicate: true`
instead of creating a second document. Snapshot failures do not fail the
original tool call; the response includes `analytics_snapshot.ok: false` with
`warning: analytics_snapshot_failed`. Snapshot documents exclude raw meeting
notes, contacts, and embeddings.

`get_metrics` accepts exact-match `stage` and `industry` filters. Invalid
metric types, invalid stages, invalid `as_of`, invalid trend `lookback_days`,
and invalid metric config fail before MongoDB storage access.
`pipeline_trend` defaults to `lookback_days: 7` and caps it at `365`. It
compares the latest per-deal snapshot at the start and end of the window,
dedupes duplicate `event_id` snapshots defensively, and returns insufficiency
warnings when the snapshot history is too sparse.

Atlas trend charts use the same `analytics_snapshots` source through the
versioned `pipeline_trend.v1.json` spec. The repository may execute read-only
aggregation smoke tests through `MongoDBClient.aggregate_analytics_snapshots()`;
it does not write dashboard objects to Atlas.

`get_deal_gaps` accepts exact-match `stage`, `industry`, and `deal_id` filters.
Valid `min_priority` values are `low`, `medium`, and `high`; default is
`medium`. `limit` defaults to `10` and is capped at `50`. When `deal_id` is
provided, the tool returns that deal regardless of priority and limit. Invalid
stages, invalid `as_of`, invalid priority, invalid limit, and invalid metric
config fail before MongoDB storage access. The tool is read-only and does not
call an LLM or embedding provider.

`export_report.report_type` currently supports:

- `weekly_pipeline`
- `pipeline_trend`

`export_report` accepts exact-match `stage` and `industry` filters. For
`pipeline_trend`, `lookback_days` defaults to `7` and is capped at `365`.
Invalid report types, invalid stages, invalid `as_of`, invalid
`lookback_days`, and invalid report/metric config fail before MongoDB storage
access. `weekly_pipeline` reads through `list_deals_for_metrics()`;
`pipeline_trend` reads through `list_analytics_snapshots()`.

`get_insights.query_type` currently supports:

- `pipeline_overview`
- `win_patterns`
- `loss_patterns`
- `compare_won_lost`
- `gap_frequency`
- `industry_benchmark`
- `stage_velocity`

`get_insights("pipeline_overview")` additionally returns the Milestone 1.2
shared summary surface:

- `kpis`
- `stage_breakdown`
- `health_bands`
- `attention_reasons`
- `pipeline_values`
- `win_rate`
- `data_quality`
- `warnings`

Compatibility aliases remain: `stages`, `total_deals`, and `total_size_krw`.
`total_size_krw` is now the Open pipeline value from the shared Part B
contract. The metrics read path uses a restricted projection that excludes
`_id`, `meetings.raw_notes`, `contacts`, and `summary_embedding`.

`get_customer_theme_breakdown` and `get_customer_theme_evidence` are read-only
M6 customer-theme surfaces. They use the restricted metric projection and only
return structured `customer_themes` fields. They do not call an LLM, do not use
embeddings, and do not expose raw meeting notes, contacts, or embeddings.

`search_deals` has additional preflight outcomes:

- `warming_up: true`, `retryable: true` while the local model is loading
- `warming_up: false` with `CONFIG_ERROR` when the embedding dependency is absent
- `warming_up: false` with `UPSTREAM_ERROR` when warmup fails or stalls

### Test Baseline

Command:

```powershell
& "$HOME\miniconda3\envs\event-intel\python.exe" -m pytest
```

Result:

```text
17 passed, 1 warning in 1.24s
```

The warning is an external OpenTelemetry `SelectableGroups` deprecation warning.

### Historical Ruff Baseline

Command:

```powershell
& "$HOME\miniconda3\envs\event-intel\python.exe" -m ruff check .
```

Milestone 0.1 initially measured 28 existing Ruff findings.

| Area | Findings |
|---|---:|
| `scripts/smoke_test.py` | 3 |
| `src/deal_intel/providers/llm.py` | 1 |
| `src/deal_intel/schema/meddpicc.py` | 17 |
| `src/deal_intel/storage/identifiers.py` | 1 |
| `src/deal_intel/tools/analyze_deal.py` | 1 |
| `src/deal_intel/tools/create_deal.py` | 1 |
| `src/deal_intel/tools/get_insights.py` | 2 |
| `src/deal_intel/tools/list_deals.py` | 1 |
| `src/deal_intel/tools/update_stage.py` | 1 |

#### Current Quality Gate

Before Milestone 1 started, all 28 findings were resolved. The current gate is:

```text
pytest -> 128 passed
ruff check . -> All checks passed
wheel build -> passed
FastMCP runtime surface exposure -> sample 16 tools, standard 21 tools,
developer 23 tools
MongoDB Atlas read smoke -> passed
```

Future subtasks must keep this gate passing.

### Privacy and Scope

- Baseline inspection must not print `MONGODB_URI`, OAuth tokens, raw meeting
  notes, contacts, or embeddings.
- Live verification is read only unless a later subtask explicitly requires a
  write smoke.
- This milestone does not change metrics, tool behavior, schemas, or stored
  documents.

### Gate Result

Milestone 0.1 passed:

- Runtime tool registration captured
- Existing success and error contracts recorded
- Full test baseline passed
- Existing Ruff debt isolated
- Existing Ruff debt subsequently resolved
- Live Atlas read path passed
