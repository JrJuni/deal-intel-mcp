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

### MCP Tool Contracts

| Tool | Required inputs | Optional inputs | Success response | Persistence or external effects |
|---|---|---|---|---|
| `create_deal` | `company` | `industry`, `deal_size_krw`, `deal_size_status`, `deal_size_low_krw`, `deal_size_high_krw`, `deal_size_note`, `expected_close_date` | `ok`, `deal_id`, `company`, deal value fields, `expected_close_date`, `expected_close_date_source` | Validates the initial deal-value classification, applies the configured close-date default when omitted, upserts one deal, and initializes `discovery` stage history |
| `add_meeting` | `deal_id`, `date`, `raw_notes` | None | `ok`, `meeting_id`, `summary`, `meddpicc`, `meddpicc_latest`, `customer_themes`, `stage_suggestion`, `embedding_stored`, `usage` | Calls LLM, appends a meeting, recalculates deal signals, optionally stores an embedding, and upserts the deal |
| `update_stage` | `deal_id`, `new_stage` | `actual_close_date` | `ok`, `deal_id`, `old_stage`, `new_stage`, `actual_close_date`, `days_in_previous_stage`, `stuck_threshold_days` | Appends stage history, records the actual terminal date, recalculates stage-aware MEDDPICC gaps, and upserts the deal |
| `update_deal` | `deal_id` | `confirmed_by_user`, value fields, `company`, `industry`, `expected_close_date`, `actual_close_date`, `close_reason`, `update_note` | `ok`, `deal_id`, `company`, old/new value snapshots, old/new metadata snapshots, `changed_fields`, `changed_value_fields`, `changed_metadata_fields`, `storage_written` | Requires explicit user confirmation, updates confirmed value/metadata fields only, appends value/metadata history entries, and upserts the deal |
| `archive_deal` | `deal_id`, `expected_company`, `archive_reason` | `confirmed_by_user` | `ok`, `deal_id`, `company`, `already_archived`, `old_deal`, `new_deal`, `storage_written` | Requires explicit confirmation and exact company match, marks the deal archived, appends archive history, and hides it from default BI/read paths |
| `restore_deal` | `deal_id`, `expected_company`, `restore_reason` | `confirmed_by_user` | `ok`, `deal_id`, `company`, `already_active`, `old_deal`, `new_deal`, `storage_written` | Requires explicit confirmation and exact company match, clears archived state, appends restore history, and returns the deal to default BI/read paths |
| `delete_deal` | `deal_id`, `expected_company`, `delete_reason` | `confirmed_by_user`, `dry_run` | `ok`, `deal_id`, `company`, `dry_run`, `can_delete`, `would_delete`, `blocked_reason`, `storage_written` or `deleted_count`, `audit_id`, `deleted_at` | Defaults to dry-run. Real hard delete requires confirmation, exact company match, a non-empty reason, and an already archived deal. Writes a safe delete audit snapshot before deleting |
| `create_sample_data` | None | `dataset`, `demo_database`, `confirmed_by_user`, `dry_run`, `overwrite` | `ok`, `dataset`, `sample_batch_id`, `primary_database`, `demo_database`, `dry_run`, `existing_count`, `deal_count`, `preview`, `storage_written` | Defaults to dry-run. Actual writes require confirmation and write only to a demo database different from the primary database |
| `delete_sample_data` | None | `dataset`, `demo_database`, `confirmed_by_user`, `dry_run` | `ok`, `dataset`, `sample_batch_id`, `primary_database`, `demo_database`, `dry_run`, `existing_count`, `sample_deals`, `storage_written` | Defaults to dry-run. Actual deletes require confirmation and delete only records with the known sample batch marker in the demo database |
| `get_deal` | `deal_id` | None | `ok`, `deal` | Read only; includes full meeting history and raw notes |
| `list_deals` | None | `stage`, `limit`, `as_of` | `ok`, `as_of`, `timezone`, `generated_at`, `deals`, `count`, `data_quality` | Read only; returns health, timing, attention, and field-quality results while excluding meeting raw notes |
| `get_metrics` | None | `metric_type`, `stage`, `industry`, `as_of` | `ok`, `metric_type`, `as_of`, `timezone`, `generated_at`, `filters`, `kpis`, `stage_breakdown`, `health_bands`, `attention_reasons`, `pipeline_values`, `win_rate`, `data_quality`, `warnings` | Read only; uses the shared metric calculator and restricted metric projection |
| `get_deal_gaps` | None | `as_of`, `stage`, `industry`, `deal_id`, `min_priority`, `limit` | `ok`, `as_of`, `timezone`, `generated_at`, `filters`, `summary`, `deals`, `warnings` | Read only; uses the restricted metric projection, prioritizes sales follow-up gaps, and excludes raw notes, contacts, and embeddings |
| `export_report` | None | `report_type`, `output_dir`, `stage`, `industry`, `as_of` | `ok`, `report_type`, `as_of`, `timezone`, `generated_at`, `filters`, `row_count`, `warnings`, `metrics`, `output_dir`, `artifacts`, `csv_path`, `markdown_path` | Reads through the restricted metric projection and writes local CSV/Markdown report artifacts |
| `get_insights` | `query_type` | `as_of` | `ok`, `query_type`, `as_of`, `timezone`, `generated_at`, query-specific aggregate fields | Read only over the current collection snapshot |
| `get_customer_themes` | None | `dimension`, `stage`, `industry`, `top_k` | `ok`, `filters`, `coverage`, `themes` | Read-only MongoDB counts and aggregation |
| `search_deals` | `query` | `limit` | `ok`, `query`, `result_count`, `results` | Generates a local query embedding and reads deal embeddings; may return a structured warmup response before search |
| `analyze_deal` | `deal_id` | None | `ok`, `deal_id`, `analysis`, `usage` | Calls LLM and attempts to persist `bd_strategy`; analysis still returns if that save fails |

`get_metrics.metric_type` currently supports:

- `pipeline_health`

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

`get_metrics` accepts exact-match `stage` and `industry` filters. Invalid
metric types, invalid stages, invalid `as_of`, and invalid metric config fail
before MongoDB storage access.

`get_deal_gaps` accepts exact-match `stage`, `industry`, and `deal_id` filters.
Valid `min_priority` values are `low`, `medium`, and `high`; default is
`medium`. `limit` defaults to `10` and is capped at `50`. When `deal_id` is
provided, the tool returns that deal regardless of priority and limit. Invalid
stages, invalid `as_of`, invalid priority, invalid limit, and invalid metric
config fail before MongoDB storage access. The tool is read-only and does not
call an LLM or embedding provider.

`export_report.report_type` currently supports:

- `weekly_pipeline`

`export_report` accepts exact-match `stage` and `industry` filters. Invalid
report types, invalid stages, invalid `as_of`, and invalid report/metric config
fail before MongoDB storage access.

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

Milestone 0.1 최초 측정 결과는 28개 기존 finding이었다.

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

Milestone 1 시작 전에 28개 finding을 모두 해결했다. 현재 gate는 다음과 같다.

```text
pytest -> 128 passed
ruff check . -> All checks passed
wheel build -> passed
FastMCP runtime registration -> 18 tools
MongoDB Atlas read smoke -> passed
```

이후 서브 태스크는 이 gate를 유지해야 한다.

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
