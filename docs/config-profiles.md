# Config Profiles

Z5 keeps one repository and one package, but introduces three product profiles:
`sample`, `full`, and `pro`. The profiles are distribution surfaces, not forks.
They share the same code and differ by generated config, requirements, and
first-run guidance.

## Mental Model

- `sample`: safe feature-test mode with bundled fictional data, designed to
  grow into lightweight local personal use.
- `full`: normal Atlas-backed operating mode for real team data.
- `pro`: paid-infrastructure upgrade path with Atlas Vector Search and API-key
  LLM providers.

The default user journey should be sample-first:

1. Start in `sample`.
2. Run `storage-status`.
3. Run `smoke-natural-questions`.
4. Confirm the tool experience works.
5. Move to `full` when the user is ready to connect MongoDB-backed real data.
6. Move to `pro` only when paid infrastructure is intentional.

The product is fundamentally designed for MongoDB-backed team operation.
`sample` exists so users and AI agents can test the workflow before setup, and
it should also become useful for lightweight personal/local experiments. The
current bundled fixture path is read-only; local personal persistence is the
next design target.

## Profile Contract

The source contract lives in `src/deal_intel/config_profiles.py`.

| Profile | Storage | Vector Search | Default LLM Provider | Primary Use |
|---|---|---|---|---|
| `sample` | `local_sample` | `python_cosine` | `chatgpt_oauth` | Zero-config feature test |
| `full` | `mongo` | `python_cosine` | `chatgpt_oauth` | Real team data on Atlas |
| `pro` | `mongo` | `atlas` | `openai_api` | Paid infra and vector search |

Notes:

- `sample` should stay safe by default, but it should not be permanently
  read-only. The next local milestone should add mutable/resettable personal
  data without requiring MongoDB.
- `full` should remain the operational default for real customer data.
- `pro` is an upgrade path, not the first-run default.
- `openai_api` in `pro` is a default, not a hard vendor lock. Users may switch
  to Anthropic in user config.

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
  `storage.backend`, `mongodb.vector_search`, and `llm.provider`.
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
- Existing config is protected: agents must preview `config switch sample
  --dry-run` and use `--force` only after explicit user approval.

### Z5.6 Packaging Surface

Implemented behavior:

- README and MCP package docs describe sample/full/pro without implying three
  separate codebases.
- Sample-first installation is the easiest path.
- Full/pro requirements are clearly labeled as opt-in.
- `mcpb/manifest.json` exposes `storage_backend` so Claude Desktop installs can
  start in `local_sample` without a MongoDB URI.
- The MCP bundle metadata now reflects the current 22-tool surface.

### Z5.7 Profile Smoke Matrix

Implemented contract:

- `src/deal_intel/profile_smoke_matrix.py` is the source contract.
- `sample` smoke is fully local and deterministic.
- `full` smoke checks Atlas readiness without mutating data.
- `pro` smoke verifies config shape and defers live OpenAI/Atlas Vector Search
  checks when credentials or paid infra are unavailable.

| Profile | BI Smoke Setup | Expected Unconfigured Offline Result | Warnings | Writes |
|---|---|---|---|---|
| `sample` | None | pass; sample storage ping is skipped offline | `llm_provider` if ChatGPT OAuth is not logged in | none; read-only |
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

### Z5.8 Tool Surface Split

Implemented contract:

- `src/deal_intel/tool_surfaces.py` is the source contract.
- Tool surfaces are optimized for non-developer first-run clarity:
  `sample`, `standard`, and `developer`.
- `sample` is a bundled read-first surface. It exposes only LLM-free,
  DB-write-free tools that work against local sample data.
- The sample local-personal target promotes safe non-LLM write/admin tools once
  mutable local storage exists: `create_deal`, `update_stage`, `update_deal`,
  `archive_deal`, `restore_deal`, and `delete_deal`.
- `standard` is the normal real-data operating surface for `full`, `pro`, and
  custom Mongo-backed configs.
- `developer` contains every MCP tool, including Atlas demo-database seed and
  cleanup helpers.

Default mapping:

| Profile | Default Tool Surface |
|---|---|
| `sample` | `sample` |
| `full` | `standard` |
| `pro` | `standard` |
| `custom` | `standard` |

Non-goals for Z5.8a:

- No MCP registration filtering yet.
- No tool hiding in the current runtime yet.
- No mutable local sample storage yet.
- No CLI command regrouping yet.

Result:

- `build_tool_surface_matrix()` returns a serializable surface matrix.
- Targeted tests verify that all 22 registered MCP tools are classified.
- Targeted tests verify that `sample` excludes persistence, LLM, semantic
  search, and Mongo demo-database maintenance tools.
- Targeted tests verify the future local-personal sample target includes safe
  non-LLM write/admin tools but still excludes LLM-heavy, semantic-search, and
  demo-database maintenance tools.
- Detailed policy lives in `docs/tool-surfaces.md`.

### Z5.9 Local Personal Sample Storage

Planned scope:

- Add mutable/resettable local personal storage on top of the current
  `local_sample` experience.
- Keep bundled fictional fixture data immutable.
- Store user-created local data separately from bundled fixture data.
- Support enough persistence for:
  `create_deal`, `update_stage`, `update_deal`, `archive_deal`,
  `restore_deal`, and `delete_deal`.
- Preserve existing safety gates:
  `confirmed_by_user`, exact company checks, dry-run defaults, archive-before-
  hard-delete, and safe delete audit snapshots.
- Add reset/export behavior so a non-developer can recover from messy local
  testing.

Non-goals for Z5.9:

- No LLM meeting ingestion in local personal mode yet.
- No semantic `search_deals` in local personal mode yet.
- No Mongo aggregation compatibility.
- No Atlas demo-database seed/cleanup behavior.

Why this comes before MCP filtering:

- If `sample` is filtered too early, first-run users only see read-only demo
  behavior.
- Local personal storage lets `sample` become useful for a small personal
  dataset before asking for MongoDB.
- Once local write support exists, Z5.10 can safely expose the right sample
  write/admin tools through config-driven MCP filtering.

### Z5.10 Config-Driven MCP Tool Filtering

Planned scope:

- Apply the Z5.8 tool surface contract to actual FastMCP registration.
- Default `sample` profile to the `sample` surface.
- Default `full`, `pro`, and `custom` profiles to the `standard` surface.
- Allow explicit maintainer override such as `tools.surface: developer`.
- Keep developer/QA/smoke helpers out of the default non-developer surface.

Dependency:

- Z5.9 should land first so the `sample` surface can include useful local
  personal write/admin tools instead of staying read-only.
