# Query Audit

This document records the current MongoDB read shapes, projection policy, and
index implications for cost and performance work.

## Scope

O1 was an audit only. Follow-up hardening has started in O2/O3:

- O2: BI read projection hardening.
- O3: index contract and `ensure_indexes` cleanup.

## Principles

- `deals` is the source-of-truth collection.
- LLM/embedding paths may read heavier fields when they explicitly need them.
- BI, metrics, reports, dashboard smokes, and quality surfaces should use
  restricted projections and avoid `meetings.raw_notes`,
  `interactions.raw_content`, `contacts`, and `summary_embedding`.
- User-requested single-deal detail is allowed to return full deal content
  through `get_deal`.
- Atlas Charts specs should apply the same visibility rules as MCP metrics,
  especially `archived != true`.

## Storage Method Inventory

| Method | Main Consumers | Query Shape | Projection | Index Coverage | Audit Notes |
|---|---|---|---|---|---|
| `get_deal(deal_id)` | `get_deal`, mutation tools | `{deal_id}` | `_id` excluded only | `deal_id_unique` | Intentional full-detail path. May include raw interaction content because the user asked for one deal. |
| `list_deals(stage, limit)` | `list_deals` | `archived != true`, optional `deal_stage`, sort `updated_at desc`, limit | excludes `_id`, `meetings.raw_notes`, `interactions.raw_content`, `contacts`, `summary_embedding` | `archived_updated`, `stage_updated`, `archived_stage_updated` | Hardened in O2. P3.2 added canonical raw-content exclusion. O3 added the compound list-view index. |
| `list_deals_for_metrics()` | `get_metrics:pipeline_health`, `get_deal_gaps`, `get_deal_review`, `get_customer_themes`, `get_customer_theme_breakdown`, `get_customer_theme_evidence`, `export_report:weekly_pipeline`, `export_data`, `get_insights:pipeline_overview` | `archived != true` | excludes `_id`, `meetings.raw_notes`, `interactions.raw_content`, `contacts`, `summary_embedding` | `archived_updated` can support archived filter | Primary deterministic BI/data-export read path. Safe today, but still blacklist-style. Allowlist conversion is deferred until BI/review/report field contracts stabilize. |
| `list_analytics_snapshots(start,end,stage,industry)` | `get_metrics:pipeline_trend`, `export_report:pipeline_trend` | `as_of` range, optional `deal_stage`, optional `industry`, sort `as_of`, `occurred_at` | allowlist-style projection | `analytics_snapshot_as_of_occurred_created`, plus event/deal indexes | O3 added the trend range/sort index. Optional stage/industry-prefixed variants are deferred until trend filters prove hot. |
| `aggregate_deals(pipeline)` | Atlas chart smoke/crosscheck | caller-supplied aggregation | caller-supplied | depends on pipeline | Needs pipeline-by-pipeline audit. Customer Themes specs are safer than Weekly Pipeline specs. |
| `aggregate_analytics_snapshots(pipeline)` | Atlas trend chart smoke | `as_of` range and sort in chart specs | aggregation projects only chart rows | same as trend snapshots | O3 aligns `ensure_indexes()` to the trend range + sort shape. |
| `count_deals(query)` | sample tooling | archived/stage/industry/theme presence depending caller | count only | partial: `stage_customer_theme`; no archived/industry prefix | Low risk at current scale. Candidate for customer theme index after taxonomy settles. |
| `get_deals_for_search()` | `search_deals` Python cosine | `archived != true`, `summary_embedding exists` | allowlist including `summary_embedding` for scoring | no dedicated embedding-exists index | Intentional vector read. Standard/pro only. O(n) Python cosine is acceptable until larger data or Atlas Vector Search. |
| `search_by_embedding()` | `search_deals` Atlas mode | `$vectorSearch`, then `archived != true` | allowlist output | Atlas Vector Search index | Pro/M10+ path. Keep out of sample/full default unless intentionally configured. |
| `list_deals_for_theme_backfill()` | maintainer backfill CLI | `archived != true` | `_id` excluded only | `archived_updated` | Intentional heavy LLM maintenance path because it needs raw notes. Not a BI path. |
| `list_deals_for_qualification_reextract()` | `backfill-qualification-reextract` CLI / `backfill_qualification_reextract` MCP | `archived != true`, optional limit | excludes `_id`, `meetings.raw_notes`, `contacts`, `summary_embedding`; intentionally includes `interactions.raw_content` | `archived_updated` | Intentional QF-v2 LLM maintenance path for historical active-framework extraction. Not a BI/reporting path. |

## MCP Read Path Map

| Surface | Tool/Command | Storage Path | Sensitivity Status |
|---|---|---|---|
| Detail | `get_deal` | `get_deal` | Full single-deal detail by design. |
| List | `list_deals` | `list_deals` | Legacy raw notes, canonical raw content, contacts, and vectors are excluded. |
| Metrics | `get_metrics:pipeline_health` | `list_deals_for_metrics` | Safe restricted projection. |
| Metrics | `get_metrics:pipeline_trend` | `list_analytics_snapshots` | Safe allowlist projection. |
| Reports | `export_report:weekly_pipeline` | `list_deals_for_metrics` | Safe restricted projection. |
| Data exports | `export_data` | `list_deals_for_metrics` | Safe restricted projection. |
| Reports | `export_report:pipeline_trend` | `list_analytics_snapshots` | Safe allowlist projection. |
| Quality | `get_deal_gaps` | `list_deals_for_metrics` | Safe restricted projection. |
| Quality | `get_deal_review` | `list_deals_for_metrics` | Safe restricted projection. |
| Themes | `get_customer_themes` | `list_deals_for_metrics` | Safe restricted projection. |
| Themes | `get_customer_theme_breakdown` | `list_deals_for_metrics` | Safe restricted projection. |
| Themes | `get_customer_theme_evidence` | `list_deals_for_metrics` | Safe restricted projection. |
| Search | `search_deals` | `get_deals_for_search` or `search_by_embedding` | Intentional embedding read for scoring; output strips vectors. |
| Maintenance | `backfill-customer-themes` | `list_deals_for_theme_backfill` | Intentional raw-note LLM path; keep out of BI/sample-first flow. |
| Maintenance | `backfill-qualification-reextract` CLI / `backfill_qualification_reextract` MCP | `list_deals_for_qualification_reextract` | Intentional raw-content LLM path; dry-run first and response must not expose raw content. |

## Atlas Charts Findings

### Weekly Pipeline Review

The Weekly Pipeline chart spec now applies a leading
`$match: {archived: {$ne: true}}` to every chart pipeline. This keeps Atlas
Charts aligned with `get_metrics`, CSV, and MCP read paths after lifecycle
tools archive deals.

### Customer Themes Review

The Customer Themes chart spec already applies:

- `archived != true`,
- active-stage scope excluding `won`/`lost`,
- curated `customer_themes.evidence`,
- projection of extracted evidence instead of raw meeting notes.

The main non-performance issue is taxonomy quality: `industry` currently mixes
industry and maturity/stage descriptors. That is already tracked in backlog.

### Pipeline Trend Review

Trend charts read `analytics_snapshots` by `as_of` range and sort by
`as_of`, `occurred_at`, and `created_at`. There is no raw-note/contact/vector
exposure. O3 added an index that matches this range + sort shape.

## Current Index Inventory

`MongoDBClient.ensure_indexes()` currently creates:

- `deals.deal_id_unique`: `(deal_id)`, unique.
- `deals.stage_updated`: `(deal_stage, updated_at desc)`.
- `deals.updated_desc`: `(updated_at desc)`.
- `deals.archived_updated`: `(archived, updated_at desc)`.
- `deals.archived_stage_updated`: `(archived, deal_stage, updated_at desc)`.
- `deals.health_pct_desc`: `(meddpicc_latest.health_pct desc)`.
- `deals.stage_customer_theme`: `(deal_stage, customer_themes.theme_key)`.
- `deals.sample_batch`: `(is_sample, sample_batch_id)`.
- `delete_audit_logs.delete_audit_deal_deleted`: `(deal_id, deleted_at desc)`.
- `analytics_snapshots.analytics_snapshot_event_id_unique`: `(event_id)`,
  unique.
- `analytics_snapshots.analytics_snapshot_deal_occurred`: `(deal_id,
  occurred_at desc)`.
- `analytics_snapshots.analytics_snapshot_event_occurred`: `(event_type,
  occurred_at desc)`.
- `analytics_snapshots.analytics_snapshot_as_of_occurred_created`: `(as_of,
  occurred_at, created_at)`.

## O2 Outcome

Completed:

1. `list_deals()` now excludes `contacts` and `summary_embedding` in addition
   to `_id`, `meetings.raw_notes`, and `interactions.raw_content`.
2. Every Weekly Pipeline Atlas chart pipeline starts with
   `archived != true`.
3. Tests inspect the list projection and rendered Weekly Pipeline chart
   visibility filter.

Deferred:

- Convert `list_deals_for_metrics()` from blacklist-style to allowlist-style.
  The current blacklist projection excludes known heavy/sensitive fields and
  keeps BI/review/report development flexible. Revisit when metric contracts
  reach v1 stability or data size makes broad BI reads costly.

## O3 Outcome

Completed:

1. Added `deals.archived_stage_updated` for list views:
   `(archived, deal_stage, updated_at desc)`.
2. Added `analytics_snapshots.analytics_snapshot_as_of_occurred_created` for
   trend reads: `(as_of, occurred_at, created_at)`.
3. Added targeted tests that lock the new index contracts while confirming
   existing unique/lifecycle indexes remain present.

Deferred:

1. Consider customer theme indexes only after the taxonomy cleanup:
   `(archived, deal_stage, customer_themes.dimension,
   customer_themes.theme_key)`, and optionally industry-prefixed variants.
2. Keep Atlas Vector Search index creation in the pro path, not first-run
   sample/full defaults.

## F-Mongo Outcome

Completed:

1. Moved ordinary MongoDB index definitions into
   `src/deal_intel/mongo_contracts.py`.
2. `MongoDBClient.ensure_indexes()` now applies that shared contract.
3. Added `MongoDBClient.check_indexes()` for read-only index drift detection.
4. Added a permissive v1 `deals` collection validator resource and
   `MongoDBClient.check_deals_schema_validation()`.
5. Added permissive v1 validator resources for `analytics_snapshots` and
   `delete_audit_logs`.
6. Added generic collection schema helpers and read-only doctor checks for all
   managed validator contracts.
7. Added CLI admin surfaces:
   - `deal-intel mongo doctor`
   - `deal-intel mongo apply-indexes`
   - `deal-intel mongo apply-schema`

Notes:

- `mongo doctor` is read-only.
- `apply-indexes` and `apply-schema` are dry-run unless `--apply` is passed.
- `apply-schema` defaults to `deals`; use `--collection all` to inspect or
  apply all managed validators.
- The v1 validators are `warn + moderate`, not hard `error`
  enforcement, because the MVP document model is still changing.
- No new read-path indexes were added in this slice; the goal was to make the
  existing contract inspectable and safer to operate.

## Current Risk Summary

- Fixed in O2: Weekly Pipeline Atlas Charts exclude archived deals.
- Fixed in O2: `list_deals()` excludes contacts and vectors.
- Fixed in O3: trend chart/snapshot range reads have a direct `as_of` index.
- Fixed in O3: list views have a compound archived/stage/updated index.
- Fixed in F-Mongo: ordinary index drift and managed collection schema
  validator drift can be diagnosed through CLI without writing to MongoDB.
- Low at current scale: legacy aggregation paths can scan the small `deals`
  collection.
- Deferred: `list_deals_for_metrics()` remains blacklist-style until metric
  field contracts stabilize.
- Intentional: `get_deal` and customer-theme backfill can read full/raw fields.
