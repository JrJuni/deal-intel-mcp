# Config Profiles

Z5 keeps one repository and one package, but introduces three product profiles:
`sample`, `full`, and `pro`. The profiles are distribution surfaces, not forks.
They share the same code and differ by generated config, requirements, and
first-run guidance.

## Mental Model

- `sample`: safe feature-test mode with bundled fictional data and optional
  lightweight local personal data.
- `full`: normal Atlas-backed operating mode for real team data.
- `pro`: paid-infrastructure upgrade path with Atlas Vector Search and API-key
  LLM providers.

The default human-facing user journey should be `full`:

1. Configure MongoDB Atlas (`MONGODB_URI`). M0/free tier is sufficient for
   normal `full` operation.
2. Run `config doctor --offline`.
3. Run `smoke-profile --profile full --offline`.
4. Use `sample` only when the user explicitly wants zero-config evaluation, or
   when an AI agent needs to quickly judge the project before setup.
5. Move to `pro` only when paid infrastructure is intentional.

The product is fundamentally designed for MongoDB-backed team operation.
`sample` exists so users and AI agents can test the workflow without setup, and
it can support lightweight personal/local experiments. It starts with a bundled
immutable fixture; once user-created local deals exist, the fixture is archived
from active reads and `storage.local_data_dir/deals.json` becomes the working
dataset.

## Profile Contract

The source contract lives in `src/deal_intel/config_profiles.py`.

| Profile | Storage | Vector Search | Default LLM Provider | Primary Use |
|---|---|---|---|---|
| `sample` | `local_sample` | `python_cosine` | `chatgpt_oauth` | Zero-config feature test |
| `full` | `mongo` | `python_cosine` | `chatgpt_oauth` | Real team data on Atlas |
| `pro` | `mongo` | `atlas` | `openai_api` (`gpt-5.4-mini` default) | Paid infra and vector search |

Notes:

- `sample` stays safe by default, but it is not permanently read-only. Local
  personal `deals.json` supports small user datasets without MongoDB, and
  `local-data reset/export` gives users a recovery path for messy testing.
- The default local personal data directory is `~/.deal-intel/local-data`, and
  users should be able to override it through config as `storage.local_data_dir`.
- `full` should remain the operational default for real customer data and the
  default human-facing install path.
- MongoDB features that work on Atlas Free/M0 and improve normal real-data
  operation belong in `full`, not `pro`. Examples include schema validation,
  ordinary indexes, bounded change-stream consumers, and time-series collections
  for snapshots/events when useful.
- `pro` is an upgrade path, not the first-run default. Reserve it for paid
  infrastructure, scale paths, paid API defaults, or admin automation that
  assumes capabilities beyond Free/M0.
- `openai_api` in `pro` is a default, not a hard vendor lock. Users may switch
  to Anthropic in user config.
- `pro` should not silently fall back from Atlas Vector Search to Python cosine.
  Failures should return a structured error and, when repeatable, be recorded in
  [pro-fallback-errors.md](pro-fallback-errors.md).

## Pro Skeleton Contract

The current Pro work is a skeleton plus guardrails, not a promise that every
paid-infra path has been live-smoked yet.

Implemented now:

- `pro` profile shape: MongoDB Atlas storage, `mongodb.vector_search: atlas`,
  `llm.provider: openai_api`.
- OpenAI API default model: `gpt-5.4-mini`.
- Versioned Atlas Vector Search index spec:
  `atlas/vector_indexes/deal_summary_vector.v1.json`.
- No-silent-fallback policy for `search_deals` in `atlas` mode.
- Dry-run/apply CLI for the versioned Atlas Vector Search index:
  `deal-intel mongo apply-vector-index --json` and
  `deal-intel mongo apply-vector-index --apply`.

Deferred until disposable paid infra is available:

- Live OpenAI API completion smoke.
- Live Atlas Vector Search query smoke.
- Atlas admin-level cluster-tier/index verification.
- Live `apply-vector-index --apply` smoke on an M10+ cluster.

## Z5 Implementation Units

### Z5.1 Profile Contract

Done when:

- `sample/full/pro` profile definitions are coded and tested.
- Config patches are deep-copied and reusable by future CLI commands.
- Current config can be classified as `sample`, `full`, or `pro`.

### Z5.2 Config Inspect CLI

Implemented commands:

```bash
deal-intel config profiles
deal-intel config show
```

Done when:

- Current profile is shown.
- Effective config is summarized without leaking secrets.
- Profile metadata can be printed for AI agents and humans.

Result:

- `config profiles` prints the `sample/full/pro` catalog.
- `config show` prints the inferred current profile, user config path,
  selected effective config fields, and configured env-key status.
- Secret values are never printed; env keys are reported as configured
  `true/false` only.

### Z5.3 Config Init/Switch CLI

Implemented commands:

```bash
deal-intel config init --profile sample
deal-intel config init --profile full
deal-intel config init --profile pro
deal-intel config switch sample
deal-intel config init --profile sample --dry-run
deal-intel config switch sample --dry-run
deal-intel config switch sample --force
```

Implemented behavior:

- `init` creates `~/.deal-intel/config.yaml` when it does not exist.
- `init` refuses to replace an existing config unless `--force` is provided.
- `switch` updates only profile-managed keys:
  `storage.backend`, `storage.local_data_dir` when present in the target
  profile, `mongodb.vector_search`, and `llm.provider`.
- `switch` preserves unrelated custom settings such as reporting, pipeline,
  metrics, and model tuning.
- Actual overwrite/switch writes back up the previous config first with a
  timestamped `config.yaml.bak.YYYYMMDD-HHMMSS` file.
- `--dry-run` previews the change without writing files.
- Secret values are not printed; output includes only profile-managed values
  and an offline doctor preview.
- `sample` setup requires no MongoDB or API key, but it is a limited feature
  test path rather than the full operating mode.

### Z5.4 Config Doctor

Implemented command:

```bash
deal-intel config doctor
deal-intel config doctor --json
deal-intel config doctor --offline
```

Implemented behavior:

- Storage, Mongo URI, vector-search mode, LLM provider, OAuth/API-key readiness,
  and sample-mode status are checked in one payload.
- Missing requirements return actionable hints.
- Live network checks are optional or carefully bounded.
- The MCP tool `config_doctor` returns the same shared report shape.
- The default path allows bounded storage ping but does not call LLM completion
  APIs, embeddings, or write to MongoDB.

### F-Mongo Mongo Doctor

Implemented commands:

```bash
deal-intel mongo doctor
deal-intel mongo doctor --json
deal-intel mongo doctor --offline
deal-intel mongo apply-indexes --json
deal-intel mongo apply-indexes --apply
deal-intel mongo apply-schema --json
deal-intel mongo apply-schema --collection analytics_snapshots --json
deal-intel mongo apply-schema --collection delete_audit_logs --json
deal-intel mongo apply-schema --collection all --json
deal-intel mongo apply-schema --apply
deal-intel mongo apply-vector-index --json
deal-intel mongo apply-vector-index --apply
```

Implemented behavior:

- `mongo doctor` is the full/pro MongoDB operational check. It verifies the
  storage backend, Mongo URI readiness, bounded ping, expected ordinary
  indexes, managed collection validator status, and vector-search mode.
- `apply-indexes` applies the versioned ordinary index contract only when
  `--apply` is passed.
- `apply-schema` applies a v1 collection validator only when `--apply` is
  passed. The default target is `deals`; `--collection all` includes
  `deals`, `analytics_snapshots`, and `delete_audit_logs`.
- `apply-vector-index` prints or applies the Pro Atlas Vector Search index
  command. It requires an M10+ Atlas cluster when `--apply` is used.
- The v1 validators are intentionally permissive: `validationAction: warn`,
  `validationLevel: moderate`, and `additionalProperties: true`.
- These are CLI/admin surfaces first. They are not exposed as MCP tools in the
  user-facing tool list.

### Z5.5 AI Start Here

Implemented AI-readable first-run guide:

```text
AI_START_HERE.md
```

Implemented behavior:

- AI agents are instructed to start in `sample`.
- Agents do not ask for MongoDB/API keys before sample smoke succeeds.
- The guide points to `storage-status`, `config profiles`, and
  `smoke-natural-questions`.
- The guide tells agents to preview `config init --profile sample --dry-run`
  before writing user config.
- Existing config is protected: agents must preview any `config switch ...`
  operation with `--dry-run` and use `--force` only after explicit user
  approval.

### Z5.6 Packaging Surface

Implemented behavior:

- README and MCP package docs describe sample/full/pro without implying three
  separate codebases.
- Full is the default human-facing install path.
- Sample is clearly labeled as a zero-config AI/demo evaluation option.
- Pro requirements are clearly labeled as paid-infra opt-in.
- `mcpb/manifest.json` exposes `storage_backend`; the installer default is
  `mongo`, while `local_sample` remains available for zero-config demos.
- The MCP bundle metadata reflects the current 24-tool internal registration
  with profile-filtered surfaces.
- The current bundle manifest version is `0.1.12`.
- `mcpb/README.md` now documents `tools_surface=auto`, mutable local personal
  sample data, and dry-run-first local-to-Mongo migration.
- `tests/test_mcpb_manifest.py` validates the manifest against the tool-surface
  contract and launcher behavior without requiring the external `mcpb` CLI.

### Z5.7 Profile Smoke Matrix

Implemented contract:

- `src/deal_intel/profile_smoke_matrix.py` is the source contract.
- `sample` smoke is fully local and deterministic.
- `full` smoke checks Atlas readiness without mutating data.
- `pro` smoke verifies config shape and defers live OpenAI/Atlas Vector Search
  checks when credentials or paid infra are unavailable.

| Profile | BI Smoke Setup | Expected Unconfigured Offline Result | Warnings | Writes |
|---|---|---|---|---|
| `sample` | None | pass; sample storage ping is skipped offline | `llm_provider` if ChatGPT OAuth is not logged in | local personal writes only when the user uses create/update/stage/lifecycle tools |
| `full` | `MONGODB_URI` | fail on `mongodb_uri` when missing | `llm_provider` if ChatGPT OAuth is not logged in | none; read-check only |
| `pro` | `MONGODB_URI`, Atlas M10+, Atlas Vector Search index | fail on `mongodb_uri` and `llm_provider` when missing | `vector_search` warns that Atlas Vector Search requires paid infra | none; read-check only |

Non-goals for Z5.7:

- No live OpenAI API calls.
- No Atlas admin API calls.
- No MongoDB writes.

Result:

- `build_profile_smoke_matrix()` returns a serializable profile matrix.
- Targeted tests verify the matrix against profile patches, config init
  dry-run output, and config doctor pass/warn/fail behavior.
- `deal-intel smoke-profile --profile sample|full|pro` builds a no-write smoke
  report from the matrix and shared config doctor.
- `--offline` skips storage ping.
- `--json` returns the same structured report shape for agents.

### Z5.8-Z5.10 Tool Surface Split And Runtime Filtering

Implemented:

- `src/deal_intel/tool_surfaces.py` is the source contract.
- Tool surfaces are optimized for non-developer first-run clarity:
  `sample`, `standard`, and `developer`.
- `sample` exposes mostly LLM-free tools that work against bundled sample data
  or local personal `deals.json`, plus `add_interaction` for user-created local
  deals when the configured LLM provider is ready.
- `sample` now includes safe non-LLM write/admin tools:
  `create_deal`, `update_stage`, `update_deal`, `archive_deal`,
  `restore_deal`, and `delete_deal`.
- `standard` is the normal real-data operating surface for `full`, `pro`, and
  custom Mongo-backed configs.
- `developer` contains every MCP tool, including Atlas demo-database seed and
  cleanup helpers.
- `tools.surface: auto` resolves the default surface from the effective
  profile.
- `DEAL_INTEL_TOOLS_SURFACE` can override the configured surface for packaged
  installs and smoke tests.
- The MCP server filters `list_tools()` and blocks hidden `call_tool()` calls.
- Invalid `tools.surface` config leaves only `config_doctor` visible so the
  server can explain the configuration problem.

Default mapping:

| Profile | Default Tool Surface |
|---|---|
| `sample` | `sample` |
| `full` | `standard` |
| `pro` | `standard` |
| `custom` | `standard` |

Result:

- `build_tool_surface_matrix()` returns a serializable surface matrix.
- Targeted tests verify that all 26 registered MCP tools are classified.
- Targeted tests verify that `sample` includes safe local personal write/admin
  tools while excluding LLM-heavy, semantic-search, legacy Mongo aggregation,
  and Mongo demo-database maintenance tools.
- Targeted tests verify runtime MCP filtering for sample/developer surfaces and
  hidden-tool call blocking.
- Detailed policy lives in `docs/tool-surfaces.md`.

### Z5.9 Local Personal Sample Storage

Implemented foundation:

- Added local personal data directory resolution.
- Added `deals.json` as the first local personal read contract.
- Added local personal `upsert_deal` persistence for safe non-LLM write tools.
- Added local personal delete audit persistence in `delete_audit_logs.json`.
- Kept bundled fictional fixture data immutable.
- Hid bundled fixture deals from active read paths once user-created local
  deals exist.
- Preserved the fixture as an archived bundled sample, visible only through
  diagnostic metadata.
- Continued stripping `raw_notes`, `contacts`, and `summary_embedding` from
  local sample read and write payloads.
- Supported local persistence for `create_deal`, `add_interaction`,
  `update_stage`, and `update_deal`.
- Supported local persistence for `archive_deal`, `restore_deal`, and
  `delete_deal` with existing confirmation, company-match, dry-run, archived-
  before-delete, and audit-snapshot gates.
- Preserved delete audit logs separately from local deal reset/delete flows.

Implemented reset/export surface:

```bash
deal-intel local-data status
deal-intel local-data export
deal-intel local-data reset
deal-intel local-data reset --force
```

Behavior:

- `status` reports the configured local personal data directory, deal count,
  and delete-audit-log count.
- `export` writes a local personal snapshot of deals and delete audit logs. It
  strips legacy raw notes, contacts, and embeddings; canonical
  `interactions.raw_content` may be present in deal details until a later
  redaction/encryption layer is added.
- `reset` is dry-run by default.
- `reset --force` clears only local personal deals in `deals.json`.
- Delete audit logs are preserved across reset.
- An empty `deals.json` still keeps the bundled fixture archived, so reset does
  not silently re-mix fictional data into the working dataset.

Remaining planned scope:

- Add local analytics snapshot persistence if trend reports need local personal
  write history.
- Preserve existing safety gates:
  `confirmed_by_user`, exact company checks, dry-run defaults, archive-before-
  hard-delete, and safe delete audit snapshots.

Non-goals for Z5.9:

- `analyze_deal` remains unavailable in local personal sample mode.
- No semantic `search_deals` in local personal mode yet.
- No Mongo aggregation compatibility.
- No Atlas demo-database seed/cleanup behavior.

### Z5.11 Local To Mongo Migration

Implemented:

- Read the local personal data directory.
- Migrates only user-created local personal deals, never bundled fixture data.
- Dry-run by default.
- Requires target MongoDB readiness before classifying rows.
- Upserts into the configured or requested MongoDB database only after explicit
  user confirmation.
- Preserve deal ids when possible.
- Skips existing target deal ids by default.
- Supports explicit `overwrite=true` / `--overwrite`.
- Reports create, overwrite, skipped, and written counts.
- Exposes both MCP `migrate_local_data` and CLI
  `deal-intel local-data migrate-to-mongo`.

Non-goals:

- No automatic background sync.
- No two-way sync between local and MongoDB.
- No migration of bundled fictional fixture data.
- No migration of local delete audit logs.
