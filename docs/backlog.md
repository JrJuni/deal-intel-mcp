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
2. Reinstall smoke with `deal-intel-mcp-0.1.12.mcpb` after the interaction
   intake manifest update and UTF-8 bundle hardening patch.
   hardening patch.
3. Decide whether release bundles need signing before external distribution.

Principle: agents and new users should start in `sample` before being asked for
MongoDB, paid APIs, or Atlas Vector Search.

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
