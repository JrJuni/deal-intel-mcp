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
   - Canonical AI setup guide: full-by-default for humans, npx/editable install
     routes, optional sample path for zero-config evaluation.
4. `../AI_USER_TEST_GUIDE.md`
   - First external tester handoff flow after an install path is available.
5. `status.md`
   - Latest completed work and current verification notes.
6. `baseline.md`
   - MCP tool contracts, input/output shape, persistence behavior, and current
     registration expectations.

Then read the area-specific contract only if your task touches it.

## Current Contract Docs

These are active source-adjacent contracts.

| File | Use When |
|---|---|
| `extending.md` | Forking or customizing the project for a specific sales motion |
| `customization-recipes.md` | Following practical examples for common fork changes |
| `baseline.md` | Changing MCP tools, storage behavior, or smoke expectations |
| `metrics.md` | Changing health, pipeline value, timing, win rate, data quality, or trend metrics |
| `reports.md` | Changing CSV/Markdown exports or report row shapes |
| `storage-backends.md` | Changing Mongo/local sample storage behavior |
| `config-profiles.md` | Changing `sample`, `full`, or `pro` profile behavior |
| `tool-surfaces.md` | Changing which MCP tools appear in sample, standard, or developer surfaces |
| `mvp-readiness.md` | Checking whether the package is ready for full-by-default external MVP trials |
| `distribution-plan.md` | Planning git clone, uvx, npx, and MCPB distribution paths |
| `bootstrapper-contract.md` | Designing or changing the future dependency-inclusive npx/bootstrapper runtime |
| `bootstrapper-fresh-smoke.md` | Running pre-publish and post-publish fresh-install bootstrapper smoke checks |
| `release-publish-checklist.md` | Maintainer-only npm/PyPI/MCPB publication checklist |
| `../infra/mongodb-atlas/README.md` | Creating the optional MongoDB Atlas Terraform PoC infrastructure |
| `atlas-charts.md` | Changing Atlas dashboard aggregation specs or UI runbooks |
| `mongodb-atlas-pro.md` | Planning chart-ready Mongo collections, Mongo doctor, and Pro Atlas Vector Search |
| `query-audit.md` | Auditing MongoDB read paths, projections, and index implications |
| `architecture.md` | Needing deeper architecture context after reading this map |
| `../mcpb/README.md` | Building or installing the Claude Desktop MCP bundle |

## Developer Customization And Forking

Use these docs when a developer or AI coding agent wants to adapt the server to
another sales process:

1. `extending.md`
   - first stop for extension seams, guardrails, and validation habits.
2. `customization-recipes.md`
   - concrete examples such as custom qualification frameworks, custom fields,
     new MCP tools, read-only surfaces, report variants, and product-context
     parser extensions.
3. `architecture.md`
   - deeper ownership map for modules, tools, engines, and change playbooks.

The root `README.md` should stay full-mode product and install oriented. Put
deep fork instructions in these docs instead of turning the public README into
an implementation manual.

## Planning And History

These files are useful but should be searched, not loaded wholesale.

| File | Reading Mode |
|---|---|
| `backlog.md` | Read the top current backlog index first; older milestone notes are archive |
| `status.md` | Read latest sections first; older sections are archive |
| `lesson-learned.md` | Search by failure symptom, date, or file path |
| `../user_docs/samples/*.sample.md` | Copy as user-owned operating notes, then adapt with the user's AI assistant |

## User Memory Boundary

`docs/` is the developer reference area. It helps an AI agent understand the
codebase, contracts, architecture, tests, and implementation history when
building or modifying custom tools.

`../user_docs/` is the user memory area. It helps a non-developer user and
their AI assistant capture preferences, repeated feedback, metric-tuning notes,
taxonomy corrections, report-review comments, and evidence-policy choices. Do
not treat `user_docs/` as source code truth; treat it as operating context that
can inspire config, taxonomy, report, or product changes after review.

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
- Update the Korean companion docs when the maintainer explicitly asks for Korean doc
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
