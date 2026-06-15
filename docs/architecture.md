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

## Tool Groups

This section is the developer map for the current tool surface. It intentionally
uses user-intent namespaces instead of Python module folders so future v2
refactors can move implementation code without changing the product mental
model.

### Tool Namespace Map

| Namespace | User intent | Current tools | Main modules | Side effects | v2 notes |
|---|---|---|---|---|---|
| Config / Diagnostics | Setup, profile, tool discovery, safe config changes | `config_doctor`, `get_tool_catalog`, `update_config` | `config_doctor.py`, `config_writer.py`, `tool_surfaces.py`, `mcp_server.py` | `update_config` writes non-secret local config only | Keep these stable and visible in every profile; they are the first-run recovery path. |
| Intake | Turn new customer evidence into structured deal intelligence | `create_deal`, `add_interaction`, developer-only `add_meeting` alias | `tools/create_deal.py`, `tools/add_interaction.py`, `schema/interactions.py`, `schema/qualification_extraction.py`, `schema/meddpicc.py`, `schema/customer_themes.py` | DB writes; `add_interaction` calls server-side LLM and may update embeddings in Mongo mode | MEDDPICC abstraction touches this first because extraction prompts, scoring dimensions, and source policy meet here. |
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
responses expose `meddpicc_latest`, `meddpicc.gaps`, MEDDPICC dimension keys,
and MEDDPICC-specific chart/report labels. If the tool surface is renamed first,
the same public contracts will likely need another pass immediately after the
framework work.

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
MEDDPICC health by default.

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
4. Snapshot calculation:
   `tools/qualification_snapshot.py` rebuilds legacy `meddpicc_latest` and
   canonical `qualification_latest` together. `schema/qualification.py`
   computes generic framework health, coverage, uncertainty, and gaps from
   stored evidence.

Current compatibility rule:

- Active `meddpicc` uses stored `interaction.meddpicc` evidence for
  `qualification_latest`.
- Non-MEDDPICC frameworks use stored `interaction.qualification` evidence.
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
`deal_intel.schema.pipeline_metrics`. CSV data exports, report data packs, and
Atlas Charts should be cross-checked against the same metric contracts.

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
- `meddpicc_latest`
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
