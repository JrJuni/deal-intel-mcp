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

Purpose:

- Make `add_interaction` extract the active framework, not hardcoded MEDDPICC.

Implementation:

- Build extraction prompt from the active framework dimensions.
- Store `interaction.qualification`.
- Keep `interaction.meddpicc` compatibility when the active framework is
  MEDDPICC.
- Recompute `deal.qualification_latest`.
- Mirror or alias `deal.meddpicc_latest` during compatibility window.
- Keep source-policy behavior:
  - customer-stated evidence can update confirmed scores;
  - outbound/internal evidence remains unconfirmed by default.

Verification gate:

- Mocked LLM extraction for default MEDDPICC.
- Mocked LLM extraction for a custom framework.
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

### QF-6. Reports, Data Exports, And Atlas Specs

Purpose:

- Make human reports, CSV ledgers, and dashboards reflect the active framework.

Implementation:

- Update `weekly_pipeline` rows to carry generic qualification fields.
- Update Markdown report labels.
- Update export data columns.
- Version Atlas chart specs:
  - keep old `meddpicc_gap_distribution` as compatibility if needed;
  - introduce `qualification_gap_distribution`.
- Update dashboard crosscheck expectations.

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
- Dashboard expects old field names.
- CSV consumers still expect `health_pct`.

### QF-7. Backfill And Recompute

Purpose:

- Let users update historical deal snapshots when framework definitions change.

Implementation:

- Add a backfill/recompute path that can distinguish:
  - no-LLM recompute for weight/threshold changes;
  - LLM re-extraction for new or changed extraction hints.
- Dry-run by default.
- Report estimated affected deals/interactions.
- Connect usage/cost warning for LLM re-extraction.

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

### QF-8. Compatibility Cleanup

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
