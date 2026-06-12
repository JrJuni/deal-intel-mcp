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

The server exposes 23 MCP tools. The source of truth is
`src/deal_intel/mcp_server.py`.

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

LLMs are allowed in:

- `add_meeting`
- `add_interaction`
- `analyze_deal`
- customer-theme extraction/backfill paths

LLMs are not allowed in BI/reporting metric paths.

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
- `export_report`

The shared metric engine lives in `deal_intel.schema.metrics` and
`deal_intel.schema.pipeline_metrics`. CSV/Markdown reports and Atlas Charts
should be cross-checked against the same metric contracts.

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
