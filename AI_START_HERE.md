# AI Start Here

This is the shortest path for an AI agent helping a new user set up
`deal-intel-mcp`.

## Default Decision

Start human users in **`full`** mode.

- `full` = normal product path, MongoDB Atlas-backed real deal data. Atlas M0
  is enough.
- `sample` = optional zero-config trial for AI evaluation, demos, or users who
  explicitly do not want MongoDB yet.
- `pro` = paid-infra upgrade path for Atlas Vector Search and API-key LLM
  operation.

Do not present `sample` as the normal install path. It is useful, but it is not
the main product posture.

## First Run For A Human User

Before asking the user to run commands, explain the required pieces in plain
language:

- MongoDB Atlas account and a Free/M0 cluster for real deal storage.
- A MongoDB connection string (`MONGODB_URI`) from that cluster.
- One chat surface:
  - Claude Desktop with the MCPB extension, or
  - Codex/ChatGPT with MCP support.
- One LLM path for extraction/scoring:
  - ChatGPT OAuth if the user has a compatible ChatGPT/Codex subscription, or
  - Anthropic API key, or
  - OpenAI API key.

Use this short prompt if the user asks what to prepare:

```text
For the normal full setup, prepare four things:
1. a MongoDB Atlas account,
2. a free Atlas cluster and connection string,
3. Claude Desktop or Codex/ChatGPT as the MCP client,
4. either ChatGPT OAuth from your subscription or an Anthropic/OpenAI API key.

If you do not want to set up MongoDB yet, we can run the sample mode first, but
that is a trial path, not the default real-data setup.
```

Use the conda environment Python directly. On Juni's machine this is usually:

```powershell
& "$HOME\miniconda3\envs\event-intel\python.exe" -m deal_intel.cli config profiles
& "$HOME\miniconda3\envs\event-intel\python.exe" -m deal_intel.cli config show
```

Then guide the user through the `full` path:

1. Confirm the package is installed in the selected Python environment.
2. Help the user create or locate a MongoDB Atlas Free/M0 cluster.
3. Help the user copy the driver connection string and save it as
   `MONGODB_URI`.
4. Keep `tools.surface=auto`.
5. Keep `llm.provider=chatgpt_oauth` unless the user chose API keys.
6. Run:

```powershell
& "$HOME\miniconda3\envs\event-intel\python.exe" -m deal_intel.cli config doctor --offline
& "$HOME\miniconda3\envs\event-intel\python.exe" -m deal_intel.cli smoke-profile --profile full --offline
```

If Atlas is reachable and the user wants a live storage check:

```powershell
& "$HOME\miniconda3\envs\event-intel\python.exe" -m deal_intel.cli storage-status
```

## Optional Zero-Config Trial

Use this only when the user asks to try without MongoDB, or when an AI agent
needs a fast product-shape check before asking the user to configure Atlas.

```powershell
$env:DEAL_INTEL_STORAGE_BACKEND='local_sample'
& "$HOME\miniconda3\envs\event-intel\python.exe" -m deal_intel.cli smoke-profile --profile sample
& "$HOME\miniconda3\envs\event-intel\python.exe" -m deal_intel.cli smoke-natural-questions --as-of 2026-06-10
```

Sample mode starts with immutable fictional data. If the user creates their own
local deals, the fixture is hidden from the active working view and the local
personal dataset becomes active.

## Claude Desktop / MCPB Install

When installing the MCPB, recommend:

- Python interpreter path: the env where `deal-intel-mcp` is installed.
- Storage backend: `mongo` for real use; `local_sample` only for zero-config
  trial.
- MCP tool surface: `auto`.
- MongoDB Atlas URI: required for `mongo`.
- LLM provider: `chatgpt_oauth` by default.

Expected visible tool counts:

- `sample`: 19 tools
- `standard` / `full`: 23 tools
- `developer`: 26 tools

After restart, ask Claude/Codex to run `config_doctor` first.

## First Useful Questions

After setup succeeds, ask:

```text
현재 파이프라인 건강도 보여줘.
딜 목록 보여줘.
가장 위험한 딜 하나 리뷰해줘.
고객들이 가장 많이 고민한 주제는 뭐야?
```

For new evidence, use `add_interaction` as the single public intake:

- meeting notes: `interaction_type=meeting`
- customer email replies: `interaction_type=email_thread`
- user interviews: `interaction_type=user_interview`
- internal notes: `interaction_type=internal_note`

Check the returned `source_policy`. Customer-stated inbound evidence can update
MEDDPICC/customer themes. Outbound-only or internal-only content is retained as
context but should not be described as confirmed deal health.

## User Memory

If the user gives durable preferences about reporting style, scoring behavior,
taxonomy, or evidence policy, use `record_user_memory`. To inspect those notes,
use `get_user_memory`.

Never store secrets, raw transcripts, full emails, contacts, API keys, OAuth
tokens, or MongoDB connection strings in user memory.

## Do Not

- Do not use bare `python` or `py` on Windows.
- Do not ask for API keys before the user chooses an API-key provider.
- Do not run `config switch ... --force` without explicit user approval.
- Do not print secrets from `.env`, user config, or command output.
- Do not auto-change deal stage from interaction content. `add_interaction`
  can suggest; `update_stage` performs the actual stage change after user
  confirmation.
