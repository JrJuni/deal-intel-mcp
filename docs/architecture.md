# Architecture

This is the English source-of-truth architecture note. Korean-facing summaries
belong only in `README.ko.md` and `AGENTS.ko.md`.

## Read First

For quick orientation, read:

1. `AGENTS.md` or `CLAUDE.md`
2. `docs/README.md`
3. `docs/baseline.md`

When this document conflicts with source code, prefer:

1. source code,
2. tests,
3. `docs/baseline.md`,
4. this architecture note.

## Runtime Shape

```text
Claude Desktop / Codex / ChatGPT
  -> stdio JSON-RPC
  -> deal_intel.mcp_server FastMCP app
  -> tools in src/deal_intel/tools
  -> storage backend selected by deal_intel._context
```

The server exposes a profile-filtered MCP tool surface. The source of truth is:

- runtime registration: `src/deal_intel/mcp_server.py`
- profile/tool-surface contract: `src/deal_intel/tool_surfaces.py`

Avoid hardcoding tool counts in docs. Use `get_tool_catalog`,
`config_doctor`, or `deal-intel config show` to inspect the current visible
surface.

## Product Profiles

The project uses one repository and one package with three profiles:

| Profile | Storage | Search | Default LLM | Purpose |
|---|---|---|---|---|
| `sample` | `local_sample` | no semantic search | `chatgpt_oauth` | Zero-config feature test, future local personal use |
| `full` | MongoDB Atlas | Python cosine | `chatgpt_oauth` | Real team data |
| `pro` | MongoDB Atlas | Atlas Vector Search | `openai_api` (`gpt-5.4-mini`) | Paid infra path |

Profile details live in `docs/config-profiles.md`.

Feature placement rule:

- `full` is the home for MongoDB-backed features that run on Atlas Free/M0 and
  help normal real-data operation.
- `pro` is reserved for paid infrastructure, paid API defaults, scale paths, or
  admin automation that assumes capabilities beyond Free/M0.

## Core Components

### FastMCP Server

`src/deal_intel/mcp_server.py` registers the MCP tools and keeps the handler
boundary thin. Handlers should delegate to modules under `src/deal_intel/tools`.

Important startup behavior:

- Mongo mode preloads selected native libraries on the main thread to avoid
  Windows background-thread import stalls.
- Embedding warmup runs in a background thread only in Mongo mode.
- Mongo index creation runs in the background and must not block first tool
  calls.
- Local sample mode skips Mongo driver preload, index creation, and embedding
  warmup.

### Context

`src/deal_intel/_context.py` owns process-level singletons:

- config
- storage backend
- LLM provider
- embedding provider

Tool implementations should use `_context` through the MCP boundary and should
not instantiate MongoDB or LLM providers directly.

### Storage

Storage behavior is selected by config:

```yaml
storage:
  backend: mongo        # mongo | local_sample
```

Mongo mode uses `MongoDBClient` over Atlas collections. Local sample mode uses
`LocalSampleClient` over bundled fictional fixture data.

The read-only BI/reporting path should use restricted projections that exclude:

- `meetings.raw_notes`
- `interactions.raw_content`
- `contacts`
- `summary_embedding`

### LLM Providers

Supported providers:

- `chatgpt_oauth`
- `openai_api`
- `anthropic`

Provider construction must go through `make_llm_provider(config)`.

### Host App LLM vs Server LLM

Deal Intelligence is normally used inside a host LLM app such as Claude
Desktop, Codex, or ChatGPT with MCP support. The host model is already good at
reading structured tool output, explaining results, asking follow-up questions,
and drafting human-facing language. The MCP server should therefore avoid
calling its own LLM unless the result must be written back as structured,
repeatable product data.

Use the host app LLM for:

- explaining `get_metrics`, `get_deal_review`, `get_deal_gaps`, `list_deals`,
  and report outputs to the user;
- turning deterministic BI payloads into meeting-ready narratives;
- asking the user confirmation questions;
- setup guidance, troubleshooting, and config-change walkthroughs;
- one-off judgment or wording that does not need to be persisted.

Use the server-side LLM provider for:

- `add_meeting`
- `add_interaction`
- `analyze_deal`
- customer-theme extraction/backfill paths

The reason is persistence and repeatability: these flows extract or generate
structured data that becomes part of the deal record. They need schema checks,
source metadata, and stable storage behavior that should not depend on a
particular host app prompt.

LLMs are not allowed in BI metric or data-export calculation paths. New
read-only tools should prefer deterministic calculation and let the host app
perform the final explanation layer. Human-facing report prose may be
host-assisted when the deterministic data pack remains the source of truth. New
write tools should make LLM calls explicit in the tool contract and provide a
lower-cost path when useful, such as raw capture, dry-run extraction, or
deferred enrichment.

### Embeddings

The local embedding provider uses `sentence-transformers` when the optional
`embedding` dependency is installed.

Embedding work is used for:

- storing deal-level summary embeddings after meetings/interactions in
  MongoDB-backed mode
- semantic `search_deals`

Embedding work is not used in BI/reporting paths.

Local sample mode does not support semantic search in the first MVP.

## Developer Navigation Map

Use this section before starting feature work. It is intentionally more
operational than conceptual: it tells an agent or contributor where ownership
lives, which adjacent modules usually move together, and which tests catch the
common regressions.

### Runtime Entry Points

| Entry point | File | Owns | Usually touches | Do not break |
|---|---|---|---|---|
| MCP server process | `src/deal_intel/mcp_server.py` | FastMCP app, tool wrappers, profile-filtered tool exposure | `tool_surfaces.py`, `mcpb/manifest.json`, `tests/test_mcpb_manifest.py`, `tests/test_tool_surfaces.py` | Keep handlers thin; do not instantiate storage/LLM providers directly. |
| CLI | `src/deal_intel/cli.py` | Local smoke tests, config/profile commands, Mongo operational commands, Atlas chart rendering | CLI-specific tests, `docs/README.md`, `AI_START_HERE.md` | Keep CLI output secret-safe and Windows-friendly. |
| Shared runtime context | `src/deal_intel/_context.py` | Effective config, storage backend, LLM provider, embedding provider singletons | `_env.py`, `storage/*`, `providers/*`, `config_profiles.py` | Tool code should enter storage/LLM through context, not direct construction. |
| Config loading | `src/deal_intel/_env.py` | `.env`, defaults, user override merge | `resources/defaults.yaml`, `config_profiles.py`, `config_writer.py` | Do not print or return raw secrets. |
| MCPB launcher | `mcpb/server/launcher.py` | Desktop bundle bootstrap | `mcpb/manifest.json`, release artifacts | Keep it tiny; it should launch the installed package, not duplicate product logic. |
| Package defaults/resources | `src/deal_intel/resources/*` | Defaults, sample fixture, Atlas specs, Mongo schema specs | docs and tests for the corresponding resource | Version resource specs; do not edit generated user data here. |

### CLI Command Families

The CLI is mostly a developer/operator surface. MCP host apps should normally
use the MCP tools, while humans and CI use CLI commands for setup, smoke tests,
and Atlas/Mongo maintenance.

| Family | Commands | Primary modules | Purpose |
|---|---|---|---|
| Auth and usage | `login-chatgpt`, `usage` | `providers/llm.py`, `usage.py` | Login and inspect persisted server-side LLM cost/usage metadata. |
| Config | `config profiles`, `config show`, `config doctor`, `config init`, `config switch`, `update_config` via MCP | `config_profiles.py`, `config_doctor.py`, `config_writer.py` | Inspect, validate, and safely update non-secret local config. |
| Profile/storage smoke | `smoke-profile`, `storage-status` | `profile_smoke.py`, `storage/diagnostics.py` | Confirm that a profile and storage backend can start before users try tools. |
| Mongo operations | `mongo doctor`, `mongo apply-indexes`, `mongo apply-schema`, `mongo apply-vector-index` | `mongo_doctor.py`, `mongo_contracts.py`, `atlas_vector_indexes.py` | Check and apply Atlas operational contracts. |
| Local data | `local-data status`, `local-data export`, `local-data reset`, `local-data migrate-to-mongo` | `storage/local_personal.py`, `tools/migrate_local_data.py` | Manage local personal data and graduate it to MongoDB. |
| Taxonomy cleanup | `audit-taxonomy`, `apply-taxonomy-cleanup`, `backfill-industry-tags` | `schema/industry_taxonomy.py`, `schema/taxonomy_audit.py`, `tools/backfill_industry_tags.py` | Normalize industry/tags/segments without forcing all uncertain cases onto humans. |
| Qualification maintenance | `backfill-qualification`, `backfill-qualification-reextract` | `tools/backfill_qualification*.py` | Recompute or regenerate qualification snapshots after framework changes. |
| Theme maintenance | `backfill-customer-themes` | `tools/backfill_customer_themes.py`, `schema/customer_themes.py` | Rebuild theme summaries from stored structured evidence. This may be LLM-costly on old data. |
| Atlas dashboards | `render-atlas-dashboard`, `crosscheck-weekly-dashboard` | `reports/atlas_charts.py`, `reports/dashboard_crosscheck.py` | Render chart pipelines and compare dashboard KPIs against MCP/report metrics. |
| QA smoke | `smoke-deal-review`, `smoke-deal-review-audit`, `smoke-natural-questions` | `schema/deal_review.py`, `schema/deal_gaps.py`, `schema/pipeline_metrics.py`, `schema/customer_theme_insights.py` | Repeatable local smoke checks without needing Claude Desktop. |

### MCP Tool Ownership Index

Use `get_tool_catalog` for the runtime-visible catalog. This table is the
developer ownership map. "Safe projection" means the path must not expose raw
notes, raw interaction content, contacts, or vectors.

| Tool | Intent alias | Owner module | Inputs | Output / side effects | Adjacent modules and tests | Do not break |
|---|---|---|---|---|---|---|
| `config_doctor` | `config.doctor` | `config_doctor.py` | effective config, `offline` | secret-safe readiness report; optional bounded storage ping | `tests/test_config_doctor.py`, `tests/test_cli_config_profiles.py` | No LLM calls, no secrets, no writes. |
| `get_tool_catalog` | `catalog.tools` | `mcp_server.py`, `tool_surfaces.py` | effective tool surface | visible tools, intent groups, selection guide, alias metadata | `tests/test_tool_surfaces.py`, `tests/test_mcpb_manifest.py` | Keep counts derived from contracts, not hardcoded docs. |
| `update_config` | `config.update` | `config_writer.py` | safe non-secret fields | local user-config write only when confirmed/apply path allows | `tests/test_config_writer.py`, `tests/test_config_doctor.py` | Reject secret-shaped values and raw API keys/URIs. |
| `get_qualification_templates` | `framework.templates` | `qualification_config.py`, `schema/qualification_framework.py` | optional template filters | built-in/custom framework templates | `tests/test_qualification_config.py`, `tests/test_qualification_framework.py` | Built-in presets are immutable recovery anchors. |
| `validate_qualification_framework` | `framework.validate` | `schema/qualification_framework.py` | framework JSON/YAML or template key | validation report, guardrail warnings | `tests/test_qualification_framework.py` | Validate before config writes; reject secret-like strings. |
| `update_qualification_framework` | `framework.update` | `qualification_config.py`, `config_writer.py` | custom framework payload | dry-run-first user config write | `tests/test_qualification_config.py`, `tests/test_config_writer.py` | Never overwrite built-in framework keys. |
| `list_qualification_frameworks` | `framework.list` | `qualification_config.py` | effective config | active/built-in/custom framework list | `tests/test_qualification_config.py` | Make the active framework obvious. |
| `set_active_qualification_framework` | `framework.activate` | `qualification_config.py`, `config_writer.py` | framework key | dry-run-first active-framework config write | `tests/test_qualification_config.py`, `tests/test_config_writer.py` | Does not recompute existing deals; tell user to backfill if needed. |
| `delete_qualification_framework` | `framework.delete` | `qualification_config.py`, `config_writer.py` | custom framework key | dry-run-first config deletion | `tests/test_qualification_config.py` | Block built-in and active framework deletion. |
| `backfill_qualification` | `framework.backfill` | `tools/backfill_qualification.py` | deal filters, dry-run/apply flags | recomputes snapshots from stored evidence; optional DB patch | `tests/test_backfill_qualification.py`, storage backend tests | No LLM calls, no raw content reads, no whole-document replacement. |
| `backfill_qualification_reextract` | `framework.reextract` | `tools/backfill_qualification_reextract.py` | deal filters, LLM cap, dry-run/apply flags | optional LLM re-extraction and snapshot patch | `tests/test_backfill_qualification_reextract.py`, `tests/test_usage.py` | Dry-run must not initialize LLM; never return raw content. |
| `create_deal` | `deal.create` | `tools/create_deal.py` | company, industry/tags, value, stage metadata | deal upsert plus analytics snapshot warning on failure | `tests/test_sample_data.py`, `tests/test_storage_backend_contract.py` | Do not infer irreversible stage outcomes. |
| `add_interaction` | `interaction.add` | `tools/add_interaction.py` | raw interaction content plus source metadata | DB update, qualification/theme extraction, optional embedding update, usage metadata | `tests/test_add_interaction.py`, `tests/test_qualification_extraction.py`, `tests/test_usage.py` | Never auto-change `deal_stage`; return suggestions only. |
| `add_meeting` | `compat.add_meeting` | `tools/add_meeting.py` | legacy meeting arguments | compatibility wrapper around canonical interaction intake | `tests/test_add_interaction.py` | Keep developer-only until removed in a breaking cleanup. |
| `update_stage` | `deal.stage.update` | `tools/update_stage.py` | deal id, target stage, optional close metadata | stage/history update plus analytics snapshot warning | `tests/test_update_stage.py`, `tests/test_analytics_snapshots.py` | Stage mutation belongs here, not in intake tools. |
| `update_deal` | `deal.update` | `tools/update_deal.py` | confirmed value/metadata patch | deal metadata/value history update | `tests/test_update_deal.py`, taxonomy cleanup tests | Require confirmation and notes for meaningful changes. |
| `archive_deal` | `deal.archive` | `tools/archive_deal.py`, `tools/deal_lifecycle.py` | deal id, expected company, confirmation | marks deal archived | `tests/test_deal_lifecycle.py`, `tests/test_archived_read_paths.py` | Archived deals disappear from default BI/read paths. |
| `restore_deal` | `deal.restore` | `tools/restore_deal.py`, `tools/deal_lifecycle.py` | archived deal id, expected company, confirmation | restores archived deal | `tests/test_deal_lifecycle.py` | Preserve history and exact-company safety. |
| `delete_deal` | `deal.delete` | `tools/delete_deal.py`, `tools/deal_lifecycle.py` | archived deal id, expected company, reason, dry-run/apply | hard delete plus audit log when applied | `tests/test_deal_lifecycle.py`, Mongo contract tests | Dry-run default; actual delete only for archived deals. |
| `migrate_local_data` | `data.migrate` | `tools/migrate_local_data.py` | local storage and Mongo target options | dry-run/apply local-to-Mongo migration | `tests/test_local_data_migration.py`, `tests/test_local_data_cli.py` | Never overwrite Mongo data unless explicitly requested. |
| `get_deal` | `deal.get` | `tools/get_deal.py` | deal id or company lookup | structured deal detail | `tests/test_archived_read_paths.py`, `tests/test_local_sample_backend.py` | This may expose richer fields than BI tools; keep sensitive handling explicit. |
| `list_deals` | `deal.list` | `tools/list_deals.py` | filters, sorting, limit | compact deal table with health/gaps/timing | `tests/test_local_sample_backend.py`, `tests/test_zero_config_sample_fixture.py` | Use active qualification snapshot and safe fields. |
| `get_metrics` | `pipeline.metrics` | `tools/get_metrics.py`, `schema/pipeline_metrics.py`, `schema/pipeline_trends.py` | metric type, filters, dates | deterministic KPI payload | `tests/test_get_metrics.py`, `tests/test_pipeline_metrics_summary.py`, `tests/test_pipeline_trends.py` | Official BI numbers live here; no LLM calls. |
| `get_insights` | `pipeline.insights` | `tools/get_insights.py`, `schema/pipeline_metrics.py` | query type, filters | framework-aware `pipeline_overview`; MEDDPICC-labeled legacy aggregate modes | `tests/test_metric_contract.py`, `tests/test_pipeline_metrics_summary.py`, `tests/test_data_quality_reporting.py` | Keep compatibility aliases stable; legacy modes must self-label with `framework_scope: meddpicc_legacy`. |
| `get_deal_gaps` | `deal.gaps` | `tools/get_deal_gaps.py`, `schema/deal_gaps.py` | filters, priority threshold | prioritized missing-info/gap list | `tests/test_deal_gaps.py`, `tests/test_get_deal_gaps.py` | Objective timing gaps can be CTA; judgment-sensitive gaps should usually be observations. |
| `get_deal_review` | `deal.review` | `tools/get_deal_review.py`, `schema/deal_review.py` | deal id/company, `as_of` | deterministic one-deal review | `tests/test_deal_review.py`, `tests/test_cli_deal_review_smoke.py` | Do not invent win probability; separate health from evidence coverage. |
| `get_usage` | `usage.cost` | `tools/get_usage.py`, `usage.py` | date window, grouping | safe token/cost estimate summary | `tests/test_usage.py` | Usage output must not include raw prompts/content. |
| `export_report` | `report.export` | `tools/export_report.py`, `reports/*` | report type, filters, language, output dir | local Markdown/CSV artifacts | `tests/test_export_report.py`, `tests/test_weekly_pipeline_report.py`, `tests/test_weekly_pipeline_markdown.py` | Report prose follows deterministic data pack; no hidden LLM calls. |
| `export_data` | `data.export` | `tools/export_data.py`, `reports/data_export.py` | dataset, filters, output dir | local spreadsheet-ready CSV artifact | `tests/test_export_data.py`, `tests/test_csv_export.py` | Ledger/export path is not the same as human report path. |
| `get_user_memory` | `memory.get` | `tools/get_user_memory.py`, `user_memory.py` | memory categories | safe Markdown memory read | `tests/test_user_memory.py` | Read only approved memory files; no business-data leakage. |
| `record_user_memory` | `memory.record` | `tools/record_user_memory.py`, `user_memory.py` | category, content | append-only safe user memory write | `tests/test_user_memory.py` | Reject secrets and path traversal. |
| `get_customer_themes` | `theme.rank` | `tools/get_customer_themes.py`, `schema/customer_theme_insights.py` | dimension/stage/top-k filters | ranked customer concerns/criteria | `tests/test_customer_themes.py`, `tests/test_customer_theme_insights.py` | Ranking entry point; use safe metric projection only. |
| `get_customer_theme_breakdown` | `theme.compare` | `tools/get_customer_theme_breakdown.py`, `schema/customer_theme_insights.py` | dimension plus group-by filter | stage/industry/tag comparison | `tests/test_customer_theme_insights.py` | Do not duplicate ranking semantics; this is the comparison step. |
| `get_customer_theme_evidence` | `theme.evidence` | `tools/get_customer_theme_evidence.py`, `schema/customer_theme_insights.py` | theme key, filters, limit | safe evidence snippets | `tests/test_customer_theme_insights.py` | Evidence snippets are curated structured evidence, not raw notes. |
| `search_deals` | `search.deals` | `tools/search_deals.py`, `providers/embedding.py` | query, filters, limit | semantic/similarity result with generic qualification metadata or unsupported-mode response | `tests/test_search_deals_startup.py` | BI paths must not depend on embeddings; never return vectors. |
| `analyze_deal` | `strategy.analyze` | `tools/analyze_deal.py`, `providers/llm.py` | deal id | optional LLM strategy and possible `bd_strategy` persistence | `tests/test_llm_providers.py` plus strategy-path smoke when changed | Keep optional; default deal review is deterministic `get_deal_review`. |
| `create_sample_data` | `sample.create` | `tools/create_sample_data.py`, `tools/sample_data.py` | demo DB, dry-run/apply flags | Atlas demo seed writes | `tests/test_sample_data.py` | Developer surface only; never write to primary DB. |
| `delete_sample_data` | `sample.delete` | `tools/delete_sample_data.py`, `tools/sample_data.py` | demo DB, dry-run/apply flags | Atlas demo seed deletion | `tests/test_sample_data.py` | Delete only known sample batch documents. |

### Major Internal Engine Index

| Engine | Owner modules | Inputs | Outputs | Adjacent modules | Main tests | Do not break |
|---|---|---|---|---|---|---|
| Config/profile engine | `_env.py`, `config_profiles.py`, `config_writer.py`, `config_doctor.py` | defaults, `.env`, user config, profile name | effective config, profile patch, doctor report | `tool_surfaces.py`, `storage/diagnostics.py` | `tests/test_config_profiles.py`, `tests/test_config_writer.py`, `tests/test_config_doctor.py` | Keep secrets out of output; keep `full` as the real-data default. |
| Tool surface/catalog engine | `tool_surfaces.py`, `mcp_server.py` | effective config/profile | visible MCP tool set, intent groups, aliases | MCPB manifest, README guidance | `tests/test_tool_surfaces.py`, `tests/test_mcpb_manifest.py` | Canonical tool names remain callable names until a breaking rename. |
| Storage adapter engine | `storage/backend.py`, `storage/mongodb.py`, `storage/local_sample.py`, `storage/local_personal.py` | storage config, query filters | storage reads/writes with capability reports | `_context.py`, diagnostics, reports, metrics | `tests/test_storage_backend_contract.py`, `tests/test_local_sample_backend.py`, `tests/test_mongodb_indexes.py` | Keep restricted projections separate from raw-content maintenance reads. |
| Qualification framework engine | `schema/qualification_framework.py`, `qualification_config.py`, `schema/qualification.py`, `schema/qualification_read.py` | framework definitions, stored evidence, stage context | `qualification_latest`, health/coverage/uncertainty/gaps | `add_interaction`, reports, metrics, review/gap tools | `tests/test_qualification_framework.py`, `tests/test_qualification_snapshot.py`, `tests/test_deal_review.py` | Built-ins immutable; missing evidence should increase uncertainty, not fake confidence. |
| Interaction extraction engine | `tools/add_interaction.py`, `schema/qualification_extraction.py`, `schema/customer_themes.py`, `tools/qualification_snapshot.py` | raw interaction content, source metadata, active framework | stored interaction evidence, customer themes, snapshots, usage metadata | LLM provider, embedding provider, storage adapter | `tests/test_add_interaction.py`, `tests/test_qualification_extraction.py`, `tests/test_usage.py` | Stage suggestions are advisory only. |
| Metrics engine | `schema/metrics.py`, `schema/pipeline_metrics.py`, `schema/pipeline_trends.py` | safe deal/snapshot documents, thresholds, dates | pipeline health/trend KPI payloads | `get_metrics`, `get_insights`, reports, Atlas crosscheck | `tests/test_pipeline_metrics_summary.py`, `tests/test_get_metrics.py`, `tests/test_pipeline_trends.py` | One official KPI definition; no report-specific duplicate math. |
| Deal review/gap engine | `schema/deal_review.py`, `schema/deal_gaps.py`, `schema/gap_actionability.py` | safe deal docs, active qualification, timing/value quality | review bands, uncertainty, missing info, gap rows | `list_deals`, `get_deal_review`, `get_deal_gaps`, smoke CLI | `tests/test_deal_review.py`, `tests/test_deal_gaps.py`, smoke audit tests | Do not over-prescribe judgment-sensitive gaps. |
| Report/data export engine | `reports/weekly_pipeline.py`, `reports/markdown_summary.py`, `reports/data_export.py`, `reports/csv_export.py`, `reports/markdown_export.py` | safe deal/snapshot rows, language, output path | Markdown/CSV artifacts and data packs | `export_report`, `export_data`, metrics engine | `tests/test_export_report.py`, `tests/test_weekly_pipeline_report.py`, `tests/test_export_data.py` | Human report and spreadsheet ledger are separate products. |
| Atlas dashboard engine | `reports/atlas_charts.py`, `reports/dashboard_crosscheck.py`, resource JSON specs | dashboard id, chart id, dates, Mongo aggregation output | rendered aggregation specs and KPI crosschecks | `mongo_doctor.py`, Atlas resources, metrics/report engines | `tests/test_atlas_charts.py`, `tests/test_dashboard_crosscheck.py` | Atlas charts mirror shared metric semantics unless explicitly documented. |
| Customer theme engine | `schema/customer_themes.py`, `schema/customer_theme_insights.py`, `schema/customer_theme_workflow.py` | stored curated theme evidence | ranking, breakdown, evidence payloads | `add_interaction`, theme tools, Atlas customer-theme spec | `tests/test_customer_themes.py`, `tests/test_customer_theme_insights.py` | Never expose raw notes as evidence. |
| Search/vector engine | `providers/embedding.py`, `tools/search_deals.py`, `atlas_vector_indexes.py` | deal summary text, query text, vector config | embeddings, similarity results, vector index command | Mongo storage, Pro profile | `tests/test_search_deals_startup.py`, `tests/test_atlas_vector_indexes.py` | Sample mode must fail gracefully before loading embeddings. |
| Usage/cost engine | `usage.py`, usage metadata writers in LLM tools | provider usage metadata, date filters | safe counts, token/cost estimates | `add_interaction`, `analyze_deal`, re-extraction backfill | `tests/test_usage.py` | Estimates are advisory and secret/content-free. |
| User memory engine | `user_memory.py`, memory tools | constrained Markdown category/content | safe memory reads/appends | AI customization docs | `tests/test_user_memory.py` | This is user preference memory, not a business data store. |
| Mongo operations engine | `mongo_contracts.py`, `mongo_doctor.py`, `atlas_vector_indexes.py` | effective config, Atlas collection/index state | doctor report, schema/index commands | CLI `mongo`, resources/mongo specs | `tests/test_mongo_contracts.py`, `tests/test_mongodb_indexes.py`, `tests/test_atlas_vector_indexes.py` | Apply commands must be explicit; doctor should not require paid admin APIs. |

### Change Playbooks

| Change type | Start here | Also inspect | Minimum tests / smoke |
|---|---|---|---|
| Add or rename an MCP tool | `mcp_server.py`, `tool_surfaces.py` | `mcpb/manifest.json`, `AI_START_HERE.md`, README tool guidance, this tool index | `tests/test_tool_surfaces.py`, `tests/test_mcpb_manifest.py`, `mcpb validate mcpb/manifest.json` |
| Add a config option | `resources/defaults.yaml`, `_env.py`, `config_writer.py` | `config_doctor.py`, `config_profiles.py`, MCPB manifest user config fields | config writer/doctor/profile tests; ensure no secret leakage |
| Add a storage method | `storage/backend.py` | Mongo, local sample/personal adapters, storage contract tests | `tests/test_storage_backend_contract.py` plus adapter-specific tests |
| Add a qualification dimension/framework feature | `schema/qualification_framework.py` | extraction, snapshot, read helper, review/gaps/metrics/reports | qualification framework/snapshot tests, deal review/gap tests, full QF targeted set |
| Change interaction ingestion | `tools/add_interaction.py` | source metadata, extraction prompt, theme rebuild, snapshots, usage, embeddings | add-interaction tests, qualification extraction/snapshot tests, usage tests |
| Change official KPI math | `schema/metrics.py`, `schema/pipeline_metrics.py` | `get_metrics`, `get_insights`, reports, Atlas crosscheck, docs/metrics.md | metric contract tests, pipeline summary tests, report/export regression |
| Change deal review quality | `schema/deal_review.py` | `deal_gaps.py`, `gap_actionability.py`, smoke audit CLI | deal-review tests, deal-gap tests, `smoke-deal-review-audit` |
| Change report output | `reports/weekly_pipeline.py`, `reports/markdown_summary.py`, `reports/data_export.py` | `export_report.py`, `export_data.py`, `docs/reports.md` | report/export tests, generated artifact inspection if layout changed |
| Change Atlas chart specs | `reports/atlas_charts.py`, resource JSON specs | dashboard crosscheck, docs/atlas-charts.md | Atlas chart tests, dashboard crosscheck tests, render CLI smoke |
| Change customer theme behavior | `schema/customer_theme_insights.py` | `schema/customer_themes.py`, theme tools, sample fixture | customer theme tests, natural-question smoke theme questions |
| Change delete/archive safety | `tools/deal_lifecycle.py` and wrapper tools | archived read paths, delete audit schema | lifecycle tests, archived read-path tests, Mongo schema tests |
| Change package/distribution | `mcpb/manifest.json`, `mcpb/server/launcher.py` | README install flow, release artifacts, launch hygiene | MCPB manifest tests, `mcpb validate`, fresh-install checklist |

## Tool Groups

This section is the developer map for the current tool surface. It intentionally
uses user-intent namespaces instead of Python module folders so future v2
refactors can move implementation code without changing the product mental
model.

### Tool Namespace Map

| Namespace | User intent | Current tools | Main modules | Side effects | v2 notes |
|---|---|---|---|---|---|
| Config / Diagnostics | Setup, profile, tool discovery, safe config changes | `config_doctor`, `get_tool_catalog`, `update_config` | `config_doctor.py`, `config_writer.py`, `tool_surfaces.py`, `mcp_server.py` | `update_config` writes non-secret local config only | Keep these stable and visible in every profile; they are the first-run recovery path. |
| Intake | Turn new customer evidence into structured deal intelligence | `create_deal`, `add_interaction`, developer-only `add_meeting` alias | `tools/create_deal.py`, `tools/add_interaction.py`, `schema/interactions.py`, `schema/qualification_extraction.py`, `schema/meddpicc.py`, `schema/customer_themes.py` | DB writes; `add_interaction` calls server-side LLM and may update embeddings in Mongo mode | Active framework extraction now happens here. Deal review, deal gaps, list views, `get_metrics(pipeline_health)`, `get_insights(pipeline_overview)`, reports, data exports, analytics snapshots, search result metadata, and weekly Atlas specs now read `qualification_latest`; MEDDPICC-specific insight aggregations remain labeled legacy compatibility paths. |
| Lifecycle / CRUD | Correct, move, archive, restore, delete, or migrate deal records | `update_stage`, `update_deal`, `archive_deal`, `restore_deal`, `delete_deal`, `migrate_local_data` | `tools/update_stage.py`, `tools/update_deal.py`, `tools/deal_lifecycle.py`, `tools/migrate_local_data.py` | DB writes; destructive paths require confirmation/dry-run/audit constraints | Keep confirmation policy explicit. Framework abstraction should not weaken lifecycle safety gates. |
| Read / Query | Answer routine deal, pipeline, gap, and usage questions | `get_deal`, `list_deals`, `get_metrics`, `get_deal_gaps`, `get_deal_review`, `get_usage`, legacy `get_insights` | `tools/get_*.py`, `schema/metrics.py`, `schema/pipeline_metrics.py`, `schema/deal_gaps.py`, `schema/deal_review.py`, `usage.py` | Read-only; no LLM calls | This is the default host-app answer surface. Keep deterministic and projection-safe. |
| Export / Artifacts | Produce local report or spreadsheet files | `export_report`, `export_data` | `tools/export_report.py`, `tools/export_data.py`, `reports/*` | Local file writes; no DB writes; no LLM calls | `export_report` is human narrative/data-pack; `export_data` is CSV ledger. Do not collapse them back together. |
| Customer Themes | Rank, compare, and show evidence for customer concerns / criteria | `get_customer_themes`, `get_customer_theme_breakdown`, `get_customer_theme_evidence` | `tools/customer_theme_analysis.py`, `tools/get_customer_theme*.py`, `schema/customer_theme_insights.py`, `schema/customer_themes.py` | Read-only; no raw notes/content in responses | Best post-framework cleanup candidate: likely consolidate behind a progressive-disclosure workflow. |
| Search / Strategy | Semantic reference search and optional LLM strategy generation | `search_deals`, `analyze_deal` | `tools/search_deals.py`, `tools/analyze_deal.py`, `providers/embedding.py`, `providers/llm.py` | `search_deals` uses embeddings; `analyze_deal` calls LLM and may persist `bd_strategy` | Keep `analyze_deal` optional. Search belongs to full/pro; sample uses deterministic reads. |
| User Memory | Persist user operating preferences and feedback | `get_user_memory`, `record_user_memory` | `user_memory.py`, `tools/get_user_memory.py`, `tools/record_user_memory.py` | `record_user_memory` writes safe Markdown only | Keep separate from business data. Never allow secrets or arbitrary file editing. |
| Sample / Admin | Seed or clean fictional demo data | developer-only `create_sample_data`, `delete_sample_data` | `tools/sample_data.py`, `tools/sample_dataset.py`, bundled sample resources | DB writes to separate demo DB; dry-run by default | Keep hidden from ordinary surfaces to avoid confusing real-data operation. |

Profile surfaces are currently defined in `src/deal_intel/tool_surfaces.py`:

- `sample`: zero-config/local personal surface; excludes Mongo-only semantic
  search, legacy insight ranking, optional strategy generation, and demo DB
  seed/cleanup helpers.
- `standard`: normal real-data surface for `full` and `pro`; includes Mongo
  reads, semantic search, customer theme ranking, and optional strategy
  generation.
- `developer`: all registered tools, including compatibility aliases and demo
  maintenance helpers.

When adding or renaming a tool, update:

1. `src/deal_intel/mcp_server.py`
2. `src/deal_intel/tool_surfaces.py`
3. `tests/test_tool_surfaces.py`
4. `mcpb/manifest.json`
5. relevant README / `AI_START_HERE.md` selection guidance
6. this namespace map if the user intent changes

### v2 Refactor Ordering Notes

The next two large refactors are coupled:

- qualification framework abstraction, currently MEDDPICC-specific;
- tool namespace / customer-theme workflow cleanup.

Do the framework abstraction before a broad namespace rename. Many current tool
responses may still expose compatibility aliases such as `meddpicc_latest`,
`meddpicc.gaps`, and MEDDPICC dimension keys. Reports, exports, and weekly
Atlas specs now also expose/read generic qualification fields, but a broad tool
namespace rename should still wait until the remaining compatibility surfaces
are intentionally handled.

However, keep the namespace map and customer-theme cleanup design ahead of the
framework implementation. The framework work should know which future user
intent surfaces it is serving, especially:

- one-deal review and uncertainty;
- missing-information gaps;
- customer theme ranking / comparison / evidence;
- manager reports and spreadsheet exports;
- Atlas chart specs and smoke fixtures.

In practice:

1. strengthen this developer map;
2. design the future customer-theme workflow shape without breaking tools yet;
3. implement qualification framework abstraction;
4. consolidate/rename tool surfaces in a compatibility-aware pass.

### Write and Lifecycle

- `create_deal`
- `add_interaction`
- `update_stage`
- `update_deal`
- `archive_deal`
- `restore_deal`
- `delete_deal`

Write tools are conservative by default. Destructive or corrective operations
require explicit confirmation, reasons, and safe audit behavior where
applicable.

`add_interaction` never changes `deal_stage`. It may return
`stage_suggestion`, but stage mutation happens only through `update_stage`
after user confirmation.

`deal.interactions` is the canonical intake store for new customer evidence.
`add_interaction` stores source metadata for `meeting`, `email_thread`,
`user_interview`, `call_summary`, `internal_note`, and config-registered
custom types. `add_meeting` remains a developer-surface deprecated
compatibility alias for `interaction_type: meeting`. Legacy `deal.meetings`
remains a read fallback for existing data. Outbound-only and internal-only
content is stored as unconfirmed interaction evidence and does not update
confirmed qualification scores by default.

### Qualification Framework V2 Data Flow

QF-v2 separates four concerns:

1. Framework definition:
   `schema/qualification_framework.py` defines built-in immutable presets,
   custom framework validation, dimensions, weights, stage rules, and safety
   checks.
2. Framework selection:
   `qualification_config.py` resolves the active framework from effective
   config. Built-in presets always win over user-config entries with the same
   key.
3. Extraction contract:
   `schema/qualification_extraction.py` builds the active-framework prompt
   contract and normalizes LLM-like output into stored
   `interaction.qualification` evidence. It does not call LLMs or storage.
   `tools/add_interaction.py` consumes this contract at runtime when the active
   framework is not MEDDPICC.
4. Snapshot calculation:
   `tools/qualification_snapshot.py` rebuilds legacy `meddpicc_latest` and
   canonical `qualification_latest` together. `schema/qualification.py`
   computes generic framework health, coverage, uncertainty, and gaps from
   stored evidence. The snapshot also stores safe dimension metadata for
   read-path labels and suggested questions.
5. Routine read paths:
   `schema/qualification_read.py` owns active snapshot selection for read
   views. `schema/deal_review.py`, `schema/deal_gaps.py`, and
   `tools/list_deals.py` prefer `qualification_latest` when available and
   fall back to `meddpicc_latest` for older data. `schema/pipeline_metrics.py`
   uses the same selector for `get_metrics(pipeline_health)` and
   `get_insights(pipeline_overview)`. `reports/weekly_pipeline.py` and
   `reports/data_export.py` now use the same canonical snapshot for report rows
   and CSV ledger rows. `tools/analytics_snapshot.py` and
   `tools/search_deals.py` also prefer the selected qualification snapshot while
   preserving legacy aliases. These paths keep legacy health aliases while
   adding or preserving generic `qualification` metadata where the row surface
   supports it.
6. Historical recompute:
   `tools/backfill_qualification.py` recomputes stored `meddpicc_latest` and
   `qualification_latest` snapshots from already stored scoring evidence. It
   does not call LLMs, read raw interaction content, or replace whole deal
   documents. Apply mode uses the storage-level
   `update_deal_qualification_snapshots(...)` patch method so restricted BI
   projections cannot accidentally erase raw content, contacts, or embeddings.
   It is exposed as the standard/developer MCP tool
   `backfill_qualification` and as the CLI command
   `deal-intel backfill-qualification`.
7. Historical re-extraction:
   `tools/backfill_qualification_reextract.py` is the explicit maintenance
   path for old interactions that need active-framework evidence regenerated
   from `interactions.raw_content`. It uses
   `list_deals_for_qualification_reextract(...)`, not BI/report readers, and
   defaults to dry-run with a 30-call LLM cap. Apply mode patches interaction
   qualification fields plus current snapshots through
   `update_deal_qualification_reextraction(...)` and records usage under
   `interaction.qualification_backfill_usage`. It is exposed as the
   standard/developer MCP tool `backfill_qualification_reextract` and as the
   CLI command `deal-intel backfill-qualification-reextract`. MCP dry-run does
   not initialize the LLM provider; apply mode requires explicit confirmation.

Current compatibility rule:

- Active `meddpicc` uses stored `interaction.meddpicc` evidence for
  `qualification_latest`.
- Non-MEDDPICC frameworks use stored `interaction.qualification` evidence.
- Unconfirmed non-MEDDPICC evidence is stored under
  `interaction.unconfirmed_qualification` and does not affect
  `qualification_latest`.
- MEDDPICC evidence is not force-mapped into unrelated custom frameworks.

### Demo Data

- `create_sample_data`
- `delete_sample_data`

These operate on a separate demo database, default to dry-run, and require
confirmation for actual writes or deletes.

### Read and Review

- `get_deal`
- `list_deals`
- `get_deal_gaps`
- `get_deal_review`

`get_deal` can expose full deal details. The BI/review tools use restricted
read paths and should not expose raw notes, raw interaction content, contacts,
or embeddings.

### BI and Reporting

- `get_insights`
- `get_metrics`
- `export_data`
- `export_report`

The shared metric engine lives in `deal_intel.schema.metrics` and
`deal_intel.schema.pipeline_metrics`. `pipeline_metrics` reads active
qualification snapshots through `schema.qualification_read`, so the official
pipeline-health KPI surface follows the selected framework while preserving
legacy health field names. CSV data exports and weekly report data packs read
the same active qualification snapshot and expose `qualification_*` canonical
fields alongside stable legacy aliases. Weekly Atlas Charts now read
`qualification_latest` first and fall back to `meddpicc_latest`. All three
surfaces should be cross-checked against the same metric contracts.

#### Data Export Pipeline

`export_data` is the spreadsheet/ledger layer. It is intentionally deterministic
and LLM-free. Use it when the user asks for CSV, Excel-ready data, open deal
records, all-deal records, or won/lost postmortem rows.

`export_data(dataset=...)` flows through these modules:

1. `deal_intel.tools.export_data.handle`
   - validates `dataset`, filters, `as_of`, and output path;
   - resolves output paths under `~/.deal-intel/reports` unless the caller
     passes an explicit absolute path;
   - reads deals through `MongoDBClient.list_deals_for_metrics()` or the active
     storage backend's equivalent restricted projection;
   - writes only local CSV artifacts and returns absolute paths plus a small
     safe preview.
2. `deal_intel.reports.data_export.build_data_export`
   - owns CSV-oriented row shaping for `open_deals`, `all_deals`, and
     `closed_deals`;
   - reuses `weekly_pipeline.build_weekly_pipeline_rows` for open-deal timing,
     health, and attention fields;
   - excludes raw notes, raw interaction content, contacts, and embeddings.
3. `deal_intel.reports.csv_export.save_report_csv`
   - writes UTF-8 BOM CSV with spreadsheet formula-injection protection.

#### Human Report Pipeline

`export_report` is the human-facing report/document layer. Use it when the user
asks for a manager/team meeting report, executive summary, or narrative weekly
pipeline review. The deterministic data pack and all numeric metrics remain the
source of truth. Host-app LLMs may turn that data pack into polished prose when
the user is working inside Claude/Codex/ChatGPT. Any future server-side LLM
report mode must be explicit, cost-visible, and must validate narrative numbers
against the deterministic data pack before returning.

`export_report(report_type="weekly_pipeline")` flows through these modules:

1. `deal_intel.tools.export_report.handle`
   - validates `report_type`, filters, `as_of`, output path, and
     `reporting.language`;
   - resolves output paths under `~/.deal-intel/reports` unless the caller
     passes an explicit absolute path;
   - reads deals through `MongoDBClient.list_deals_for_metrics()` or the active
     storage backend's equivalent restricted projection;
   - coordinates row generation, Markdown generation, CSV write, Markdown
     write, and the final MCP response shape.
2. `deal_intel.reports.weekly_pipeline.build_weekly_pipeline_rows`
   - owns row-level weekly report shaping;
   - filters active/open deals by `stage` and `industry`;
   - computes row fields such as stage timing, overdue/stuck flags, attention
     reasons, objective action items, gap observations, data-quality status,
     primary pain, and primary decision criteria;
   - does not write files and does not format user-facing prose beyond stable
     row labels/reasons.
3. `deal_intel.reports.markdown_summary.build_weekly_pipeline_markdown`
   - owns human-facing Markdown report rendering;
   - owns the deterministic meeting narrative for Markdown reports, including
     the executive summary, key deal watchlist, issues-to-watch framing, and
     next-week action flow;
   - also computes Markdown-level summary metrics from the report rows, such as
     open deal count, pipeline value totals, amount/health coverage, average
     health, attention counts, stage breakdown, action-item counts, and
     data-quality issue counts;
   - localizes Markdown labels and deterministic report prose according to
     `reporting.language` (`en` or `ko`);
   - must not infer new facts or prescribe judgment-sensitive BD actions beyond
     the row report's `objective_action_items` and `gap_observations`
     contracts;
   - should not become a second source of truth for business metric semantics.
     If a calculation affects BI, CSV, Atlas Charts, or MCP metrics, move that
     calculation into `schema.metrics`, `schema.pipeline_metrics`, or the report
     row builder and test it there.
4. `deal_intel.reports.csv_export.save_report_csv`
   - currently writes a compatibility CSV artifact from the row report;
   - spreadsheet-first deal ledgers should use `export_data` instead.
5. `deal_intel.reports.markdown_export.save_report_markdown`
   - writes already-rendered Markdown to disk;
   - owns file naming, encoding, and IO error reporting only.

`export_report(report_type="pipeline_trend")` flows through these modules:

1. `deal_intel.tools.export_report.handle`
   - validates `lookback_days`, output path, filters, and language;
   - reads snapshots through `list_analytics_snapshots(start_date, end_date,
     stage, industry)`.
2. `deal_intel.schema.pipeline_trends.build_pipeline_trend_summary`
   - owns the trend metric calculation from analytics snapshots;
   - computes start/end/delta KPI values and stage-change structures.
3. `deal_intel.reports.pipeline_trend.build_pipeline_trend_report`
   - converts the trend summary into CSV-oriented report rows.
4. `deal_intel.reports.pipeline_trend.build_pipeline_trend_markdown`
   - renders the trend report into localized Markdown;
   - may localize labels, but must not reinterpret trend metric semantics.
5. `csv_export` and `markdown_export`
   - perform artifact writes using the same IO responsibilities as weekly
     pipeline reports.

Atlas Charts uses a parallel but separate path:

- `deal_intel.reports.atlas_charts` renders versioned aggregation specs under
  `atlas/charts/`.
- `deal_intel.reports.dashboard_crosscheck` compares Atlas aggregation output,
  `get_metrics`, and `export_report` results for major KPI alignment.
- Atlas specs should mirror shared metric semantics. When exact parity is not
  possible because a chart is a visualization convenience, document the
  difference in `docs/atlas-charts.md` and keep the MCP/CSV metric contract as
  the source of truth.

When adding or changing a report module, update this section with:

- the entry point function;
- input data source and projection expectations;
- calculation responsibility;
- output contract;
- side effects;
- tests or smoke commands that protect the behavior.

### Customer Themes

- `get_customer_themes`
- `get_customer_theme_breakdown`
- `get_customer_theme_evidence`

Theme read tools use curated structured evidence, not raw meeting notes.

### Search and Strategy

- `search_deals`
- `analyze_deal`

`search_deals` may return structured warmup or unsupported-mode responses
before doing embedding work. `analyze_deal` calls an LLM and may persist
`bd_strategy`.

## Data Model Summary

Primary deal fields:

- `deal_id`
- `company`
- `industry`
- `industry_tags`
- `customer_segment`
- `deal_size_amount`
- `deal_size_currency`
- `deal_size_status`
- `deal_size_low_amount`
- `deal_size_high_amount`
- `deal_size_note`
- `deal_stage`
- `expected_close_date`
- `actual_close_date`
- `close_reason`
- `stage_history`
- `meetings`
- `interactions`
- `meddpicc_latest`
- `qualification_latest`
- `customer_themes`
- `summary_embedding`
- lifecycle fields such as `archived`

Analytics snapshots are stored separately and power pipeline trend metrics and
trend dashboards.

## Indexing

Mongo mode creates regular indexes for common point lookups and dashboard
queries. Atlas Vector Search is optional and belongs to the `pro` path.

The Pro vector index spec is versioned at
`atlas/vector_indexes/deal_summary_vector.v1.json` and packaged under
`deal_intel.resources/atlas/vector_indexes/`. Runtime code should read the spec
through `deal_intel.atlas_vector_indexes` instead of duplicating the index name,
dimensions, or search candidate settings.

Local sample mode does not create indexes.

## Documentation Language Policy

English is the source language for runtime, architecture, contracts, backlog,
status, and lesson-learned documents.

The only Korean-maintained docs are:

- `README.ko.md`
- `AGENTS.ko.md`

If a Korean explanation is needed elsewhere, generate it on request rather than
making it part of the persistent source docs.
