# Documentation Map

This repository has accumulated implementation notes, contracts, runbooks, and
failure logs. Do not read every file by default. Use this map to choose the
smallest useful context.

## Start Here

Read these first for normal work:

1. `../README.md`
   - Human-facing quickstart, product profile overview, and tool guide.
2. `../AGENTS.md` or `../CLAUDE.md`
   - Current agent rules, workflow, tool count, and architecture guardrails.
3. `../AI_START_HERE.md`
   - First-run AI onboarding path for sample-first evaluation.
4. `status.md`
   - Latest completed work and current verification notes.
5. `baseline.md`
   - MCP tool contracts, input/output shape, persistence behavior, and current
     registration expectations.

Then read the area-specific contract only if your task touches it.

## Current Contract Docs

These are active source-adjacent contracts.

| File | Use When |
|---|---|
| `baseline.md` | Changing MCP tools, storage behavior, or smoke expectations |
| `metrics.md` | Changing health, pipeline value, timing, win rate, data quality, or trend metrics |
| `reports.md` | Changing CSV/Markdown exports or report row shapes |
| `storage-backends.md` | Changing Mongo/local sample storage behavior |
| `config-profiles.md` | Changing `sample`, `full`, or `pro` profile behavior |
| `tool-surfaces.md` | Changing which MCP tools appear in sample, standard, or developer surfaces |
| `mvp-readiness.md` | Checking whether the package is ready for sample-first external MVP trials |
| `atlas-charts.md` | Changing Atlas dashboard aggregation specs or UI runbooks |
| `query-audit.md` | Auditing MongoDB read paths, projections, and index implications |
| `architecture.md` | Needing deeper architecture context after reading this map |
| `../mcpb/README.md` | Building or installing the Claude Desktop MCP bundle |

## Planning And History

These files are useful but should be searched, not loaded wholesale.

| File | Reading Mode |
|---|---|
| `backlog.md` | Read the top current backlog index first; older milestone notes are archive |
| `status.md` | Read latest sections first; older sections are archive |
| `lesson-learned.md` | Search by failure symptom, date, or file path |

## Archive Boundary

Archived content is intentionally preserved for traceability, but it is not the
first source of truth. Treat it as historical context when:

- debugging a repeated failure,
- checking why a decision was made,
- reconstructing a previous milestone,
- or writing migration/release notes.

If archived content conflicts with code or active contract docs, prefer:

1. source code,
2. tests,
3. `baseline.md` / relevant contract doc,
4. `status.md` latest update,
5. archived notes.

## Maintenance Rules

- Keep `AGENTS.md` and `CLAUDE.md` short. They are runtime instructions, not
  history.
- English is the source language for persistent repo docs.
- Keep English source docs ASCII-only unless the file format or quoted external
  value genuinely requires otherwise.
- The only Korean-maintained companion docs are `README.ko.md` and
  `AGENTS.ko.md`.
- Update the Korean companion docs when Juni explicitly asks for Korean doc
  updates; otherwise translate on demand in chat.
- Put durable contracts in contract docs, not only in `status.md`.
- Add new failures to `lesson-learned.md`, but avoid realistic secret-shaped
  examples.
- When a roadmap item is completed, keep the historical record but add a short
  current index near the top of `backlog.md`.
- When docs become long, add navigation and archive markers instead of deleting
  useful history.

## Current Product Streams

- Z5 profile/config work: `sample`, `full`, `pro` in one package.
- Zero-config sample mode: MongoDB-free read-first demo path, with local
  personal data as the next target.
- Full mode: Atlas-backed real team data.
- Pro mode: paid-infrastructure path for API-key LLM providers and Atlas Vector
  Search.
- Deal review quality: separate evidence coverage, health quality, confirmed
  risks, and uncertainty.
- Reporting/BI: shared metric engine feeding MCP answers, CSV/Markdown, and
  Atlas Charts.
