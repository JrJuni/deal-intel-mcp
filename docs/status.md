# Status

This file tracks the current workstream and the most recent completed
milestones. Longer roadmap items live in [backlog.md](backlog.md), and durable
contracts live in [baseline.md](baseline.md) and [metrics.md](metrics.md).

## Reading Note

Read the newest section first. Older sections are retained as an archive for
traceability and should be searched by topic, milestone, or file path rather
than loaded wholesale.

## Latest Update - 2026-06-11

### Config profiles Z5.8a tool surface contract

Implemented:

- Added `deal_intel.tool_surfaces` as the source contract for MCP tool
  visibility surfaces.
- Defined non-developer-first surfaces:
  `sample`, `standard`, and `developer`.
- Mapped `sample` profile to the `sample` surface, and `full`/`pro`/`custom`
  to the `standard` surface.
- Kept `sample` read-first: no DB writes, no LLM calls, no semantic search,
  and no Atlas demo-database seed/cleanup tools.
- Kept real operator admin tools such as `delete_deal` in `standard`, relying
  on their existing dry-run, confirmation, exact-company, archive-gate safety
  contracts.
- Added [tool-surfaces.md](tool-surfaces.md) and linked it from the docs map.
- Updated [config-profiles.md](config-profiles.md) and [backlog.md](backlog.md)
  to mark Z5.8a as contract-only and make mutable local personal storage the
  next sample-mode implementation target.
- Clarified user-facing sample-mode positioning: sample is a limited
  feature-test path with bundled fictional data, while real operation assumes
  MongoDB-backed `full` mode.
- Revised that positioning so `sample` is not permanently read-only: the next
  sample-mode target is mutable/resettable local personal data for small user
  datasets before MongoDB.
- Added `sample_local_personal_target` to the tool surface matrix. It promotes
  safe non-LLM write/admin tools after mutable local storage exists while still
  excluding LLM-heavy analysis, semantic search, and Atlas demo-database
  maintenance.
- Reordered the Z5 plan tree: the originally planned next step was
  config-driven MCP tool filtering, but mutable/resettable local personal
  storage now comes first so the filtered `sample` surface is actually useful
  for small user datasets.
- Added `storage.local_data_dir` to the config contract. The default planned
  local personal data directory is `~/.deal-intel/local-data`, and config tools
  can expose/override it through the sample profile.
- Added a later dry-run-first local personal data to MongoDB migration target
  to the Z5 plan tree.
- Added Z5.9a local personal read foundation:
  `storage.local_data_dir/deals.json` can provide user-created local deals.
  When local deals exist, bundled fixture data is treated as archived demo data
  and removed from active `local_sample` read paths.
- Added Z5.9b local personal safe write foundation:
  `LocalSampleClient.upsert_deal` persists to local `deals.json`, stripping
  sensitive fields before storage. `create_deal`, `update_stage`, and
  `update_deal` can now write local personal sample data.
- Added Z5.9c-1 local lifecycle safety:
  `archive_deal`, `restore_deal`, and `delete_deal` now work on local personal
  data. `delete_deal` preserves audit snapshots in `delete_audit_logs.json`
  before hard delete, keeps audit logs independent from deal storage, and
  blocks bundled fixture deal ids from being persisted through lifecycle writes.
- Added Z5.9c-2 local reset/export safety:
  `deal-intel local-data status`, `deal-intel local-data export`, and
  `deal-intel local-data reset` now inspect, export, and reset local personal
  data without touching bundled fixture data.
- `local-data reset` is dry-run by default.
- `local-data reset --force` clears only local personal deals in `deals.json`
  and preserves delete audit logs in `delete_audit_logs.json`.
- An empty local `deals.json` keeps bundled fixture data archived, so reset
  does not silently re-mix fictional sample data into the active working set.
- `local-data export` writes a secret-safe JSON snapshot without raw notes,
  contacts, or embeddings.

Verification:

- Tool surface/config/profile regression:
  `71 passed`, `1 warning`
- Local sample/personal read foundation:
  `12 passed`
- Local safe-write/config regression:
  `86 passed`, `1 warning`
- Local lifecycle safety:
  `17 passed`
- Local reset/export CLI safety:
  `21 passed`
- Lifecycle/config regression:
  `92 passed`, `1 warning`
- Local sample/config/profile regression:
  `45 passed`, `1 warning`
- Local data/config/profile regression:
  `68 passed`
- Config CLI smoke:
  `config init --profile sample --dry-run` shows
  `storage.local_data_dir: ~/.deal-intel/local-data`
- Full pytest:
  `390 passed`, `1 warning`
- Diff whitespace check:
  `git diff --check`
- Ruff:
  `All checks passed`

### Config profiles Z5.7b smoke-profile CLI

Implemented:

- Added `deal_intel.profile_smoke` to build no-write first-run smoke reports
  from the Z5.7a matrix and shared config doctor.
- Added `deal-intel smoke-profile --profile sample|full|pro`.
- Added `--offline` to skip storage ping and `--json` for agent-readable
  structured output.
- Updated README and `AI_START_HERE.md` so first-run checks include
  `smoke-profile --profile sample`.
- Updated [config-profiles.md](config-profiles.md) and [backlog.md](backlog.md)
  to mark the CLI surface implemented and move the next candidate work to
  release packaging checks.

Verification:

- Profile smoke CLI targeted tests:
  `14 passed`
- Config/profile regression:
  `51 passed`, `1 warning`
- Full pytest:
  `351 passed`, `1 warning`
- CLI smoke:
  `smoke-profile --profile sample --json` returned `ok=true`
- Expected not-ready CLI smoke:
  `smoke-profile --profile pro --offline --json` returned exit code `1`
  because `OPENAI_API_KEY` is not configured; no live OpenAI or Atlas admin
  calls were attempted.
- Diff whitespace check:
  `git diff --check`
- Ruff:
  `All checks passed`

### Config profiles Z5.7a profile smoke matrix

Implemented:

- Added `deal_intel.profile_smoke_matrix` as the source contract for
  `sample`, `full`, and `pro` first-run smoke behavior.
- The matrix records each profile's managed config values, required setup,
  expected unconfigured offline fail/warn checks, no-live-call boundaries,
  write policy, and deferred checks.
- Added targeted tests that compare the matrix against profile patches,
  `config init --dry-run` output, and `config doctor` pass/warn/fail behavior.
- Updated [config-profiles.md](config-profiles.md) with the human-readable
  smoke matrix.
- Updated [backlog.md](backlog.md) so the next candidate unit is the future
  `deal-intel smoke-profile --profile sample|full|pro` CLI.

Verification:

- Profile smoke matrix targeted tests:
  `8 passed`
- Config profile/doctor/writer regression:
  `40 passed`, `1 warning`
- Full pytest:
  `345 passed`, `1 warning`
- CLI smoke:
  `config profiles`, `config init --profile sample --dry-run`,
  `config doctor --offline`
- ASCII check:
  new source/test/docs files passed
- Diff whitespace check:
  `git diff --check`
- Ruff:
  `All checks passed`

Notes:

- The first targeted pytest attempt failed before tests ran because Windows
  denied access to the default pytest temp root under AppData. Re-running with
  `TEMP`/`TMP` set to workspace `.tmp/pytest` passed.

### Config profiles Z5.6 packaging surface

Implemented:

- Reworked README onboarding to be sample-first: profile inspection, sample
  dry-run, local sample smoke, then optional Claude Desktop / MongoDB setup.
- Updated `README.ko.md` with the same user-facing sample/full/pro flow.
- Updated `mcpb/README.md` for first-run `local_sample` installs.
- Bumped `mcpb/manifest.json` to `0.1.9`, added `storage_backend`, made
  `mongodb_uri` optional unless `storage_backend=mongo`, and updated bundle
  metadata to the current 22-tool surface.
- Updated the documentation map, config-profile contract notes, and active
  backlog index.

Verification:

- Manifest JSON parse:
  `version=0.1.9`, `tools=22`, `storage_backend=local_sample`,
  `mongodb_required=False`
- Manifest/server tool-name comparison:
  `server=22`, `manifest=22`, `tool names match`
- CLI dry-run smoke:
  `deal-intel config init --profile sample --dry-run`
- CLI offline doctor smoke:
  `deal-intel config doctor --offline`
- English-source ASCII check:
  `README.md`, `AI_START_HERE.md`, `docs/README.md`, `docs/backlog.md`,
  `docs/config-profiles.md`, `mcpb/README.md`, `mcpb/manifest.json`
- Diff whitespace check:
  `git diff --check`
- Ruff:
  `All checks passed`

Not run:

- `mcpb validate manifest.json`; the `mcpb` CLI is not available on PATH in
  this environment.

### Config profiles Z5.5 AI start-here guide

Implemented:

- Added root-level `AI_START_HERE.md` for AI agents onboarding a new user.
- The guide enforces a sample-first flow before asking for MongoDB, API keys,
  Atlas Vector Search, or paid infrastructure.
- It points agents to `config profiles`, `config show`,
  `config init --profile sample --dry-run`, `config doctor --offline`,
  `storage-status`, and `smoke-natural-questions`.
- It tells agents to avoid overwriting existing user config and to use
  `config switch ... --force` only after explicit user approval.
- Linked the guide from `AGENTS.md`, `CLAUDE.md`, `docs/README.md`, and
  [config-profiles.md](config-profiles.md).

Verification:

- Docs are ASCII-only.
- Ruff:
  `All checks passed`

### Config profiles Z5.3 init/switch CLI

Implemented:

- Added `deal_intel.config_writer` for safe profile config writes.
- Added `deal-intel config init --profile sample|full|pro`.
- Added `deal-intel config switch sample|full|pro`.
- Added `--dry-run`, `--force`, and `--json` support for both commands.
- `init` writes a new user config when missing and refuses to overwrite an
  existing config unless `--force` is provided.
- `switch` changes only profile-managed keys:
  `storage.backend`, `mongodb.vector_search`, and `llm.provider`.
- Actual overwrite/switch operations back up the previous config with a
  timestamped `config.yaml.bak.YYYYMMDD-HHMMSS` file.
- Outputs show only profile-managed values and an offline doctor preview; they
  do not print custom config bodies or secrets.

Verification:

- Config writer targeted tests:
  `10 passed`
- Config CLI/doctor/storage regression:
  `30 passed`
- CLI dry-run smoke:
  `config init --profile sample --dry-run` succeeded without writing files
- Full pytest:
  `337 passed`, `1 warning`
- Ruff:
  `All checks passed`

### Config profiles Z5.4 config doctor

Implemented:

- Added `deal_intel.config_doctor` as the shared diagnostic engine for config
  readiness checks.
- Added `deal-intel config doctor`, `deal-intel config doctor --json`, and
  `deal-intel config doctor --offline`.
- Added the read-only MCP tool `config_doctor(offline=false)`.
- The doctor checks the effective profile, user config readability, storage
  backend, MongoDB URI, optional storage ping, vector-search mode, and LLM
  provider readiness without LLM calls, embeddings, or writes.
- Kept diagnostic output secret-safe: environment values, tokens, raw notes,
  contacts, and embeddings are not returned.

Verification:

- Config doctor targeted tests:
  `10 passed`
- Config/storage targeted regression:
  `19 passed`
- MCP registration and related regression:
  `75 passed`
- Full pytest:
  `327 passed`, `1 warning`
- Ruff:
  `All checks passed`
- CLI offline smoke:
  `ok=true`, `profile=full`, `storage_ping=skipped`
- CLI live storage smoke:
  returned a structured `storage_ping` failure because this environment hit a
  DNS timeout while resolving Atlas. No writes were attempted.

### Secret scan cleanup and debt audit

Implemented:

- Investigated the secret detection on commit `89d0aa0`; confirmed it was a
  false positive caused by realistic fake test/doc placeholders, not a real
  credential leak.
- Replaced API-key-shaped and credential-URI-shaped examples with neutral
  placeholders in `.env.example`, README files, and mcpb metadata.
- Updated config CLI tests to use scanner-safe sentinel values while still
  asserting that config output never echoes environment values.
- Recorded the failure mode in [lesson-learned.md](lesson-learned.md).

Audit notes:

- No `eval`, `exec`, `shell=True`, `pickle`, unsafe YAML load, or environment
  dumps were found in the reviewed source/test/doc paths.
- Sensitive fields such as raw meeting notes, contacts, and embeddings are
  intentionally excluded from reporting/metric/gap surfaces and covered by
  existing tests.
- Low-priority technical debt remains around broad best-effort exception
  handling in vector-index setup and malformed timestamp fallback paths.

Verification:

- Secret-like pattern scan:
  `no matches`
- Config/storage targeted tests:
  `22 passed`
- Full pytest:
  `317 passed`, `1 warning`
- Ruff:
  `All checks passed`

### Config profiles Z5.2 inspect CLI

Implemented:

- Added `deal-intel config profiles` for the one-package
  `sample/full/pro` profile catalog.
- Added `deal-intel config show` for the current inferred profile, user config
  path, selected effective config fields, and configured env-key status.
- Kept output secret-safe: environment values are never printed, only
  `configured: true/false`.
- Added `_env.user_config_path()` so CLI and tests do not need to duplicate the
  user config path.

Verification:

- Z5.2 targeted tests:
  `22 passed`
- Full pytest:
  `317 passed`, `1 warning`
- Ruff:
  `All checks passed`

### Config profiles Z5.1 profile contract

Implemented:

- Added `deal_intel.config_profiles` with one-codebase profile definitions for
  `sample`, `full`, and `pro`.
- Added reusable profile config patches for future config CLI commands.
- Added profile inference for effective config:
  `local_sample` -> `sample`, Mongo + Atlas vector search -> `pro`,
  otherwise `full`.
- Documented the Z5 plan in [config-profiles.md](config-profiles.md).

Verification:

- Z5.1 targeted tests:
  `17 passed`
- Full pytest:
  `312 passed`, `1 warning`
- Ruff:
  `All checks passed`

### Zero-config sample mode Z4 startup diagnostics

Implemented:

- Added `deal_intel.storage.diagnostics` with the shared local sample mode hint.
- Updated Mongo missing-URI `ping()` and runtime errors to explain both paths:
  set `MONGODB_URI` for Atlas, or use `DEAL_INTEL_STORAGE_BACKEND=local_sample`
  for bundled sample mode.
- Added `deal_intel.cli storage-status` for install checks, local demos, and
  agent smoke tests.
- Documented the zero-config sample quickstart in README and
  [storage-backends.md](storage-backends.md).

Verification:

- Z4 targeted tests:
  `25 passed`
- Local sample storage-status CLI smoke:
  `ok=true`, `storage_backend=local_sample`, `deal_count=12`,
  `snapshot_count=24`
- Local sample natural-question CLI smoke:
  `OK: True`, `derived=3`, `direct=5`, `Sensitive failures: none`,
  `Blocked questions: none`
- Full pytest:
  `300 passed`, `1 warning`
- Ruff:
  `All checks passed`

### Zero-config sample mode Z3 local sample backend

Implemented:

- Added `deal_intel.storage.local_sample.LocalSampleClient`.
- Added `storage.backend: mongo | local_sample` to defaults.
- Added `DEAL_INTEL_STORAGE_BACKEND=local_sample` as a temporary env override.
- Updated `_context.mongo()` to select `MongoDBClient` or `LocalSampleClient`
  while preserving the existing tool-call surface.
- Local sample mode now skips Mongo driver preload, Mongo index creation, and
  embedding warmup during MCP startup.
- `search_deals` now returns a structured unsupported-mode response in local
  sample mode before touching embeddings.
- Fixed the bundled fixture so the natural-question smoke pack's PayBridge
  question resolves to `PayBridge` instead of falling back to the first deal.

Verification:

- Z3 targeted tests:
  `28 passed`
- Local sample natural-question CLI smoke:
  `OK: True`, `derived=3`, `direct=5`, `Sensitive failures: none`,
  `Blocked questions: none`
  with `DEAL_INTEL_STORAGE_BACKEND=local_sample`
- Full pytest with workspace-local temp:
  `295 passed`
- Ruff:
  `All checks passed`

### Zero-config sample mode Z2 bundled fixture

Implemented:

- Added `deal_intel.storage.local_sample_fixture`.
- Added a safe bundled fictional data pack for MongoDB-free demos and agent
  smoke tests.
- Included 12 current deal documents across all canonical stages.
- Included all deal value statuses:
  `unknown`, `rough_estimate`, `customer_budget`, `quoted`, and
  `strategic_zero`.
- Added 7-day analytics snapshots so `pipeline_trend` can return meaningful
  movement without Atlas.
- Kept the fixture free of `meetings.raw_notes`, `contacts`, and
  `summary_embedding`.
- Added fixture validation and summary helpers for future zero-config
  diagnostics.

Verification:

- Zero-config sample fixture tests:
  `5 passed`
- Full pytest with workspace-local temp:
  `280 passed`
- Ruff:
  `All checks passed`

### Zero-config sample mode Z1 storage contract

Implemented:

- Added `deal_intel.storage.backend`.
- Defined the `local_sample_mvp` read-only storage contract before adding a
  `LocalSampleClient`.
- Added `SampleReadStorageBackend`, storage method contracts, capability
  reporting, and validation helpers.
- Fixed the first sample-mode support boundary:
  `ping`, `get_deal`, `list_deals`, `list_deals_for_metrics`, and
  `list_analytics_snapshots`.
- Documented deferred paths such as Mongo aggregations, semantic search,
  write tools, and admin/index setup in [storage-backends.md](storage-backends.md).

Verification:

- Storage backend contract tests:
  `6 passed`
- Full pytest with workspace-local temp:
  `275 passed`
- Ruff:
  `All checks passed`

### Natural question smoke CLI

Implemented:

- Added `deal-intel smoke-natural-questions`.
- The command runs a deterministic pack of eight realistic natural-language
  questions without requiring Claude Desktop or another MCP client.
- The pack combines existing read-only payloads from pipeline metrics, deal
  review, deal gaps, and customer-theme evidence.
- It writes `summary.md`, `summary.json`, and per-question JSON files under
  `outputs/smoke/...`.
- It is a developer/QA CLI, not a user-facing MCP tool.
- Raw meeting notes, contacts, and embeddings remain excluded from the saved
  artifacts.

Verification:

- CLI targeted tests:
  `12 passed`
- Full pytest with workspace-local temp:
  `269 passed`
- Ruff:
  `All checks passed`
- Live Atlas read-only smoke:
  `smoke-natural-questions --as-of 2026-06-10` returned `OK: True`,
  `derived=3`, `direct=5`, `Sensitive failures: none`, and
  `Blocked questions: none`
- Live smoke artifacts saved locally:
  `outputs/smoke/natural-question-pack-20260610_200827/summary.md`

### Deal review Calibration v2

Implemented:

- Tightened `verified_healthy`.
  - It now requires high evidence coverage, no missing information, no
    confirmed risk rows, and confirmed data quality.
  - Healthy-looking deals with open questions are downgraded to
    `promising_but_unproven`.
  - Healthy-looking deals with confirmed risk rows are downgraded to
    `watch_with_evidence`.
- Tightened `low` uncertainty.
  - Missing information, rough estimates, invalid value classification, or
    unconfirmed data quality now prevent `low` uncertainty.
- Added `forecast_confidence` to deal review interpretation.
  - Values include `quoted`, `strategic_zero`, `customer_indicated`,
    `estimated`, `unknown`, and `invalid`.
- Extended the audit smoke rules so `verified_healthy` and `low` uncertainty
  cannot hide open gaps, risk rows, or unconfirmed data.

Verification:

- Calibration targeted tests:
  `22 passed`
- Full pytest with workspace-local temp:
  `267 passed`
- Ruff:
  `All checks passed`
- Live Atlas read-only audit smoke:
  `smoke-deal-review-audit --as-of 2026-06-10 --limit 50` reviewed `22`
  deals and returned `Sensitive field check: passed`, `Quality rules: passed`
- 10-set live smoke artifacts saved locally:
  `outputs/smoke/deal-review-calibration-v2-20260610_175009/summary.md`

Observed calibration delta:

- Before v2:
  `verified_healthy=19`, `watch_with_evidence=2`, `low uncertainty=21`,
  `medium uncertainty=0`, `watch alert=8`
- After v2:
  `verified_healthy=10`, `watch_with_evidence=8`,
  `promising_but_unproven=3`, `low uncertainty=12`,
  `medium uncertainty=9`, `watch alert=11`

### Deal review audit smoke pack

Implemented:

- Added `deal-intel smoke-deal-review-audit`.
- The command audits selected deal reviews through the restricted metrics read
  path without requiring Claude Desktop or another MCP client.
- Supports `--company`, `--stage`, `--industry`, `--limit`, `--as-of`,
  `--json`, and `--fail-on-issues`.
- Summarizes alert levels, uncertainty levels, review bands, warnings, quality
  issue counts, and top review targets.
- Added deterministic quality rules for:
  - win-probability suppression
  - low-evidence healthy overconfidence
  - confirmed risk alert consistency
  - missing information follow-up questions
  - confirmed risk follow-up actions
  - closed-deal postmortem gap reporting
  - accidental percentage estimates in guidance
  - sensitive field exposure
- Fixed deal review alert interpretation so any confirmed risk row raises the
  review to at least `watch`.

Verification:

- Deal review audit CLI targeted tests:
  `10 passed`
- Related deal review regression tests:
  `21 passed`
- Full pytest with workspace-local temp:
  `266 passed`
- Ruff:
  `All checks passed`
- Live Atlas read-only audit smoke:
  `smoke-deal-review-audit --as-of 2026-06-10 --limit 50` reviewed `22`
  deals, returned `Sensitive field check: passed`, `Quality rules: passed`,
  and moved confirmed-risk rows from `alert=none` to `watch`

### Deal review local smoke CLI

Implemented:

- Added `deal-intel smoke-deal-review`.
- The command exercises the same read-only `get_deal_review` handler path
  without requiring Claude Desktop or another MCP client.
- Supports exact `--deal-id`, company substring `--company`, `--limit`,
  `--as-of`, and `--json`.
- Text output summarizes review band, alert level, uncertainty, evidence
  coverage, missing information, confirmed risks, recommended questions, and
  warnings.
- JSON output returns the full structured tool response for repeatable local
  smoke checks.
- Successful smoke output omits raw notes, contacts, embeddings, and even the
  restricted field names themselves.

Verification:

- New CLI targeted tests:
  `5 passed`
- Related deal review regression tests:
  `15 passed`
- Full pytest with workspace-local temp:
  `260 passed`
- Ruff:
  `All checks passed`
- Live Atlas read-only smoke:
  `smoke-deal-review --as-of 2026-06-10 --limit 2` returned two deal reviews
  and `Sensitive field check: passed`

### Deal review quality hardening

Implemented:

- Added `get_deal_review` MCP tool.
- Added deterministic `deal_review` calculation module.
- Separated legacy `health_pct` from MEDDPICC evidence coverage.
- Added `uncertainty_level`, `review_band`, and `alert_level`.
- Added explicit `missing_information`, `confirmed_risks`,
  `known_signals`, `recommended_questions`, and `recommended_actions`.
- Suppressed uncalibrated win-probability numbers in review responses.
- Kept the read path free of LLM calls, embedding calls, and MongoDB writes.
- Used the restricted metrics projection so raw notes, contacts, and
  embeddings remain excluded.

Verification:

- `tests/test_deal_review.py`:
  `10 passed`
- Related MCP/read-path regression tests:
  `54 passed`
- Full pytest with workspace-local temp:
  `255 passed`
- Ruff:
  `All checks passed`
- FastMCP registration smoke:
  `21` tools, `get_deal_review` registered
- Live Atlas read-only smoke:
  `deal_count=22`, `ok=true`, first reviewed deal returned
  `review_band=verified_healthy`, `alert_level=none`,
  `warnings=win_probability_suppressed`

### BI Reporting Milestone 6.1-M6.3 Customer Themes expansion

Implemented:

- Added `get_customer_theme_breakdown` MCP tool.
  - Compares curated customer themes by `stage`, `industry`, or `dimension`.
  - Supports `dimension`, `stage`, `industry`, `group_by`, and `top_k`.
- Added `get_customer_theme_evidence` MCP tool.
  - Returns curated evidence snippets for one `theme_key`.
  - Supports `dimension`, `stage`, `industry`, `limit`, and `min_importance`.
- Added pure `customer_theme_insights` calculation module for breakdown and
  drill-down behavior.
- Added versioned Atlas Charts spec:
  `atlas/charts/customer_themes.v1.json`.
- Added `Customer Themes Review` dashboard source over `deals`.
- Extended `render-atlas-dashboard` with `--dashboard customer_themes`.
- Kept the M6 read paths free of LLM calls, embedding calls, and MongoDB
  writes.
- Raw meeting notes, contacts, and embeddings remain excluded from the new
  read paths.

Verification:

- M6.1-M6.2 targeted tests:
  `18 passed`
- M6.3 Atlas chart targeted tests:
  `15 passed`
- M6 related regression tests:
  `69 passed`
- Full pytest with workspace-local temp:
  `245 passed`
- Ruff:
  `All checks passed`
- CLI render smoke:
  `render-atlas-dashboard --dashboard customer_themes --chart-id theme_overview`
  printed a rendered Atlas aggregation pipeline
- Live Atlas read-only smoke:
  `get_customer_theme_breakdown` returned `deals_analyzed=13`,
  `deals_with_evidence=13`, `group_count=4`; `get_customer_theme_evidence`
  returned `unique_deal_count=10`, `evidence_count=21`; Customer Themes Atlas
  aggregations returned rows for all 4 charts

### BI Reporting Milestone 5.8 Atlas trend chart

Implemented:

- Added versioned Atlas Charts spec:
  `atlas/charts/pipeline_trend.v1.json`.
- Added `Pipeline Trend Review` dashboard source over
  `analytics_snapshots`.
- Added chart pipelines:
  `trend_kpis` and `trend_delta_bars`.
- Extended `render-atlas-dashboard` with:
  `--dashboard pipeline_trend` and `--lookback-days`.
- Added `MongoDBClient.aggregate_analytics_snapshots()` for read-only Atlas
  pipeline smoke tests.
- No LLM, embedding, or MongoDB writes are used by the trend chart path.

Verification:

- M5.8 targeted tests:
  `20 passed`
- Related Atlas/report/trend regression tests:
  `34 passed`
- Full pytest with workspace-local temp:
  `234 passed`
- Ruff:
  `All checks passed`
- CLI render smoke:
  `render-atlas-dashboard --dashboard pipeline_trend --chart-id trend_kpis`
  wrote rendered JSON with no unresolved placeholders
- Live Atlas aggregation smoke:
  `trend_kpis=1 row`, `trend_delta_bars=3 rows`

Manual follow-up:

- Create or update the Atlas Charts dashboard named `Pipeline Trend Review`
  using [atlas-charts.md](atlas-charts.md). This is a manual Atlas UI step.

## History

### BI Reporting Milestone 5.7 trend CSV

Implemented:

- Added `export_report(report_type="pipeline_trend")`.
- Added `lookback_days`, default `7`, max `365`, for trend reports.
- Added pipeline trend CSV rows for KPI start/end/delta and stage movement.
- Added LLM-free Markdown summary for pipeline trend reports.
- Reused the M5.6 `build_pipeline_trend_summary()` calculator.
- Trend report reads only `analytics_snapshots` through
  `list_analytics_snapshots()` and does not read deal raw notes.
- No LLM, embedding, or MongoDB writes are used by the trend export path.

Verification:

- M5.7 targeted tests:
  `17 passed`
- Related report/trend regression tests:
  `33 passed`
- Full pytest with workspace-local temp:
  `228 passed`
- Ruff:
  `All checks passed`
- Live Atlas read-only smoke:
  `ok=true`, `report_type=pipeline_trend`, `snapshot_count=0`, `row_count=7`,
  expected sparse-history warnings returned, CSV/Markdown artifacts created

### OpenAI API LLM provider support

Implemented:

- Added `OpenAIAPIProvider` using the official OpenAI Responses API.
- Added `llm.provider: openai_api`.
- Added `llm.openai_api_model` and `llm.openai_api_reasoning_effort`.
- Added `OPENAI_API_KEY` support through `.env` and MCP bundle user config.
- Added `DEAL_INTEL_LLM_PROVIDER` as the explicit provider override while
  preserving legacy `DEAL_INTEL_USE_CHATGPT_OAUTH` behavior.
- Bumped the MCP bundle manifest to `0.1.8`.
- Kept the then-current MCP tool surface unchanged.

Verification:

- OpenAI provider targeted tests:
  `10 passed`
- Related LLM/provider regression tests:
  `27 passed`
- Full pytest with workspace-local temp:
  `226 passed`
- Ruff:
  `All checks passed`
- MCP bundle manifest JSON:
  valid
- Live OpenAI API smoke:
  not run because this environment does not currently have API credits/key;
  provider behavior is covered with mock HTTP tests.

### BI Reporting Milestone 5.6 pipeline_trend metric

Implemented:

- Added `get_metrics(metric_type="pipeline_trend")`.
- Added `lookback_days`, default `7`, max `365`.
- Added `MongoDBClient.list_analytics_snapshots()` with a restricted
  projection over `analytics_snapshots`.
- Added pure `build_pipeline_trend_summary()` calculator.
- Trend output compares the window start and end latest snapshots by deal.
- Trend output includes active/open counts, open pipeline value, average health,
  attention count, won/lost counts, stage transitions, and data sufficiency
  warnings.
- Duplicate `event_id` snapshots are ignored defensively by the calculator.
- No LLM, embedding, or MongoDB writes are used by the trend read path.

Verification so far:

- M5.6 targeted tests:
  `24 passed`
- Related BI regression tests:
  `21 passed`
- Full pytest with workspace-local temp:
  `216 passed`
- Ruff:
  `All checks passed`
- Live Atlas read smoke:
  `ok=true`, `metric_type=pipeline_trend`, `lookback_days=7`,
  `snapshot_count=0`, expected insufficiency warnings returned

### BI Reporting Milestone 5.1-5.5 analytics snapshot foundation

Implemented:

- Added an internal `analytics_snapshots` write model for trend analysis.
- Added idempotent snapshot storage keyed by `event_id`.
- Added snapshot indexes for `event_id`, `deal_id + occurred_at`, and
  `event_type + occurred_at`.
- Connected snapshots to `create_deal`, `add_meeting`, and `update_stage`.
- Snapshot failures do not block the original deal mutation; tool responses
  include an `analytics_snapshot` warning object instead.
- Snapshot documents store only lightweight BI state:
  deal metadata, value fields, stage, health band, MEDDPICC gaps, timing, and
  attention reasons.
- Snapshot documents do not store raw meeting notes, contacts, or embeddings.

Verification so far:

- New targeted tests:
  `6 passed`
- Related regression tests:
  `58 passed`
- Full pytest with workspace-local temp:
  `203 passed`
- Ruff:
  `All checks passed`
- Live Atlas write smoke:
  first insert `true`, duplicate insert `false`, found before cleanup `1`,
  cleanup deleted `1`

### BI Reporting Milestone 4.4 onboarding/demo sample data

Implemented:

- Added MCP tools: `create_sample_data`, `delete_sample_data`.
- FastMCP registration target was updated for the then-current tool surface.
- Added `mongodb.demo_database`, default `deal_intel_demo`.
- Sample tools reject any demo database equal to the primary
  `mongodb.database`.
- `create_sample_data` writes fictional `weekly_pipeline_demo` deals only to
  the resolved demo database.
- `delete_sample_data` deletes only documents matching `is_sample=true` and
  the known `sample_batch_id`.
- Both tools default to `dry_run=true`.
- Actual create/delete requires `confirmed_by_user=true`.
- No LLM, embedding, or production database writes are used by the sample-data
  workflow.

Verification so far:

- Targeted tests with workspace-local temp:
  `32 passed`
- Command:
  `pytest tests/test_sample_data.py tests/test_get_metrics.py tests/test_export_report.py tests/test_get_deal_gaps.py tests/test_deal_lifecycle.py -q --basetemp .tmp\pytest-m44-targeted`
- Full pytest with workspace-local temp:
  `197 passed`
- Ruff:
  `All checks passed`
- Live Atlas demo DB dry-run smoke:
  `create_ok=true`, `create_storage_written=false`,
  `delete_ok=true`, `delete_storage_written=false`,
  demo database `deal_intel_demo`, existing sample count `0`

### BI Reporting Milestone 4.3 deal lifecycle safety layer

Implemented:

- Added MCP tools: `archive_deal`, `restore_deal`, `delete_deal`.
- FastMCP registration target is now 16 tools.
- `archive_deal` marks a deal archived and hides it from default BI/read paths.
- `restore_deal` returns an archived deal to default BI/read paths.
- `delete_deal` defaults to `dry_run=true`.
- Actual hard delete requires:
  - `confirmed_by_user=true`
  - exact `expected_company` match after trimming whitespace
  - non-empty `delete_reason`
  - already archived deal
- Hard delete writes one `delete_audit_logs` entry before deletion.
- Delete audit snapshots exclude `_id`, `contacts`, `summary_embedding`, and
  `meetings.raw_notes`.
- `get_deal` still returns archived deals and adds `warnings=["deal_archived"]`.

Archived read-path contract:

```json
{"archived": {"$ne": true}}
```

This keeps legacy documents visible when they do not have an `archived` field.

Updated read paths:

- `MongoDBClient.list_deals`
- `MongoDBClient.list_deals_for_metrics`
- `MongoDBClient.list_deals_for_theme_backfill`
- `MongoDBClient.get_deals_for_search`
- `MongoDBClient.search_by_embedding`
- `get_insights` direct aggregation paths
- `get_customer_themes` scope queries

Verification so far:

- Targeted tests with workspace-local temp:
  `49 passed`
- Command:
  `pytest tests/test_deal_lifecycle.py tests/test_archived_read_paths.py tests/test_data_quality_reporting.py tests/test_customer_themes.py tests/test_get_metrics.py tests/test_get_deal_gaps.py tests/test_export_report.py -q --basetemp .tmp\pytest-m43-targeted`
- Full pytest with workspace-local temp:
  `189 passed`
- Ruff:
  `All checks passed`
- Live Atlas read-only dry-run smoke:
  `ok=true`, `dry_run=true`, `storage_written=false`,
  visible deal count `22`, `would_delete=false`

### BI Reporting Milestone 4.2 update_deal metadata extension

Completed before M4.3:

- Extended `update_deal` beyond value fields to selected metadata:
  `company`, `industry`, `expected_close_date`, `actual_close_date`,
  `close_reason`.
- All mutations require `confirmed_by_user=true`.
- Value updates require `deal_size_note`.
- Metadata updates require `update_note` or fallback `deal_size_note`.
- `expected_close_date` is allowed only for open deals and records
  `expected_close_date_source=user_provided`.
- `actual_close_date` is allowed only for won/lost deals.
- `close_reason` is allowed only for lost deals.
- Stage transitions remain exclusively in `update_stage`.
- Metadata changes append `deal_metadata_history`.

Verification:

- Targeted `tests/test_update_deal.py`: `16 passed`
- Full pytest at completion: `176 passed`
- Ruff: passed
- Live Atlas no-op smoke: `ok=true`, `storage_written=false`, `changed=[]`

## Next

1. M6 Customer Themes expansion.
