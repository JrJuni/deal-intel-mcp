# Storage Backends

This document records the storage contract for the MongoDB-free zero-config
sample mode.

## Goal

The production backend remains MongoDB Atlas. The local sample backend is a
separate zero-config experience for demos, friend reviews, and agent smoke
tests when `MONGODB_URI`, Atlas Charts, paid API keys, and Atlas Vector Search
are not available.

The first sample-mode milestone is intentionally read-only. It proves that the
core BI and deal-review read paths can run over bundled fixture data before any
local write/reset semantics are introduced.

## Backend Kinds

| Backend | Purpose | Persistence | Scope |
|---|---|---|---|
| `mongo_full` | Production and real demos backed by Atlas | MongoDB Atlas | Full read/write/admin surface |
| `local_sample_mvp` | Zero-config sample experience | Bundled/local fixture data | Read-only BI/review/report surface |

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

## Deferred From Local Sample MVP

The first sample backend does not need to implement:

- Mongo aggregation compatibility: `aggregate_deals`,
  `aggregate_analytics_snapshots`
- Legacy aggregate-heavy tools: `get_customer_themes`,
  non-`pipeline_overview` `get_insights` query types
- Semantic/vector search: `get_deals_for_search`, `search_by_embedding`
- Writes: `upsert_deal`, `upsert_deals`, `upsert_analytics_snapshot`,
  `insert_delete_audit_log`, `hard_delete_deal`, `delete_sample_deals`
- Admin paths: `ensure_indexes`, `ensure_vector_index`

Those paths can be added after the read-only experience is stable. In
particular, local write support requires separate product decisions about
where mutable sample state lives, whether it survives restarts, and how reset
works.

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

The fixture is intentionally not a `LocalSampleClient` yet. It is the data
pack that the next step can wrap with the read-only storage backend contract.

## Verification

Current contract checks:

- `tests/test_storage_backend_contract.py`
- `tests/test_zero_config_sample_fixture.py`
- `SampleReadStorageBackend` runtime protocol
- `backend_capability_report(...)`
- `validate_backend_capabilities(...)`

The next implementation step is to add a `LocalSampleClient` that satisfies
`local_sample_mvp`, serves this fixture, and then runs zero-config smoke tests
without `MONGODB_URI`.
