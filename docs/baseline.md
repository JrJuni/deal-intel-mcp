# Verification Baseline

BI and reporting work must compare its behavior against this baseline before
changing shared deal or MCP behavior.

## 2026-06-08 - Milestone 0.1

### Runtime

- Python: 3.11.15 (Python 3.11 conda environment)
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

The Python server keeps all 28 handler functions available internally, but MCP
clients see a config-filtered tool surface:

- `tools.surface: auto` resolves from the effective profile.
- `sample` exposes 21 tools for bundled/local personal sample mode.
- `standard` exposes 25 tools for normal MongoDB-backed operation.
- `developer` exposes all 28 tools, including demo database seed/cleanup.
- Invalid `tools.surface` config exposes only `config_doctor` and
  `update_config` so setup can be diagnosed and repaired.

| Tool | Required inputs | Optional inputs | Success response | Persistence or external effects |
|---|---|---|---|---|
| `config_doctor` | None | `offline` | `ok`, `profile`, `generated_at`, `summary`, `checks`, `next_actions` | Read only; checks config, storage readiness, vector-search mode, and LLM provider readiness without LLM calls, embeddings, or writes. The default path may perform a bounded storage ping; `offline=true` skips it |
| `update_config` | None | `dry_run`, `confirmed_by_user`, `llm_provider`, `chatgpt_oauth_model`, `openai_api_model`, `reporting_output_dir`, `reporting_timezone`, `tools_surface` | `ok`, `command`, `user_config_path`, `dry_run`, `changed_fields`, `doctor`, `storage_written`, `backup_path` | Dry-run-first local file write. Applies only allowlisted non-secret settings to `~/.deal-intel/config.yaml`; real writes require `confirmed_by_user=true`; rejects MongoDB URIs and API-key shaped values |
| `create_deal` | `company` | `industry`, `industry_tags`, `customer_segment`, `deal_size_amount`, `deal_size_currency`, `deal_size_status`, `deal_size_low_amount`, `deal_size_high_amount`, `deal_size_note`, `expected_close_date` | `ok`, `deal_id`, `company`, `industry`, `industry_tags`, `customer_segment`, deal value fields, `expected_close_date`, `expected_close_date_source`, `taxonomy_warnings`, optional `analytics_snapshot` | Validates the initial deal-value classification, normalizes industry metadata, applies the configured close-date default when omitted, upserts one deal, initializes `discovery` stage history, and attempts a non-blocking analytics snapshot |
| `add_meeting` | `deal_id`, `date`, `raw_notes` | None | `ok`, `interaction_id`, `meeting_id`, `summary`, `meddpicc`, `meddpicc_latest`, `customer_themes`, `stage_suggestion`, `embedding_stored`, `usage`, `usage_summary`, optional `analytics_snapshot` | Deprecated developer-surface compatibility alias over `add_interaction` with `interaction_type: meeting`. Calls LLM, writes an `interaction_type: meeting` record under `deal.interactions`, stores `llm_usage` metadata, recalculates deal signals, optionally stores an embedding for MongoDB-backed data, upserts the deal, and attempts a non-blocking analytics snapshot. New clients should call `add_interaction` directly |
| `add_interaction` | `deal_id`, `date`, `interaction_type`, `direction`, `content` | `participants`, `subject`, `source_confidence`, `custom_fields_json` | `ok`, `interaction_id`, `meeting_id`, `interaction_type`, `direction`, `source_confidence`, `source_policy`, `participants`, `subject`, `summary`, `meddpicc`, `unconfirmed_meddpicc`, `meddpicc_latest`, `customer_themes`, `unconfirmed_customer_themes`, `scoring_applied`, `stage_suggestion`, `embedding_stored`, `usage`, `usage_summary`, optional `analytics_snapshot` | Calls LLM, appends a canonical `deal.interactions` record, stores source metadata, `raw_content`, and `llm_usage` metadata, recalculates deal signals only when the source is scoring-eligible, optionally stores an embedding for MongoDB-backed data, upserts the deal, and attempts a non-blocking analytics snapshot. `source_policy` explains whether the input became confirmed scoring evidence or stored-unconfirmed context. `outbound_unconfirmed` and `internal` evidence is stored but does not update MEDDPICC health or customer-theme counts by default. Custom interaction types must be registered in config |
| `update_stage` | `deal_id`, `new_stage` | `actual_close_date` | `ok`, `deal_id`, `old_stage`, `new_stage`, `actual_close_date`, `days_in_previous_stage`, `stuck_threshold_days`, optional `analytics_snapshot` | Appends stage history, records the actual terminal date, recalculates stage-aware MEDDPICC gaps, upserts the deal, and attempts a non-blocking analytics snapshot |
| `update_deal` | `deal_id` | `confirmed_by_user`, value fields, `company`, `industry`, `industry_tags`, `customer_segment`, `expected_close_date`, `actual_close_date`, `close_reason`, `update_note` | `ok`, `deal_id`, `company`, old/new value snapshots, old/new metadata snapshots, `changed_fields`, `changed_value_fields`, `changed_metadata_fields`, `storage_written`, `taxonomy_warnings` | Requires explicit user confirmation, updates confirmed value/metadata fields only, normalizes industry metadata, appends value/metadata history entries, and upserts the deal |
| `archive_deal` | `deal_id`, `expected_company`, `archive_reason` | `confirmed_by_user` | `ok`, `deal_id`, `company`, `already_archived`, `old_deal`, `new_deal`, `storage_written` | Requires explicit confirmation and exact company match, marks the deal archived, appends archive history, and hides it from default BI/read paths |
| `restore_deal` | `deal_id`, `expected_company`, `restore_reason` | `confirmed_by_user` | `ok`, `deal_id`, `company`, `already_active`, `old_deal`, `new_deal`, `storage_written` | Requires explicit confirmation and exact company match, clears archived state, appends restore history, and returns the deal to default BI/read paths |
| `delete_deal` | `deal_id`, `expected_company`, `delete_reason` | `confirmed_by_user`, `dry_run` | `ok`, `deal_id`, `company`, `dry_run`, `can_delete`, `would_delete`, `blocked_reason`, `storage_written` or `deleted_count`, `audit_id`, `deleted_at` | Defaults to dry-run. Real hard delete requires confirmation, exact company match, a non-empty reason, and an already archived deal. Writes a safe delete audit snapshot before deleting |
| `migrate_local_data` | None | `target_database`, `confirmed_by_user`, `dry_run`, `overwrite` | `ok`, `migration_type`, `dry_run`, `storage_written`, `source`, `target`, `options`, `counts`, `deals`, `warnings` | Migrates only user-created local personal deals from `storage.local_data_dir` to MongoDB. Defaults to dry-run, requires confirmation for writes, skips existing target deal ids unless `overwrite=true`, and never migrates bundled fixture records or local delete audit logs |
| `create_sample_data` | None | `dataset`, `demo_database`, `confirmed_by_user`, `dry_run`, `overwrite` | `ok`, `dataset`, `sample_batch_id`, `primary_database`, `demo_database`, `dry_run`, `existing_count`, `deal_count`, `preview`, `storage_written` | Defaults to dry-run. Actual writes require confirmation and write only to a demo database different from the primary database |
| `delete_sample_data` | None | `dataset`, `demo_database`, `confirmed_by_user`, `dry_run` | `ok`, `dataset`, `sample_batch_id`, `primary_database`, `demo_database`, `dry_run`, `existing_count`, `sample_deals`, `storage_written` | Defaults to dry-run. Actual deletes require confirmation and delete only records with the known sample batch marker in the demo database |
| `get_deal` | `deal_id` | None | `ok`, `deal` | Read only; includes full deal detail, including stored interactions and any legacy meeting history |
| `list_deals` | None | `stage`, `limit`, `as_of` | `ok`, `as_of`, `timezone`, `generated_at`, `deals`, `count`, `data_quality` | Read only; returns health, timing, attention, and field-quality results while excluding meeting raw notes and interaction raw content |
| `get_metrics` | None | `metric_type`, `stage`, `industry`, `as_of`, `lookback_days` | `ok`, `metric_type`, `as_of`, `timezone`, `generated_at`, `filters`, metric-specific summary fields, `warnings` | Read only; `pipeline_health` uses the shared deal metric calculator and restricted deal projection; `pipeline_trend` uses `analytics_snapshots` and a restricted snapshot projection |
| `get_deal_gaps` | None | `as_of`, `stage`, `industry`, `deal_id`, `min_priority`, `limit` | `ok`, `as_of`, `timezone`, `generated_at`, `filters`, `summary`, `deals`, `warnings` | Read only; uses the restricted metric projection, prioritizes sales follow-up gaps, annotates gaps with `actionability`/`cta_policy`, exposes `actionable_gaps` and `gap_observations`, and excludes raw notes, raw interaction content, contacts, and embeddings |
| `get_deal_review` | `deal_id` | `as_of` | `ok`, `as_of`, `timezone`, `generated_at`, `review` | Read only; uses the restricted metric projection, separates health quality from evidence coverage, returns v2 `assessment`, `actionable_gaps`, and `gap_observations`, suppresses uncalibrated win probability numbers, and excludes raw notes, raw interaction content, contacts, and embeddings |
| `get_usage` | None | `since`, `until` | `ok`, `generated_at`, `filters`, `summary`, `by_provider`, `by_tool`, `by_operation`, `entries`, `pricing_policy`, `warnings` | Read only; summarizes persisted server-side LLM usage metadata without prompts, raw notes, raw interaction content, contacts, API keys, OAuth tokens, MongoDB URIs, or embeddings. ChatGPT OAuth is reported as zero incremental API estimate; API-provider cost is estimated only when `usage.pricing` is configured |
| `export_report` | None | `report_type`, `output_dir`, `stage`, `industry`, `as_of`, `lookback_days` | `ok`, `report_type`, `as_of`, `timezone`, `generated_at`, `filters`, `row_count`, `warnings`, `metrics`, `output_dir`, `artifacts`, `csv_path`, `markdown_path` | Reads through the report-specific restricted projection and writes local CSV/Markdown report artifacts |
| `get_user_memory` | None | `category`, `custom_doc_slug`, `limit` | `ok`, `memory_dir`, `filters`, `documents`, `summary`, `warnings` | Read only; reads safe Markdown files from `user_docs/` or configured `user_memory.dir` for assistant context loading. Excludes sample templates from broad reads |
| `record_user_memory` | `content` | `category`, `custom_doc_slug`, `title`, `source`, `importance`, `tags` | `ok`, `entry_id`, `memory_dir`, `path`, `category`, `document`, `is_custom_document`, `bytes_written`, `secret_scan` | Appends durable user feedback to safe Markdown files under `user_docs/` or configured `user_memory.dir`; rejects unsafe paths, non-Markdown custom slugs, and secret-shaped content before writing |
| `get_insights` | `query_type` | `as_of` | `ok`, `query_type`, `as_of`, `timezone`, `generated_at`, query-specific aggregate fields | Read only over the current collection snapshot |
| `get_customer_themes` | None | `dimension`, `stage`, `industry`, `top_k` | `ok`, `filters`, `coverage`, `themes` | Read-only MongoDB counts and aggregation. The `industry` filter matches primary `industry` or `industry_tags` |
| `get_customer_theme_breakdown` | None | `dimension`, `stage`, `industry`, `group_by`, `top_k` | `ok`, `filters`, `summary`, `groups`, `warnings` | Read only; compares curated customer themes by stage, primary industry, industry tag, or dimension using the restricted metric projection. The `industry` filter matches primary `industry` or `industry_tags` |
| `get_customer_theme_evidence` | `theme_key` | `dimension`, `stage`, `industry`, `limit`, `min_importance`, `interaction_type`, `source_confidence` | `ok`, `filters`, `summary`, `evidence`, `warnings` | Read only; returns curated customer-theme evidence snippets plus safe source metadata (`industry_tags`, `interaction_type`, `source_confidence`, `source_label`, `subject`), can filter by source type/confidence and primary-or-tag industry, treats legacy meeting evidence as `interaction_type=meeting`, and excludes raw notes, raw interaction content, contacts, and embeddings |
| `search_deals` | `query` | `limit` | `ok`, `query`, `result_count`, `results` | Generates a local query embedding and reads deal embeddings; may return a structured warmup response before search |
| `analyze_deal` | `deal_id` | None | `ok`, `deal_id`, `analysis`, `usage`, `usage_summary` | Calls LLM and attempts to persist `bd_strategy` plus `bd_strategy_usage`; analysis still returns if that save fails |

`get_metrics.metric_type` currently supports:

- `pipeline_health`
- `pipeline_trend`

`create_deal` validates initial deal-value fields with the shared Part B metric
contract before storage. Valid `deal_size_status` values are `unknown`,
`rough_estimate`, `customer_budget`, `quoted`, and `strategic_zero`; zero is
valid only with `strategic_zero`. A bare `deal_size_amount: 0` returns a
preflight clarification error with retry options instead of saving. Explicit
`deal_size_status: unknown` with zero amount fields is normalized to a missing
amount before storage. A positive `deal_size_amount` without `deal_size_status`
also returns a preflight clarification error so new records do not enter BI as
unclassified amounts. `deal_size_currency` is optional and defaults from
`deal_value.default_currency`.

`industry` is the single primary business vertical. `industry_tags` is the
multi-select vertical tag list for cross-industry accounts; the primary
`industry` is always included in `industry_tags`. Use `customer_segment` for
maturity, account segment, ownership, or lifecycle labels such as startup,
Series B, enterprise, public_sector, or Pre-IPO. This split keeps industry
dashboards and theme breakdowns from mixing verticals with company stage.
Primary industry input is normalized against the shared taxonomy when possible.
Tool entrypoints such as `create_deal`, `update_deal`, and
`backfill-industry-tags` first try to normalize recognizable mixed labels into
primary industry, `industry_tags`, and `customer_segment`. The user-facing
taxonomy UX is draft-first and correction-friendly: non-empty unmapped labels
become low-confidence custom drafts, and missing industries become either a
company-name inference candidate or an AI/web research task with an
`update_deal` follow-up. Low-level schema helpers remain stricter so internal
callers can still opt into explicit validation when they need it.

`update_deal` supports confirmed deal value fields plus selected metadata:
`company`, `industry`, `industry_tags`, `customer_segment`,
`expected_close_date`, `actual_close_date`, and `close_reason`. It requires
`confirmed_by_user: true`. Value updates require a non-empty `deal_size_note`;
metadata updates require `update_note` or a fallback `deal_size_note`.
`expected_close_date` is allowed only on open deals and sets
`expected_close_date_source: user_provided`; `actual_close_date` is allowed only
on won/lost deals; `close_reason` is allowed only on lost deals. It does not
update `deal_stage`, interactions, legacy meetings, contacts, or notes.

`archive_deal`, `restore_deal`, and `delete_deal` form the M4.3 lifecycle
safety layer. All three require exact `expected_company` matching after
trimming whitespace. `delete_deal` defaults to `dry_run: true`; actual hard
delete is allowed only after `archive_deal` has marked the deal archived and
`confirmed_by_user: true` is provided. The delete audit snapshot excludes
`_id`, `contacts`, `summary_embedding`, `meetings.raw_notes`, and
`interactions.raw_content`.

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
`add_interaction`, `update_stage`, and the deprecated `add_meeting` alias attempt to write one
lightweight snapshot after the source deal mutation succeeds. Snapshot writes
are idempotent by
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

Compatibility aliases remain: `stages`, `total_deals`, and `total_size_amount`.
`total_size_amount` is now the Open pipeline value from the shared Part B
contract. The metrics read path uses a restricted projection that excludes
`_id`, `meetings.raw_notes`, `interactions.raw_content`, `contacts`, and
`summary_embedding`.

`get_customer_theme_breakdown` and `get_customer_theme_evidence` are read-only
M6 customer-theme surfaces. They use the restricted metric projection and only
return structured `customer_themes` fields. Evidence rows include safe source
labels derived from structured metadata so assistants can distinguish meetings,
email threads, and user interviews without reading raw content. They do not
call an LLM, do not use embeddings, and do not expose raw meeting notes, raw
interaction content, contacts, or embeddings.

`search_deals` has additional preflight outcomes:

- `warming_up: true`, `retryable: true` while the local model is loading
- `warming_up: false` with `CONFIG_ERROR` when the embedding dependency is absent
- `warming_up: false` with `UPSTREAM_ERROR` when warmup fails or stalls

### Test Baseline

Command:

```powershell
& "$HOME\miniconda3\envs\deal-intel\python.exe" -m pytest -q --basetemp=.tmp\pytest-full
```

Result:

```text
17 passed, 1 warning in 1.24s
```

The warning is an external OpenTelemetry `SelectableGroups` deprecation warning.

### Historical Ruff Baseline

Command:

```powershell
& "$HOME\miniconda3\envs\deal-intel\python.exe" -m ruff check .
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
FastMCP runtime surface exposure -> sample 21 tools, standard 25 tools,
developer 28 tools
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
