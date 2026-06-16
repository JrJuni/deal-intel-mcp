# Qualification Framework v2 Plan

This document is the execution plan for turning MEDDPICC from a hardcoded
product assumption into the default configurable qualification framework.

The goal is not to remove MEDDPICC. The goal is to let teams keep MEDDPICC,
extend it, or replace it with their own deal-evaluation model without forking
the whole product.

## North Star

Users should be able to:

1. add, update, disable, or remove deal-evaluation criteria;
2. get guidance and guardrails when defining criteria;
3. have review, gap, metric, report, and chart paths reflect the active
   framework;
4. keep the architecture flexible enough for non-MEDDPICC frameworks.

The product should still work out of the box with MEDDPICC as the default.

## Mental Model

Current shape:

```text
interaction.meddpicc
  -> deal.meddpicc_latest
  -> health_pct / gaps / review / reports / charts
```

Target shape:

```text
interaction.qualification
  -> deal.qualification_latest
  -> quality_pct / coverage_pct / uncertainty / gaps / review / reports / charts
```

Compatibility shape during migration:

```text
qualification_latest is the new canonical field.
meddpicc_latest remains as a mirror or read alias while existing tools/tests move.
```

## Design Decisions

- MEDDPICC remains the bundled default framework.
- Use `qualification` as the generic public concept.
- Use `qualification_latest` as the future canonical deal snapshot.
- Keep `meddpicc_latest` temporarily for compatibility.
- Separate score quality from evidence coverage:
  - `quality_pct`: how strong known evidence is;
  - `coverage_pct`: how much of the framework is actually evidenced;
  - `uncertainty_level`: how cautious the assistant should be.
- Keep the v2 score scale fixed at 0-5 first. Custom score scales are deferred.
- Framework edits update config only. Historical data recomputation/backfill is
  a separate explicit step.
- Dimension removal should start as disable/deprecate, not silent hard removal.
- BI/data exports remain LLM-free. Wizard/suggestion tools may use the
  server-side LLM only when explicitly documented and cost-visible.

## Work Units

### QF-0. Developer Map And Execution Gates

Purpose:

- Create the map and guardrails before changing runtime behavior.

Implementation:

- Expand architecture docs with current MEDDPICC dependency points.
- Add this execution plan.
- Link the plan from backlog/status.

Verification gate:

- Documentation diff only.
- Confirm no runtime files changed unless intentionally noted.
- Confirm next unit has clear acceptance criteria.

Corner cases to keep visible:

- Existing docs may still say MEDDPICC where the future concept should be
  qualification framework.
- Hardcoded tool counts or stale names should not be introduced.

### QF-1. Framework Contract, Templates, And Static Validator

Status:

- Implemented in `src/deal_intel/schema/qualification_framework.py`.
- Covered by `tests/test_qualification_framework.py`.
- Runtime-neutral: no MCP tool, storage schema, extraction, metric, report, or
  existing MEDDPICC behavior changed.

Contract:

- Input: a qualification framework payload with `key`, `display_name`, fixed
  `score_scale`, and `dimensions`.
- Output: a validated framework model or a secret-safe validation report with
  `ok`, `framework`, `errors`, and `warnings`.
- Side effects: none. No config writes, DB access, LLM calls, embedding work, or
  MCP registration.
- Security: secret-shaped strings are rejected and never echoed in validation
  messages.
- Out of scope: applying framework changes, recomputing existing deals, and
  changing current MEDDPICC scoring behavior.

Purpose:

- Define what a valid qualification framework is.
- Give users templates instead of forcing them to write YAML from scratch.
- Provide deterministic guardrails before wizard/update tools exist.

Implementation:

- Add `src/deal_intel/schema/qualification_framework.py`.
- Define dataclasses or Pydantic models for:
  - framework key;
  - display name;
  - fixed score scale 0-5;
  - dimensions;
  - dimension label;
  - description;
  - extraction hint;
  - weight;
  - gap threshold;
  - suggested question;
  - CTA policy;
  - optional stage rules.
- Add bundled templates:
  - `meddpicc`;
  - `simple_b2b`;
  - `pilot_poc`;
  - `enterprise_procurement`;
  - `product_led_sales`.
- Add a static validator that rejects:
  - invalid keys;
  - missing labels/descriptions/extraction hints;
  - zero or negative weights;
  - fewer than two enabled dimensions;
  - invalid CTA policy;
  - secret-shaped strings;
  - obviously unscorable extraction hints.

Verification gate:

- Targeted tests for valid built-in templates.
- Targeted tests for every validator failure mode.
- Targeted tests that MEDDPICC default dimensions and weights match the current
  v1 defaults.
- Ruff.

Corner cases:

- A user writes a dimension called `Champion!` instead of `champion`.
- A dimension has a label but no extraction hint.
- A dimension says "score this well" but gives no evidence criteria.
- Weight is 0, negative, boolean, or a string.
- A framework disables all but one dimension.
- A field accidentally contains an API key or MongoDB URI.

### QF-2. Framework Wizard And Config Update Tools

Status:

- Partially implemented as the non-LLM safe path.
- Implemented MCP tools:
  - `get_qualification_templates`
  - `validate_qualification_framework`
  - `update_qualification_framework`
- Deferred to QF-2b:
  - `suggest_qualification_framework`, because it needs separate LLM cost,
    quality, and prompt-injection test coverage.

Contract:

- `get_qualification_templates`
  - Input: optional `template_key`, optional `include_dimensions`.
  - Output: bundled templates, summaries, and usage guidance.
  - Side effects: none. No config writes, DB access, LLM calls, embeddings, or
    storage access.
- `validate_qualification_framework`
  - Input: either `template_key` or a JSON/YAML `framework_json` payload.
  - Output: static validation report with framework details, errors, and
    warnings.
  - Side effects: none. No file writes, DB access, LLM calls, embeddings, or
    storage access.
- `update_qualification_framework`
  - Input: either `template_key` or `framework_json`, optional `copy_as_key`
    and `copy_display_name` when copying a built-in template, plus `dry_run`,
    `confirmed_by_user`, and `set_active`.
  - Output: dry-run/apply result, changed fields, validation report, backup
    path when applicable, `preset_immutable`, `stores_framework`, and
    `restart_required`.
  - Side effects: dry-run by default. Actual writes require
    `confirmed_by_user=true` and only update non-secret user config under
    `~/.deal-intel/config.yaml`.
  - Out of scope: recomputing historical deals, rewriting existing
    interactions, changing extraction prompts, calling LLMs, touching MongoDB,
    and updating embeddings.

Purpose:

- Make framework customization usable for non-developers.
- Let AI hosts help users design criteria without leaving them with raw YAML.
- Keep bundled presets recoverable. Built-in templates such as `meddpicc`,
  `simple_b2b`, and `pilot_poc` cannot be overwritten under their original
  keys. Customization must copy a preset to a new framework key first.

Implementation:

- Add read-only `get_qualification_templates`.
- Add deterministic `validate_qualification_framework`.
- Add dry-run-first `update_qualification_framework`.
  - Selecting a built-in template without `copy_as_key` only switches the
    active preset; it does not store a mutable copy.
  - Supplying `copy_as_key` clones the template into
    `qualification.frameworks.<copy_as_key>`.
  - Supplying `framework_json` with a built-in key is rejected with
    `PRESET_FRAMEWORK_IMMUTABLE`.
- Add optional `suggest_qualification_framework`.
  - This tool may call the configured server-side LLM.
  - It should clearly report that it is suggestion-only and may incur LLM cost.
- Update MCPB manifest and tool surfaces.
- Keep update writes limited to safe non-secret config fields.

Verification gate:

- MCP registration/tool-surface tests.
- Static validation tests.
- Config writer tests for dry-run and confirmed apply.
- Secret rejection tests.
- LLM suggestion tests should mock the provider.
- Ruff and relevant full regression.

Corner cases:

- Host asks to remove a dimension used by existing historical data.
- User asks for an extremely vague criterion such as "good fit".
- Wizard suggests overlapping dimensions.
- Wizard suggests too many dimensions for a small team.
- User wants to apply a framework change without confirmation.
- User tries to mutate `meddpicc` directly and later wants the original back.

### QF-2b. Framework Manager Tools

Status:

- Implemented the non-LLM lifecycle manager for saved qualification frameworks.
- Added MCP tools:
  - `list_qualification_frameworks`
  - `set_active_qualification_framework`
  - `delete_qualification_framework`

Contract:

- `list_qualification_frameworks`
  - Input: optional `include_dimensions`.
  - Output: built-in templates, user-configured frameworks, validation state,
    active framework, and warnings.
  - Side effects: none. No file writes, DB access, LLM calls, embeddings, or
    storage access.
- `set_active_qualification_framework`
  - Input: `framework_key`, `dry_run`, `confirmed_by_user`.
  - Output: dry-run/apply result, changed fields, backup path when applicable,
    previous framework, target framework, and `restart_required`.
  - Side effects: dry-run by default. Actual writes require
    `confirmed_by_user=true` and only update
    `qualification.active_framework` in user config.
- `delete_qualification_framework`
  - Input: `framework_key`, `dry_run`, `confirmed_by_user`.
  - Output: dry-run/apply result, deleted framework summary, changed fields,
    backup path when applicable, and `restart_required`.
  - Side effects: dry-run by default. Actual writes require
    `confirmed_by_user=true` and delete only stored custom frameworks from user
    config.

Guardrails:

- Built-in templates cannot be deleted.
- Stored overrides using built-in keys are ignored so the original preset stays
  recoverable.
- The active framework cannot be deleted; switch active framework first.
- Invalid configured frameworks can be listed with warnings but cannot be
  activated.
- These tools do not recompute existing deals. Historical recomputation remains
  a separate backfill concern.

Verification gate:

- Targeted config tests for list, switch, delete, dry-run, confirmation gating,
  backup creation, built-in delete protection, and active delete protection.
- MCP wrapper test.
- Tool surface and MCPB manifest alignment tests.
- Ruff and full regression.

### QF-3. Generic Qualification Snapshot Engine

Status:

- Partially implemented as the pure calculation layer.
- Added `src/deal_intel/schema/qualification.py` with
  `compute_qualification_latest(...)`.
- Moved stage constants into `src/deal_intel/schema/stages.py` to break the
  MEDDPICC/framework import cycle.
- Kept `compute_meddpicc_latest(...)` as the compatibility wrapper used by
  existing write paths.
- Added `compute_meddpicc_qualification_latest(...)` so future write/read paths
  can consume the canonical qualification snapshot without changing current
  `meddpicc_latest` consumers.

Contract:

- Input:
  - iterable evidence items;
  - a validated `QualificationFramework`;
  - one or more evidence field names such as `qualification` or `meddpicc`;
  - current deal stage.
- Output:
  - `framework_key`, `framework_display_name`, `score_scale`;
  - nested `dimensions` with score, trend, evidence count, and weight;
  - `quality_pct`, `coverage_pct`, `uncertainty_level`;
  - compatibility `health_pct`, `filled_count`, `total_count`, and `gaps`.
- Score math uses the framework score scale and enabled dimension weights.
- Side effects: none. No config reads, DB access, LLM calls, embeddings, file
  writes, or historical recomputation.
- Compatibility:
  - existing `compute_meddpicc_latest(...)` output shape remains unchanged;
  - existing `meddpicc_latest` read/report/metric paths still work;
  - this unit does not yet write `qualification_latest` to deals.

Purpose:

- Generalize `compute_meddpicc_latest` into framework-based scoring.

Implementation:

- Add `compute_qualification_latest(...)`.
- Keep MEDDPICC compatibility wrapper.
- Output canonical fields:
  - `framework_key`;
  - `framework_display_name`;
  - `quality_pct`;
  - `coverage_pct`;
  - `uncertainty_level`;
  - `filled_count`;
  - `total_count`;
  - `gaps`;
  - `dimensions`.
- Keep compatibility fields where needed:
  - `health_pct`;
  - `meddpicc_latest`.

Verification gate:

- Existing MEDDPICC fixtures produce compatible scores.
- Missing evidence increases uncertainty/low coverage instead of pretending to
  be neutral confidence.
- Stage-aware gap rules still work for default MEDDPICC.
- Custom dimensions without stage rules use simple threshold gap detection.
- Ruff and targeted score-engine regression.

Corner cases:

- No dimensions are filled.
- One dimension is very strong but coverage is low.
- Evidence is complete but scores are low.
- A won deal should not show open gaps.
- A lost deal may keep gaps for postmortem.

### QF-3b. Persist Canonical Qualification Snapshot

Status:

- Implemented write-path persistence for `qualification_latest`.
- `create_deal` initializes `qualification_latest: {}`.
- `add_interaction` rebuilds both:
  - legacy `meddpicc_latest`;
  - canonical `qualification_latest`.
- `update_stage` rebuilds both snapshots when scoring evidence exists so
  stage-aware gap classification stays aligned.
- MongoDB deals schema recognizes optional `qualification_latest`.

Contract:

- `meddpicc_latest` remains the compatibility read-path contract for existing
  BI, reports, Atlas charts, and deal review.
- `qualification_latest` is the new framework-aware snapshot for future read
  paths.
- Built-in qualification presets are immutable. `qualification_latest` resolves
  active built-in keys from bundled templates first and ignores user-configured
  frameworks that reuse preset keys.
- Legacy `meddpicc.weights` and `meddpicc.gap_threshold` still feed the
  compatibility `meddpicc_latest` read path until that path is retired or
  migrated.
- When a non-MEDDPICC framework is active, `qualification_latest` reads only
  `interaction.qualification` evidence. QF-4 will generate that evidence.
- MEDDPICC evidence is not force-mapped into unrelated custom frameworks.

Verification gate:

- `create_deal` persists an empty canonical snapshot slot.
- `add_interaction` stores and returns `qualification_latest`.
- `update_stage` recomputes canonical gaps for terminal stage changes.
- Mongo validator includes `qualification_latest`.
- Existing MEDDPICC read paths keep using `meddpicc_latest`.

### QF-4a. Generic Extraction Contract

Purpose:

- Define the active-framework extraction contract before changing the
  `add_interaction` LLM prompt.
- Keep the boundary permissive for LLM output but strict for stored
  qualification evidence.

Implemented:

- Added `src/deal_intel/schema/qualification_extraction.py`.
- `build_qualification_extraction_contract(framework)` returns a serializable
  prompt contract containing enabled dimension keys, labels, descriptions,
  extraction hints, score scale, output schema, and safety rules.
- `render_qualification_extraction_prompt_block(framework)` renders a compact
  prompt block for the future interaction extraction prompt.
- `normalize_qualification_extraction(payload, framework=...)` normalizes
  LLM-like output into:
  - `qualification.<dimension>.score`
  - optional short `evidence`
  - optional short `reason`
  - optional `confidence`
- Missing dimensions remain missing. They are not converted into neutral scores.
- Unknown dimensions, disabled dimensions, invalid scores, fractional scores,
  out-of-range scores, invalid confidence, long evidence, and secret-like text
  are handled with structured warnings.
- `normalize_interaction_record()` now preserves stored
  `interaction.qualification` and `interaction.unconfirmed_qualification` so
  custom framework evidence survives the `scoring_interactions()` read path.

Verification gate:

- Contract includes enabled dimensions only.
- Prompt block includes active framework dimensions and output hints.
- Wrapped and direct dimension maps normalize into the same storage shape.
- Unknown, disabled, invalid, fractional, and out-of-range dimensions are
  dropped without contaminating the score engine.
- Secret-like text is redacted and long evidence is bounded.
- Normalized evidence feeds `compute_qualification_latest()` without neutral
  filler scores.
- Stored `interaction.qualification` survives normalization into
  `rebuild_latest_snapshots()`.
- Existing `add_interaction` regression tests remain green.

### QF-4b. Interaction Extraction Generalization

Status:

- Implemented the first runtime integration.
- `add_interaction` now resolves the active framework before calling the LLM.
- Non-MEDDPICC active frameworks inject the framework extraction contract into
  the LLM prompt and store normalized evidence in `interaction.qualification`.
- Unconfirmed sources store custom-framework evidence in
  `interaction.unconfirmed_qualification` only.
- `qualification_latest` is rebuilt from the active framework after each
  interaction.
- Legacy `interaction.meddpicc`, `meddpicc_latest`, customer themes, and
  stage suggestions remain compatible.

Contract:

- Active `meddpicc`:
  - LLM output uses the existing top-level `meddpicc` object.
  - `qualification_latest` reads `interaction.meddpicc`.
- Active non-MEDDPICC framework:
  - LLM output may include a top-level `qualification` object keyed by the
    active framework's dimensions.
  - Stored confirmed evidence goes to `interaction.qualification`.
  - Stored unconfirmed evidence goes to `interaction.unconfirmed_qualification`.
  - Unknown, disabled, invalid, fractional, or out-of-range dimensions are
    dropped with structured warnings.
- Invalid active framework config fails during preflight before LLM calls.

Purpose:

- Make `add_interaction` extract the active framework, not hardcoded MEDDPICC.

Implementation:

- Build extraction prompt from the active framework dimensions.
- Store `interaction.qualification`.
- Keep `interaction.meddpicc` compatibility when the active framework is
  MEDDPICC.
- Recompute `deal.qualification_latest`.
- Keep `deal.meddpicc_latest` as the compatibility mirror during the migration
  window.
- Keep source-policy behavior:
  - customer-stated evidence can update confirmed scores;
  - outbound/internal evidence remains unconfirmed by default.

Verification gate:

- Mocked LLM extraction for default MEDDPICC.
- Mocked LLM extraction for a custom framework.
- Custom framework extraction without a `meddpicc` object is parsed safely.
- Source-policy tests remain green.
- Usage tracking still records server-side LLM calls.
- No raw content leaks into list/report/BI paths.
- Ruff and targeted interaction regression.

Corner cases:

- LLM returns unknown dimension keys.
- LLM omits a required dimension.
- LLM returns scores outside 0-5.
- Custom framework has similar dimension names.
- Existing legacy `meetings` data must remain readable.

### QF-5. Review, Gap, And Metric Migration

Purpose:

- Move deterministic read paths from MEDDPICC-only logic to qualification
  framework logic.

Implementation:

- Update:
  - `get_deal_review`;
  - `get_deal_gaps`;
  - `list_deals`;
  - `get_metrics`;
  - `get_insights` compatibility paths.
- Rename internal concepts carefully:
  - MEDDPICC health -> qualification quality where generic;
  - MEDDPICC filled count -> qualification evidence coverage;
  - MEDDPICC gaps -> qualification gaps.
- Keep old output aliases for compatibility where needed.

Verification gate:

- Existing natural-question smoke still passes.
- Deal review audit still passes.
- Targeted tests for default MEDDPICC compatibility.
- Targeted tests for a non-MEDDPICC custom framework.
- No BI/read path calls LLM.
- Ruff and full regression.

Corner cases:

- Sample data still has only `meddpicc_latest`.
- A custom dimension has no suggested question.
- A dimension is disabled but historical evidence exists.
- A report asks for "MEDDPICC gaps" while the active framework is not
  MEDDPICC.

#### QF-5a. Deal Review Read Path

Status: implemented.

Implemented:

- `build_deal_review()` now chooses `qualification_latest` as the canonical
  review snapshot when available, with `meddpicc_latest` as the legacy fallback.
- Deal-review responses include a top-level `qualification` summary with:
  `framework_key`, `framework_display_name`, `source_field`, `health_pct`,
  `quality_pct`, `coverage_pct`, `filled_count`, `total_count`, and `gaps`.
- Existing MEDDPICC compatibility fields remain present while generic
  `qualification_*` interpretation fields are added.
- Scorecards, known signals, confirmed risks, and recommended questions now use
  framework-aware dimension labels and fields.
- Non-MEDDPICC review gaps are rendered as `qualification.<dimension>` instead
  of `meddpicc.<dimension>`.
- `compute_qualification_latest()` now stores secret-safe dimension metadata so
  read paths can preserve labels and suggested questions without reloading the
  full framework config.
- Data-quality health assessment accepts valid `qualification_latest` snapshots.

Boundaries:

- This subtask does not migrate `get_deal_gaps`, `list_deals`, metrics,
  reports, or Atlas chart specs.
- Custom framework qualitative gaps remain observations by default; objective
  timing/data-quality gaps still drive CTA-safe action rows.

Verification:

- `pytest tests/test_deal_review.py tests/test_qualification_snapshot.py -q --basetemp .tmp\pytest-qf5a-targeted`:
  23 passed, 1 warning.
- `pytest tests/test_deal_review.py tests/test_cli_deal_review_smoke.py tests/test_zero_config_sample_fixture.py tests/test_deal_gaps.py tests/test_metric_contract.py tests/test_pipeline_metrics_summary.py tests/test_add_interaction.py tests/test_update_stage.py -q --basetemp .tmp\pytest-qf5a-wide`:
  107 passed, 1 warning.
- `pytest -q --basetemp .tmp\pytest-qf5a-full`:
  628 passed, 1 warning.
- `ruff check src/deal_intel/schema/deal_review.py src/deal_intel/schema/qualification.py src/deal_intel/schema/metrics.py tests/test_deal_review.py`:
  passed.
- `ruff check .`:
  passed.

#### QF-5b. Deal Gaps And List Views

Status: implemented.

Implemented:

- Added `schema/qualification_read.py` as the shared active-framework snapshot
  selector for deterministic read paths.
- `get_deal_gaps` and `list_deals` now prefer canonical
  `qualification_latest` when available and fall back to `meddpicc_latest` for
  legacy/sample data.
- `get_deal_gaps` emits custom-framework gaps as
  `qualification.<dimension>` fields and `qualification:<dimension>` IDs while
  preserving `meddpicc.*` / `meddpicc:*` compatibility for MEDDPICC data.
- `list_deals` keeps existing `health_pct`, `filled_count`, and `gaps` aliases
  but now sources them from the active qualification snapshot.
- Both read views expose generic `qualification_*` metadata so host apps can
  explain which framework produced the visible health/gap state.
- Qualitative `qualification.*` gaps are observation-only by default, matching
  the existing MEDDPICC CTA-safety policy.

Boundaries:

- This unit does not migrate `get_metrics`, `get_insights`, report/export
  fields, Atlas chart specs, or analytics snapshots.
- Existing old data with only `meddpicc_latest` remains readable.

Verification:

- `pytest tests/test_deal_gaps.py tests/test_data_quality_reporting.py tests/test_deal_review.py -q --basetemp .tmp\pytest-qf5b-targeted`:
  38 passed, 1 warning.
- `pytest tests/test_deal_gaps.py tests/test_get_deal_gaps.py tests/test_deal_review.py tests/test_data_quality_reporting.py tests/test_pipeline_timing.py tests/test_zero_config_sample_fixture.py tests/test_local_sample_backend.py -q --basetemp .tmp\pytest-qf5b-wide`:
  107 passed, 1 warning.
- Targeted Ruff over touched files:
  passed.

#### QF-5c. Pipeline Metrics And Pipeline Overview

Status: implemented.

Implemented:

- `schema/pipeline_metrics.py` now reads active health/quality state through
  `schema/qualification_read.py`.
- `get_metrics(metric_type="pipeline_health")` now prefers
  `qualification_latest` and falls back to legacy `meddpicc_latest`.
- `get_insights(query_type="pipeline_overview")` now reflects the same active
  qualification snapshot because it delegates to the shared pipeline metric
  engine.
- Existing public metric aliases remain unchanged: `avg_health_pct`,
  `health_coverage_pct`, `health_bands`, stage-level `avg_health_pct`, and
  attention `at_risk` counts.

Boundaries:

- This unit does not migrate direct Mongo aggregation insight paths:
  `win_patterns`, `loss_patterns`, `compare_won_lost`, `gap_frequency`, and
  `industry_benchmark`.
- This unit does not migrate report/export rows, Atlas specs, or analytics
  snapshots.
- Existing old/sample data with only `meddpicc_latest` remains readable.

Verification:

- `pytest tests/test_pipeline_metrics_summary.py tests/test_get_metrics.py tests/test_data_quality_reporting.py -q --basetemp .tmp\pytest-qf5c-targeted-rerun`:
  31 passed, 1 warning.
- `pytest tests/test_pipeline_metrics_summary.py tests/test_get_metrics.py tests/test_data_quality_reporting.py tests/test_dashboard_crosscheck.py tests/test_metric_contract.py tests/test_pipeline_timing.py tests/test_export_report.py -q --basetemp .tmp\pytest-qf5c-wide`:
  119 passed, 1 warning.
- `pytest -q --basetemp .tmp\pytest-qf5c-full`:
  633 passed, 1 warning.
- `ruff check .`:
  passed.

### QF-6. Reports, Data Exports, And Atlas Specs

Purpose:

- Make human reports, CSV ledgers, and dashboards reflect the active framework.

Status:

- Implemented.

Implementation:

- `weekly_pipeline` rows now carry generic qualification fields:
  `qualification_framework`, `qualification_framework_display_name`,
  `qualification_source_field`, `qualification_health_pct`,
  `qualification_quality_pct`, `qualification_coverage_pct`, and
  `qualification_gaps`.
- `health_pct`, `health_band`, and `meddpicc_gaps` remain compatibility aliases;
  `meddpicc_gaps` is populated only when the selected/fallback snapshot is
  MEDDPICC-backed.
- Markdown report labels and reasons now say qualification gap/health where the
  active framework may not be MEDDPICC.
- `export_data` columns now include qualification fields for open/all/closed
  datasets.
- Version Atlas chart specs:
  - weekly health calculations read `qualification_latest` first and
    `meddpicc_latest` as fallback;
  - keep old `meddpicc_gap_distribution` as compatibility;
  - introduce `qualification_gap_distribution`.
- Update dashboard render/crosscheck expectations.

Verification gate:

- Report export targeted tests.
- CSV formula-injection tests remain green.
- Markdown numbers still match source data.
- Atlas chart render tests.
- Dashboard crosscheck tests.
- Ruff and full regression.

Corner cases:

- Non-MEDDPICC framework labels are long.
- Mixed framework data exists during migration.
- Dashboard expects old field names; legacy chart id remains available.
- CSV consumers still expect `health_pct`.

### QF-7. Backfill And Recompute

Purpose:

- Let users update historical deal snapshots when framework definitions change.

#### QF-7a. Recompute-Only Qualification Snapshot Backfill

Status:

- Implemented.

Implemented:

- Added `tools/backfill_qualification.py`.
- Added CLI command `deal-intel backfill-qualification`.
- Dry-run is the default; writes require `--apply --confirmed-by-user`.
- Recomputes `meddpicc_latest` and `qualification_latest` from already stored
  scoring evidence only.
- Performs no LLM calls, embedding work, raw-content reads, or full deal
  replacement writes.
- Added `update_deal_qualification_snapshots(...)` storage method so recompute
  apply operations patch only snapshot fields and `updated_at`.
- Skips deals with no scoring evidence so unassessed deals do not become false
  low-health/all-gap records.
- Flags active custom-framework records with only legacy MEDDPICC evidence as
  `needs_reextraction`, leaving them for QF-7b.

Verification:

- `pytest tests/test_backfill_qualification.py tests/test_storage_backend_contract.py -q --basetemp .tmp\pytest-qf7a-targeted`:
  15 passed.
- Targeted Ruff over touched files:
  passed.

Boundaries:

- This unit does not read `interaction.raw_content`.
- This unit does not re-run extraction prompts.
- This unit does not expose an MCP tool yet; QF-7c will decide final MCP
  surface and tool contract after QF-7b.

#### QF-7b. LLM Re-Extraction

Status:

- Implemented as core + CLI.
- Added command: `deal-intel backfill-qualification-reextract`.
- MCP exposure remains deferred to QF-7c.

Purpose:

- Re-extract active-framework evidence from historical `interaction.raw_content`
  when stored evidence is missing for the active framework.

Decisions:

- Default scope is scoring-eligible interactions only. Internal and
  outbound-unconfirmed context is excluded unless explicitly requested.
- Default one-run LLM cap is 30 calls.
- This unit exposes core + CLI first. MCP exposure is deferred to QF-7c after
  the raw-content and cost contract has been proven.

Implementation:

- Add an explicit raw-content re-extraction path for new or changed extraction
  hints.
- Use a dedicated maintenance storage read path. Do not reuse BI/reporting
  readers that intentionally exclude `interactions.raw_content`.
- Store a framework fingerprint beside extracted evidence so future framework
  changes can distinguish clean evidence from stale evidence.
- Dry-run by default.
- Report affected deals/interactions, selected call count, input-character
  estimate, and cost warnings.
- Apply mode requires explicit confirmation.
- Patch only interaction qualification evidence and deal-level qualification
  snapshots. Do not replace unrelated deal fields.
- Track usage under `interaction.qualification_backfill_usage` so `get_usage`
  can report re-extraction cost without overwriting original interaction usage.

Implemented:

- Added `tools/backfill_qualification_reextract.py`.
- Added `list_deals_for_qualification_reextract(...)` storage read path that
  intentionally includes `interactions.raw_content` while excluding contacts,
  vectors, and legacy meeting raw notes.
- Added `update_deal_qualification_reextraction(...)` patch write path for
  interactions plus current qualification snapshots.
- Added `qualification_framework_fingerprint(...)` and persist
  `qualification_framework_hash` on new `add_interaction` writes.
- Re-extraction stores:
  - `interaction.meddpicc` for active MEDDPICC;
  - `interaction.qualification` for active custom frameworks;
  - unconfirmed fields only when explicitly requested.
- `get_usage` now includes `qualification_backfill_usage`.

Verification gate:

- Dry-run tests.
- Recompute-only tests without LLM.
- LLM re-extraction tests with mocked provider.
- Idempotency tests.
- No raw-content exposure in responses.
- Ruff and targeted storage regression.

Corner cases:

- Raw content is unavailable for old records.
- Framework change affects thousands of interactions.
- Partial failure should return structured warnings.
- User cancels after dry-run.

#### QF-7c. MCP Backfill Surface

Status:

- Implemented.

Purpose:

- Let Claude, Codex, and other MCP hosts complete the same historical
  qualification maintenance flow that the CLI supports, without forcing users
  to leave the chat app for routine framework migration checks.

Implemented:

- Added MCP tool `backfill_qualification`.
  - Exposed on the `standard` and `developer` surfaces.
  - Hidden from `sample` to keep first-run zero-config mode simple.
  - Defaults to dry-run.
  - Performs no LLM calls and does not read `interaction.raw_content`.
  - Apply mode patches only current qualification snapshots and requires
    `dry_run=false` plus `confirmed_by_user=true`.
- Added MCP tool `backfill_qualification_reextract`.
  - Exposed on the `standard` and `developer` surfaces.
  - Hidden from `sample`.
  - Defaults to dry-run and does not initialize the LLM provider in dry-run.
  - Defaults to `max_llm_calls=30`.
  - Apply mode may read historical `interactions.raw_content` through the
    dedicated maintenance storage path and call the configured LLM once per
    selected interaction.
  - Responses never include raw interaction content.
- Updated tool-surface contracts and MCPB manifest tool declarations.
- Current runtime tool counts:
  - `sample=24`
  - `standard=35`
  - `developer=38`

Recommended host flow:

1. After framework changes, call `backfill_qualification` with defaults.
2. If it reports `needs_reextraction`, call
   `backfill_qualification_reextract` in dry-run mode.
3. Review `selected_count`, `max_llm_calls`, warnings, and target rows.
4. Apply only after user confirmation.
5. Use `get_usage` afterward if the user wants cost/usage visibility.

Verification:

- MCP wrapper dry-run tests confirm no LLM initialization for both recompute
  and re-extraction dry-runs.
- MCP apply test confirms re-extraction uses the confirmed LLM path and
  respects the one-run cap.
- Tool surface tests confirm the new tools are hidden from `sample` and visible
  in `standard`/`developer`.
- MCPB manifest tests confirm package metadata matches runtime contracts.
- Targeted QF-7c test gate:
  `82 passed, 1 warning`.

### QF-8. Compatibility Cleanup

Status:

- Implemented as the public-surface wording cleanup pass.
- MCP docstrings, MCPB manifest descriptions, README, AI_START_HERE, and
  baseline docs now describe MEDDPICC as the bundled default qualification
  framework instead of the permanent hardcoded model.
- Compatibility field names such as `meddpicc`, `meddpicc_latest`, and
  `unconfirmed_meddpicc` remain intentionally documented because old records
  and default-framework records still expose them.
- Broad tool renaming and namespace reshaping remain deferred to QF-9.

Purpose:

- Reduce MEDDPICC-only naming after generic framework paths are stable.

Implementation:

- Update docs to call MEDDPICC the default framework.
- Deprecate or remove old MEDDPICC-only helpers once tests and docs no longer
  need them.
- Keep a migration note for existing users.
- Do not rename tools broadly until the namespace cleanup pass.

Verification gate:

- Full pytest.
- Ruff.
- Natural smoke.
- MCPB manifest tests.
- Launch hygiene scan for stale names that are not intentionally preserved.

Corner cases:

- External users may still ask "MEDDPICC" by name.
- Old datasets may still contain only `meddpicc_latest`.
- Public docs should not imply MEDDPICC is removed.

### QF-9. Tool Namespace And Customer Theme Cleanup

Purpose:

- After framework abstraction, make the public tool surface more intent-driven.

Implementation:

- Revisit customer-theme tools:
  - keep current tools as compatibility aliases if needed;
  - consider `get_customer_themes` with detail/depth options.
- Revisit tool descriptions and names only after framework field names settle.
- Preserve `get_tool_catalog` as the discovery escape hatch.

Current implementation direction:

- Keep the existing customer-theme tool names for compatibility.
- Add user-intent workflow metadata to `get_tool_catalog` so host apps can
  group tools by setup, intake, deal review, customer themes, reports,
  framework admin, usage/memory, optional LLM/search, and sample/admin flows.
- Add short `namespace` / `intent_alias` metadata to catalog rows for
  developer and host-model readability. These are not callable alias tools;
  canonical MCP tool names remain unchanged.
- Add `workflow` metadata to customer-theme responses:
  - `get_customer_themes` = ranking step;
  - `get_customer_theme_breakdown` = comparison step;
  - `get_customer_theme_evidence` = evidence drill-down step.
- Defer hard renames or a single replacement theme tool until real host usage
  proves the 3-tool workflow still causes confusion.

Verification gate:

- Tool-surface tests.
- MCPB manifest alignment.
- Natural-question smoke focused on tool selection.
- Backward-compatibility tests for old tool names if aliases remain.
- Ruff and full regression.

Corner cases:

- Host app still discovers only a subset of tools.
- A renamed tool breaks an external prompt/tutorial.
- Customer-theme evidence and framework evidence become confused.

### QF-10. Generic Qualification Default With MEDDPICC Compatibility

Status:

- Implemented.

Purpose:

- Make `qualification_latest` and generic qualification language the default
  architecture while preserving MEDDPICC as the bundled default framework and
  legacy compatibility surface.
- Do not remove tools, fields, sample data, chart ids, or legacy insight modes
  in this unit.

Audit commands:

```bash
rg -n "meddpicc_latest|meddpicc_|MEDDPICC" src tests docs/architecture.md docs/baseline.md docs/qualification-framework-v2.md
rg -n "meddpicc_latest|meddpicc_|MEDDPICC" src/deal_intel/tools src/deal_intel/storage src/deal_intel/resources
rg -n "qualification_latest|qualification_framework|framework_scope" src tests docs
```

Classification summary:

| Classification | References | Action |
| --- | --- | --- |
| `generic_migration_needed` | `tools/analytics_snapshot.py`, `tools/search_deals.py`, `storage/mongodb.py` search and snapshot projections, `resources/mongo/analytics_snapshots.v1.json` | Prefer `qualification_latest` through `select_qualification_snapshot(...)`; keep legacy aliases. |
| `legacy_mark_only` | `tools/get_insights.py` modes `win_patterns`, `loss_patterns`, `compare_won_lost`, `gap_frequency`, `industry_benchmark` | Keep existing MEDDPICC aggregation logic but return `framework_scope: meddpicc_legacy` and a compatibility note. |
| `compatibility_keep` | `schema/qualification_read.py`, `schema/qualification_framework.py`, `tools/qualification_snapshot.py`, `resources/defaults.yaml`, `resources/mongo/deals.v1.json`, Atlas chart ids, public docs that mention MEDDPICC as the default framework | Preserve because MEDDPICC is still the default built-in framework or an old-record compatibility field. |
| `test_fixture_only` | MEDDPICC fixtures in unit tests and sample data builders | Keep unless the specific test now targets generic qualification behavior. |

Implementation split:

- QF-10a: tracked audit and classification only.
- QF-10b: analytics snapshot generic qualification fields.
- QF-10c: search result generic qualification metadata.
- QF-10d: legacy insight labeling.
- QF-10e: wording and docs cleanup.
- QF-10f: regression gate.

Implemented:

- `build_analytics_snapshot(...)` now selects the active qualification snapshot
  through `select_qualification_snapshot(...)`.
- Analytics snapshots include `qualification_framework`,
  `qualification_framework_display_name`, `qualification_source_field`,
  `qualification_health_pct`, `qualification_coverage_pct`,
  `qualification_quality_pct`, `qualification_gap_count`, and
  `qualification_gaps`.
- Search results include active-framework qualification metadata and preserve
  `health_pct` / `gaps` compatibility aliases.
- Atlas vector search projection mirrors the same result field names where the
  MongoDB aggregation can derive them.
- MEDDPICC-only `get_insights` aggregation modes now self-label as
  `framework_scope: meddpicc_legacy`.
- `pipeline_overview` remains the generic framework-aware insight path.

Compatibility rules:

- `meddpicc_latest` is not removed.
- `health_pct`, `health_band`, and existing report/search aliases remain.
- For a non-MEDDPICC active framework, new generic fields use the active
  framework while `meddpicc_*` compatibility fields are empty/null instead of
  being fabricated from unrelated dimensions.
- Existing MEDDPICC-compatible sample data remains valid.

### QF-11. Custom Framework End-to-End Smoke

Status:

- Implemented.

Purpose:

- Prove that a non-MEDDPICC active framework can move through the main read and
  reporting surfaces without being silently converted back to MEDDPICC.
- Keep this as a thin integration smoke, not a replacement for the detailed
  unit tests in review, gaps, metrics, reports, search, and analytics snapshot
  modules.

Covered surfaces:

- `get_qualification_templates` / `update_qualification_framework`
- `list_qualification_frameworks`
- `set_active_qualification_framework`
- `delete_qualification_framework`
- `add_interaction`
- `backfill_qualification_reextract`
- `get_deal_review`
- `get_deal_gaps`
- `get_metrics(metric_type="pipeline_health")`
- `export_report(report_type="weekly_pipeline")`
- `search_deals` with Python cosine search
- `build_analytics_snapshot`

Regression guarded:

- `qualification_latest` remains the source of truth when present.
- Built-in templates can be copied to custom framework keys, activated, used by
  interaction extraction, revised, and safely removed after switching away.
- Updating a custom framework changes its extraction fingerprint and causes
  historical interactions with the old hash to appear in the re-extraction
  dry-run plan.
- Compatibility aliases such as `health_pct` / `gaps` stay populated from the
  active framework.
- Non-MEDDPICC snapshots do not fabricate `meddpicc_*` analytics fields from
  unrelated custom dimensions.
- Public responses do not expose raw notes, raw interaction content, contacts,
  or embeddings.

Test:

- `tests/test_qualification_framework_e2e.py`

## Gate Policy

Every QF unit should close with:

- design note or architecture update;
- targeted tests;
- relevant regression tests;
- Ruff;
- smoke test if MCP behavior changes;
- explicit note for any skipped verification.

If a unit hits three or more failed implementation iterations caused by the same
architecture uncertainty, stop and re-plan before making more code changes.

## First Recommended Unit

Start with QF-1 after this document is accepted.

QF-1 should not change runtime behavior. It should only add the framework
contract, built-in templates, and static validation tests. That gives later
wizard, scoring, extraction, review, and reporting work a stable target.
