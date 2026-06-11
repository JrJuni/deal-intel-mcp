# MVP Readiness Checklist

This checklist answers one question:

> Is the current package ready for a first external MVP trial without pretending
> that every future feature is finished?

The MVP target is a sample-first, AI-assisted sales/deal-intelligence workflow.
Users should be able to install the package, run the zero-config sample mode,
ask useful deal questions through MCP, create a small local personal dataset,
and understand the path to MongoDB-backed full mode.

## Release Position

Current position: **MVP candidate, sample-first**.

Green:

- Zero-config sample/local mode works without MongoDB.
- MCP tool surfaces are filtered by profile.
- Deal review v2 separates evidence coverage, uncertainty, confirmed risks,
  objective actions, and judgment-sensitive observations.
- Customer interaction intake supports meeting notes, email threads, user
  interviews, call summaries, and internal notes through one public tool:
  `add_interaction`.
- Natural-question smoke has a deterministic 12-question pack.
- Local personal data can be exported, reset, and migrated to MongoDB by
  dry-run-first commands.

Yellow:

- KRW-specific amount field names remain in the core schema. Because there are
  no external users yet, this should be cleaned up before locking a v1.0 public
  contract.
- Claude Desktop MCPB reinstall should be smoked once more after any manifest
  or bundle hardening change.
- Full MongoDB mode works in development, but a disposable live migration smoke
  is still recommended before a broader external release.
- Pro mode is a skeleton upgrade path, not a fully validated paid-infra product.

Not MVP-blocking:

- npx/uvx wrappers.
- Signed MCPB bundles.
- Atlas Vector Search live validation.
- OpenAI API live smoke with paid credits.
- Deep account people graph / CRM-like contact model.

## Required Gates

Run these before calling a build "MVP-ready".

### 1. Source And Tests

```powershell
& "$HOME\miniconda3\envs\event-intel\python.exe" -m pytest -q -p no:cacheprovider
& "$HOME\miniconda3\envs\event-intel\python.exe" -m ruff check .
git diff --check
```

Pass criteria:

- Full pytest passes.
- Ruff passes.
- `git diff --check` has no whitespace errors. Windows line-ending warnings are
  acceptable if no actual diff-check failure is reported.

### 2. Sample Profile Smoke

```powershell
& "$HOME\miniconda3\envs\event-intel\python.exe" -m deal_intel.cli config profiles
& "$HOME\miniconda3\envs\event-intel\python.exe" -m deal_intel.cli config init --profile sample --dry-run
& "$HOME\miniconda3\envs\event-intel\python.exe" -m deal_intel.cli config doctor --offline
& "$HOME\miniconda3\envs\event-intel\python.exe" -m deal_intel.cli smoke-profile --profile sample
```

Pass criteria:

- The sample path does not ask for MongoDB, API keys, or Atlas Vector Search.
- `config doctor` reports actionable next steps without leaking secrets.
- `smoke-profile --profile sample` succeeds or reports only expected local
  environment warnings.

### 3. Natural Question Smoke

```powershell
$env:DEAL_INTEL_STORAGE_BACKEND='local_sample'
$env:DEAL_INTEL_TOOLS_SURFACE='auto'
& "$HOME\miniconda3\envs\event-intel\python.exe" -m deal_intel.cli smoke-natural-questions --as-of 2026-06-10
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
& "$HOME\miniconda3\envs\event-intel\python.exe" -m deal_intel.cli smoke-deal-review-audit --as-of 2026-06-10 --limit 20
```

Pass criteria:

- Sensitive field check passes.
- No quality rule failures.
- Reviews do not expose uncalibrated win-probability percentages.
- Objective CTA gaps and judgment-sensitive observations stay separated.

### 5. Tool Surface Smoke

Run the relevant tests:

```powershell
& "$HOME\miniconda3\envs\event-intel\python.exe" -m pytest tests\test_tool_surfaces.py tests\test_mcpb_manifest.py -q -p no:cacheprovider
```

Pass criteria:

- `sample`, `standard`, and `developer` tool counts match the documented
  contract.
- `add_interaction` is visible on sample/standard.
- Deprecated `add_meeting` is hidden from sample/standard and only visible on
  developer.
- MCPB manifest tool metadata matches the runtime contract.

### 6. Local Personal Data Safety

```powershell
& "$HOME\miniconda3\envs\event-intel\python.exe" -m deal_intel.cli local-data status
& "$HOME\miniconda3\envs\event-intel\python.exe" -m deal_intel.cli local-data export
& "$HOME\miniconda3\envs\event-intel\python.exe" -m deal_intel.cli local-data reset
& "$HOME\miniconda3\envs\event-intel\python.exe" -m deal_intel.cli local-data migrate-to-mongo
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
mcpb pack . deal-intel-mcp-0.1.12.mcpb
mcpb info deal-intel-mcp-0.1.12.mcpb
```

Pass criteria:

- Manifest validation passes.
- Pack succeeds.
- The bundle remains unsigned unless a signing decision has been made.
- Reinstall smoke in Claude Desktop should show the expected sample or standard
  surface based on selected config.

## User Trial Script

Use this lightweight script for a friend or first external evaluator:

1. Start with sample mode. Do not ask for MongoDB yet.
2. Run `config doctor`.
3. Ask: "What is the current pipeline health?"
4. Ask: "Which deals need attention first?"
5. Ask: "Tell me the status of Orion Insurance."
6. Ask: "What themes are backed by email or interview evidence?"
7. Create one local personal deal.
8. Add one meeting or email reply through `add_interaction`.
9. Confirm the result explains `source_policy` and does not silently change
   stage.
10. Show `local-data export` and `local-data reset` dry-run behavior.

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
- Ready for sample-first external MVP trial: yes/no
```
