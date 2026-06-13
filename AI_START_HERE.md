# AI Start Here

This guide is for AI agents helping a new user try `deal-intel-mcp`.

## First Rule

Default to `full` for human-facing setup.

Use `sample` only when the user explicitly wants zero-config evaluation, has no
MongoDB URI ready, or asks the AI to quickly judge whether the project is worth
trying before setup.

## Mental Model

The project has one package and three profiles:

- `full`: MongoDB Atlas-backed real team data.
- `sample`: local bundled fictional data for zero-config evaluation, plus
  lightweight local personal create/update/stage/lifecycle flows. Source-aware
  `add_interaction` is available when the configured LLM provider is ready.
  Semantic search and demo-database maintenance are intentionally unavailable
  in the default sample surface.
- `pro`: paid-infrastructure path with Atlas Vector Search and API-key LLM
  providers.

Your first job is to identify the intended path:

- For a person installing the product for real use, configure `full`.
- For an AI-only quick check or no-MongoDB demo, use `sample`.
- For paid Atlas Vector Search/API-key operation, use `pro` only after the user
  explicitly chooses it.

## Step 1 - Inspect, Do Not Guess

Use the conda environment Python directly. On this machine the usual path is:

```powershell
& "$HOME\miniconda3\envs\event-intel\python.exe" -m deal_intel.cli config profiles
& "$HOME\miniconda3\envs\event-intel\python.exe" -m deal_intel.cli config show
```

If the environment path differs, locate the correct Python before continuing.
Do not use bare `python` or `py` on Windows.

## Step 2 - Configure Full By Default

For normal setup, ask for `MONGODB_URI` or confirm it is already configured in
the environment/MCPB form. Then run:

```powershell
& "$HOME\miniconda3\envs\event-intel\python.exe" -m deal_intel.cli config doctor --offline
& "$HOME\miniconda3\envs\event-intel\python.exe" -m deal_intel.cli smoke-profile --profile full --offline
```

If the user wants an explicit user config file, preview before writing:

```powershell
& "$HOME\miniconda3\envs\event-intel\python.exe" -m deal_intel.cli config init --profile full --dry-run
```

Apply `config init --profile full` only after the preview looks right.

## Step 3 - Optional Zero-Config Sample

Use this path only when the user asks to try without MongoDB or when an AI agent
needs to evaluate the product shape before requesting setup:

```powershell
& "$HOME\miniconda3\envs\event-intel\python.exe" -m deal_intel.cli config init --profile sample --dry-run
& "$HOME\miniconda3\envs\event-intel\python.exe" -m deal_intel.cli smoke-profile --profile sample
```

For a temporary shell-only sample check:

```powershell
$env:DEAL_INTEL_STORAGE_BACKEND='local_sample'
& "$HOME\miniconda3\envs\event-intel\python.exe" -m deal_intel.cli storage-status
& "$HOME\miniconda3\envs\event-intel\python.exe" -m deal_intel.cli smoke-natural-questions --as-of 2026-06-10
```

Persist sample mode only if the user explicitly wants zero-config/local personal
operation:

```powershell
& "$HOME\miniconda3\envs\event-intel\python.exe" -m deal_intel.cli config init --profile sample
```

If the user wants to try their own temporary data, use sample mode's local
personal storage. It defaults to `~/.deal-intel/local-data` and can be
overridden with `storage.local_data_dir`.

Useful local personal commands:

```powershell
& "$HOME\miniconda3\envs\event-intel\python.exe" -m deal_intel.cli local-data status
& "$HOME\miniconda3\envs\event-intel\python.exe" -m deal_intel.cli local-data export
& "$HOME\miniconda3\envs\event-intel\python.exe" -m deal_intel.cli local-data reset
& "$HOME\miniconda3\envs\event-intel\python.exe" -m deal_intel.cli local-data migrate-to-mongo
```

Tell the user that `local-data reset` is dry-run by default and
`local-data reset --force` clears only local personal deals while preserving
delete audit logs. Help the user migrate to `full` only after local/sample smoke
succeeds and they want shared MongoDB-backed operation. Migration is also
dry-run by default; use `local-data migrate-to-mongo --apply` only after the
target database and skipped/overwrite counts look right.

When adding user-provided evidence, use `add_interaction` as the single public
intake tool:

- meeting notes: `interaction_type=meeting`, usually `direction=inbound`
- customer email replies: `interaction_type=email_thread`, use `direction=mixed`
  for a thread with both seller and customer messages
- user interviews: `interaction_type=user_interview`, usually
  `direction=inbound`
- internal account notes: `interaction_type=internal_note`,
  `direction=internal`

Check the returned `source_policy` before summarizing the result. Inbound
customer-stated evidence can update MEDDPICC/customer themes. Outbound-only and
internal-only content is retained as context but should be described as
unconfirmed, not as improved deal health.

Only request `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or Atlas Vector Search setup
after the user chooses that provider/path. `MONGODB_URI` is normal for `full`.

## Do Not

- Do not ask for API keys before the user chooses an API-key provider.
- Do not run `config switch ... --force` without explicit user approval.
- Do not present `sample` as the default human install path.
- Do not use `pro` as the default first-run path.
- Do not print secrets from `.env`, user config, or command output.

## Good First Response Pattern

When a new user asks to try the project, say:

```text
For normal use, I will start with the MongoDB-backed full profile. I will check
the configured profile, run config doctor offline, then run the full profile
smoke without writes. If you want a zero-config demo instead, I can switch to
the sample path temporarily.
```
