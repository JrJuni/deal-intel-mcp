# MCP Tool Surfaces

English is the source language for this document. Korean summaries belong only
in `README.ko.md` and `AGENTS.ko.md`.

## Goal

Tool surfaces keep the MCP tool list understandable for non-developers while
preserving the full internal development toolbox.

The source contract lives in `src/deal_intel/tool_surfaces.py`.

## Mental Model

- `sample`: a zero-config, bundled, limited feature-test surface with safe
  local personal write/admin tools and optional LLM-backed note intake for
  user-created local deals. User-memory tools are included because they only
  read/write constrained local Markdown files.
- `standard`: the normal operator surface for real team data.
- `developer`: everything, including demo seeding and internal QA helpers.

The rule of thumb is: a first-time user should not see tools that require
MongoDB, paid APIs, embeddings, or dangerous data mutation before they have
successfully tried the sample experience. The team/shared product is still
designed around MongoDB-backed real data; `sample` is the low-friction test path
and future local personal path.

## Surface Contract

| Surface | Default Profiles | Purpose | Tool Policy |
|---|---|---|---|
| `sample` | `sample` | Let a new user or AI agent test useful questions and small local personal datasets with no setup | Mostly LLM-free tools that work against bundled sample data or local personal `deals.json`, plus `add_interaction` when the configured LLM provider is ready |
| `standard` | `full`, `pro`, `custom` | Real operating mode for teams using MongoDB-backed data | User-facing core, admin, analysis, semantic search, and reporting tools |
| `developer` | none by default | Maintainer/debug mode | Every MCP tool, including sample-data seeding helpers |

## Sample Surface

`sample` intentionally contains only tools that should work in local sample mode
without MongoDB today. It is not the full operating surface:

- `config_doctor`
- `create_deal`
- `add_interaction`
- `update_stage`
- `update_deal`
- `archive_deal`
- `restore_deal`
- `delete_deal`
- `migrate_local_data`
- `get_deal`
- `list_deals`
- `get_metrics`
- `get_deal_gaps`
- `get_deal_review`
- `export_report`
- `get_user_memory`
- `record_user_memory`
- `get_customer_theme_breakdown`
- `get_customer_theme_evidence`

Why this matters:

- `create_deal`, `update_stage`, `update_deal`, `archive_deal`,
  `restore_deal`, and `delete_deal` now persist through local personal storage
  and keep their existing confirmation/dry-run safety gates.
- `add_interaction` is the source-aware intake path for email threads, user
  interviews, call summaries, internal notes, meeting notes
  (`interaction_type: meeting`), and config-registered custom types. It writes
  canonical `deal.interactions` records and keeps outbound/internal-only
  content out of MEDDPICC scoring by default. Local sample mode skips
  embedding storage, stores canonical interaction content for user-created
  local personal deals, and keeps list/BI/report paths free of raw content,
  contacts, and vectors.
- `migrate_local_data` is visible in `sample` so a user can graduate local
  personal deals to MongoDB after connecting a URI. It is dry-run-first and
  never migrates bundled fixture records.
- `get_user_memory` and `record_user_memory` support user-owned operating
  notes under `user_docs/` or configured `user_memory.dir`; writes are
  constrained to safe Markdown slugs and reject secret-shaped content.
- `search_deals` currently needs Mongo-backed embeddings or Atlas Vector Search.
- `analyze_deal` calls an LLM and may persist strategy output.
- `create_sample_data` and `delete_sample_data` manage an Atlas demo database,
  not the bundled zero-config local sample dataset.
- `get_insights` and `get_customer_themes` still include legacy Mongo
  aggregation paths; sample mode should prefer shared metric/theme surfaces that
  use the local sample read contract.

## Standard Surface

`standard` is the real operating surface. It includes:

- setup diagnostics,
- core create/read/update flows,
- lifecycle admin tools such as archive/restore/delete,
- BI/reporting tools,
- customer-theme tools,
- semantic search,
- LLM deal analysis.

`delete_deal` remains a standard admin tool because real operators need a
cleanup path. Safety is enforced by the tool contract itself: dry-run defaults,
exact company match, explicit confirmation, and archived-deal requirement.

`create_sample_data` and `delete_sample_data` are excluded from `standard`
because they are demo-database maintenance helpers. They are useful, but they
make the default real-data tool list noisier.

## Developer Surface

`developer` includes every MCP tool. It is for maintainers, testing, fixture
management, and local debugging. Future release work can expose this through
explicit config such as `tools.surface: developer`.

`add_meeting` remains registered only on this surface as a deprecated
compatibility alias for `add_interaction` with `interaction_type: meeting`.
New documentation, examples, and integrations should not depend on it.

## Runtime Filtering

Runtime MCP exposure is now config-driven:

```yaml
tools:
  surface: auto   # auto | sample | standard | developer
```

Behavior:

- `auto` resolves from the effective profile.
- `sample` profile exposes the `sample` surface.
- `full`, `pro`, and `custom` profiles expose the `standard` surface.
- `developer` exposes every registered tool.
- Invalid `tools.surface` config leaves only `config_doctor` visible so the
  server can explain the configuration problem.

Current exposed counts:

- `sample`: 19 tools
- `standard`: 23 tools
- `developer`: 26 tools

Implementation notes:

- The server registers all Python handlers internally, then filters
  `list_tools()` and blocks hidden `call_tool()` requests by surface.
- This keeps developer tests and direct module imports stable while making the
  MCP client-facing tool list non-developer friendly.
- `DEAL_INTEL_TOOLS_SURFACE` can override the configured surface for smoke
  tests or packaged installs.
