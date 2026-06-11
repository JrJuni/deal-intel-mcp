# Backlog

English is the source language for this document. Korean summaries belong only
in `README.ko.md` and `AGENTS.ko.md`.

## Reading Note

Read the current streams first. Historical milestone summaries are preserved at
the bottom for traceability, but they are not active planning material.

When this file conflicts with code, tests, or contract docs, prefer:

1. source code,
2. tests,
3. `docs/baseline.md` and area contract docs,
4. this backlog.

## Current Active Streams

### Z5 - Profile and Config Rollout

Goal: keep one package while making first-run setup clear for `sample`, `full`,
and `pro`.

Next candidate units:

1. Optional live Atlas smoke for local personal -> MongoDB migration when a
   disposable target database is available.
2. Release packaging artifact check: rebuild/validate the `.mcpb` artifact once
   the external `mcpb` CLI is available.

Principle: agents and new users should start in `sample` before being asked for
MongoDB, paid APIs, or Atlas Vector Search.

### Deal Review Quality

Goal: make deal review feel useful to real sales operators, not like a toy
scorecard.

Backlog items:

- Separate health quality, evidence coverage, confirmed risks, missing
  information, and uncertainty.
- Revisit MEDDPICC unknown-first scoring. Missing evidence should increase
  uncertainty instead of masquerading as neutral strength.
- Keep uncalibrated win-probability numbers suppressed unless a real
  probability contract exists.
- Use smoke packs to compare natural-language deal reviews across multiple
  companies.

### Customer Themes

Goal: make customer theme analysis more operationally useful.

Backlog items:

- Split `industry` from company maturity/stage taxonomy. Current data can mix
  true industry with descriptors such as startup, series stage, or enterprise.
- Defer customer-theme CSV until the human-readable reporting artifact has a
  clearer user and use case.
- Keep raw notes, contacts, and embeddings out of customer-theme dashboards and
  evidence responses.

### Reporting

Goal: make CSV/Markdown reports meaningfully different from Atlas dashboards.

Deferred questions:

- Should `weekly_pipeline` flatten primary pain, decision criteria, attention
  reasons, and data quality into reader-friendly columns?
- Should a separate `pipeline_performance` report exist for won/lost outcomes,
  booked value, lost value, win rate, close dates, and close reasons?
- Who is the intended reader: AE weekly review, executive status report,
  customer success handoff, or investor-style performance summary?
- How should CSV differ from Atlas Charts rather than being another raw
  dashboard export?

### Packaging

Goal: make the project easy for non-developers and fast evaluators.

Backlog items:

- Keep one repository and one package.
- Expose `sample`, `full`, and `pro` through config profiles, not separate
  repositories.
- Keep the config-driven `sample`, `standard`, and `developer` MCP tool
  surfaces aligned with the actual tool set before a stable external release.
- Keep local personal mode safe for temporary user data. The `sample` profile
  starts with bundled fictional data, then switches active reads to local
  `deals.json` once a user creates personal deals. Reset/export is now
  available; real team/shared operation still uses MongoDB-backed `full`.
- Consider whether natural-language smoke tools should remain CLI-only in
  production bundles.
- Keep the dry-run-first local-to-Mongo migration path conservative; before
  release, live-smoke it against a disposable database.
- Keep `tests/test_mcpb_manifest.py` as the repo-local contract check for
  manifest fields, tool list alignment, environment mapping, and launcher
  behavior.
- Rebuild and attach a fresh `.mcpb` artifact after bundle manifest changes.

### Pro Infrastructure

Goal: define the paid-infrastructure upgrade path without making it mandatory.

Backlog items:

- Live smoke `openai_api` once disposable API credit is available.
- Add Atlas Vector Search validation for M10+ clusters.
- Explore MongoDB Change Streams, Time Series Collections, and Schema
  Validation after the core MVP is stable.

## Historical Milestone Summary

### M1 - Metric Foundation

Completed:

- Metric contracts for pipeline populations, health bands, value coverage,
  stuck/overdue, win rate, data quality, and reporting context.
- Shared `build_pipeline_health_summary`.
- `get_metrics(metric_type="pipeline_health")`.

See `docs/metrics.md` and `docs/baseline.md`.

### M2 - Weekly Reporting

Completed:

- Weekly pipeline row builder.
- UTF-8 BOM CSV export with formula-injection protection.
- LLM-free Markdown summary.
- `export_report(report_type="weekly_pipeline")`.

See `docs/reports.md`.

### M3 - Atlas Charts

Completed:

- Weekly Pipeline Review dashboard specs.
- Atlas UI setup runbook.
- Cross-check between `get_metrics`, CSV/Markdown, and Atlas aggregations.

See `docs/atlas-charts.md`.

### M4 - Data Quality and Lifecycle

Completed:

- `get_deal_gaps`.
- `update_deal` for confirmed value and selected metadata fields.
- `archive_deal`, `restore_deal`, and `delete_deal` safety layer.
- `create_sample_data` and `delete_sample_data` for demo database management.

Remaining ideas:

- Deal value suggestions from LLM paths should remain suggestions until user
  confirmation.
- Confirmation strictness may eventually become configurable by user mode.

### M5 - Trend Analysis

Completed:

- `analytics_snapshots` foundation.
- Non-blocking snapshot writes from create/add-meeting/update-stage.
- Idempotent snapshot events.
- `get_metrics(metric_type="pipeline_trend")`.
- `export_report(report_type="pipeline_trend")`.
- Pipeline Trend Review Atlas chart specs.

### M6 - Customer Themes

Completed:

- `get_customer_theme_breakdown`.
- `get_customer_theme_evidence`.
- Customer Themes Review Atlas dashboard specs.

Deferred:

- Human-readable Customer Themes CSV.
- Stronger taxonomy cleanup around industry versus maturity/stage.

### Z1-Z4 - Zero-Config Sample Mode

Completed:

- Storage backend contract.
- Bundled fictional sample fixture.
- `LocalSampleClient`.
- Startup diagnostics and `storage-status`.

Local sample mode is intentionally read-only for the first MVP.

### Z5 - Config Profiles

Completed:

- `sample`, `full`, and `pro` profile definitions.
- `deal-intel config profiles`.
- `deal-intel config show`.

Remaining work is tracked in the current active stream above.
