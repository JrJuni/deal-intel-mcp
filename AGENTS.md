# AGENTS.md

This is the short operating guide for Codex and other coding agents working in
this repository. Keep it current and compact. Put long history in `docs/`.

## Project North Star

`deal-intel-mcp` is an MCP server for B2B deal intelligence. It turns meeting
notes into MEDDPICC signals, stores deal state, and exposes BI/reporting tools
that Claude, Codex, ChatGPT, CSV exports, and Atlas Charts can use.

The product direction is one repository / one package with three profiles:

- `sample`: zero-config, MongoDB-free, read-only demo over bundled data.
- `full`: Atlas-backed operating mode for real team data.
- `pro`: paid-infrastructure path with API-key LLM providers and Atlas Vector
  Search.

## Read First

Do not read every doc by default. Start here:

1. `AGENTS.md` or `CLAUDE.md` for agent rules.
2. `docs/README.md` for the documentation map and current reading order.
3. `docs/status.md` for the latest completed work.
4. `docs/baseline.md` for MCP tool contracts.
5. `docs/metrics.md`, `docs/reports.md`, `docs/storage-backends.md`, or
   `docs/config-profiles.md` only when the task touches that area.

Append-only or historical docs such as `docs/lesson-learned.md` and old
sections of `docs/backlog.md` are archive material. Search them for a specific
failure or decision; do not load them wholesale for ordinary tasks.

## Documentation Language Policy

- English is the source language for repository docs, contracts, status,
  backlog, architecture, and lesson-learned files.
- Keep persistent English source docs ASCII-only unless a file format or quoted
  external value genuinely requires otherwise.
- The only Korean-maintained companion docs are `README.ko.md` and
  `AGENTS.ko.md`.
- Update the Korean companion docs when Juni explicitly asks for a Korean doc
  update. Otherwise keep implementation docs English-first and translate on
  demand in chat.

## Dev Environment

Use the conda environment Python directly. Do not use bare `python` or `py` on
Windows.

```powershell
& "$HOME\miniconda3\envs\event-intel\python.exe" -m pip install -e ".[dev,embedding]"
& "$HOME\miniconda3\envs\event-intel\python.exe" -m pytest
& "$HOME\miniconda3\envs\event-intel\python.exe" -m ruff check .
```

Useful CLI checks:

```powershell
& "$HOME\miniconda3\envs\event-intel\python.exe" -m deal_intel.cli storage-status
& "$HOME\miniconda3\envs\event-intel\python.exe" -m deal_intel.cli config profiles
& "$HOME\miniconda3\envs\event-intel\python.exe" -m deal_intel.cli config show
& "$HOME\miniconda3\envs\event-intel\python.exe" -m deal_intel.cli config doctor
```

For temporary zero-config sample mode:

```powershell
$env:DEAL_INTEL_STORAGE_BACKEND='local_sample'
```

## Working Loop

Juni's preferred loop:

1. Decide the large workstream and the next subtask.
2. For complex or product-sensitive tasks, write the detailed plan, risks,
   verification criteria, and sensemaker summary before implementation.
3. For small low-decision tasks, move directly into implement -> verify.
4. Turn suspected edge cases into targeted tests first.
5. Verify with targeted tests, relevant regressions, full pytest, Ruff, and any
   required smoke test.
6. Record unverified risk in `docs/status.md` or `docs/backlog.md`.
7. Update docs and commit only the intended scope. Push when requested.

## Current MCP Tool Surface

Source of truth: `src/deal_intel/mcp_server.py`.

Current tool count: 22.

- Config/readiness: `config_doctor`
- Write/lifecycle: `create_deal`, `add_meeting`, `update_stage`,
  `update_deal`, `archive_deal`, `restore_deal`, `delete_deal`
- Demo data: `create_sample_data`, `delete_sample_data`
- Read/review: `get_deal`, `list_deals`, `get_deal_gaps`,
  `get_deal_review`
- BI/reporting: `get_insights`, `get_metrics`, `export_report`
- Customer themes: `get_customer_themes`, `get_customer_theme_breakdown`,
  `get_customer_theme_evidence`
- Search/analysis: `search_deals`, `analyze_deal`

## Architecture Rules

- Access storage and LLM providers only through `deal_intel._context`.
- Use `make_llm_provider(config)`; do not instantiate provider classes
  directly.
- Keep `pymongo` imports inside `storage/mongodb.py`, except for the explicit
  `preload_driver()` startup path.
- BI/reporting paths must not call LLMs or embeddings.
- Restricted metric/report read paths must exclude raw meeting notes, contacts,
  and embeddings unless the tool contract explicitly says otherwise.
- `add_meeting` never changes `deal_stage`. It may return `stage_suggestion`;
  apply the change only after user confirmation through `update_stage`.
- Destructive tools stay conservative: dry-run first, explicit confirmation,
  exact company matching where applicable, and audit-safe snapshots.
- Do not use realistic secret-looking placeholders in tests or docs. Use
  neutral values such as `replace-with-openai-api-key` or scanner-safe
  sentinels.

## Docs Convention

- `docs/README.md`: documentation map and current reading order.
- `docs/status.md`: latest work and verification notes; older entries are
  archive.
- `docs/backlog.md`: current backlog index first, historical roadmap below.
- `docs/baseline.md`: MCP tool contracts and verification baseline.
- `docs/metrics.md`: BI metric definitions and boundary contracts.
- `docs/reports.md`: CSV/Markdown report contracts.
- `docs/storage-backends.md`: Mongo vs local sample storage contract.
- `docs/config-profiles.md`: `sample/full/pro` profile plan.
- `docs/lesson-learned.md`: append-only failure log; search it when debugging.
