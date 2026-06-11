# AI Start Here

This guide is for AI agents helping a new user try `deal-intel-mcp`.

## First Rule

Start in `sample` mode.

Do not ask the user for MongoDB Atlas, API keys, Atlas Vector Search, or paid
infrastructure until the bundled sample smoke path works.

## Mental Model

The project has one package and three profiles:

- `sample`: local bundled fictional data for feature testing, plus lightweight
  local personal create/update/stage/lifecycle flows. LLM meeting ingestion,
  semantic search, and demo-database maintenance are intentionally unavailable
  in the default sample surface.
- `full`: MongoDB Atlas-backed real team data.
- `pro`: paid-infrastructure path with Atlas Vector Search and API-key LLM
  providers.

Your first job is not to configure production. Your first job is to prove the
tool experience works in `sample`. For team/shared operation, the real
operating path assumes MongoDB-backed deal data. For solo experiments, sample
mode can now persist small local personal datasets before the user graduates to
`full`.

## Step 1 - Inspect, Do Not Guess

Use the conda environment Python directly. On this machine the usual path is:

```powershell
& "$HOME\miniconda3\envs\event-intel\python.exe" -m deal_intel.cli config profiles
& "$HOME\miniconda3\envs\event-intel\python.exe" -m deal_intel.cli config show
```

If the environment path differs, locate the correct Python before continuing.
Do not use bare `python` or `py` on Windows.

## Step 2 - Preview Sample Setup

Always preview before writing user config:

```powershell
& "$HOME\miniconda3\envs\event-intel\python.exe" -m deal_intel.cli config init --profile sample --dry-run
```

If `~/.deal-intel/config.yaml` does not exist and the user wants a persistent
sample setup, run:

```powershell
& "$HOME\miniconda3\envs\event-intel\python.exe" -m deal_intel.cli config init --profile sample
```

If a user config already exists, do not overwrite it automatically. Preview the
switch instead:

```powershell
& "$HOME\miniconda3\envs\event-intel\python.exe" -m deal_intel.cli config switch sample --dry-run
```

Apply `config switch ... --force` only after the user explicitly approves. The
tool backs up the existing config before writing.

## Step 3 - Run Readiness Checks

Run the offline doctor first:

```powershell
& "$HOME\miniconda3\envs\event-intel\python.exe" -m deal_intel.cli config doctor --offline
```

Then run the profile smoke and storage status:

```powershell
& "$HOME\miniconda3\envs\event-intel\python.exe" -m deal_intel.cli smoke-profile --profile sample
& "$HOME\miniconda3\envs\event-intel\python.exe" -m deal_intel.cli storage-status
```

In `sample`, storage status should use `local_sample` and should not require
MongoDB. Tell the user that this is a limited feature-test mode, not the full
operating mode.

## Step 4 - Run The Sample Smoke

Use the deterministic sample smoke:

```powershell
& "$HOME\miniconda3\envs\event-intel\python.exe" -m deal_intel.cli smoke-natural-questions --as-of 2026-06-10
```

Success means the AI-facing read/review/reporting flow works without asking for
external infrastructure.

## Step 5 - Only Then Discuss Full Or Pro

After sample succeeds, ask what the user wants next:

- Stay in `sample` for demos and evaluation.
- Move to `full` for real MongoDB Atlas-backed team data.
- Move to `pro` only when paid Atlas Vector Search and API-key LLM providers
  are intentional.

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

Only request `MONGODB_URI`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or Atlas
Vector Search setup after the user chooses `full` or `pro`.

## Do Not

- Do not ask for MongoDB before sample smoke succeeds.
- Do not ask for API keys before the user chooses an API-key provider.
- Do not run `config switch ... --force` without explicit user approval.
- Do not use `pro` as the default first-run path.
- Do not print secrets from `.env`, user config, or command output.

## Good First Response Pattern

When a new user asks to try the project, say:

```text
I will start with the zero-config sample path first, so we can verify the tool
experience before asking for MongoDB or API keys. I will run config profiles,
preview sample setup, run config doctor offline, then run the natural-question
sample smoke.
```
