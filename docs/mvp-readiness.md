# MVP Readiness Checklist

This checklist answers one question:

> Is the current package ready for a first external MVP trial without pretending
> that every future feature is finished?

The MVP target is a MongoDB-backed, AI-assisted sales/deal-intelligence
workflow. Humans should start with the `full` profile by default. The
zero-config `sample` mode remains available for AI agents, demos, and users who
explicitly want to evaluate the workflow before configuring MongoDB.

This checklist is not the validation gate for MongoDB-backed feature work. When
changing MongoDB storage, indexes, schema validation, change streams, time
series, Atlas Charts, or other Atlas-backed behavior, validate against `full`
or `pro` as appropriate. `sample` checks only protect the first-run/no-MongoDB
experience.

## Release Position

Current position: **MVP candidate, full-by-default with optional zero-config sample**.

Green:

- `full` profile is the default real-data operating path.
- Zero-config sample/local mode works without MongoDB.
- MCP tool surfaces are filtered by profile.
- User-memory tools are available for safe repo-local operating preferences,
  scoring feedback, taxonomy notes, report feedback, and evidence-policy notes.
- Industry metadata now separates primary industry, industry tags, and customer
  segment instead of overloading one mixed `industry` string.
- Deal review v2 separates evidence coverage, uncertainty, confirmed risks,
  objective actions, and judgment-sensitive observations.
- Customer interaction intake supports meeting notes, email threads, user
  interviews, call summaries, and internal notes through one public tool:
  `add_interaction`.
- LLM usage/cost visibility is planned as v1 polish so users can see estimated
  provider spend from the MCP surface.
- Local mode can create/update/stage/archive/delete local personal deals, then
  export, reset, or migrate them to MongoDB through dry-run-first commands.
- Natural-question smoke has a deterministic 12-question pack.
- Claude Desktop MCPB `0.1.13` packs successfully and reflects the current
  installer fields.

Yellow:

- Atlas Charts are still intended for one reporting currency per dashboard.
  Python metrics and CSV/Markdown reports detect mixed currencies, but Atlas
  dashboard values should be cross-checked when operating with more than one
  currency.
- Claude Desktop MCPB reinstall should be smoked after manifest or bundle
  changes. Current package build is available, but each external evaluator's
  install still needs a quick `config_doctor` check.
- Full MongoDB mode works in development, but a disposable live migration smoke
  is still recommended before a broader external release.
- Pro mode is a skeleton upgrade path, not a fully validated paid-infra product.
- The first-run copy is now full-by-default, but Korean companion docs may need
  a final pass before a non-English external trial.

Not MVP-blocking:

- npx/uvx wrappers.
- Signed MCPB bundles.
- Atlas Vector Search live validation.
- OpenAI API live smoke with paid credits.
- Deep account people graph / CRM-like contact model.

V1 polish candidates before broader public release:

- Add an MCP usage tool focused on LLM call counts, token usage, and estimated
  provider spend.
- Improve MCP tool descriptions and first-run docs so AI hosts can clearly
  choose between adjacent tools. Each high-traffic tool should say when to use
  it, when not to use it, and which neighboring tool to prefer for adjacent
  tasks.
- Improve CSV/Markdown report readability so exported artifacts have a clearer
  role than Atlas Charts or chat-rendered dashboards.
- Reposition `analyze_deal` as optional generated strategy text, with
  `get_deal_review` as the default LLM-free review.

Post-v1 tool design cleanup:

- Consolidate customer-theme analysis after real host usage is observed.
  Ranking, breakdown, and evidence are one user workflow today, but this is not
  an MVP blocker because current natural-question smoke already passes.
- Audit `update_deal` field groups. Keep the current wide schema while it
  remains one coherent "confirmed metadata correction" workflow; split only if
  unrelated decision types enter the tool.

Post-v2 tool design candidates:

- Add response verbosity controls such as `response_format=concise|detailed`
  only if real traces show meaningful token pressure.
- Consider broad tool namespace changes only as a breaking-version cleanup, not
  as v1 polish.

## Required Gates

Run these before calling a build "MVP-ready".

### 1. Source And Tests

```powershell
& "$HOME\miniconda3\envs\deal-intel\python.exe" -m pytest -q
& "$HOME\miniconda3\envs\deal-intel\python.exe" -m ruff check .
git diff --check
```

Pass criteria:

- Full pytest passes.
- Ruff passes.
- `git diff --check` has no whitespace errors. Windows line-ending warnings are
  acceptable if no actual diff-check failure is reported.

### 1b. Public Launch Hygiene

Use the Codex `launch-hygiene` skill before any public release candidate,
package handoff, MCPB rebuild, or major install-doc update.

Minimum checks:

```powershell
rg "<known-local-username>|<machine-local-path-pattern>|<old-project-name>|<old-env-name>|API_KEY|TOKEN|SECRET|BEGIN .*PRIVATE KEY" . --glob "!mcpb/outputs/**" --glob "!.git/**"
git status --short --ignored
```

Pass criteria:

- No tracked personal usernames, machine-local paths, old project/env names,
  private generated-output paths, secrets, tokens, or API keys.
- `.env`, local override YAML, generated bundles, caches, smoke outputs, and
  local DB/output directories are ignored unless intentionally tracked.
- Public docs explain how to discover the user's own Python interpreter path
  instead of copying a maintainer path.
- Public docs avoid hardcoded tool counts where a doctor/smoke command can
  report the current surface more reliably.

### 2. Full Profile Smoke

```powershell
& "$HOME\miniconda3\envs\deal-intel\python.exe" -m deal_intel.cli config profiles
& "$HOME\miniconda3\envs\deal-intel\python.exe" -m deal_intel.cli config doctor --offline
& "$HOME\miniconda3\envs\deal-intel\python.exe" -m deal_intel.cli smoke-profile --profile full --offline
```

Pass criteria:

- The default human-facing path is `full`.
- `config doctor --offline` reports whether the current machine is configured
  for MongoDB-backed operation without leaking secrets.
- `smoke-profile --profile full --offline` matches the `full` profile contract
  without writes, LLM completions, embeddings, or Atlas admin calls.

### 2b. Optional Zero-Config Sample Smoke

Run this only for AI-first evaluation, demos, or no-MongoDB environments.

```powershell
& "$HOME\miniconda3\envs\deal-intel\python.exe" -m deal_intel.cli config init --profile sample --dry-run
& "$HOME\miniconda3\envs\deal-intel\python.exe" -m deal_intel.cli smoke-profile --profile sample
```

Pass criteria:

- The sample path does not ask for MongoDB, API keys, or Atlas Vector Search.
- `smoke-profile --profile sample` succeeds or reports only expected local
  environment warnings.

### 2c. MongoDB-Backed Feature Gate

Run this when the change touches MongoDB-backed behavior. Do not substitute the
sample smoke for this gate.

```powershell
& "$HOME\miniconda3\envs\deal-intel\python.exe" -m deal_intel.cli smoke-profile --profile full --offline
& "$HOME\miniconda3\envs\deal-intel\python.exe" -m deal_intel.cli config doctor --offline
```

Pass criteria:

- `smoke-profile --profile full --offline` matches the `full` profile contract.
- `config doctor --offline` reports whether the current machine is actually
  configured for MongoDB-backed operation.
- If the feature requires live reads or writes, run a bounded Atlas smoke in a
  disposable database or record why it was deferred.

### 3. Natural Question Smoke

```powershell
$env:DEAL_INTEL_STORAGE_BACKEND='local_sample'
$env:DEAL_INTEL_TOOLS_SURFACE='auto'
& "$HOME\miniconda3\envs\deal-intel\python.exe" -m deal_intel.cli smoke-natural-questions --as-of 2026-06-10
```

Pass criteria:

- `questions=12`.
- `OK: True`.
- No blocked questions.
- No sensitive failures.
- The pack covers pipeline health, company status, riskiest deals, uncertainty,
  closing gaps, closed-deal postmortem gaps, decision criteria, evidence
  drill-down, email/interview-backed evidence, pipeline trend, actionability
  separation, and interaction source coverage.

### 4. Deal Review QA

```powershell
$env:DEAL_INTEL_STORAGE_BACKEND='local_sample'
& "$HOME\miniconda3\envs\deal-intel\python.exe" -m deal_intel.cli smoke-deal-review-audit --as-of 2026-06-10 --limit 20
```

Pass criteria:

- Sensitive field check passes.
- No quality rule failures.
- Reviews do not expose uncalibrated win-probability percentages.
- Objective CTA gaps and judgment-sensitive observations stay separated.

### 5. Tool Surface Smoke

Run the relevant tests:

```powershell
& "$HOME\miniconda3\envs\deal-intel\python.exe" -m pytest tests\test_tool_surfaces.py tests\test_mcpb_manifest.py -q
```

Pass criteria:

- `sample`, `standard`, and `developer` tool counts match the documented
  contract: `sample=21`, `standard=25`, `developer=28`.
- `add_interaction` is visible on sample/standard.
- Deprecated `add_meeting` is hidden from sample/standard and only visible on
  developer.
- MCPB manifest tool metadata matches the runtime contract.

### 6. Local Personal Data Safety

```powershell
& "$HOME\miniconda3\envs\deal-intel\python.exe" -m deal_intel.cli local-data status
& "$HOME\miniconda3\envs\deal-intel\python.exe" -m deal_intel.cli local-data export
& "$HOME\miniconda3\envs\deal-intel\python.exe" -m deal_intel.cli local-data reset
& "$HOME\miniconda3\envs\deal-intel\python.exe" -m deal_intel.cli local-data migrate-to-mongo
```

Pass criteria:

- Export writes a JSON snapshot when local personal data exists.
- Reset is dry-run by default.
- Migration is dry-run by default.
- Bundled fixture records are never reset or migrated as user data.

### 7. MCPB Package Smoke

From `mcpb/`:

```powershell
mcpb validate manifest.json
mcpb pack . deal-intel-mcp-0.1.13.mcpb
mcpb info deal-intel-mcp-0.1.13.mcpb
```

Pass criteria:

- Manifest validation passes.
- Pack succeeds.
- The bundle remains unsigned unless a signing decision has been made.
- Reinstall smoke in Claude Desktop should show the expected sample or standard
  surface based on selected config.
- For the current package, the latest known build is
  `deal-intel-mcp-0.1.13.mcpb` with an unsigned-package warning only.

## User Trial Script

Use this lightweight script for a friend or first external evaluator:

1. Start with `full` and ask for/configure `MONGODB_URI`.
2. Install or reconnect the MCPB with `storage_backend=mongo` and
   `tools_surface=auto`.
3. Run `config_doctor`.
4. Ask: "What is the current pipeline health?"
5. Ask: "Which deals need attention first?"
6. Ask: "Tell me the status of one specific deal."
7. Ask: "What themes are backed by email or interview evidence?"
8. Create one real or test deal in the configured MongoDB database.
9. Add one meeting or email reply through `add_interaction`.
10. Confirm the result explains `source_policy` and does not silently change
   stage.
11. Record one reporting/scoring preference through `record_user_memory`, then
    read it back with `get_user_memory`.

Optional zero-config demo script:

1. Set `DEAL_INTEL_STORAGE_BACKEND=local_sample`.
2. Run `smoke-profile --profile sample`.
3. Run `smoke-natural-questions --as-of 2026-06-10`.
4. Show `local-data export` and `local-data reset` dry-run behavior.
5. Explain that this is a demo/evaluation path, not the default team-storage
   path.

## Deferred After MVP

Do not block the first MVP on these:

- npx/uvx no-git-clone wrapper.
- Pro-grade Atlas Vector Search validation.
- MongoDB Change Streams, Time Series Collections, and Schema Validation.
- Full customer/account people graph.
- Human-readable CSV redesign beyond the current weekly/trend reports.
- OpenAI API live smoke when no API credits are available.
- Full MEDDPICC/qualification-framework abstraction. The MVP uses MEDDPICC as
  the default framework; replacing the dimension set is v2.0 work.

## Sign-Off Template

```text
MVP readiness sign-off

Date:
Commit:
Profile tested:
Storage backend:
MCP surface:

Gates:
- Full pytest:
- Ruff:
- Natural smoke:
- Deal review audit:
- Tool surface/MCPB contract:
- MCPB install/reinstall:
- Local personal data safety:

Known non-blockers:
- 

Decision:
- Ready for full-by-default external MVP trial: yes/no
```
