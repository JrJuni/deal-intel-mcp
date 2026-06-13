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

### Product Roadmap To v1.0 And v2.0

Goal: keep the MVP useful for one-person or small AI-assisted sales teams while
preserving a clear path to deeper customization.

Current positioning:

- The default product is an AI-assisted sales/deal-intelligence record and
  review tool for teams without a mature CRM or dedicated sales operations
  function.
- Different industries have different deal tempo, expected close windows,
  qualification signals, and reporting expectations. Configuration is therefore
  a product feature, not just an implementation detail.
- The MVP should stay simple enough for sample/local evaluation, but the core
  data model should avoid unnecessary Korea-only or MEDDPICC-only assumptions
  where the migration cost is still low.

Recommended implementation order:

1. Full-profile MongoDB operational hardening.
   - Keep ordinary MongoDB features that work on Atlas Free/M0 in `full`, not
     `pro`.
   - First slice: version the normal index contract, add read-only Mongo
     doctor checks, and add a permissive deals collection validator with
     dry-run/apply CLI commands.
   - Later slices can evaluate change streams and time-series collections only
     after the core full/Mongo path is stable.
2. Pro profile skeleton and infrastructure path.
   - Add the paid-infra upgrade path around MongoDB M10+, Atlas Vector Search,
     and related MongoDB ecosystem features where they provide real value.
   - Keep `sample` and `full` working without paid infrastructure.
   - MongoDB features that work on Atlas Free/M0 and improve normal real-data
     operation belong in `full`, not `pro`.
   - P-Pro.1/P-Pro.2 skeleton decisions: no silent Atlas fallback, version the
     `deal_summary_vector` index spec, default OpenAI API usage to
     `gpt-5.4-mini`, add a dry-run/apply vector-index CLI, and defer live
     OpenAI/Atlas smoke until paid infra is available.
3. v1.0 distribution decision.
   - Confirm the first external distribution path after the MVP package is
     stable enough: git-clone assisted install, MCPB, uvx/Python-native, or a
     thin npx wrapper.
4. Review and CSV quality improvements.
   - Improve human-readable deal review and reporting artifacts using external
     feedback after the architecture is stable enough to trial.
5. Other MVP polish and issue fixes.
6. Qualification framework abstraction for v2.0.
   - Defer full MEDDPICC abstraction until after v1.0.
   - Do it on a dedicated branch or separate repository if needed, because it
     touches extraction prompts, score calculation, gap logic, reports,
     dashboards, tests, and user mental models.

MongoDB feature placement rule:

- `full` should include MongoDB-backed features that run on Atlas Free/M0 and
  help ordinary teams operate real data, such as schema validation, ordinary
  indexes, bounded change-stream consumers that respect Free-cluster filter
  limits, and time-series collections for analytics snapshots/events if they
  materially simplify the product.
- `pro` should be reserved for paid infrastructure, paid API defaults, scale
  paths, or admin automation that assumes capabilities beyond Free/M0, such as
  dedicated search/analytics nodes, Atlas Vector Search at scale, paid-tier
  cluster operations, and API-key LLM operation by default.
- Before promoting a MongoDB ecosystem feature to `full`, add a mock/contract
  test and, when practical, a Free-cluster smoke note. If the feature creates
  paid-infra or cost risk, keep it in `pro`.

### Currency Abstraction - Implemented 2026-06-12

Goal: remove currency-specific field names from the core schema so the product
can serve non-KRW teams without making every metric/report feel tied to one
market.

Preferred v1 canonical fields:

- `deal_size_amount`
- `deal_size_low_amount`
- `deal_size_high_amount`
- `deal_size_currency`

Configuration:

```yaml
deal_value:
  default_currency: KRW
```

Implementation stance:

- Do not preserve `_krw` fields as a long-term public contract. There are no
  external users yet, so schema clarity is worth the one-time migration.
- Existing fixture/sample data, tests, reports, metrics, Atlas chart specs, and
  docs should move to the generic names together.
- If compatibility aliases are needed during implementation, keep them local to
  migration/read helpers and remove or mark them temporary before v1.0.
- Output labels should include currency explicitly, for example
  `pipeline_value_amount` plus `currency`, or user-facing labels such as
  `Pipeline value (configured currency)`.

Acceptance criteria:

- `create_deal` and `update_deal` accept the new amount/currency fields.
- Pipeline metrics no longer expose single-currency canonical keys.
- Reports and Atlas specs render values with the configured/default currency.
- Local sample fixtures and Mongo migration paths use the new schema.
- Full pytest, Ruff, natural smoke, report smoke, and Atlas chart render tests
  pass.

Follow-up:

- Atlas Charts remain easiest to operate as one reporting currency per
  dashboard. Python metrics and reports already detect mixed currencies and
  expose per-currency breakdowns.

### Industry And Customer Segment Taxonomy Cleanup

Status: field support, read-only audit, and confirmed cleanup CLI are
implemented; existing live data cleanup is still an operator action because
medium-confidence rows require judgment.

Goal: keep `industry` useful for real vertical analysis while still preserving
account-stage and account-segment labels that matter for BD strategy.

Rules:

- `industry` should be a true business vertical, such as Finance, Retail,
  Healthcare, Logistics, Manufacturing, Education, Government, Insurance,
  Gaming, or Energy.
- `customer_segment` should hold maturity, ownership, market segment, or
  funding-stage labels such as startup, enterprise, mid_market,
  public_sector, Series B, or Pre-IPO.
- Expected-close defaults should prefer `days_by_segment`, then
  `days_by_industry`, then `default_days`.

Deferred work:

- Review medium-confidence rows manually. These rows include sensemaking
  explanations because choosing between two plausible industries can change
  charts, reporting groups, and future search behavior.
- Add optional `customer_segment` filters/grouping to Customer Themes and Atlas
  Charts after the existing dashboard is stable.
- Extend Atlas Charts Customer Themes views with optional `industry_tag`
  dashboard cuts after the current MongoDB dashboard is stable.
- Add an operator backfill to initialize `industry_tags` on older MongoDB rows
  from the current primary `industry`, then review ambiguous rows manually.

### Qualification Framework Abstraction v2.0

Goal: eventually allow teams to replace or extend the default MEDDPICC
qualification model without forking the whole product.

Timing:

- Deferred until after v1.0.
- Treat as v2.0 work on a dedicated branch or separate repository if the
  blast radius grows.

Why deferred:

- The current code intentionally uses MEDDPICC as the default operating model.
- The dimension list is embedded in extraction prompts, health calculation,
  stage-aware gap logic, deal review, reports, Atlas chart specs, tests, and
  docs.
- Generalizing this before the MVP has real user feedback risks turning the
  product into a framework before the core workflow is proven.

Minimum future concept:

- A qualification framework has:
  - `framework_id`
  - dimensions with `key`, `label`, `weight`, score scale, and extraction
    description
  - optional stage-aware gap rules
  - optional framework-specific report labels
- Custom dimensions without stage rules should still work with simple
  threshold-based gap detection.
- Extraction descriptions are mandatory for custom dimensions. A dimension
  without instructions becomes a dead metric because the LLM will not know what
  evidence to collect.

### F-Mongo - Full-Profile MongoDB Hardening

Goal: make the normal MongoDB-backed `full` path operationally diagnosable and
safe on Atlas Free/M0 before spending effort on paid-infrastructure Pro paths.

Implemented slices:

- Versioned ordinary MongoDB index contract in code.
- `MongoDBClient.ensure_indexes()` now applies the shared contract.
- Read-only index/schema readiness checks.
- Permissive v1 `deals` collection validator resource.
- Permissive v1 `analytics_snapshots` and `delete_audit_logs` validator
  resources.
- CLI admin commands:

```bash
deal-intel mongo doctor
deal-intel mongo doctor --offline --json
deal-intel mongo apply-indexes --json
deal-intel mongo apply-indexes --apply
deal-intel mongo apply-schema --json
deal-intel mongo apply-schema --collection analytics_snapshots --json
deal-intel mongo apply-schema --collection delete_audit_logs --json
deal-intel mongo apply-schema --collection all --json
deal-intel mongo apply-schema --apply
```

Rules:

- `mongo doctor` is read-only.
- `apply-indexes` and `apply-schema` are dry-run unless `--apply` is provided.
- `apply-vector-index` is also dry-run unless `--apply` is provided and should
  be used only for the Pro/M10+ Atlas Vector Search path.
- Schema validation starts as `warn + moderate`; do not switch to hard
  `error` enforcement until the document model is stable and existing Atlas
  data has been audited.
- Keep this CLI/admin first. Add an MCP developer-surface tool only if users
  actually need to diagnose MongoDB from inside Claude/Codex chat.

Next candidate units:

1. Optional live Atlas smoke:
   - `deal-intel mongo doctor --json`
   - `deal-intel mongo apply-indexes --json`
   - `deal-intel mongo apply-schema --collection all --json`
   - `deal-intel mongo apply-schema --collection all --apply` only after
     manual confirmation.
   - `deal-intel mongo apply-vector-index --apply` only on an M10+ Pro cluster.
2. Evaluate whether `analytics_snapshots` should remain a normal collection or
   get a separate time-series/event collection after v1.0.
3. Evaluate bounded change-stream consumers only when there is a clear product
   workflow that benefits from them.

### Z5 - Profile and Config Rollout

Goal: keep one package while making first-run setup clear for `sample`, `full`,
and `pro`.

Next candidate units:

1. Optional live Atlas smoke for local personal -> MongoDB migration when a
   disposable target database is available.
2. Reinstall smoke with `deal-intel-mcp-0.1.12.mcpb` after the interaction
   intake manifest update and UTF-8 bundle hardening patch.
   hardening patch.
3. Decide whether release bundles need signing before external distribution.

Principle: human-facing setup starts with `full`. `sample` remains an optional
zero-config evaluation path for AI agents, demos, and users who explicitly do
not want to configure MongoDB yet.

### Deal Review Quality

Goal: make deal review feel useful to real sales operators, not like a toy
scorecard.

Backlog items:

- Implemented in v2: deal reviews now separate health quality, evidence
  coverage, confirmed risks, missing information, uncertainty, objective
  actionable gaps, and judgment-sensitive gap observations. Keep report and
  natural-language rendering aligned with this contract.
- Revisit MEDDPICC unknown-first scoring. Missing evidence should increase
  uncertainty instead of masquerading as neutral strength.
- Keep uncalibrated win-probability numbers suppressed unless a real
  probability contract exists.
- Use smoke packs to compare natural-language deal reviews across multiple
  companies.
- Natural Smoke QA expanded to 12 deterministic questions covering pipeline
  health, specific deal review, riskiest deals, high-health uncertainty,
  closing gaps, postmortem gaps, decision criteria themes, evidence drill-down,
  email/interview-backed themes, pipeline trend, actionability separation, and
  interaction source coverage.
- Implemented in v2, with follow-up rendering work still useful: separate
  objective CTA triggers from judgment-sensitive gap observations.
  - Objective triggers can produce explicit CTAs: overdue close dates,
    missed commitments, missing actual close dates for won/lost deals, missing
    close reasons for lost deals, or clearly required initiation steps.
  - Judgment-sensitive MEDDPICC gaps should usually be shown as gap points
    rather than prescriptive actions: competition, champion quality, economic
    buyer mapping, or decision criteria can depend on account context and BD
    strategy.
  - Reporting language should avoid making uncertain qualitative gaps sound
    like mandatory next actions. Example: "competition gap exists" is safer
    than "prepare competitor comparison and close negotiation" unless the
    account evidence objectively supports that action.
  - Current implementation: `get_deal_gaps` and `get_deal_review` gap rows
    include `actionability` and `cta_policy`; both expose `actionable_gaps` and
    `gap_observations`.
  - Weekly pipeline rows and Markdown reports render objective action items
    separately from gap observations.
  - Remaining follow-up: future document/Word renderers and LLM answer
    templates should keep the same distinction instead of flattening all gaps
    into recommended actions.

### Customer Interaction Intake

Goal: expand from "meeting-note intake" to a lightweight customer interaction
intelligence layer that can ingest emails, interviews, call summaries, and
internal notes without pretending every input is the same kind of evidence.

Priority: high, after the current Deal Review Quality loop and before deeper
Reporting/Pro infrastructure work. This improves local mode usefulness and
real-world data capture more than another dashboard/report would right now.

Candidate implementation units:

1. `add_interaction` read/write contract.
   - Inputs: `deal_id`, `date`, `interaction_type`, `direction`, `content`,
     optional `participants`, `subject`, `source_confidence`.
   - Interaction types: `meeting`, `email_thread`, `user_interview`,
     `call_summary`, `internal_note`.
   - Direction: `inbound`, `outbound`, `mixed`, `internal`.
   - Store source metadata so later scoring can distinguish customer-stated
     evidence from AE/internal notes or outbound claims.
2. Storage compatibility.
   - Keep `add_meeting` as a short-lived backward-compatible wrapper.
   - P3.2 decision: new records live under canonical `interactions`; old
     `meetings` remain supported as a legacy read fallback.
   - BI/report/search paths must continue to exclude raw content unless the
     user asks for single-deal detail.
3. Extraction prompt update.
   - Replace "meeting notes" assumptions with "customer interaction content".
   - Treat inbound customer email and direct user interview quotes as stronger
     evidence than outbound email or internal notes.
   - Outbound/internal-only content should create suggested follow-up questions
     or uncertainty, not confirmed MEDDPICC strength.
4. Evidence and uncertainty model.
   - Feed interaction source metadata into the unknown-first scoring work.
   - Distinguish confirmed risk, missing information, unconfirmed internal
     hypothesis, and customer-stated evidence.
5. Sample/local UX.
   - Add at least one sample email thread and one user interview fixture.
   - Add smoke questions such as "What did customers say in emails?" and
     "Which interview quotes support this pain?".

Open decision points:

- Whether to expose a new MCP tool only (`add_interaction`) or also add CLI
  import helpers for pasted email/interview files.
- Whether to add redaction/encryption policy for retained `raw_content` in
  local/full/pro storage.
- Whether outbound emails should update MEDDPICC scores immediately or only
  create weak/unconfirmed evidence.

Current implementation note:

- P3.0 exposed `add_meeting` in sample/local mode for user-created local
  personal deals.
- P3.1 added `add_interaction` as a meeting-compatible intake path for
  `meeting`, `email_thread`, `user_interview`, `call_summary`, and
  `internal_note`.
- P3.2 switched new writes to canonical `deal.interactions` only. `meetings`
  is now legacy read fallback, and helpers merge/dedupe both sources for
  existing data.
- P3.2 stores `interactions.raw_content` in local/full/pro storage for future
  redaction/security modules, but excludes it from BI/list/report/delete-audit
  paths.
- Custom interaction types must be registered under
  `interactions.custom_types`; arbitrary types are rejected.
- `outbound_unconfirmed` and `internal` inputs are stored with source metadata
  but do not update MEDDPICC health or customer-theme counts unless the caller
  explicitly marks the source as stronger evidence.
- P3.4 added source-aware sample evidence:
  - bundled fixture deals now include canonical `interactions` records while
    preserving legacy `meetings` for compatibility,
  - one inbound `email_thread` and one `user_interview` are included as
    curated evidence examples,
  - customer-theme evidence rows expose safe source metadata so agents can
    distinguish meeting, email, and interview support without reading raw
    content.
- P3.5 added source-aware filters to `get_customer_theme_evidence`:
  `interaction_type` and `source_confidence`. This lets agents answer
  questions like "show only email-backed evidence" without reading raw
  interaction content.
- P3.6 added source-aware rendering:
  - customer-theme evidence rows include a human-readable `source_label`,
  - weekly pipeline rows and Markdown reports show primary pain / decision
    criteria source labels,
  - the natural-question smoke summary includes a Source Evidence section so
    source-aware answers can be checked without reopening an MCP client.
- P3.7 closed the MVP intake contract:
  - `add_interaction` responses include `source_policy` so clients can explain
    confirmed-evidence versus stored-unconfirmed behavior,
  - first-run guidance now describes meeting, email, interview, call-summary,
    and internal-note intake through the single public tool,
  - policy text remains response-only and does not expand restricted BI/list/
    report projections.

#### P3.3 cleanup: single public intake surface

Goal: make the codebase easier for outside users and fork authors to
understand by removing "meeting tool vs interaction tool" ambiguity.
`add_interaction` should become the single public intake concept; meeting notes
are just `interaction_type: meeting`.

First cleanup implemented on 2026-06-11:

- `sample` and `standard` surfaces expose `add_interaction`, not
  `add_meeting`.
- `add_meeting` remains registered only on the `developer` surface as a
  deprecated compatibility alias.
- README, MCPB manifest text, baseline/tool-surface docs, AGENTS/CLAUDE rules,
  and primary tests now point new integrations to `add_interaction`.
- Runtime surface counts are now `sample=17`, `standard=21`, `developer=24`.

Why now:

- P3.2 already made `deal.interactions` the canonical storage path.
- Keeping `add_meeting` as a second first-class tool creates duplicate mental
  models for users and future contributors.
- The repo is intended to be reused by others, so public API clarity matters
  more than preserving a convenience alias forever.

Remaining implementation units:

1. Code cleanup.
   - Stop adding new feature logic to `src/deal_intel/tools/add_meeting.py`.
   - Keep the wrapper tiny or remove it once no test/docs path needs it.
   - Keep legacy `deal.meetings` read fallback in `schema.interactions`; that
     is data compatibility, not a public write API.
2. Final alias removal.
   - Remove `src/deal_intel/tools/add_meeting.py` and the MCP handler after at
     least one compatibility window, or when no supported client path needs it.
   - Keep one release note explaining the replacement call:
     `add_interaction(interaction_type="meeting", direction="inbound", ...)`.
3. Legacy data compatibility.
   - Keep `deal.meetings` read fallback covered by tests even after the write
     alias is removed.

Acceptance criteria:

- No user tutorial or README happy path requires `add_meeting`.
- `interaction_type: meeting` through `add_interaction` covers the former
  `add_meeting` behavior.
- If `add_meeting` remains, it is visibly deprecated and excluded from default
  user-facing surfaces, or there is a documented reason to keep it for one more
  release.
- Legacy `deal.meetings` read fallback remains covered by tests.
- Full pytest, Ruff, MCP/tool-surface count smoke, and MCPB manifest tests pass.

### Account People Graph

Goal: eventually track customer-side people and relationships as queryable
deal intelligence, especially Champion, Economic Buyer, decision committee,
procurement, security, legal, and blockers.

Priority: medium-long term. Do not implement before the deal review quality and
interaction intake work, but keep the design in mind because it will become a
natural query key for BD workflows.

Possible shape:

- Store people in a separate local NoSQL/Mongo collection or RDBMS-like table
  keyed by normalized company/account identity.
- Link people to deals by `company`/`account_id` and optionally `deal_id`.
- Track role labels such as `champion`, `economic_buyer`, `decision_maker`,
  `influencer`, `blocker`, `procurement`, `security`, and `legal`.
- Track confidence and evidence source:
  direct customer statement, meeting note, email thread, internal AE note, or
  inferred/unconfirmed.
- Let BD ask questions like:
  "Who is the champion at this account?",
  "Do we know the economic buyer?",
  "Who blocks security approval?",
  "Which accounts lack a mapped decision committee?".

Implementation cautions:

- Avoid turning this into a full CRM too early.
- Keep raw contact details out of default BI/report paths.
- Prefer explicit source/confidence metadata over silently treating every
  extracted person as confirmed.
- Decide later whether this belongs in MongoDB collections, local JSON/SQLite,
  or a small relational layer. The key requirement is account/company-indexed
  lookup and safe links back to deals.

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

Current MVP stance:

- `docs/mvp-readiness.md` is the full-by-default external MVP gate, with
  optional zero-config sample checks for AI evaluation.
- npx/uvx wrappers are useful, but not required before the first MVP trial.
- Packaging work should not preempt sample/local UX completion unless it
  directly reduces first-run confusion.
- `docs/distribution-plan.md` records the wrapper rollout order:
  package-data readiness first, then uvx/Python-native distribution, with npx
  as a thin convenience wrapper after the core package can run without a git
  checkout.

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
  Current local artifact target: `deal-intel-mcp-0.1.12.mcpb`; unsigned.

### Cost And Query Optimization

Goal: keep MongoDB reads cheap, predictable, and aligned across MCP, reports,
and Atlas Charts.

Next candidate units:

1. Deferred BI metrics allowlist projection.
   - Convert `list_deals_for_metrics()` from blacklist-style projection to
     allowlist-style projection after BI/review/report field contracts
     stabilize.
2. Optional Atlas `explain`/index smoke on a disposable or production-safe
   database.
   - O3 added the intended index contracts in code and tests, but did not run
     live Atlas index creation/explain as part of the local validation loop.

Audit record:

- See [query-audit.md](query-audit.md).

Completed:

- O3 index contract:
  - Added `(archived, deal_stage, updated_at desc)` for list views.
  - Added `(as_of, occurred_at, created_at)` for trend reads.

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
