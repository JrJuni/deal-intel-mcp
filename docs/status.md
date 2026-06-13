# Status

This file tracks the current workstream and the most recent completed
milestones. Longer roadmap items live in [backlog.md](backlog.md), and durable
contracts live in [baseline.md](baseline.md) and [metrics.md](metrics.md).

## Reading Note

Read the newest section first. Older sections are retained as an archive for
traceability and should be searched by topic, milestone, or file path rather
than loaded wholesale.

## Latest Update - 2026-06-13

### Auxiliary Mongo collection validators

Implemented:

- Generalized MongoDB schema validation contracts from deals-only helpers to
  managed collection helpers in `src/deal_intel/mongo_contracts.py`.
- Added permissive v1 validator resources:
  - `src/deal_intel/resources/mongo/analytics_snapshots.v1.json`
  - `src/deal_intel/resources/mongo/delete_audit_logs.v1.json`
- Added generic MongoDB client methods:
  - `check_collection_schema_validation(collection)`
  - `check_schema_validations()`
  - `collection_schema_command(collection)`
  - `apply_collection_schema_validation(collection)`
- Kept existing deals wrappers for compatibility:
  `check_deals_schema_validation()`, `deals_schema_command()`, and
  `apply_deals_schema_validation()`.
- Extended `mongo doctor` to report:
  - `deals_schema`
  - `analytics_snapshots_schema`
  - `delete_audit_logs_schema`
- Extended `deal-intel mongo apply-schema` with:
  - `--collection deals` (default)
  - `--collection analytics_snapshots`
  - `--collection delete_audit_logs`
  - `--collection all`

Behavior:

- All validators use `validationAction: warn` and
  `validationLevel: moderate`.
- The new validators are intentionally permissive and keep
  `additionalProperties: true` so MVP field evolution is not blocked.
- `apply-schema` remains dry-run by default.
- Live Atlas apply was performed after user confirmation with
  `deal-intel mongo apply-schema --collection all --apply --json`.

Validation:

- Targeted Mongo contract/index/snapshot/lifecycle tests:
  `38 passed, 1 warning`.
- Targeted Ruff:
  `All checks passed`.
- Full regression:
  `464 passed, 1 warning`.
- Full Ruff:
  `All checks passed`.
- CLI dry-runs passed:
  - `deal-intel mongo apply-schema --collection analytics_snapshots --json`
  - `deal-intel mongo apply-schema --collection delete_audit_logs --json`
  - `deal-intel mongo apply-schema --collection all --json`
- Live Atlas read-only smoke:
  - Before apply, `deal-intel mongo doctor --json` returned `ok=true` with
    expected warnings for missing auxiliary validators.
  - The first apply attempt failed with DNS timeout before completion.
  - The unsandboxed retry applied all three validators successfully:
    `deals`, `analytics_snapshots`, and `delete_audit_logs`.
  - Post-apply `deal-intel mongo doctor --json` returned `ok=true`,
    `failed_checks=0`, `warning_checks=0`, and all three schema checks passed.

## Previous Update - 2026-06-12

### F-Mongo operational contracts

Implemented:

- Extracted the MongoDB index contract into
  `src/deal_intel/mongo_contracts.py`.
- Updated `MongoDBClient.ensure_indexes()` to apply the shared index contract
  instead of hard-coded inline index definitions.
- Added read-only Mongo readiness checks:
  `MongoDBClient.check_indexes()` and
  `MongoDBClient.check_deals_schema_validation()`.
- Added a permissive v1 deals collection validator resource:
  `src/deal_intel/resources/mongo/deals.v1.json`.
- Added CLI admin surfaces:
  - `deal-intel mongo doctor`
  - `deal-intel mongo doctor --json`
  - `deal-intel mongo doctor --offline`
  - `deal-intel mongo apply-indexes --json`
  - `deal-intel mongo apply-indexes --apply`
  - `deal-intel mongo apply-schema --json`
  - `deal-intel mongo apply-schema --apply`
- Added Pro vector-index CLI skeleton:
  - `deal-intel mongo apply-vector-index --json`
  - `deal-intel mongo apply-vector-index --apply`
- Updated `MongoDBClient.ensure_vector_index()` so Atlas Vector Search setup
  failures are not silently swallowed. Duplicate/already-existing indexes are
  reported as OK.

Behavior:

- `mongo doctor` is read-only.
- `apply-indexes` and `apply-schema` are dry-run by default.
- `apply-vector-index` is dry-run by default and should be used only on M10+
  Pro clusters when `--apply` is passed.
- The deals schema validator starts with `validationAction: warn` and
  `validationLevel: moderate` so it catches obvious drift without blocking the
  fast-changing MVP schema.
- No MCP tool surface was added; this is CLI/admin functionality first.

Validation:

- F-Mongo targeted tests: `12 passed`.
- Targeted Ruff: `All checks passed`.
- Full regression: `456 passed, 1 warning`.
- Full Ruff: `All checks passed`.
- CLI dry-runs passed:
  - `deal-intel mongo doctor --offline --json`
  - `deal-intel mongo apply-indexes --json`
  - `deal-intel mongo apply-schema --json`
- Live Atlas write smoke:
  - `deal-intel mongo apply-schema --apply --json` applied the validator.
  - The first JSON output failed because PyMongo returned a non-JSON
    `Timestamp`; the command result was confirmed by `mongo doctor`, and the
    CLI now serializes Mongo command responses with `default=str`.
  - The live apply output was rerun after the fix and now returns a safe result
    summary with `ok` and `operationTime`, without raw `$clusterTime.signature`
    metadata.
- Live Atlas read-only smoke passed after unsandboxed retry:
  - ping succeeded,
  - expected ordinary indexes are present,
  - deals collection validator now matches the v1 contract.

Not applied:

- `deal-intel mongo apply-vector-index --apply` was not run because the current
  full/M0 path should stay on Python cosine. Run it only on a prepared M10+
  Pro cluster.

### v1.0 distribution readiness D1 first pass

Implemented:

- Aligned README, Korean README, AI start guide, MVP readiness checklist, and
  distribution plan on the full-by-default external trial flow.
- Clarified that `sample` is an optional zero-config AI/demo evaluation path,
  not the default human-facing install path.
- Updated the MCPB install surface so `storage_backend` defaults to `mongo`;
  users choose `local_sample` only for zero-config demos.
- Corrected public tool-surface counts to the runtime contract:
  `sample=17`, `standard=21`, `developer=24`.
- Reframed distribution D1 as external MVP trial readiness before uvx/npx
  wrapper work.

Validation:

- `config profiles`: passed.
- `config doctor --offline`: passed, current effective profile `full`.
- `smoke-profile --profile full --offline`: passed.
- Tool surface and MCPB manifest targeted tests: `29 passed`.
- Earlier optional zero-config sample checks in this slice also passed:
  `config init --profile sample --dry-run`, `smoke-profile --profile sample`,
  temporary local sample `storage-status`, and local sample natural-question
  smoke `12/12`.

Notes:

- This was a first-run distribution readiness slice, not a deep MongoDB feature
  validation slice. Human-facing setup should start with `full`; optional
  `sample` checks protect only the no-MongoDB demo/evaluation path.
- Live `storage-status`/Atlas ping was not rerun after the doc correction
  because this environment previously hit MongoDB DNS/network resolution.
- Claude Desktop MCPB reinstall smoke was not rerun in this slice.

### Pro profile skeleton planning and P-Pro.1/P-Pro.2 start

Decisions:

- `pro` stays an upgrade path, not the default first-run profile.
- `pro` uses `openai_api` by default with `gpt-5.4-mini` to reduce API cost
  pressure. The model can still be overridden in user config.
- Atlas Vector Search failures must not silently fall back to Python cosine.
  Repeatable failures should be recorded in
  [pro-fallback-errors.md](pro-fallback-errors.md).
- The current target is skeleton plus guardrails. Live OpenAI API and Atlas
  Vector Search smoke will run later when disposable paid infra is available.
- MongoDB ecosystem features that work on Atlas Free/M0 and improve ordinary
  real-data operation should be implemented in `full`; `pro` is reserved for
  paid infrastructure, cost-bearing defaults, or scale/admin paths beyond Free/M0.

Implemented in this slice:

- Added a versioned Atlas Vector Search index spec:
  `atlas/vector_indexes/deal_summary_vector.v1.json`.
- Added package resource copy under
  `src/deal_intel/resources/atlas/vector_indexes/`.
- Added `deal_intel.atlas_vector_indexes` as the source loader for future
  doctor/check/apply tooling.
- Updated OpenAI API defaults to `gpt-5.4-mini`.
- Confirmed `search_deals` in `atlas` mode returns a structured error instead
  of silently falling back to Python cosine.

Validation:

- P-Pro.1/P-Pro.2 targeted tests: `65 passed`
- Targeted Ruff: `All checks passed`
- `smoke-profile --profile pro --offline --json`: profile contract passed;
  overall `ok=false` is expected until `OPENAI_API_KEY` is configured.

### Currency abstraction implementation

Implemented:

- Replaced currency-specific canonical amount fields with generic amount/currency
  fields across schema, tools, metrics, reports, local sample data, analytics
  snapshots, and tests.
- Added `deal_value.default_currency` with `KRW` as the default.
- Added `deal_size_currency` to create/update/list/search/deal review/deal gaps
  surfaces and report rows.
- Updated pipeline value summaries to expose `currency`, `currencies`,
  `mixed_currency`, and `amount_by_currency`.
- Mixed currencies are not silently summed in Python metrics or Markdown
  reports.

Validation:

- C1 targeted metric/schema tests: `91 passed`
- C2 storage/sample/snapshot tests: `72 passed`
- C3 report/Atlas/get_insights tests: `61 passed`
- Targeted Ruff checks: `All checks passed`
- Full regression: `436 passed, 1 warning`
- Full Ruff: `All checks passed`
- Natural question smoke: `12/12 pass`
- Deal review smoke: `2/2 pass`, sensitive field check passed

Remaining note:

- Atlas Charts are still best treated as single-reporting-currency dashboards;
  mixed-currency operation should use Python metric/report outputs for the
  authoritative breakdown.

### Product roadmap adjustment before Pro work

Decision:

- Repositioned the product as an AI-assisted sales/deal-intelligence record and
  review tool for one-person or small AI teams that need customizable sales
  metrics without adopting a full CRM.
- Moved currency abstraction ahead of Pro infrastructure work.
- Because there are currently no external users, the preferred currency plan is
  a clean canonical schema migration instead of keeping `_krw` fields as a
  long-lived public API.
- Deferred full MEDDPICC/qualification-framework abstraction until after v1.0.
  It should be handled as v2.0 work on a dedicated branch or separate repo if
  needed.

Updated roadmap:

1. Currency abstraction.
2. Pro profile skeleton and MongoDB/Atlas Vector Search upgrade path.
3. v1.0 distribution decision.
4. Deal Review and CSV/report quality improvements.
5. Other MVP polish and issue fixes.
6. Qualification framework abstraction for v2.0.

Docs:

- Added Product Roadmap, Currency Abstraction, and Qualification Framework
  Abstraction sections to `docs/backlog.md`.
- Updated `docs/mvp-readiness.md` so currency schema cleanup is a v1.0
  yellow item and MEDDPICC abstraction is explicitly deferred.

## Previous Update - 2026-06-11

### Package-data readiness for future uvx/npx distribution

Implemented:

- Added package resources for `config/defaults.yaml` and Atlas chart specs.
- Updated config loading to use repo-root defaults first, then packaged
  defaults when running outside a git checkout.
- Updated Atlas chart loading to use repo-root specs first, then packaged chart
  specs.
- Added package-data metadata in `pyproject.toml`.
- Aligned `pyproject.toml` version with `mcpb/manifest.json` (`0.1.12`).
- Added resource drift and fallback tests for config defaults and dashboard
  specs.

Verification:

- Targeted config/Atlas/MCPB regression:
  `30 passed`
- Targeted Ruff:
  `All checks passed`
- Wheel build:
  `deal_intel_mcp-0.1.12-py3-none-any.whl`
- Wheel resource inspection:
  packaged defaults and all 3 Atlas chart specs present
- Wheel target-install smoke:
  loaded `deal_intel._env` from `.tmp/wheel-install`, read packaged defaults,
  and loaded the Weekly Pipeline Review spec
- Full pytest:
  `433 passed`, `1 warning`
- Ruff:
  `All checks passed`

### Distribution plan

Implemented:

- Added `docs/distribution-plan.md`.
- Recorded the current MVP stance: git clone remains acceptable for the first
  MVP, while npx/uvx wrappers should not preempt sample/local readiness.
- Documented the package portability constraint: repo-root `config/defaults.yaml`
  reads must be refactored before a clean wheel/uvx path.
- Recommended sequence: package-data readiness, uvx/Python-native distribution,
  then npx as a thin convenience wrapper.
- Linked the plan from the docs map and backlog.

### Zero-config sample/local UX polish

Implemented:

- Improved local-to-Mongo dry-run UX for empty local personal stores.
- `migrate_local_data` now skips target MongoDB readiness checks when
  `dry_run=true` and there are no local personal deals to migrate.
- Documented the skip behavior in README and the local storage contract.

Verification:

- Targeted local-data/storage/profile regression:
  `22 passed`, `1 warning`
- Local sample CLI smoke:
  `local-data migrate-to-mongo` returns an empty dry-run preview without DNS
  timeout when there are no local personal deals.
- Targeted Ruff:
  `All checks passed`
- Full pytest:
  `428 passed`, `1 warning`
- Ruff:
  `All checks passed`

### MVP readiness checklist

Implemented:

- Added `docs/mvp-readiness.md` as the sample-first external MVP readiness
  checklist.
- Captured required gates for full tests, Ruff, sample profile smoke, natural
  question smoke, deal review audit, tool surface/MCPB contract checks, local
  personal data safety, and MCPB package smoke.
- Separated green, yellow, not-MVP-blocking, and deferred-after-MVP items so
  wrapper/pro-infra work does not obscure the current MVP path.
- Added a lightweight friend/evaluator trial script and sign-off template.
- Linked the checklist from the docs map.

### Natural Smoke QA expansion

Implemented:

- Expanded `smoke-natural-questions` from 9 to 12 deterministic questions.
- Added coverage for pipeline trend, deal-review actionability separation, and
  interaction source coverage.
- Kept the pack LLM-free and read-only against deal data; it only writes local
  smoke artifacts.
- Updated tests so the smoke pack fails if the expanded question set shrinks,
  blocks, or leaks sensitive fields.

Verification:

- Targeted natural-smoke/trend/metrics regression:
  `34 passed`, `1 warning`
- Targeted Ruff:
  `All checks passed`
- Local sample natural-question smoke:
  `questions=12`, `answerability=derived=6,direct=6`,
  `source_evidence=2 (email_thread=1, user_interview=1)`,
  `actionable=4`, `observations=6`, `risks=3`
- Full pytest:
  `427 passed`, `1 warning`
- Ruff:
  `All checks passed`

### P3.7 interaction intake MVP closeout

Implemented:

- Added `source_policy` to `add_interaction` responses so MCP clients can
  explain whether the submitted interaction was treated as confirmed evidence
  or stored as unconfirmed context.
- Kept `source_policy` response-only; persisted interaction records keep source
  metadata, but restricted BI/list/report paths do not carry extra policy text
  or raw interaction content.
- Clarified README and AI-start guidance for meeting notes, email threads, user
  interviews, call summaries, and internal notes.
- Updated the MCP baseline contract for the new response field.

Verification:

- Targeted interaction/surface/fixture/natural-smoke regression:
  `49 passed`, `1 warning`
- Targeted Ruff:
  `All checks passed`
- Local sample natural-question smoke:
  `questions=9`, `answerability=derived=4,direct=5`,
  `source_evidence=2 (email_thread=1, user_interview=1)`
- Full pytest:
  `427 passed`, `1 warning`
- Ruff:
  `All checks passed`

### P3.6 source-aware evidence rendering

Implemented:

- Added shared source-label formatting for curated customer evidence.
- Added `source_label` to `get_customer_theme_evidence` rows.
- Preserved source metadata on weekly pipeline primary pain and decision
  criteria rows.
- Added a Customer Evidence section to weekly pipeline Markdown summaries.
- Added a Source Evidence section to natural-question smoke `summary.md`.
- Updated the Customer Themes Atlas evidence drill-down spec to project
  `interaction_type`, `source_confidence`, `source_label`, `subject`, and
  `interaction_date`.

Verification:

- Targeted reporting/theme/smoke/Atlas regression:
  `48 passed`, `1 warning`
- Local sample natural-question smoke:
  `questions=9`, `source_evidence=2 (email_thread=1, user_interview=1)`,
  Source Evidence section rendered with meeting/email/interview labels
- Full pytest:
  `427 passed`, `1 warning`
- Ruff:
  `All checks passed`

### P3.5 source-aware theme evidence filters

Implemented:

- Added `interaction_type` and `source_confidence` filters to
  `get_customer_theme_evidence`.
- Supported exact source filtering for built-in interaction types:
  `meeting`, `email_thread`, `user_interview`, `call_summary`, and
  `internal_note`.
- MCP tool validation also honors config-registered custom interaction types.
- Preserved legacy compatibility by treating old meeting-derived theme rows as
  `interaction_type=meeting`.
- Updated the natural-question smoke pack so the email/interview evidence
  question calls the native source filters instead of only post-filtering rows.

Verification:

- Targeted theme/fixture/natural-smoke regression:
  `28 passed`, `1 warning`
- Full pytest:
  `425 passed`, `1 warning`
- Ruff:
  `All checks passed`
- Local sample natural-question smoke:
  `questions=9`, `source_evidence=2 (email_thread=1, user_interview=1)`

### P3.4 sample interaction evidence UX

Implemented:

- Added canonical `interactions` records to the bundled zero-config fixture
  while keeping legacy `meetings` for read compatibility.
- Added one inbound `email_thread` sample and one `user_interview` sample with
  curated customer-theme evidence, source confidence, subject, and interaction
  metadata.
- Extended `get_customer_theme_evidence` rows with safe source metadata:
  `interaction_id`, `interaction_date`, `interaction_type`,
  `source_confidence`, and `subject`.
- Added natural-question smoke coverage for:
  "Which customer themes are supported by email or user interview evidence?"

Verification:

- Targeted fixture/theme/smoke regression:
  `25 passed`, `1 warning`
- Local sample natural-question smoke:
  `questions=9`, `answerability=derived=4,direct=5`,
  `source_evidence=2 (email_thread=1, user_interview=1)`

### P3.3 single public interaction intake

Implemented:

- Promoted `add_interaction` as the only public/customer-evidence intake path
  on the `sample` and `standard` MCP surfaces.
- Kept `add_meeting` registered only on the `developer` surface as a
  deprecated compatibility alias for `add_interaction` with
  `interaction_type: meeting`.
- Updated tests so primary meeting-note behavior is exercised through
  `add_interaction(interaction_type="meeting")`.
- Updated README, MCPB manifest text, baseline/tool-surface docs, and
  AGENTS/CLAUDE rules so new users and fork authors see one clear intake
  concept.

Verification:

- Targeted surface/intake/profile/bundle/local regression:
  `100 passed`, `1 warning`
- Full pytest:
  `423 passed`, `1 warning`
- Ruff:
  `All checks passed`
- Runtime surface count smoke:
  `sample=17`, `standard=21`, `developer=24`; `add_meeting` hidden from
  sample/standard and present only in developer
- MCPB manifest validation:
  `Manifest schema validation passes!`
- Diff whitespace check:
  `git diff --check` passed with Git line-ending normalization warnings only

### P3.2 canonical interaction storage

Implemented:

- Added `schema.interactions` as the canonical interaction helper layer.
- New `add_interaction` writes now append only to `deal.interactions`; they no
  longer dual-write to `deal.meetings`.
- `add_meeting` is now a backward-compatible wrapper over canonical
  `interaction_type: meeting` intake. It keeps returning `meeting_id`, but the
  stored record lives under `interactions`.
- Legacy `meetings` remain supported as read fallback. If a deal has both
  `interactions` and old `meetings`, read helpers merge them and de-duplicate
  matching ids so historical evidence is not lost.
- Custom interaction types are config-registered rather than free-form:
  `interactions.custom_types: ["security_review"]`.
- Local/full/pro storage preserves `interactions.raw_content` for future
  security/redaction modules and forked workflows, while restricted BI/list/
  report/delete-audit paths exclude it.
- `list_deals`, `update_stage`, weekly reports, deal analysis, customer-theme
  flattening, and data-quality checks now read through interaction helpers.

Verification so far:

- Canonical interaction targeted regression:
  `94 passed`, `1 warning`
- Reporting/review/read-path targeted regression:
  `77 passed`, `1 warning`
- Full pytest:
  `422 passed`, `1 warning`
- Ruff:
  `All checks passed`
- Runtime surface count smoke:
  `sample=18`, `standard=22`, `developer=24`

Follow-up:

- P3.3 should reduce `add_meeting` from a compatibility wrapper to a
  deprecated alias and eventually remove it from default user-facing tool
  surfaces. `add_interaction(interaction_type="meeting")` should become the
  single clear intake path for new users and forked implementations.
- Detailed P3.3 implementation units are tracked in
  [backlog.md](backlog.md#customer-interaction-intake) under "single intake
  surface".

### P3.1 customer interaction intake contract

Implemented:

- Added MCP tool `add_interaction`.
- Supported interaction types:
  `meeting`, `email_thread`, `user_interview`, `call_summary`, and
  `internal_note`.
- Supported directions:
  `inbound`, `outbound`, `mixed`, and `internal`.
- Stored interactions as meeting-compatible evidence so existing
  MEDDPICC/customer-theme/report paths keep working without a migration.
- Added source metadata:
  `interaction_type`, `direction`, `source_confidence`, `participants`, and
  `subject`.
- Preserved `add_meeting` as the simpler backward-compatible meeting-note
  entry point.
- Added scoring safety for weak sources:
  `outbound_unconfirmed` and `internal` inputs are saved as unconfirmed
  structured interaction evidence but do not update MEDDPICC health or
  customer-theme counts by default.
- Kept local sample privacy behavior: no embedding warmup, no persisted raw
  content, and bundled fixture records remain read-only.
- Bumped MCPB manifest to `0.1.12`.
- Updated current runtime surface count:
  `sample=18`, `standard=22`, `developer=24`.

Verification:

- P3.1 targeted interaction/surface/profile/bundle/local tests:
  `68 passed`, `1 warning`
- Targeted Ruff:
  `All checks passed`
- Full pytest:
  `419 passed`, `1 warning`
- Full Ruff:
  `All checks passed`
- MCPB manifest contract:
  `6 passed`
- Runtime surface count smoke:
  `sample=18`, `standard=22`, `developer=24`, `server=24`
- Diff whitespace check:
  `git diff --check`

### P3.0 sample/local note intake surface

Implemented:

- Exposed `add_meeting` on the `sample` MCP surface so local/sample users can
  add notes to user-created local personal deals when the configured LLM
  provider is ready.
- Kept bundled fictional fixture deals immutable; `add_meeting` cannot promote
  fixture records into local personal storage.
- Skipped embedding provider initialization for `add_meeting` when the storage
  backend is `local_sample`.
- Preserved local privacy behavior: local personal persistence strips raw
  notes, contacts, and embeddings while keeping extracted summaries,
  MEDDPICC signals, and customer themes.
- Updated profile/docs language so sample mode is described as mostly
  LLM-free with optional LLM-backed note intake, not as strictly LLM-free.
- Updated current runtime surface count:
  `sample=17`, `standard=21`, `developer=23`.

Verification:

- P3.0 targeted regression:
  `66 passed`, `1 warning`
- Full pytest:
  `410 passed`, `1 warning`
- Ruff:
  `All checks passed`
- Runtime surface count smoke:
  `sample=17`, `standard=21`, `developer=23`
- Diff whitespace check:
  `git diff --check`

### Deal review v2 rendering alignment

Implemented:

- Added shared gap actionability classification.
- Reused it in `get_deal_gaps`, `get_deal_review`, weekly pipeline rows, and
  weekly Markdown reports.
- `get_deal_gaps` rows now expose `actionable_gaps` and `gap_observations` in
  addition to the original `gaps` list.
- Weekly pipeline rows now expose `objective_action_items` and
  `gap_observations`.
- Weekly Markdown now renders separate Objective Action Items and Gap
  Observations sections.
- `attention:overdue`, stuck, and stalled are CTA-safe. MEDDPICC gaps and
  `attention:at_risk` are observation-only because they require account/BD
  judgment before prescribing action.

Verification:

- Targeted rendering/gaps/deal-review tests: `53 passed`, `1 warning`
- Targeted Ruff: `All checks passed`
- Local sample `export_report(weekly_pipeline)` smoke: passed, generated CSV
  and Markdown under `.tmp/v2-rendering-smoke-2`
- Local sample `smoke-natural-questions`: passed, `8` questions, no sensitive
  failures, final payload under `.tmp/natural-v2-rendering-smoke-3`
- Local sample `smoke-deal-review`: passed for `2` deals
- Full pytest: `408 passed`, `1 warning`
- Full Ruff: `All checks passed`

### Deal review quality v2

Implemented:

- Added `review_version: "v2"` to deterministic deal reviews.
- Added a top-level `assessment` summary that separates health quality,
  evidence coverage, uncertainty, confirmed risk level, review band, and alert
  level.
- Split gap output into `actionable_gaps` for objective CTA-safe items such as
  overdue timing, and `gap_observations` for judgment-sensitive MEDDPICC gaps
  such as competition, champion quality, economic buyer mapping, and decision
  criteria.
- Added per-gap `actionability` and `cta_policy` so reports and natural
  language answers can avoid turning qualitative gaps into overconfident
  instructions.
- Made deal-review evidence coverage thresholds configurable under
  `deal_review.evidence_coverage.low_max` and
  `deal_review.evidence_coverage.high_min`.
- Extended the deal-review smoke audit so it catches v2 contract regressions,
  judgment-sensitive gaps promoted into CTAs, and non-CTA gaps leaking into
  actionable output.

Verification:

- Targeted deal-review tests: `26 passed`, `1 warning`
- Targeted Ruff: `All checks passed`
- Full pytest: `406 passed`, `1 warning`
- Full Ruff: `All checks passed`

### Planning note: customer interaction intake

Added to [backlog.md](backlog.md):

- A high-priority Customer Interaction Intake stream.
- Direction: keep `add_meeting` compatible, then introduce `add_interaction`
  for meeting notes, email threads, user interviews, call summaries, and
  internal notes.
- Rationale: local/sample mode is useful enough that broadening the input
  surface is now more valuable than another dashboard/report. Source metadata
  also supports the upcoming unknown-first scoring and uncertainty work.

Recommended priority:

1. Finish/continue Deal Review Quality calibration.
2. Implement `add_interaction` contract and source-aware extraction.
3. Then return to reporting polish, Pro infrastructure, or MongoDB ecosystem
   upgrades.

### Planning note: CTA eligibility for gaps

Added to [backlog.md](backlog.md):

- Deal Review/Reporting should separate objective CTA triggers from
  judgment-sensitive gap observations.
- Objective triggers can still become explicit actions: overdue dates, missed
  commitments, missing terminal close metadata, or obvious initiation steps.
- Qualitative MEDDPICC gaps such as competition, champion quality, economic
  buyer mapping, or decision criteria should usually be rendered as gap points
  unless the account evidence makes the next action objectively clear.
- Candidate implementation: add `actionability` or `cta_policy` to gap rows
  so reports can render `cta_allowed`, `observation_only`, and
  `needs_human_judgment` differently.

### Planning note: account people graph

Added to [backlog.md](backlog.md):

- Medium-long-term Account People Graph stream.
- Direction: eventually track Champion, Economic Buyer, decision committee,
  procurement, security, legal, and blockers as company/account-indexed people
  intelligence.
- Keep it deferred until deal review quality and customer interaction intake
  are stable. The near-term design constraint is only to preserve source and
  confidence metadata so people extraction can become trustworthy later.

### MCPB Claude Desktop smoke and UTF-8 hardening

Observed:

- Claude Desktop loaded the MCPB extension successfully in `sample` profile
  with `local_sample` storage and the then-current 16 sample-surface tools.
  Current sample surface count is 17 after P3.0.
- `config_doctor`, `list_deals`, `get_metrics`, `get_deal_review`,
  customer-theme analysis, report export, delete dry-run safety, and
  update-stage guidance all worked against bundled sample data.
- One generated Korean progress phrase showed a replacement character in the
  word "heatmap". Tool JSON payloads and sample data did not show broad
  corruption.

Implemented:

- Bumped MCPB manifest to `0.1.11`.
- Added `PYTHONUTF8=1` alongside `PYTHONIOENCODING=utf-8` in MCPB runtime env.
- Removed Korean examples/descriptions from MCP tool docstrings so Claude's
  tool metadata path is English-only.

Verification so far:

- MCPB/tool-surface targeted regression:
  `27 passed`, `1 warning`
- Targeted Ruff:
  `All checks passed`
- MCP tool metadata Korean/replacement-character scan:
  no matches in `mcp_server.py`, MCPB manifest, MCPB README, or manifest tests.
- Full pytest:
  `404 passed`, `1 warning`
- Final Ruff:
  `All checks passed`
- MCPB CLI:
  `mcpb validate manifest.json`
- MCPB artifact:
  `deal-intel-mcp-0.1.11.mcpb`, `size=5.30 KB`,
  `shasum=bbf9099225cb1fbfb01a82c1f7bf54832a7a997b`

Notes:

- The 0.1.11 bundle is still unsigned.

### O3 Mongo index contract

Implemented:

- Added `deals.archived_stage_updated`:
  `(archived, deal_stage, updated_at desc)` for visible list views with stage
  filters and newest-first sorting.
- Added `analytics_snapshots.analytics_snapshot_as_of_occurred_created`:
  `(as_of, occurred_at, created_at)` for pipeline trend range/sort reads and
  Atlas trend charts.
- Preserved existing indexes, including `deal_id_unique`,
  `analytics_snapshot_event_id_unique`, `archived_updated`, and
  `sample_batch`.
- Added targeted index contract tests and updated
  [query-audit.md](query-audit.md) and [backlog.md](backlog.md).

Verification so far:

- O3 targeted regression:
  `14 passed`
- Targeted Ruff:
  `All checks passed`
- Full pytest:
  `404 passed`, `1 warning`
- Final Ruff:
  `All checks passed`
- Live Atlas index creation/explain smoke:
  not run; keep this optional and production-safe.

### O2 BI read projection and Atlas visibility hardening

Implemented:

- Added leading `archived != true` filters to every Weekly Pipeline Atlas chart
  pipeline.
- Hardened `MongoDBClient.list_deals()` projection to exclude
  `contacts` and `summary_embedding` in addition to `_id` and
  `meetings.raw_notes`.
- Added regression tests for Weekly Pipeline chart visibility filters and
  list-view projection.
- Deferred `list_deals_for_metrics()` allowlist conversion until
  BI/review/report field contracts stabilize.
- Updated [query-audit.md](query-audit.md), [atlas-charts.md](atlas-charts.md),
  and [backlog.md](backlog.md).

Verification so far:

- O2 targeted regression:
  `31 passed`, `1 warning`
- Targeted Ruff:
  `All checks passed`
- Full pytest:
  `402 passed`, `1 warning`
- Final Ruff:
  `All checks passed`
- Diff whitespace check:
  `git diff --check`
- CLI render smoke:
  `render-atlas-dashboard --as-of 2026-06-09 --chart-id pipeline_kpis --output .tmp/pipeline_kpis_o2.json`

### O1 Index / query / projection audit

Implemented:

- Added [query-audit.md](query-audit.md) as the current MongoDB read-path audit.
- Inventoried storage read methods, main MCP/report/chart consumers, query
  shapes, projection policy, and current index coverage.
- Confirmed that the main BI/metric/report/deal-review/deal-gap paths use
  restricted projections through `list_deals_for_metrics()` or
  `list_analytics_snapshots()`.
- Confirmed intentional full/raw read exceptions:
  `get_deal` for single-deal detail and `backfill-customer-themes` for
  maintainer LLM backfill.
- Identified O2 follow-up candidates:
  harden `list_deals()` projection, convert metrics projection to allowlist,
  and add archived visibility filters to Weekly Pipeline Atlas chart specs.
- Identified O3 follow-up candidates:
  list-view compound index and trend `as_of` range/sort index.

Verification:

- Documentation map updated.
- Diff whitespace check:
  `git diff --check`

### Z5.12 MCP bundle packaging contract check

Implemented:

- Added repo-local MCP bundle contract tests in
  `tests/test_mcpb_manifest.py`.
- Verified that `mcpb/manifest.json` tool names match
  `deal_intel.tool_surfaces` exactly.
- Verified that bundle installer fields map to runtime environment variables:
  storage backend, tool surface, MongoDB URI, LLM provider, Anthropic API key,
  OpenAI API key, and UTF-8 stdio.
- Verified that the bundled launcher delegates to the installed
  `deal_intel.mcp_server` module and returns an actionable editable-install
  hint when the package is not importable.
- Bumped the bundle manifest version to `0.1.10`.
- Updated `mcpb/README.md` so first-run install guidance reflects current
  sample/local personal mode, `tools_surface=auto`, and dry-run-first
  local-to-Mongo migration.

Verification:

- MCP bundle/config/tool-surface targeted regression:
  `44 passed`, `1 warning`
- Targeted Ruff:
  `All checks passed`
- Full pytest:
  `401 passed`, `1 warning`
- Final Ruff:
  `All checks passed`
- Diff whitespace check:
  `git diff --check`
- MCPB CLI smoke:
  `mcpb pack . deal-intel-mcp-0.1.10.mcpb`
- MCPB artifact contents:
  `manifest.json`, `README.md`, `server/launcher.py`
- MCPB artifact info:
  `size=5.29 KB`, `shasum=291b3f44b330d1fa8252d7917353f654d6695221`

Notes:

- The bundle is not signed yet; `mcpb info` reports `WARNING: Not signed`.

### Z5.11 local personal to MongoDB migration

Implemented:

- Added shared `migrate_local_data` migration engine.
- Added MCP tool `migrate_local_data`.
- Added CLI command `deal-intel local-data migrate-to-mongo`.
- Migration reads only user-created local personal deals from
  `storage.local_data_dir`.
- Bundled zero-config fixture records are never migrated.
- Migration is dry-run by default.
- Actual writes require explicit confirmation through MCP
  `confirmed_by_user=true`; the CLI equivalent is `--apply`.
- Existing target `deal_id` values are skipped by default.
- Existing target `deal_id` values are overwritten only with
  `overwrite=true` / `--overwrite`.
- Local delete audit logs stay local and are reported as a warning; they are
  not migrated.
- Updated MCP tool counts:
  `sample=17`, `standard=21`, `developer=23`.

Verification:

- Migration/tool-surface targeted regression:
  `56 passed`, `1 warning`
- Targeted Ruff:
  `All checks passed`
- Full pytest:
  `395 passed`, `1 warning`
- Final Ruff:
  `All checks passed`
- Diff whitespace check:
  `git diff --check`
- Manifest/surface count smoke:
  `manifest=23`, `sample=17`, `standard=21`, `developer=23`

### Config profiles Z5.8-Z5.10 tool surface runtime filtering

Implemented:

- Added `deal_intel.tool_surfaces` as the source contract for MCP tool
  visibility surfaces.
- Defined non-developer-first surfaces:
  `sample`, `standard`, and `developer`.
- Mapped `sample` profile to the `sample` surface, and `full`/`pro`/`custom`
  to the `standard` surface.
- Kept `sample` semantic-search-free and mostly LLM-free while allowing safe
  local personal create/update/stage/lifecycle writes. P3.0 later added
  optional LLM-backed `add_meeting` for user-created local personal deals.
- Kept real operator admin tools such as `delete_deal` in `standard`, relying
  on their existing dry-run, confirmation, exact-company, archive-gate safety
  contracts.
- Added [tool-surfaces.md](tool-surfaces.md) and linked it from the docs map.
- Updated [config-profiles.md](config-profiles.md) and [backlog.md](backlog.md)
  to mark tool filtering and local personal storage as implemented.
- Clarified user-facing sample-mode positioning: sample is a limited
  feature-test path with bundled fictional data, while real operation assumes
  MongoDB-backed `full` mode.
- Revised that positioning so `sample` is not read-only: mutable/resettable
  local personal data now supports small user datasets before MongoDB.
- Kept `sample_local_personal_target` as a backward-compatible matrix alias for
  the now-current sample tool set.
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
- Added Z5.10 config-driven MCP runtime filtering:
  `tools.surface: auto|sample|standard|developer`.
- Added `DEAL_INTEL_TOOLS_SURFACE` as a packaged/runtime override.
- Runtime `auto` resolves from the effective profile:
  `sample -> sample`, `full/pro/custom -> standard`.
- `sample` now exposes safe local personal write/admin tools alongside
  mostly LLM-free read/reporting tools.
- MCP `list_tools()` is filtered by surface and hidden `call_tool()` requests
  are blocked.
- Invalid `tools.surface` config exposes only `config_doctor` so the setup
  problem remains diagnosable.
- `config show` and `config doctor` now report configured/resolved tool
  surface and MCP tool count.
- Updated the MCP bundle manifest with `tools_surface` and
  `DEAL_INTEL_TOOLS_SURFACE`.

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
- Tool surface runtime targeted regression:
  `61 passed`, `1 warning`
- Expanded MCP surface regression:
  `109 passed`, `1 warning`
- Runtime surface count smoke:
  `sample=17`, `standard=21`, `developer=23`
- Config CLI smoke:
  `config init --profile sample --dry-run` shows
  `storage.local_data_dir: ~/.deal-intel/local-data`
- Full pytest:
  `388 passed`, `1 warning`
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
  `mongodb_uri` optional unless `storage_backend=mongo`, and later updated
  bundle metadata to the current 23-tool surface.
- Updated the documentation map, config-profile contract notes, and active
  backlog index.

Verification:

- Manifest JSON parse:
  `version=0.1.9`, `tools=23`, `storage_backend=local_sample`,
  `mongodb_required=False`
- Manifest/server tool-name comparison:
  `server=23`, `manifest=23`, `tool names match`
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
