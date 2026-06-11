# Storage Backends

This document records the storage contract for the MongoDB-free zero-config
sample and local-personal modes.

## Goal

The team/shared production backend remains MongoDB Atlas. The local sample
backend is a separate zero-config experience for demos, friend reviews, agent
smoke tests, and future lightweight personal use when `MONGODB_URI`, Atlas
Charts, paid API keys, and Atlas Vector Search are not available.

The first sample-mode milestone was intentionally read-only. It proved that the
core BI and deal-review read paths can run over bundled fixture data. Sample
mode now also supports a small mutable local personal dataset for users who want
to try their own data before MongoDB.

## Backend Kinds

| Backend | Purpose | Persistence | Scope |
|---|---|---|---|
| `mongo_full` | Production and real demos backed by Atlas | MongoDB Atlas | Full read/write/admin surface |
| `local_sample_mvp` | Zero-config sample experience | Bundled/local fixture data | Read-first BI/review/report surface |
| `local_personal` | Personal trial mode | Local resettable user data file | Safe create/update/stage/lifecycle surface plus LLM-backed note intake when configured |

Runtime config uses:

```yaml
storage:
  backend: mongo        # mongo | local_sample
```

`DEAL_INTEL_STORAGE_BACKEND=local_sample` can be used for temporary smoke
tests without editing user config.

Local personal storage should default to:

```yaml
storage:
  local_data_dir: ~/.deal-intel/local-data
```

Users can override this directory through config tools before mutable local
storage writes any data.

## Local Sample MVP Contract

The code contract lives in `src/deal_intel/storage/backend.py`.

`local_sample_mvp` must implement:

| Method | Consumers | Notes |
|---|---|---|
| `ping()` | startup diagnostics, zero-config smoke | Should not require network access |
| `get_deal(deal_id)` | `get_deal` | Returns one safe sample deal |
| `list_deals(stage=None, limit=50)` | `list_deals` | Supports stage filter and limit |
| `list_deals_for_metrics()` | `get_metrics`, `get_deal_gaps`, `get_deal_review`, customer theme tools, weekly report, natural question smoke | Primary LLM-free BI/read path; excludes legacy raw notes, canonical raw content, contacts, and vectors |
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

## Local Personal Contract

Local personal storage adds enough persistence for a user to try their own
small dataset without MongoDB. Implemented methods:

- `upsert_deal` (implemented for local personal `deals.json`)
- `insert_delete_audit_log` (implemented for local personal
  `delete_audit_logs.json`)
- `hard_delete_deal` (implemented for local personal `deals.json`)

Supported safe mutation tools:

- `create_deal` (supported by local personal `upsert_deal`)
- `add_interaction` (supported by local personal `upsert_deal`; requires a
  ready LLM provider, stores source metadata, skips embeddings in local sample
  mode, and persists canonical raw interaction content)
- `update_stage` (supported by local personal `upsert_deal`)
- `update_deal` (supported by local personal `upsert_deal`)
- `archive_deal` (supported by local personal `upsert_deal`)
- `restore_deal` (supported by local personal `upsert_deal`)
- `delete_deal` (supported by local personal audit + hard delete)

This target still defers heavier analysis and semantic-search paths until their
runtime requirements are clear:

- `analyze_deal`
- `search_deals`

Reset/export behavior must be explicit before local personal writes ship:

- Local data lives under `storage.local_data_dir`.
- `deal-intel local-data status` displays the resolved directory and counts.
- `deal-intel local-data export` writes a secret-safe JSON snapshot.
- `deal-intel local-data reset` is dry-run by default.
- `deal-intel local-data reset --force` clears only local personal deals.
- Local delete audit logs are retained after reset.
- Local personal data to MongoDB migration is available through
  `migrate_local_data` and `deal-intel local-data migrate-to-mongo`.

Active read policy:

- When no user-created local deals exist, read paths use the bundled fixture.
- When at least one user-created local deal exists, read paths use only local
  personal deals.
- The bundled fixture remains immutable and archived in the package; it is not
  mixed into the working dataset after local personal data exists.
- `get_deal` should not find bundled fixture deal ids while local personal
  deals are active.
- Pipeline trend fixture snapshots are also hidden while local personal deals
  are active until local personal snapshots are implemented.

Implemented write policy:

- `LocalPersonalStore` writes `deals.json` with schema version and dataset
  metadata.
- Writes strip legacy `raw_notes`, `contacts`, and `summary_embedding` before
  persistence. Canonical `interactions.raw_content` is retained in local
  personal storage so future redaction/security modules can process it.
- `create_deal`, `update_stage`, and `update_deal` can persist through
  `LocalSampleClient.upsert_deal`.
- `add_interaction` persists canonical interactions with summaries, source
  metadata, raw content, MEDDPICC signals, and customer themes for
  user-created local deals, including meeting notes via
  `interaction_type: meeting`. Outbound and internal-only content is stored as
  unconfirmed interaction evidence and does not update the scoring snapshot by
  default. Local sample mode does not initialize or store embeddings.
- `archive_deal` and `restore_deal` can persist through
  `LocalSampleClient.upsert_deal`.
- `delete_deal` writes an audit entry to `delete_audit_logs.json` before
  removing a local personal deal from `deals.json`.
- Delete audit logs are preserved independently from `deals.json` and should
  not be removed by future local reset unless the user explicitly asks for an
  audit reset.
- `local-data reset --force` writes an empty `deals.json`, which keeps the
  bundled fixture archived instead of re-mixing fictional data into active
  reads.
- `local-data export` includes local personal deals and delete audit logs, but
  not legacy raw notes, contacts, or embeddings. Canonical raw content may be
  present in local deal details.
- Bundled fixture deal ids are read-only and cannot be promoted into local
  personal storage through lifecycle writes.
- Bundled fixture deal ids are also read-only for `add_interaction`; users
  should create their own local deal before adding notes or interactions.
- Analytics snapshot writes are still deferred, so these local writes do not
  yet create local trend snapshots.

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

## Local To Mongo Migration

Local personal writes can now graduate to MongoDB-backed `full` mode through a
dry-run-first migration path.

Behavior:

- Dry-run by default.
- Never migrate bundled fictional fixture records.
- Read only user-created records from `storage.local_data_dir`.
- Require target MongoDB readiness before classifying rows.
- Require explicit confirmation before any Mongo write.
- Preserve `deal_id` values where possible.
- Skip existing target `deal_id` values by default.
- Overwrite existing target `deal_id` values only when `overwrite=true`.
- Return create, overwrite, skipped, and written counts.
- Keep local delete audit logs local; they are not migrated by this command.

CLI:

```bash
deal-intel local-data migrate-to-mongo
deal-intel local-data migrate-to-mongo --apply
deal-intel local-data migrate-to-mongo --apply --overwrite
```

Non-goals:

- No automatic background sync.
- No two-way sync.
- No migration from MongoDB back into local personal storage.

## Privacy Contract

The local sample backend should preserve the same safe read posture as
`MongoDBClient.list_deals_for_metrics()`:

- no `meetings.raw_notes`
- no `interactions.raw_content`
- no `contacts`
- no `summary_embedding`

Fixture data may include curated meeting summaries, source-aware interaction
metadata, and customer-theme evidence, but not raw notes, raw interaction
content, or private contacts.

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
- curated meeting summaries, source-aware interaction metadata, and
  customer-theme evidence included
- trend snapshots included for a 7-day pipeline movement smoke
- no `meetings.raw_notes`, `interactions.raw_content`, `contacts`, or
  `summary_embedding`

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
