# Storage Backends

This document records the storage contract for the MongoDB-free zero-config
sample and local-personal modes.

## Goal

The team/shared production backend remains MongoDB Atlas. The local sample
backend is a separate zero-config experience for demos, friend reviews, agent
smoke tests, and future lightweight personal use when `MONGODB_URI`, Atlas
Charts, paid API keys, and Atlas Vector Search are not available.

The first sample-mode milestone was intentionally read-only. It proved that the
core BI and deal-review read paths can run over bundled fixture data. The next
sample-mode storage milestone should add mutable/resettable local personal data
for users who want to try their own small dataset before MongoDB.

## Backend Kinds

| Backend | Purpose | Persistence | Scope |
|---|---|---|---|
| `mongo_full` | Production and real demos backed by Atlas | MongoDB Atlas | Full read/write/admin surface |
| `local_sample_mvp` | Zero-config sample experience | Bundled/local fixture data | Read-first BI/review/report surface |
| `local_personal` | Future personal trial mode | Local resettable user data file | Safe non-LLM create/update/stage/lifecycle surface |

Runtime config uses:

```yaml
storage:
  backend: mongo        # mongo | local_sample
```

`DEAL_INTEL_STORAGE_BACKEND=local_sample` can be used for temporary smoke
tests without editing user config.

## Local Sample MVP Contract

The code contract lives in `src/deal_intel/storage/backend.py`.

`local_sample_mvp` must implement:

| Method | Consumers | Notes |
|---|---|---|
| `ping()` | startup diagnostics, zero-config smoke | Should not require network access |
| `get_deal(deal_id)` | `get_deal` | Returns one safe sample deal |
| `list_deals(stage=None, limit=50)` | `list_deals` | Supports stage filter and limit |
| `list_deals_for_metrics()` | `get_metrics`, `get_deal_gaps`, `get_deal_review`, customer theme tools, weekly report, natural question smoke | Primary LLM-free BI/read path; excludes raw notes, contacts, vectors |
| `list_analytics_snapshots(start_date, end_date, stage=None, industry=None)` | `pipeline_trend`, trend report | Returns bundled fixture snapshots for sample mode |

This contract supports the first zero-config read stack:

- `list_deals`
- `get_deal`
- `get_metrics(metric_type="pipeline_health")`
- `get_metrics(metric_type="pipeline_trend")` with sparse-history warnings
- `get_deal_gaps`
- `get_deal_review`
- `get_customer_theme_breakdown`
- `get_customer_theme_evidence`
- `export_report(report_type="weekly_pipeline")`
- `export_report(report_type="pipeline_trend")`
- `smoke-natural-questions`

## Local Personal Target

The next local storage target should add enough persistence for a user to try
their own small dataset without MongoDB. Candidate methods:

- `upsert_deal`
- `upsert_analytics_snapshot`
- `insert_delete_audit_log`
- `hard_delete_deal`

Candidate MCP tools to enable after that storage exists:

- `create_deal`
- `update_stage`
- `update_deal`
- `archive_deal`
- `restore_deal`
- `delete_deal`

This target should still defer LLM-heavy and semantic-search paths until their
runtime requirements are clear:

- `add_meeting`
- `analyze_deal`
- `search_deals`

Reset/export behavior must be explicit before local personal writes ship:

- where the local data file lives,
- whether bundled fixture data and personal data are merged or separated,
- how users reset only their personal data,
- whether local delete audit logs are retained after reset.

## Still Deferred From Local Sample

The sample/local-personal backend does not need to implement:

- Mongo aggregation compatibility: `aggregate_deals`,
  `aggregate_analytics_snapshots`
- Legacy aggregate-heavy tools: `get_customer_themes`,
  non-`pipeline_overview` `get_insights` query types
- Semantic/vector search: `get_deals_for_search`, `search_by_embedding`
- Atlas demo database writes: `upsert_deals`, `delete_sample_deals`
- Admin paths: `ensure_indexes`, `ensure_vector_index`

Those paths are not required for lightweight personal use.

## Privacy Contract

The local sample backend should preserve the same safe read posture as
`MongoDBClient.list_deals_for_metrics()`:

- no `meetings.raw_notes`
- no `contacts`
- no `summary_embedding`

Fixture data may include curated meeting summaries and customer-theme evidence,
but not raw notes or private contacts.

## Bundled Zero-Config Fixture

Z2 adds the bundled fixture in
`src/deal_intel/storage/local_sample_fixture.py`.

It provides:

- `load_zero_config_sample_deals()`
- `load_zero_config_sample_snapshots()`
- `build_zero_config_sample_summary()`
- `validate_zero_config_sample_fixture()`

Fixture contract:

- dataset: `zero_config_sample`
- version: `2026-06-10.v1`
- as-of date: `2026-06-10`
- trend window start: `2026-06-03`
- at least 10 fictional deals
- all canonical stages represented:
  `discovery`, `qualification`, `proposal`, `negotiation`, `stalled`,
  `won`, `lost`
- all deal value statuses represented:
  `unknown`, `rough_estimate`, `customer_budget`, `quoted`,
  `strategic_zero`
- curated meeting summaries and customer-theme evidence included
- trend snapshots included for a 7-day pipeline movement smoke
- no `meetings.raw_notes`, `contacts`, or `summary_embedding`

The fixture remains immutable. Future local personal data should be stored as a
separate resettable overlay rather than mutating the bundled fixture.

## LocalSampleClient

Z3 adds `src/deal_intel/storage/local_sample.py`.

`LocalSampleClient` wraps the bundled fixture and satisfies the
`local_sample_mvp` read contract:

- `ping()`
- `get_deal(deal_id)`
- `list_deals(stage=None, limit=50)`
- `list_deals_for_metrics()`
- `list_analytics_snapshots(start_date, end_date, stage=None, industry=None)`

When `storage.backend` is `local_sample`, `_context.mongo()` returns this local
backend instead of `MongoDBClient`. The existing function name is kept for tool
compatibility, but the runtime behavior is now storage-backend selection rather
than Mongo-only construction.

Local sample mode skips Mongo driver preload, Mongo index creation, and
embedding warmup at MCP startup. `search_deals` returns a structured
unsupported-mode response before touching the embedding provider because
semantic search is outside the current sample MVP.

## Startup Diagnostics And Quickstart

Z4 adds explicit user-facing diagnostics for MongoDB-free startup.

When `storage.backend` is `mongo` and `MONGODB_URI` is missing,
`MongoDBClient.ping()` now returns:

- `status: missing_uri`
- `storage_backend: mongo`
- the configured database name
- a message explaining that Atlas-backed storage needs `MONGODB_URI`
- a `sample_mode_hint` with the temporary env var and persistent config shape

The same hint is used by the missing-URI runtime error so MCP startup or CLI
smoke failures point users toward the sample path instead of failing silently.

The new CLI command is:

```powershell
& "$HOME\miniconda3\envs\event-intel\python.exe" -m deal_intel.cli storage-status
```

Temporary sample mode:

```powershell
$env:DEAL_INTEL_STORAGE_BACKEND='local_sample'
```

Persistent sample mode:

```yaml
storage:
  backend: local_sample
```

`storage-status --json` is intended for installer checks and agent smoke tests.
It exits with code `1` when Mongo storage is selected but not ready, and exits
with code `0` in local sample mode.

## Verification

Current contract checks:

- `tests/test_storage_backend_contract.py`
- `tests/test_zero_config_sample_fixture.py`
- `tests/test_storage_diagnostics.py`
- `SampleReadStorageBackend` runtime protocol
- `backend_capability_report(...)`
- `validate_backend_capabilities(...)`

Next local-sample work should focus on mutable/resettable local personal state,
not on expanding the production Mongo path.
