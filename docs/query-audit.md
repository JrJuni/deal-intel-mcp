# Query Audit

This document records the current MongoDB read shapes, projection policy, and
index implications for cost and performance work.

## Scope

O1 is an audit only. It does not change runtime behavior. Follow-up hardening
belongs in O2/O3:

- O2: BI read projection hardening.
- O3: index contract and `ensure_indexes` cleanup.

## Principles

- `deals` is the source-of-truth collection.
- LLM/embedding paths may read heavier fields when they explicitly need them.
- BI, metrics, reports, dashboard smokes, and quality surfaces should use
  restricted projections and avoid `meetings.raw_notes`, `contacts`, and
  `summary_embedding`.
- User-requested single-deal detail is allowed to return full deal content
  through `get_deal`.
- Atlas Charts specs should apply the same visibility rules as MCP metrics,
  especially `archived != true`.

## Storage Method Inventory

| Method | Main Consumers | Query Shape | Projection | Index Coverage | Audit Notes |
|---|---|---|---|---|---|
| `get_deal(deal_id)` | `get_deal`, mutation tools | `{deal_id}` | `_id` excluded only | `deal_id_unique` | Intentional full-detail path. May include raw meeting notes because the user asked for one deal. |
| `list_deals(stage, limit)` | `list_deals` | `archived != true`, optional `deal_stage`, sort `updated_at desc`, limit | excludes `_id`, `meetings.raw_notes` | partial: `archived_updated`, `stage_updated` | Candidate for O2 allowlist or exclusion of `contacts` and `summary_embedding`. Candidate for O3 compound index `(archived, deal_stage, updated_at desc)`. |
| `list_deals_for_metrics()` | `get_metrics:pipeline_health`, `get_deal_gaps`, `get_deal_review`, `get_customer_theme_breakdown`, `get_customer_theme_evidence`, `export_report:weekly_pipeline`, `get_insights:pipeline_overview` | `archived != true` | excludes `_id`, `meetings.raw_notes`, `contacts`, `summary_embedding` | `archived_updated` can support archived filter | Primary LLM-free BI read path. Safe today, but still blacklist-style; O2 can convert to allowlist. |
| `list_analytics_snapshots(start,end,stage,industry)` | `get_metrics:pipeline_trend`, `export_report:pipeline_trend` | `as_of` range, optional `deal_stage`, optional `industry`, sort `as_of`, `occurred_at` | allowlist-style projection | partial: `analytics_snapshot_deal_occurred`, `analytics_snapshot_event_occurred`; no direct `as_of` index | Candidate for O3 index `(as_of, occurred_at, created_at)` and optionally `(as_of, deal_stage, industry)`. |
| `aggregate_deals(pipeline)` | legacy `get_customer_themes`, Atlas chart smoke/crosscheck | caller-supplied aggregation | caller-supplied | depends on pipeline | Needs pipeline-by-pipeline audit. Customer Themes specs are safer than Weekly Pipeline specs. |
| `aggregate_analytics_snapshots(pipeline)` | Atlas trend chart smoke | `as_of` range and sort in chart specs | aggregation projects only chart rows | same as trend snapshots | O3 should align index to `as_of` range + sort. |
| `count_deals(query)` | `get_customer_themes`, sample tooling | archived/stage/industry/theme presence depending caller | count only | partial: `stage_customer_theme`; no archived/industry prefix | Low risk at current scale. Candidate for customer theme index after taxonomy settles. |
| `get_deals_for_search()` | `search_deals` Python cosine | `archived != true`, `summary_embedding exists` | allowlist including `summary_embedding` for scoring | no dedicated embedding-exists index | Intentional vector read. Standard/pro only. O(n) Python cosine is acceptable until larger data or Atlas Vector Search. |
| `search_by_embedding()` | `search_deals` Atlas mode | `$vectorSearch`, then `archived != true` | allowlist output | Atlas Vector Search index | Pro/M10+ path. Keep out of sample/full default unless intentionally configured. |
| `list_deals_for_theme_backfill()` | maintainer backfill CLI | `archived != true` | `_id` excluded only | `archived_updated` | Intentional heavy LLM maintenance path because it needs raw notes. Not a BI path. |

## MCP Read Path Map

| Surface | Tool/Command | Storage Path | Sensitivity Status |
|---|---|---|---|
| Detail | `get_deal` | `get_deal` | Full single-deal detail by design. |
| List | `list_deals` | `list_deals` | Raw notes excluded; contacts/vectors should be excluded or allowlisted in O2. |
| Metrics | `get_metrics:pipeline_health` | `list_deals_for_metrics` | Safe restricted projection. |
| Metrics | `get_metrics:pipeline_trend` | `list_analytics_snapshots` | Safe allowlist projection. |
| Reports | `export_report:weekly_pipeline` | `list_deals_for_metrics` | Safe restricted projection. |
| Reports | `export_report:pipeline_trend` | `list_analytics_snapshots` | Safe allowlist projection. |
| Quality | `get_deal_gaps` | `list_deals_for_metrics` | Safe restricted projection. |
| Quality | `get_deal_review` | `list_deals_for_metrics` | Safe restricted projection. |
| Themes | `get_customer_theme_breakdown` | `list_deals_for_metrics` | Safe restricted projection. |
| Themes | `get_customer_theme_evidence` | `list_deals_for_metrics` | Safe restricted projection. |
| Themes legacy | `get_customer_themes` | `count_deals`, `aggregate_deals` | Aggregation path is curated; keep raw fields out of projection stages. |
| Search | `search_deals` | `get_deals_for_search` or `search_by_embedding` | Intentional embedding read for scoring; output strips vectors. |
| Maintenance | `backfill-customer-themes` | `list_deals_for_theme_backfill` | Intentional raw-note LLM path; keep out of BI/sample-first flow. |

## Atlas Charts Findings

### Weekly Pipeline Review

The Weekly Pipeline chart spec computes useful summaries but does not currently
apply a leading `archived != true` visibility filter consistently. This creates
two risks:

- archived deals may still be counted in Atlas charts,
- Charts can drift from `get_metrics`, CSV, and MCP read paths after lifecycle
  tools archive deals.

O2 should add a leading `$match: {archived: {$ne: true}}` to every Weekly
Pipeline chart pipeline and update chart/crosscheck tests.

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
exposure. O3 should consider an index that matches this range + sort shape.

## Current Index Inventory

`MongoDBClient.ensure_indexes()` currently creates:

- `deals.deal_id_unique`: `(deal_id)`, unique.
- `deals.stage_updated`: `(deal_stage, updated_at desc)`.
- `deals.updated_desc`: `(updated_at desc)`.
- `deals.archived_updated`: `(archived, updated_at desc)`.
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

## O2 Candidates

1. Convert `list_deals()` to a safer projection.
   - Minimum: also exclude `contacts` and `summary_embedding`.
   - Better: introduce a user-list allowlist projection.
2. Convert `list_deals_for_metrics()` from blacklist-style to allowlist-style.
   This would make accidental future heavy fields safe by default.
3. Add `archived != true` to every Weekly Pipeline Atlas chart pipeline.
4. Add tests that inspect rendered Weekly Pipeline chart pipelines for the
   visibility filter and sensitive-field exclusion.

## O3 Candidates

1. Add or document a compound index for list views:
   `(archived, deal_stage, updated_at desc)`.
2. Add or document an analytics snapshot index for trend reads:
   `(as_of, occurred_at, created_at)`.
3. Consider customer theme indexes only after the taxonomy cleanup:
   `(archived, deal_stage, customer_themes.dimension,
   customer_themes.theme_key)`, and optionally industry-prefixed variants.
4. Keep Atlas Vector Search index creation in the pro path, not first-run
   sample/full defaults.

## Current Risk Summary

- High: Weekly Pipeline Atlas Charts may include archived deals.
- Medium: `list_deals()` reads more fields than the list response needs.
- Medium: trend chart/snapshot range reads do not have a direct `as_of` index.
- Low at current scale: legacy aggregation paths can scan the small `deals`
  collection.
- Intentional: `get_deal` and customer-theme backfill can read full/raw fields.
