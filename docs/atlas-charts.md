# Atlas Charts Dashboard

This document records the Atlas Charts setup path for the `Weekly Pipeline
Review`, `Pipeline Trend Review`, and `Customer Themes Review` dashboards in
MongoDB Atlas Charts.

Metric definitions remain in [metrics.md](metrics.md). Report/CSV contracts
remain in [reports.md](reports.md).

## Scope

- Dashboard titles:
  - `Weekly Pipeline Review`
  - `Pipeline Trend Review`
  - `Customer Themes Review`
- Data sources:
  - `TestCluster` / `deal_intel` / `deals`
  - `TestCluster` / `deal_intel` / `analytics_snapshots`
- Versioned specs:
  - [weekly_pipeline_review.v1.json](../atlas/charts/weekly_pipeline_review.v1.json)
  - [pipeline_trend.v1.json](../atlas/charts/pipeline_trend.v1.json)
  - [customer_themes.v1.json](../atlas/charts/customer_themes.v1.json)
- Renderer: `deal_intel.reports.atlas_charts`
- CLI helper: `deal-intel render-atlas-dashboard`
- LLM / embedding: none
- MongoDB writes: none from this repository

Atlas UI changes are manual because Atlas Charts dashboard objects live inside
MongoDB Atlas. The repository stores the source aggregation pipelines and the
exact command used to render config placeholders.

Official Atlas Charts references:

- [Dashboards](https://www.mongodb.com/docs/charts/dashboards/)
- [Build Charts](https://www.mongodb.com/docs/charts/build-charts/)
- [Run Aggregation Pipelines on Your Data](https://www.mongodb.com/docs/charts/aggregation-pipeline/)

## Render The Pipelines

Always render placeholders before pasting a pipeline into Atlas Charts.

Full dashboard spec:

```bash
~/miniconda3/envs/event-intel/python.exe -m deal_intel.cli render-atlas-dashboard --as-of 2026-06-09 --output outputs/atlas_charts/weekly_pipeline_review_20260609.json
```

Pipeline trend dashboard spec:

```bash
~/miniconda3/envs/event-intel/python.exe -m deal_intel.cli render-atlas-dashboard --dashboard pipeline_trend --as-of 2026-06-10 --lookback-days 7 --output outputs/atlas_charts/pipeline_trend_20260610.json
```

Customer themes dashboard spec:

```bash
~/miniconda3/envs/event-intel/python.exe -m deal_intel.cli render-atlas-dashboard --dashboard customer_themes --as-of 2026-06-10 --output outputs/atlas_charts/customer_themes_20260610.json
```

Single chart pipeline:

```bash
~/miniconda3/envs/event-intel/python.exe -m deal_intel.cli render-atlas-dashboard --as-of 2026-06-09 --chart-id pipeline_kpis
```

Pipeline trend single chart pipeline:

```bash
~/miniconda3/envs/event-intel/python.exe -m deal_intel.cli render-atlas-dashboard --dashboard pipeline_trend --as-of 2026-06-10 --lookback-days 7 --chart-id trend_kpis
```

Customer themes single chart pipeline:

```bash
~/miniconda3/envs/event-intel/python.exe -m deal_intel.cli render-atlas-dashboard --dashboard customer_themes --as-of 2026-06-10 --chart-id theme_overview
```

The single-chart output is already a JSON array, so it can be pasted directly
into the Atlas Charts Query bar.

Rendered defaults on 2026-06-09:

```json
{
  "as_of_datetime": "2026-06-09T00:00:00Z",
  "healthy_min": 70.0,
  "watch_min": 40.0,
  "overdue_grace_days": 0,
  "stuck_days": {
    "discovery": 7,
    "qualification": 14,
    "proposal": 21,
    "negotiation": 30
  }
}
```

## Create The Dashboard

1. In MongoDB Atlas, open the project that contains `TestCluster`.
2. Open Atlas Charts:
   - From Data Explorer, select `deal_intel.deals` and click `Visualize Your Data`; or
   - From the Atlas sidebar, open `Visualization`, then `Project Dashboards`.
3. Create a dashboard named `Weekly Pipeline Review`.
4. Add each chart below using data source `deal_intel.deals`.
5. In the Chart Builder Query bar, paste the rendered pipeline for that chart
   and click `Apply`.
6. Save each chart back to the `Weekly Pipeline Review` dashboard.

If Atlas shows the free-tier Charts banner, that is expected on M0 and is not a
blocker for this MVP dashboard.

## Create The Trend Dashboard

1. In MongoDB Atlas, open the project that contains `TestCluster`.
2. Open Atlas Charts.
3. Create a dashboard named `Pipeline Trend Review`.
4. Add each chart below using data source `deal_intel.analytics_snapshots`.
5. In the Chart Builder Query bar, paste the rendered pipeline for that chart
   and click `Apply`.
6. Save each chart back to the `Pipeline Trend Review` dashboard.

If the snapshot history is still sparse, `trend_kpis` will still render a
single row with zeros/nulls and `trend_delta_bars` will render the known metric
delta rows. That is expected until enough deal events create snapshots.

## Create The Customer Themes Dashboard

1. In MongoDB Atlas, open the project that contains `TestCluster`.
2. Open Atlas Charts.
3. Create a dashboard named `Customer Themes Review`.
4. Add each chart below using data source `deal_intel.deals`.
5. In the Chart Builder Query bar, paste the rendered pipeline for that chart
   and click `Apply`.
6. Save each chart back to the `Customer Themes Review` dashboard.

This dashboard is intentionally exploratory. It should help answer:

- Which customer pains are most common across active deals?
- Which decision criteria dominate each stage?
- Which industries have different pain patterns?
- Which curated evidence snippets justify the theme ranking?

## Chart Contract

Weekly Pipeline chart pipelines start with:

```json
{"$match": {"archived": {"$ne": true}}}
```

If you already created the dashboard manually in Atlas, re-render and re-paste
the Weekly Pipeline chart pipelines after this contract changes. Existing Atlas
Charts do not automatically update from repository JSON files.

| Chart ID | Title | Chart Type | Primary Fields |
|---|---|---|---|
| `pipeline_kpis` | Pipeline KPIs | Table | `deal_count`, `active_deal_count`, `open_deal_count`, `active_pipeline_value_krw`, `open_pipeline_value_krw`, `avg_health_pct`, `health_coverage_pct`, `stuck_deal_count`, `overdue_deal_count`, `attention_deal_count` |
| `stage_breakdown` | Stage Breakdown | Bar or Table | `stage`, `count`, `pipeline_value_krw`, `avg_health_pct`, `health_coverage_pct`, `stuck_count`, `overdue_count` |
| `health_bands` | Health Bands | Donut | `health_band`, `count` |
| `attention_deals` | Stuck / Overdue / At Risk Deals | Table | `company`, `industry`, `deal_stage`, `deal_size_krw`, `expected_close_date`, `days_in_stage`, `is_stuck`, `is_overdue`, `health_pct`, `health_band`, `attention_reasons` |
| `meddpicc_gap_distribution` | MEDDPICC Gap Distribution | Bar | `gap`, `count` |

## Trend Chart Contract

| Chart ID | Title | Chart Type | Primary Fields |
|---|---|---|---|
| `trend_kpis` | Pipeline Trend KPIs | Table | `window_start`, `window_end`, `lookback_days`, `snapshot_count`, start/end/delta fields for active/open count, open pipeline value, avg health, attention, won, lost |
| `trend_delta_bars` | Pipeline Trend Delta | Bar or Table | `metric`, `start_value`, `end_value`, `delta` |

## Customer Themes Chart Contract

| Chart ID | Title | Chart Type | Primary Fields |
|---|---|---|---|
| `theme_overview` | Top Customer Themes | Bar or Table | `theme_key`, `label`, `deal_count`, `avg_importance` |
| `decision_criteria_by_stage` | Decision Criteria By Stage | Grouped Bar or Table | `stage`, `theme_key`, `label`, `count`, `avg_importance` |
| `pain_by_industry` | Pain By Industry | Grouped Bar or Table | `industry`, `theme_key`, `label`, `count`, `avg_importance` |
| `theme_evidence_drilldown` | Theme Evidence Drill-down | Table | `company`, `industry`, `deal_stage`, `theme_key`, `label`, `dimension`, `importance`, `evidence`, `interaction_type`, `source_confidence`, `source_label`, `subject`, `interaction_date` |

Suggested customer themes layout:

1. Top row: `theme_overview`
2. Middle row: `decision_criteria_by_stage`, `pain_by_industry`
3. Bottom row: `theme_evidence_drilldown`

Suggested trend layout:

1. Top row: `trend_kpis`
2. Bottom row: `trend_delta_bars`

Suggested layout:

1. Top row: `pipeline_kpis`
2. Middle row: `stage_breakdown`, `health_bands`
3. Bottom row: `attention_deals`, `meddpicc_gap_distribution`

## Verification Checklist

After creating the dashboard:

- No rendered pipeline contains `{{...}}` placeholders.
- `pipeline_kpis.open_pipeline_value_krw` matches
  `get_metrics(metric_type="pipeline_health").kpis.open_pipeline_value_krw`.
- `pipeline_kpis.active_pipeline_value_krw` matches the same `get_metrics`
  result.
- `pipeline_kpis.avg_health_pct`, `health_coverage_pct`, `stuck_deal_count`,
  `overdue_deal_count`, and `attention_deal_count` match `get_metrics`.
- `stage_breakdown` stage order is:
  `discovery`, `qualification`, `proposal`, `negotiation`, `stalled`, `won`,
  `lost`.
- `attention_deals` contains no `meetings.raw_notes`,
  `interactions.raw_content`, `contacts`, or `summary_embedding`.
- `Pipeline Trend Review` uses `analytics_snapshots`, not `deals`.
- `trend_kpis` and `trend_delta_bars` contain no raw notes, contacts, or
  embeddings.
- `Customer Themes Review` uses `deal_intel.deals` and only selected
  `customer_themes.evidence`, not raw meeting notes or raw interaction
  content.
- `theme_evidence_drilldown` contains no contacts, embeddings, raw meeting
  notes, or raw interaction content.

Milestone 3.3 is the formal cross-check between:

- `get_metrics`
- CSV/Markdown export
- Atlas Charts dashboard data

Run it with:

```bash
~/miniconda3/envs/event-intel/python.exe -m deal_intel.cli crosscheck-weekly-dashboard --as-of 2026-06-09 --output-dir outputs/m3_3_crosscheck
```

The command uses the same versioned aggregation pipelines as the dashboard, so a
passing result means the dashboard data source is aligned with the MCP and report
metric surfaces.
