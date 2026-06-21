# Status

This file tracks the current workstream and the most recent completed
milestones. Longer roadmap items live in [backlog.md](backlog.md), and durable
contracts live in [baseline.md](baseline.md) and [metrics.md](metrics.md).

## Reading Note

Read the newest section first. Older sections are retained as an archive for
traceability and should be searched by topic, milestone, or file path rather
than loaded wholesale.

## Latest Update - 2026-06-21

### MongoDB Atlas Terraform PoC template

Completed:

- Added `infra/mongodb-atlas/` as a small Terraform template for the optional
  Atlas `full`/`pro` setup path.
- The template creates an Atlas project, cost-safe M0 tenant cluster by
  default, app database user, optional CIDR access list entries, and sensitive
  SRV connection string output.
- Kept Terraform responsible for infrastructure only; app data, sample data,
  schema application, chart-ready refresh, product-context indexing, and Atlas
  Vector Search indexing remain CLI/app responsibilities.
- Added repo ignore rules for Terraform local state, `.tfvars`, and local
  override files, and linked the new runbook from the documentation map.

Validation:

- `terraform fmt -check` from `infra/mongodb-atlas/` -> passed.
- `terraform init -backend=false` from `infra/mongodb-atlas/` -> passed after
  allowing registry network access; locked `mongodb/mongodbatlas` v2.12.0.
- `terraform validate` from `infra/mongodb-atlas/` -> passed.

## Previous Update - 2026-06-19

### V3 Step 1 HubSpot Deal import CSV

Completed:

- Added `export_data(dataset="hubspot_deals")` as a deterministic manual
  HubSpot Deal import template.
- The export writes HubSpot-oriented Deal columns from current deal-level state
  and includes review warnings for default pipeline mapping, stalled-stage
  mapping, duplicate company names, and skipped missing deal names.
- Kept Step 1 scoped to local CSV artifact generation: no HubSpot API calls, no
  CRM update matching, no Contact/Company export, and no account/person storage
  layer.
- Updated MCP/tool-surface docs, MCPB manifest text, report contracts, baseline,
  and architecture notes to describe the HubSpot CSV template and deferred
  Account People Graph.

Validation:

- `pytest tests\test_export_data.py -q -p no:cacheprovider --basetemp=.tmp\pytest-hubspot-export`
  -> 14 passed.
- `pytest tests\test_export_data.py tests\test_tool_surfaces.py tests\test_mcpb_manifest.py -q -p no:cacheprovider --basetemp=.tmp\pytest-hubspot-targeted`
  -> 59 passed, 1 third-party deprecation warning.
- `ruff check src tests` -> passed.

### CI workflow baseline

Completed:

- Added `.github/workflows/ci.yml` for PRs, `main` pushes, `codex/**` branch
  pushes, and manual runs.
- CI now installs the package on Python 3.11 and 3.12, runs `ruff check src
  tests`, full pytest with `-p no:cacheprovider`, sample profile smoke, and
  explicit Node 24 setup for bootstrapper tests.
- CI also runs npm bootstrapper checks: `node --check`, `npm pack --dry-run`,
  and `npm run smoke`.
- Updated stale developer tool-count assertions/docs from 41 to 42 after the
  `get_deal_raw` addition.

Validation:

- `pytest -q -p no:cacheprovider --basetemp .tmp\pytest-ci-local` -> 775
  passed, 1 third-party deprecation warning.
- `ruff check src tests` -> passed.
- `node --check npm\bin\deal-intel-mcp.js` -> passed.
- `npm.cmd pack --dry-run` -> passed.
- `npm.cmd run smoke` -> passed.

## Previous Update - 2026-06-19

### Post-v2 MCP safety and cost guardrails

Completed:

- Made `get_deal` a safe read path that excludes raw notes, raw interaction
  content, contacts, and embeddings.
- Added developer-only `get_deal_raw` with explicit confirmation, reason, and
  raw include flag; embeddings remain excluded.
- Added `add_interaction` guardrails: 20,000-character content cap, exact
  duplicate skip before LLM calls, untrusted-source prompt boundaries, and
  non-retryable LLM failures.
- Changed `analyze_deal` to preview by default, require explicit confirmation
  for `bd_strategy` persistence, use a 10-minute process cache for repeated
  same deal/prompt/product-context calls, and mark LLM failures non-retryable.
- Updated MCP tool contracts, MCPB manifest metadata, architecture/tool-surface
  docs, and onboarding guidance.

Validation:

- `pytest tests\test_add_interaction.py tests\test_analyze_deal.py
  tests\test_deal_lifecycle.py tests\test_tool_surfaces.py tests\test_usage.py
  tests\test_mcpb_manifest.py -q -p no:cacheprovider --basetemp
  .tmp\pytest-p0-guardrails` -> 91 passed, 1 third-party deprecation warning.
- `ruff check src tests` -> passed.
- `mcpb validate mcpb\manifest.json` -> passed.

## Previous Update - 2026-06-19

### First evidence onboarding after config doctor

Completed:

- Added `first_data_next_steps` to `config_doctor` so a successful readiness
  check tells first-time users to create or choose a deal, paste customer
  evidence with `add_interaction`, and review it with `get_deal_review`.
- Updated CLI text output to show a `First data flow` section after
  `config_doctor`.
- Updated the npm bootstrapper, MCPB README, npm README, root README, and
  `AI_START_HERE.md` so the install flow no longer stops at diagnostics.
- Added a short MongoDB Atlas URI setup path to README, AI onboarding docs, and
  MCPB/npm install docs.
- Updated the missing-`MONGODB_URI` `config_doctor` hint so hosts ask whether
  to continue in zero-config sample mode for now or set up Atlas full mode.
- Updated the MCP baseline contract for `config_doctor`.

Validation:

- `pytest tests/test_config_doctor.py tests/test_bootstrapper_skeleton.py -q
  -p no:cacheprovider --basetemp .tmp\pytest-first-evidence` -> 23 passed, 1
  third-party deprecation warning.
- `ruff check src\deal_intel\config_doctor.py src\deal_intel\cli.py
  tests\test_config_doctor.py tests\test_bootstrapper_skeleton.py` -> passed.
- `node --check npm\bin\deal-intel-mcp.js` -> passed.

## Previous Update - 2026-06-18

### 0.2.3 npx bootstrapper + MCPB handoff prep

Completed:

- Bumped version alignment to `0.2.3` across the Python package, npm
  bootstrapper, and MCPB manifest.
- Updated `npx deal-intel-mcp setup` to install the matching pinned Python
  runtime package (`deal-intel-mcp[embedding]==0.2.3`) instead of a moving
  latest install.
- Bundled `mcpb/deal-intel-mcp-0.2.3.mcpb` into the npm package and added
  handoff metadata so `setup`, `where --json`, `mcp-config --json`, and
  `mcpb --json` all expose:
  - the managed Python interpreter path;
  - the bundled MCPB path;
  - the persistent local MCPB path under `~/.deal-intel/runtime/mcpb/`;
  - Claude Desktop next steps.
- Updated MCPB installer wording to tell users to run
  `npx deal-intel-mcp setup` and paste the printed Python path, rather than
  assuming a git clone or editable install.
- `release/latest/` was intentionally not updated; this patch keeps latest
  handoff artifacts manually curated.
- `.gitignore` keeps ordinary MCPB build artifacts ignored, with an explicit
  exception for `mcpb/deal-intel-mcp-0.2.3.mcpb` so the current handoff artifact
  is visible in the repository.

Validation:

- `node npm\bin\deal-intel-mcp.js setup --dry-run --json --python <python>`
  -> passed; output includes the pinned install spec and MCPB copy plan.
- `node --check npm\bin\deal-intel-mcp.js` -> passed.
- `pytest tests\test_bootstrapper_skeleton.py tests\test_mcpb_manifest.py -q
  -p no:cacheprovider --basetemp .tmp\pytest-bootstrapper-023` -> 19 passed.
- `pytest -q -p no:cacheprovider --basetemp .tmp\pytest-full-023` -> 760
  passed, 1 third-party deprecation warning.
- `ruff check .` -> passed.
- `git diff --check` -> passed; Windows line-ending warnings only.
- `mcpb validate mcpb\manifest.json` -> passed.
- `mcpb pack . deal-intel-mcp-0.2.3.mcpb` from `mcpb/` -> passed.
- `mcpb info mcpb\deal-intel-mcp-0.2.3.mcpb` -> passed with the expected
  unsigned-package warning.
- Root `mcpb/deal-intel-mcp-0.2.3.mcpb` and npm-bundled
  `npm/mcpb/deal-intel-mcp-0.2.3.mcpb` have matching SHA256 hashes.
- `npm pack --dry-run` from `npm/` -> passed and confirmed the tarball includes
  the bundled `mcpb/deal-intel-mcp-0.2.3.mcpb`.
- Stale version scan found no `0.2.1`/`0.2.2` references in current release
  entrypoint docs and package metadata.

Deployment:

- Committed and pushed `57acf65` (`Release 0.2.3 npx MCPB handoff`) to
  `main`.
- Pushed release tag `v0.2.3`.
- GitHub Actions release run `27767000102` completed successfully:
  - release-candidate tests passed;
  - Python package publish to PyPI passed;
  - npm bootstrapper publish passed.
- Registry verification:
  - PyPI latest: `deal-intel-mcp 0.2.3`;
  - npm latest: `deal-intel-mcp 0.2.3`;
  - npm available versions: `0.2.1`, `0.2.2`, `0.2.3`.

### npm publish auth note

Recorded:

- npm `publish` may return `EOTP` even when the maintainer account uses
  security-key/WebAuthn 2FA and no authenticator-app OTP is visible.
- The previously successful maintainer path for this project was to rerun
  `npm publish --access public`, follow the CLI browser authentication URL, and
  authenticate with the account security key/device flow.
- Granular tokens with package write access and 2FA bypass, or future trusted
  publishing, are fallback paths. Do not ask the maintainer to find a
  nonexistent OTP field.

### Trusted publishing workflow

Completed:

- Added `.github/workflows/release.yml` for tag-based GitHub Actions releases.
- The workflow runs release-targeted checks, publishes the Python package to
  PyPI first, then publishes the npm bootstrapper.
- PyPI trusted publisher should use workflow `release.yml` and environment
  `pypi`.
- npm trusted publisher should use workflow `release.yml` and environment
  `npm`.

Pending maintainer setup:

- Register the PyPI trusted publisher for `JrJuni/deal-intel-mcp`.
- Register the npm trusted publisher for `JrJuni/deal-intel-mcp`.
- Push a release tag such as `v0.2.2` after registry setup.

Follow-up from first trusted-publishing run:

- PyPI publication for `0.2.2` succeeded.
- npm publication failed under Node 20 / npm 10.8.2 with an npm registry
  `E404` after provenance signing.
- Updated the release workflow to use Node 24, upgrade npm before publishing,
  and support `workflow_dispatch` with `target=npm` so the npm publish can be
  retried without republishing the same PyPI version.

Final registry verification:

- PyPI latest: `deal-intel-mcp 0.2.2`.
- npm latest: `deal-intel-mcp 0.2.2`.
- npm available versions: `0.2.1`, `0.2.2`.
- npm-only trusted-publishing rerun succeeded through GitHub Actions
  `workflow_dispatch` run `27753104966`.

### V2 docs and MCPB 0.2.2 release-candidate prep

Completed:

- Added clearer README architecture-at-a-glance and developer customization
  entry points.
- Added forkability docs for extension entry points and customization recipes.
- Consolidated the AI install entrypoint around `AI_START_HERE.md`; removed the
  separate scenario and npx install guides to reduce first-run document
  clutter.
- Prepared source package, npm bootstrapper, and MCPB metadata for `0.2.2`.
- `release/latest/` intentionally remains on the previous explicit handoff
  artifact until the maintainer asks to refresh it.

Validation:

- Documentation scans found no stale deleted install-guide links, no stale
  sample-first wording, and no maintainer-local path/environment references in
  active public docs.
- `git diff --check` reports only expected Windows line-ending warnings.

### V2 polish close-out gate

Completed:

- Treated deal-review quality as usage-driven follow-up instead of continuing
  to tune it without real user traces.
- Closed the current v2 polish queue around release friction, diagnostics, and
  report/export readability.
- Added an explicit `--dry-run` compatibility option to
  `deal-intel mongo refresh-chart-ready`. The command already defaulted to
  dry-run without `--apply`, but explicit `--dry-run` now works for scripts and
  readiness plans.
- Extended chart-ready refresh failures with the same secret-safe storage
  diagnostic hint used by export paths. DNS/network failures now return
  actionable next steps instead of only a raw storage exception.

Validated:

- `ruff check .` -> passed.
- `pytest -q -p no:cacheprovider --basetemp .tmp\pytest-v2-polish-closeout-final`
  -> 757 passed, 1 environment warning.
- `config doctor --offline --json` -> `ok: true`, full profile, zero failed
  checks; runtime diagnostics still correctly report local editable-install
  version drift (`0.1.0` package metadata vs the current source tree).
- `smoke-profile --profile full --offline` -> passed.
- `smoke-profile --profile sample` -> passed.
- `smoke-natural-questions --as-of 2026-06-10` -> `OK: True`; output:
  `~/.deal-intel/smoke/natural-question-pack-20260618_155953`.
- `smoke-deal-review-audit --as-of 2026-06-10 --limit 20` -> sensitive field
  check passed; quality rules passed.
- `crosscheck-weekly-dashboard --as-of 2026-06-10` -> `ok: true`; generated
  weekly report artifacts under `~/.deal-intel/reports`.
- `mongo refresh-chart-ready --target all --as-of 2026-06-10 --dry-run --json`
  now accepts the explicit `--dry-run` option. The live run on this machine
  currently hits transient DNS timeout, but returns `likely_issue:
  dns_or_network` plus next actions; this is an environment/UX observation, not
  a release blocker.
- Local-sample report/export smoke generated:
  - weekly pipeline Markdown/CSV,
  - pipeline trend Markdown/CSV,
  - open-deals ledger CSV.
- `pytest tests\test_product_context.py tests\test_analyze_deal.py tests\test_add_interaction.py -q -p no:cacheprovider --basetemp .tmp\pytest-v2-polish-product-context-final`
  -> 37 passed, 1 environment warning.

Remaining after close-out:

- Deal-review quality should now improve through real usage traces and the
  planned corner-case synthetic dataset, not through more blind pre-release
  tuning.
- Runtime version drift repair can be made more automatic post-v2; the current
  diagnostic already exposes the mismatch and next action.
- Mongo DNS/network instability is handled with actionable hints; live Atlas
  reliability remains environment-dependent.

### Report Quality v2 - pipeline trend readability polish

Completed:

- Updated `export_report(report_type="pipeline_trend")` Markdown so the
  visible generated timestamp uses the configured reporting timezone.
- Added a deterministic executive summary before the KPI table.
- Formatted trend KPI values for human review: comma-separated counts,
  currency-suffixed pipeline value, health percentages, and signed deltas.
- Preserved the deterministic report contract: no LLM, no embeddings, no
  MongoDB writes, and the returned `generated_at` remains UTC metadata.

Validated:

- `pytest tests\test_export_report.py tests\test_pipeline_trends.py -q -p no:cacheprovider --basetemp .tmp\pytest-pipeline-trend-polish-final`
  -> 26 passed, 1 environment warning.
- `ruff check src\deal_intel\reports\pipeline_trend.py src\deal_intel\tools\export_report.py tests\test_export_report.py`
  -> passed.
- Local-sample Korean `export_report(report_type="pipeline_trend",
  as_of="2026-06-10")` generated a Markdown report with an `Asia/Seoul`
  timestamp, executive summary, readable KRW values, and percentage deltas.

### Report Quality v2 - timezone-aware Markdown header

Completed:

- Updated weekly pipeline Markdown reports so the visible `Generated at` /
  `생성 시각` header uses the configured reporting timezone instead of a raw
  UTC ISO timestamp.
- Preserved the machine contract: returned `generated_at` remains UTC, while
  `generated_at_display` and `timezone` make the human-facing report header
  explicit.
- Replaced the remaining internal "export" wording in the meeting-flow text
  with "report" wording.

Validated:

- `pytest tests\test_weekly_pipeline_markdown.py tests\test_export_report.py tests\test_export_data.py -q -p no:cacheprovider --basetemp .tmp\pytest-report-quality-timezone`
  -> 31 passed, 1 environment warning.
- `ruff check src\deal_intel\reports\markdown_summary.py src\deal_intel\tools\export_report.py tests\test_weekly_pipeline_markdown.py tests\test_export_report.py`
  -> passed.
- Local-sample Korean `export_report(report_type="weekly_pipeline",
  as_of="2026-06-10")` generated a report whose header now reads like
  `생성 시각: YYYY-MM-DD HH:MM:SS Asia/Seoul`.

### V2 public docs/readiness sweep

Completed:

- Updated `docs/mvp-readiness.md` from pre-release MVP-candidate wording to
  the current v2 public-trial-ready posture.
- Reframed the active backlog from "v2 closure" to the remaining post-v2
  quality order: report quality, deal-review quality, tool workflow cleanup,
  and usage/cost tracking.
- Confirmed `release/latest` already points at MCPB `0.2.1`; the newer
  candidate rebuild remains in `mcpb/deal-intel-mcp-0.2.1.mcpb` until an
  explicit handoff-release refresh is desired.

Validated:

- Public docs use the current `0.2.1` package line and avoid stale personal
  path, old env-name, and old tool-count references.
- `release/latest/VERSION` and tracked release artifact are still `0.2.1`.

### V2 MCPB artifact refresh

Completed:

- Repacked `mcpb/deal-intel-mcp-0.2.1.mcpb` from the current `mcpb/`
  manifest and launcher.
- Intentionally left `release/latest` unchanged. That folder is reserved for
  explicit handoff releases, not every release-candidate rebuild.
- Removed public-doc references to the maintainer-specific smoke path and old
  environment-name scan text.

Validated:

- `mcpb validate mcpb\manifest.json` -> passed.
- `mcpb info mcpb\deal-intel-mcp-0.2.1.mcpb` -> readable artifact, unsigned.
- `pytest tests\test_tool_surfaces.py tests\test_mcpb_manifest.py -q -p no:cacheprovider --basetemp .tmp\pytest-artifact-refresh`
  -> 44 passed, 1 environment warning.
- Public-facing doc scan found no stale personal path, old env name, old tool
  count, or old current-version references.
- `git diff --check` -> no blocking whitespace errors.

### V2 polish final gate - storage, runtime, context, and review UX

Completed:

- Closed the v2 polish queue for storage error hints, runtime drift
  diagnostics, product-context cold-start messaging, and deal-review
  uncertainty wording.
- Extended `mongo doctor` to reuse the same secret-safe storage diagnostics as
  export paths. Live DNS/network failures now report a classified
  `dns_or_network` hint with next actions instead of a generic Mongo failure.
- Confirmed that the current live Mongo read/report paths still work even when
  a standalone doctor ping sees transient DNS timeout behavior on this machine.

Validated:

- `ruff check .` -> passed.
- `pytest -q -p no:cacheprovider --basetemp .tmp\pytest-v2-polish-final`
  -> 754 passed, 1 environment warning.
- `smoke-natural-questions --as-of 2026-06-10`
  -> `OK: True`; output:
  `~/.deal-intel/smoke/natural-question-pack-20260618_150502`.
- `smoke-deal-review-audit --as-of 2026-06-10 --limit 20`
  -> sensitive field check passed; quality rules passed.
- `config doctor --offline --json`
  -> `ok: true`, full profile, zero failed checks; runtime diagnostics
  correctly surfaced local package/source version drift (`0.1.0` metadata vs
  `0.2.1` source tree).
- `smoke-profile --profile full --offline` -> pass.
- `smoke-profile --profile sample` -> pass.
- `crosscheck-weekly-dashboard --as-of 2026-06-10` -> `ok: true`; generated
  CSV/Markdown artifacts under `~/.deal-intel/reports`.
- `mongo refresh-chart-ready --target all --as-of 2026-06-10 --json`
  -> dry-run pass; 200 chart-ready rows across weekly pipeline, customer
  themes, and pipeline trend.
- `mongo doctor --json` currently reports one live `storage_ping` failure caused
  by local DNS timeout. The response now classifies the issue as
  `dns_or_network` and returns actionable next steps; this is tracked as an
  environment/UX observation, not a v2 release blocker.

UX findings:

- `blocker`: none.
- `v2 polish`: none remaining from the current queue.
- `post-v2`:
  - make runtime version drift easier to repair automatically, not just
    diagnose;
  - consider making Mongo doctor less all-or-nothing when read-only Mongo
    checks succeed but the initial ping path sees transient DNS failure;
  - keep improving sample data quality so deal-review uncertainty does not look
    alarming without context.

### V2 polish step 4 - deal-review uncertainty wording

Completed:

- `get_deal_review` now returns structured `uncertainty_reasons` whenever the
  review should stay cautious.
- `health_interpretation` also includes `uncertainty_reason_codes` for compact
  host summaries.
- Reasons distinguish low/partial qualification coverage, missing customer
  evidence, invalid/unknown/estimated deal value, invalid/missing/estimated
  structured fields, unassessed health, and seller-side product context that
  must not be treated as customer-stated evidence.
- Deal-review smoke text now prints uncertainty reasons, and the audit accepts
  structured reasons as a valid backing for high uncertainty.
- No scoring, health-band, or forecast-confidence thresholds changed.

Validated:

- `pytest tests/test_deal_review.py tests/test_cli_deal_review_smoke.py -q -p no:cacheprovider --basetemp .tmp\pytest-deal-review-uncertainty`
  -> 31 passed, 1 environment warning.
- `ruff check src\deal_intel\schema\deal_review.py src\deal_intel\cli.py tests\test_deal_review.py tests\test_cli_deal_review_smoke.py`
  -> passed.

### V2 polish step 3 - product-context cold-start UX

Completed:

- Product-context retrieval now returns explicit `product_context_status`,
  `embedding_status`, and `next_actions` fields.
- `get_product_context` distinguishes missing embeddings, loading/not-started
  embeddings, failed warmup, disabled product context, and an empty/unindexed
  cache.
- `analyze_deal` no longer risks blocking on product-context retrieval when the
  local embedding model is still warming. It skips seller-side context, keeps
  strategy generation running, and returns a warning plus embedding status.
- No raw product documents are returned or stored; `analyze_deal` still stores
  only product-context refs when context is actually used.

Validated:

- `pytest tests/test_product_context.py tests/test_analyze_deal.py -q -p no:cacheprovider --basetemp .tmp\pytest-product-context-coldstart`
  -> 22 passed, 1 environment warning.
- `ruff check src\deal_intel\product_context.py src\deal_intel\mcp_server.py src\deal_intel\tools\analyze_deal.py tests\test_product_context.py tests\test_analyze_deal.py`
  -> passed.

### V2 polish step 2 - runtime drift diagnostics

Completed:

- Added a shared runtime diagnostic helper used by both `config show` and
  `config doctor`.
- Runtime diagnostics now report the package name/version, source-tree version
  when running from a checkout, Python executable, Python version, module file,
  and package location.
- If installed package metadata and the source tree version differ, the runtime
  block reports `version_mismatch: true` with a next-action warning to reinstall
  or rebuild artifacts before publishing.
- `config doctor` MCP/CLI JSON now includes the same runtime block as
  `config show`, making Claude/Codex host setup drift easier to diagnose.
- Text output now separates runtime location from config readiness so users can
  distinguish "wrong Python/package" from "wrong Mongo/API config".

Observed:

- Local `config show` now reports package metadata `0.1.0` beside source-tree
  version `0.2.1`, which correctly surfaces the stale editable-install drift
  that motivated this polish item.

Validated:

- `pytest tests/test_cli_config_profiles.py tests/test_config_doctor.py -q -p no:cacheprovider --basetemp .tmp\pytest-runtime-diagnostics`
  -> 17 passed, 1 environment warning.
- `ruff check src\deal_intel\runtime.py src\deal_intel\cli.py src\deal_intel\config_doctor.py tests\test_cli_config_profiles.py tests\test_config_doctor.py`
  -> passed.
- `rg "<maintainer-user>|<old-env-name>" AGENTS.md CLAUDE.md README.md AI_START_HERE.md docs mcpb -g "*.md" -g "*.json"`
  -> no tracked public-doc matches.

### V2 polish step 1 - storage error hints

Completed:

- Added secret-safe storage diagnostics for Mongo-backed export failures.
- `export_report` now returns actionable `STORAGE_ERROR.hint` values for
  weekly pipeline and pipeline trend read failures.
- `export_data` now returns the same style of hint for ledger export read
  failures.
- The hint classifies common failure modes such as missing `MONGODB_URI`,
  authentication/authorization, DNS/network trouble, and Atlas failover or
  cluster unavailability.
- Hints include next actions such as running `deal-intel config doctor`,
  checking Atlas Network Access/IP allowlist, verifying credentials, and
  retrying after cluster resume/failover. Hints intentionally omit MongoDB URIs,
  API keys, tokens, and raw credentials.

Validated:

- `pytest tests/test_storage_diagnostics.py tests/test_export_report.py tests/test_export_data.py -q -p no:cacheprovider --basetemp .tmp\pytest-storage-hints`
  -> 30 passed, 1 environment warning.
- `ruff check src\deal_intel\storage\diagnostics.py src\deal_intel\tools\export_report.py src\deal_intel\tools\export_data.py tests\test_storage_diagnostics.py tests\test_export_report.py tests\test_export_data.py`
  -> passed.

### V2 readiness gate with UX friction review

Completed:

- Ran the v2 readiness gate across functional checks and user-experience
  friction checks. No v2 release blocker was found.
- Used the environment whose editable install points at this repository after
  finding that the documented local conda environment on this machine was stale
  and pointed at a different checkout. This is tracked as a maintainer/dev UX
  polish item, not a product runtime failure.
- Verified core regression:
  - `ruff check .` -> passed.
  - `pytest -q -p no:cacheprovider --basetemp .tmp\pytest-v2-full`
    -> 743 passed, 1 warning.
  - targeted config/Mongo/vector/product-context/add-interaction/analyze-deal
    tests passed.
- Verified install/config/profile flow:
  - `config doctor --offline --json` -> `ok: true`, full/mongo, zero failed
    checks, only the expected offline storage-ping skip.
  - `smoke-profile --profile full --offline` -> pass.
  - `smoke-profile --profile sample` -> pass.
- Verified natural question and deal review smoke:
  - `smoke-natural-questions --as-of 2026-06-10` -> `OK: True`; output:
    `~/.deal-intel/smoke/natural-question-pack-20260618_114707`.
  - `smoke-deal-review-audit --as-of 2026-06-10 --limit 20` -> sensitive
    field check passed; 20/20 reviews completed.
- Verified product-context flow:
  - existing local test sources included Markdown, JSON, PDF, and DOCX files;
  - `add_product_context_note` dry-run returned a clear next-action path;
  - `index_product_context` dry-run reported unchanged indexed files;
  - `analyze_deal` used product-context refs (`product_context_used: true`,
    `product_context_ref_count: 5`) without returning raw product content.
- Verified MongoDB/Atlas full path:
  - `mongo doctor --json` -> `ok: true`, zero failed/warning/skipped checks.
  - `crosscheck-weekly-dashboard --as-of 2026-06-10` -> `ok: true`.
  - `mongo refresh-chart-ready --target all --as-of 2026-06-10 --json`
    -> dry-run pass; 200 chart-ready rows across weekly pipeline, customer
    themes, and pipeline trend targets.
- Verified export/report flow:
  - `export_report(report_type="weekly_pipeline", as_of="2026-06-10")`
    -> `ok: true`, 13 rows, `incomplete_data_quality` warning, artifacts under
    `~/.deal-intel/reports`.
  - `export_data(dataset="open_deals", as_of="2026-06-10")`
    -> `ok: true`, 13 rows, ledger CSV artifact under `~/.deal-intel/reports`.
  - The Markdown report now reads as a meeting agenda/watchlist/action report,
    not a raw dump. CSV remains the ledger-style export surface.
- Verified distribution surfaces:
  - `mcpb validate mcpb\manifest.json` -> passed.
  - From `mcpb/`, `mcpb pack . deal-intel-mcp-0.2.1.mcpb` -> passed.
  - `mcpb info mcpb\deal-intel-mcp-0.2.1.mcpb` -> passed, unsigned warning
    only.
  - npm latest: `0.2.1`; PyPI latest: `0.2.1`.
- Hardened MCPB packaging hygiene:
  - added `.claude/**` to `mcpb/.mcpbignore`;
  - repacked locally from the `mcpb/` directory;
  - confirmed the bundle contains only `manifest.json`, `README.md`, and
    `server/launcher.py`.
  - `release/latest/` was intentionally left unchanged.

UX findings:

- `blocker`: none.
- `v2 polish`:
  - make environment drift easier to diagnose, e.g. document or automate
    checking that `pip show deal-intel-mcp` points at the intended checkout;
  - improve storage/DNS error hints for Mongo-backed exports so retry/network
    next actions are not `null`;
  - improve product-context cold-start behavior or messaging for direct CLI/tool
    calls that see the local embedding model as still warming up;
  - improve deal-review uncertainty messaging for cases where high uncertainty
    appears without a clear gap or warning.
- `post-v2`:
  - run macOS fresh-machine smoke after the next packaging or installer change;
  - consider broader installer diagnostics for missing Python/Node and stale
    editable installs.

### Documentation current-state sweep

Completed:

- Updated Korean companion docs and active contract docs to the current
  `0.2.1` public package state.
- Aligned the documented MCP tool surface with the runtime contract:
  `sample=24`, `standard=38`, `developer=41`.
- Updated distribution/bootstrapper docs so npm/npx is described as the current
  published no-git-clone front door, not a future-only plan.
- Added a Distribution Surfaces section to
  [architecture.md](architecture.md) covering PyPI, npm/npx, MCPB, and editable
  git-clone paths.
- Added lesson-learned entries for npm browser/device-key authentication and
  the MCPB/runtime dependency boundary.

Validated:

- `deal-intel config show` on the local full profile reported
  `resolved=standard` and `mcp_tools=38`.
- `deal-intel config doctor --offline --json` reported `ok: true`, full/mongo,
  zero failed checks, and only the expected offline storage-ping skip.
- Direct runtime surface check reported
  `sample=24`, `standard=38`, `developer=41`.

### Install scenario routing for Claude Desktop users

Completed:

- Added install scenario guidance, now consolidated into
  [AI_START_HERE.md](../AI_START_HERE.md), to make the
  three current user setup paths explicit:
  - non-developer with Claude Desktop but no Python/IDE;
  - beginner with Python, VS Code, Warp, or similar tools;
  - developer/infra engineer with an existing environment.
- Updated README and AI start docs to point setup assistants at the scenario
  selector before choosing npx, git clone, PyPI, or editable install.
- Updated MCPB documentation so the npx-managed Python runtime path is treated
  as the easiest no-git-clone preparation path, not only editable installs.

Current scenario assessment:

- Scenario 1 is supported, but not zero-prerequisite: the user still needs
  Node.js 18+ and Python 3.11+ before `npx deal-intel-mcp setup` can create the
  managed runtime. MCPB alone does not bundle Python dependencies.
- Scenario 2 is supported through either npx or git clone depending on whether
  the user wants usage only or customization.
- Scenario 3 is supported through PyPI, editable install, or npx by preference.

### Public npm/PyPI bootstrapper release

Completed:

- Published `deal-intel-mcp==0.2.1` to PyPI:
  <https://pypi.org/project/deal-intel-mcp/0.2.1/>.
- Published `deal-intel-mcp@0.2.1` to npm with the `latest` tag.
- Confirmed npm registry visibility:
  `npm view deal-intel-mcp version` -> `0.2.1`.
- Confirmed PyPI fresh install in a disposable venv:
  `pip install "deal-intel-mcp[embedding]==0.2.1"` -> success.
- Confirmed public npx bootstrapper smoke from a disposable
  `DEAL_INTEL_HOME`:
  - `npx deal-intel-mcp@0.2.1 setup --python <python-3.11>` -> success;
  - `npx deal-intel-mcp@0.2.1 where --json` -> returned managed runtime paths;
  - `npx deal-intel-mcp@0.2.1 smoke --profile-only` -> pass;
  - `npx deal-intel-mcp@0.2.1 mcp-config --json` -> returned the managed
    Python interpreter path and host config snippet.

Observed install UX note:

- On Windows, `npx deal-intel-mcp setup` may report Python as `unknown` when
  Python is installed but not on `PATH`. Rerun with
  `npx deal-intel-mcp setup --python <path-to-python-3.11+>`.

Remaining non-blocking follow-up:

- macOS fresh-machine smoke is still useful before wider announcement.

### Final local readiness gate before registry publish

Completed:

- Added [AI_USER_TEST_GUIDE.md](../AI_USER_TEST_GUIDE.md) for first external
  tester handoff.
- Added [release-publish-checklist.md](release-publish-checklist.md) for the
  maintainer-only npm/PyPI/MCPB publication sequence.
- Aligned the pre-registry user-test handoff docs with the current included
  MCPB artifact: `release/latest/deal-intel-mcp-0.2.1.mcpb`.
- Confirmed the local repository is ready for the next maintainer decision:
  actual npm/PyPI publication.

Validated:

- Full pytest:
  `pytest -q -p no:cacheprovider --basetemp .tmp\pytest-final-local-readiness`
  -> `743 passed, 1 warning`.
- Ruff:
  `ruff check .` -> pass.
- Natural-question smoke:
  `smoke-natural-questions --as-of 2026-06-10 --output-dir .tmp\final-readiness-natural`
  -> `OK: True`, 12/12 questions passed, no sensitive failures, no blocked
  questions.
- Deal review audit:
  `smoke-deal-review-audit --as-of 2026-06-10 --limit 20` -> sensitive field
  check passed and quality rules passed.
- MCPB manifest:
  `mcpb validate mcpb\manifest.json` -> schema validation passed.
- Full profile offline readiness:
  `config doctor --offline` and `smoke-profile --profile full --offline`
  -> pass with no failed or warning checks.
- Package surface smoke:
  `npm pack .\npm --dry-run --cache .tmp\npm-cache` -> package
  `deal-intel-mcp-0.2.1.tgz` dry-run succeeded.
- Handoff-doc consistency:
  targeted checks on `release/README.md` and `AI_USER_TEST_GUIDE.md` confirm
  current release/user-test handoff docs point at `0.2.1`. Older `0.1.15`
  references remain only in archived status history.
- Whitespace:
  `git diff --check` -> pass.

Superseded by the public release section above:

- npm and PyPI publication have now been completed for `0.2.1`.
- Public `npx deal-intel-mcp@0.2.1` smoke has now passed with an explicit
  Python 3.11+ interpreter path on Windows.
- Host-app `export_report` should be checked during user testing because report
  export is an MCP tool surface rather than a standalone CLI command.

### Product-context live smoke and distribution planning

Completed:

- Ran a live product-context smoke against the configured local source folder:
  `.tmp-product-context/sources`.
- Confirmed the product-context source set contains and parses:
  - `notion-ai.pdf`
  - `notion-enterprise-integrations-competitive.docx`
  - `notion-enterprise-overview.md`
  - `notion-enterprise-security.json`
- Confirmed `index_product_context` sees 4 source files with no skips, errors,
  or warnings. The cache path is
  `~/.deal-intel/product-context/cache`.
- Confirmed retrieval returns relevant bounded snippets for security,
  integration, and ROI/value-proposition queries across PDF, DOCX, Markdown,
  and JSON sources.
- Confirmed the MCP wrapper path returns refs/snippets without exposing full raw
  product documents.

Notes:

- One-shot CLI calls can still report embedding `warming_up` because the MCP
  server normally warms the local embedding model in a long-running background
  process. The live smoke warmed the provider inside one process before
  indexing/retrieval.
- Product-context behavior is ready to close for the current v2 pass. Future
  improvements should be usage-driven: larger-file UX, optional PPTX/XLSX
  parsing, cache-health visibility, and shared/Mongo product context only if
  local cache proves insufficient.

Planning:

- Updated [distribution-plan.md](distribution-plan.md) so the next distribution
  work is a dependency-inclusive bootstrapper, not a thin command alias.

### D3.1 bootstrapper contract

Completed:

- Added [bootstrapper-contract.md](bootstrapper-contract.md) as the design
  contract for the future dependency-inclusive `npx` bootstrapper.
- Defined:
  - runtime directories under `~/.deal-intel/runtime`;
  - user-facing commands: `setup`, `doctor`, `smoke`, `mcp`, and `where`;
  - install source policy: PyPI by default after metadata is ready, TestPyPI for
    validation, GitHub release wheel URL only as an explicit fallback;
  - default install profile: `deal-intel-mcp[embedding]`, with lightweight mode
    as an explicit opt-in;
  - secret redaction and install-state boundaries;
  - MCPB handoff responsibility boundary.

Next:

- D3.2 should create the Node CLI skeleton only after this contract stays
  stable enough to avoid building a thin wrapper around unresolved Python setup
  ambiguity.

### D3.2 Node CLI skeleton

Implemented:

- Added the first npm package skeleton under `npm/`.
- Added `npm/bin/deal-intel-mcp.js` with command routing for:
  - `where`
  - `setup`
  - `doctor`
  - `smoke`
  - `mcp`
- Kept the npm package `private: true` while the installer is incomplete.
- `where` is functional and prints the future runtime paths.
- `doctor`, `smoke`, and `mcp` delegate to the Python package when a runtime
  Python exists or `DEAL_INTEL_PYTHON` is set.
- `setup` intentionally returns a not-yet-implemented result until D3.3 owns
  runtime environment installation.

Validation:

- Added targeted tests for package metadata, runtime path resolution, and
  missing-runtime diagnostics.

### D3.3 runtime environment installer

Implemented:

- Upgraded `npm/bin/deal-intel-mcp.js setup` from placeholder to a real runtime
  installer flow.
- `setup --dry-run --json` now returns the exact plan for:
  - Python 3.11+ detection;
  - venv creation under `~/.deal-intel/runtime/venv`;
  - pip upgrade;
  - package install;
  - post-install sample profile smoke.
- `setup` without `--dry-run` can create the managed venv, install the selected
  package source, run the sample profile smoke, and write
  `~/.deal-intel/runtime/install-state.json`.
- Added installer options:
  - `--python PATH`
  - `--source pypi|testpypi`
  - `--wheel-url URL`
  - `--lightweight`
- Default install spec is `deal-intel-mcp[embedding]`; lightweight mode is
  explicit.

Validation:

- Added targeted dry-run installer tests for default, lightweight, and invalid
  source behavior.

### D3.4 MCP/Claude handoff

Implemented:

- Added `deal-intel-mcp mcp-config`.
- The command prints:
  - the Python interpreter path to paste into the MCPB form;
  - a copy-paste Claude Desktop `mcpServers` JSON snippet for manual setup;
  - short notes that secrets are intentionally excluded.
- `--json` returns the same handoff contract as structured data.
- `--server-name NAME` lets AI-assisted users generate a snippet with a custom
  MCP server name without editing JSON by hand.

Validation:

- Added targeted bootstrapper tests for the default handoff path, custom server
  names, and `DEAL_INTEL_PYTHON` overrides.

### D3.5 fresh-runtime smoke hardening

Implemented:

- Added [bootstrapper-fresh-smoke.md](bootstrapper-fresh-smoke.md) as the
  pre-publish and post-publish fresh-install smoke checklist.
- Changed the bootstrapper `setup` post-install check from
  `config doctor --offline` to `smoke-profile --profile sample`.
- This keeps first install from failing only because MongoDB/API values have
  not been configured yet. Full/pro readiness remains a `doctor` concern after
  the user enters real configuration.
- Updated the install state field from `last_doctor_status` to
  `last_post_install_check_status`.

Validation:

- Windows local-wheel fresh-runtime setup passed using an isolated
  `DEAL_INTEL_HOME` and a local wheel artifact.
- Managed runtime setup created the venv, installed the wheel, ran
  `smoke-profile --profile sample`, and wrote install state with
  `last_post_install_check_status: pass`.
- `deal-intel-mcp smoke --profile-only` passed from the managed runtime.
- `deal-intel-mcp mcp-config --json` returned the managed Python path and
  Claude Desktop snippet.

Remaining:

- Public `npx` install from npm is not verified until the package is published.
- PyPI/TestPyPI install-source smoke is still pending.
- macOS fresh-machine smoke is still pending.

### D3 package-surface smoke

Validated:

- `npm pack --dry-run` passes when npm cache is redirected to a workspace-local
  `.tmp` cache on Windows.
- The npm tarball currently contains only:
  - `README.md`
  - `bin/deal-intel-mcp.js`
  - `package.json`
- This confirms the bootstrapper does not bundle or reimplement the Python MCP
  server.
- `mcpb validate mcpb\manifest.json` passes.
- `mcpb info mcpb\deal-intel-mcp-0.2.1.mcpb` passes with the expected unsigned
  package warning.

Remaining:

- At this point the npm package surface smoke passed, but public
  `npx deal-intel-mcp ...` smoke was still pending until publish metadata was
  finalized.

### D3 publish metadata preparation

Implemented:

- Added PyPI-facing project metadata to `pyproject.toml`:
  description, README, MIT license, author, keywords, classifiers, and project
  URLs.
- Updated the npm bootstrapper package metadata to match `0.2.1`.
- Marked the npm package publish-shaped with public access metadata, while
  leaving actual npm publication as a maintainer credential step.
- Added npx install guidance, now consolidated into
  [AI_START_HERE.md](../AI_START_HERE.md), for the future no-git-clone install
  path after npm/PyPI publication.
- Added [AI_USER_TEST_GUIDE.md](../AI_USER_TEST_GUIDE.md) for first external
  tester handoff once an install path is available.
- Added [release-publish-checklist.md](release-publish-checklist.md) for the
  maintainer-only npm/PyPI/MCPB publication sequence.
- Linked the npx guide from README, AI_START_HERE, and the docs map.
- Updated the bootstrapper runtime version to read from `npm/package.json`,
  preventing package metadata/runtime output drift.

Validated:

- Python build metadata smoke:
  `python -m build --no-isolation --outdir .tmp\publish-metadata-dist`.
- npm package surface smoke:
  `npm pack --dry-run --cache ..\.tmp\npm-cache`.
- Node syntax smoke:
  `node --check npm\bin\deal-intel-mcp.js`.
- npm runtime smoke:
  `npm run smoke --cache ..\.tmp\npm-cache`, confirming
  `bootstrapper_version: 0.2.1`.
- Targeted regression:
  `pytest tests\test_bootstrapper_skeleton.py tests\test_mcpb_manifest.py -q -p no:cacheprovider --basetemp .tmp\pytest-publish-metadata`.
- Ruff:
  `ruff check .`.
- Public docs path hygiene scan found no maintainer-specific conda environment
  name or local user path references in the checked docs/npm surfaces.
- Release handoff docs were added and smoke-checked:
  `AI_USER_TEST_GUIDE.md`, `docs/release-publish-checklist.md`, and
  `npm pack .\npm --dry-run --cache .tmp\npm-cache`.

Superseded by the public release section above:

- Public npm and PyPI publication have now been completed for `0.2.1`.
- Public `npx deal-intel-mcp@0.2.1` smoke has now passed.

### D2.2 clean wheel install smoke

Completed:

- Rebuilt wheel and sdist artifacts with:
  `python -m build --no-isolation --outdir .tmp\d2_2_dist`.
- Installed the rebuilt wheel into a fresh venv:
  `.tmp\d2_2_venv_clean`.
- Verified the installed package metadata from the clean venv:
  - package version: `0.2.1`
  - base dependencies include `pymongo>=4.7` and `dnspython>=2.0`
  - `sentence-transformers` is not installed by the base wheel and remains
    gated behind the `embedding` extra.
- Fixed a packaging dependency warning exposed by the clean install:
  `pymongo[srv]` is no longer advertised by current PyMongo, so SRV support is
  now expressed as explicit `pymongo>=4.7` plus `dnspython>=2.0`.
- Verified clean-venv CLI behavior:
  - `config doctor --offline --json` with `local_sample` override -> pass
  - `smoke-profile --profile sample` -> pass
  - installed console script `deal-intel config show` -> pass
  - `smoke-natural-questions --as-of 2026-06-10 --output-dir <workspace-local-dir>`
    -> pass, 12/12 questions

Notes:

- Locally built wheel files under `.tmp\d2_*_dist` can inherit restrictive
  Windows sandbox ACLs. Copying the wheel to a normal workspace runtime path
  before installing normalizes file permissions. Treat this as a local
  sandbox/release-process note, not a package metadata failure.
- Build-isolated artifact creation remains a release/CI gate because the local
  Windows environment previously hit a pip-output decoding issue while creating
  the isolated build env.
- Fresh-install smoke commands should keep using explicit output directories
  until the bootstrapper owns a known-writable runtime directory.

### D2.1 package artifact smoke

Completed:

- Built local immutable artifacts with:
  `python -m build --no-isolation --outdir .tmp\d2_1_dist`.
- Produced:
  - `.tmp\d2_1_dist\deal_intel_mcp-0.2.1-py3-none-any.whl`
  - `.tmp\d2_1_dist\deal_intel_mcp-0.2.1.tar.gz`
- Installed the wheel into `.tmp\d2_1_install` with `pip install --no-deps`
  and verified imports from the installed target instead of the repo source
  tree.
- Verified packaged resources from the wheel:
  - `defaults.yaml`
  - `sample_datasets/weekly_pipeline_demo.v2.json`
  - `atlas/charts/weekly_pipeline_review.v1.json`
  - `atlas/chart_ready/weekly_pipeline_review.v1.json`
  - `atlas/vector_indexes/deal_summary_vector.v1.json`
  - `mongo/deals.v1.json`
  - `mongo/dashboard_weekly_pipeline.v1.json`
- Verified installed-artifact CLI smoke:
  - `config doctor --offline --json` with `local_sample` override -> pass
  - `smoke-profile --profile sample` -> pass
  - `render-atlas-dashboard --source chart-ready --as-of 2026-06-10 --chart-id pipeline_kpis`
    -> pass
  - `smoke-natural-questions --as-of 2026-06-10 --output-dir <workspace-local-dir>`
    -> pass, 12/12 questions

Notes:

- A default `config doctor --offline` call from the installed artifact correctly
  reported the current user config as `full/mongo` with missing `MONGODB_URI`
  in that subprocess. This was an environment/config check, not a packaging
  failure.
- A natural-question smoke call without `--output-dir` hit a local Windows
  permission error under `~/.deal-intel/smoke`. The command succeeds when
  given an explicit writable output directory. Treat this as a distribution UX
  follow-up for fresh-install guidance and bootstrapper defaults, not as a
  package-data failure.
- `python -m build --outdir .tmp\d2_1_dist` with build isolation hit a local
  Windows pip-output decoding error while creating the isolated build
  environment. Local D2.1 used `--no-isolation`; isolated build remains a
  release/CI gate before PyPI-style publishing.

## Archive - 2026-06-17

### V2 integration merge and release artifact

Implemented:

- Merged the MongoDB Atlas/Pro branch and the product/solution context branch
  through `codex/v2-integration`, then merged the verified integration branch
  into `main` and pushed `origin/main`.
- Resolved the only merge conflict in [backlog.md](backlog.md) by preserving
  both the MongoDB MDB workstream notes and the product-context roadmap.
- Refreshed `release/latest/` to MCPB `0.2.1`:
  - replaced `release/latest/deal-intel-mcp-0.1.15.mcpb`;
  - added `release/latest/deal-intel-mcp-0.2.1.mcpb`;
  - updated `release/latest/VERSION` and `checksums.txt`.
- Hardened Atlas Vector Search index creation so a live Atlas response such as
  "already defined" is treated as the idempotent `already_exists` state, not a
  failed apply.

Validation:

- Targeted integration gate:
  `pytest tests/test_config_doctor.py tests/test_mongo_contracts.py tests/test_chart_ready_refresh.py tests/test_product_context.py tests/test_add_interaction.py tests/test_analyze_deal.py tests/test_tool_surfaces.py tests/test_mcpb_manifest.py -q -p no:cacheprovider --basetemp=.tmp\pytest-v2-integration`
  -> 115 passed.
- Full regression:
  `pytest -q -p no:cacheprovider --basetemp=.tmp\pytest-v2-full-final`
  -> 731 passed, 1 warning.
- `ruff check .` -> passed.
- `mcpb validate mcpb\manifest.json` -> passed.
- From `mcpb/`, `mcpb pack . deal-intel-mcp-0.2.1.mcpb` -> passed.
- `mcpb info mcpb\deal-intel-mcp-0.2.1.mcpb` -> passed, unsigned warning only.
- Natural-question smoke:
  `deal-intel smoke-natural-questions --as-of 2026-06-10`
  -> `OK: True`.
- `deal-intel mongo doctor --json` -> `ok: true` on the current full/Mongo
  configuration with `python_cosine`.

Operational follow-up:

- The current M0/free MongoDB cluster is ready, but `mongo doctor` reports
  warnings until the latest collection validators and chart-ready rows are
  applied/refreshed:
  - apply current validators for `deals` and `analytics_snapshots`;
  - run `mongo refresh-chart-ready --target all --as-of YYYY-MM-DD --apply`;
  - then smoke the simplified Atlas Charts path from the `dashboard_*`
    collections.

Follow-up completed later on 2026-06-17:

- Applied current validators for `deals` and `analytics_snapshots` on the
  M0/free cluster.
- Refreshed chart-ready rows for `as_of=2026-06-10`:
  - `dashboard_weekly_pipeline`: 17 rows;
  - `dashboard_customer_themes`: 175 rows;
  - `dashboard_pipeline_trend`: 8 rows.
- Re-ran `deal-intel mongo doctor --json`; result is `ok: true` with
  `warning_checks: 0`.
- Existing Atlas Charts dashboards that were tied to the terminated M10 data
  source do not automatically recover. Rebuild or reconnect charts against the
  new M0 cluster and the `dashboard_*` collections.
- Added `deal-intel mongo backfill-analytics-snapshots` as a dry-run-first,
  idempotent baseline snapshot command for trend dashboards.
- Backfilled current-state baseline analytics snapshots for `2026-06-03` and
  `2026-06-10` with `baseline_id=trend-seed`:
  - 22 snapshots inserted for each date;
  - 44 baseline snapshots total;
  - the command records `event_type=baseline_snapshot`,
    `baseline_kind=current_state_as_of`, and deterministic event ids.
- Refreshed `dashboard_pipeline_trend` after baseline seeding:
  - 8 rows inserted for window `2026-06-03` to `2026-06-10`;
  - `snapshot_count` is now 44 instead of 0;
  - no chart-ready warnings.
- Re-ran `deal-intel mongo doctor --json`; result is still `ok: true` with
  `warning_checks: 0`.
- Updated [atlas-charts.md](atlas-charts.md) with the validated chart-ready
  Atlas UI setup for `Weekly Pipeline Review`, `Customer Themes Review`, and
  `Pipeline Trend Review`.
- Refreshed the local MCPB package artifact in `mcpb/` only:
  - `mcpb validate mcpb\manifest.json` -> passed;
  - from `mcpb/`, `mcpb pack . deal-intel-mcp-0.2.1.mcpb` -> passed after
    rerunning outside the sandbox because Windows denied the sandboxed pack;
  - `mcpb info mcpb\deal-intel-mcp-0.2.1.mcpb` -> passed with the expected
    unsigned-package warning.
- `release/latest/` was intentionally left unchanged.

### MongoDB Atlas/Pro MDB-0 audit

- Added [mongodb-atlas-pro.md](mongodb-atlas-pro.md) as the current-state audit
  and planning center for the MongoDB Atlas/Pro workstream.
- Classified existing MongoDB surfaces:
  - `full`/M0-compatible: ordinary indexes, collection validators, Mongo
    doctor, raw Atlas dashboard spec rendering, dashboard cross-checks, and
    future chart-ready collections.
  - `pro`/M10+-only: Atlas Vector Search index creation, `$vectorSearch`, M10+
    live smoke, and paid-infra validation.
- Identified the main usability gap: current Atlas Charts setup works but is
  query-bar-heavy. The next full/M0 improvement should be chart-ready
  materialized collections such as `dashboard_weekly_pipeline`,
  `dashboard_customer_themes`, and `dashboard_pipeline_trend`.
- No runtime behavior changed.

### MongoDB Atlas/Pro MDB-1 chart-ready data contract

- Added versioned chart-ready collection contracts:
  - `dashboard_weekly_pipeline`
  - `dashboard_customer_themes`
  - `dashboard_pipeline_trend`
- Added `deal_intel.chart_ready_contracts` as the loader/summary API for these
  contracts.
- Kept the contracts separate from `mongo_schema_collections()` so MDB-1 does
  not make `mongo doctor` warn about collections that the refresh engine does
  not create yet.
- Chose materialized collections over views for the first implementation path.
  Rationale: easier Atlas UI setup, explicit freshness, simpler row-count
  checks, and fewer surprises on M0.
- Validation:
  - `pytest tests/test_chart_ready_contracts.py tests/test_mongo_contracts.py tests/test_atlas_charts.py -q -p no:cacheprovider --basetemp .tmp\pytest-mdb1-targeted`
    -> 37 passed.
  - `ruff check src/deal_intel/chart_ready_contracts.py tests/test_chart_ready_contracts.py`
    -> passed.
  - `git diff --check` -> passed.

### MongoDB Atlas/Pro MDB-2 chart-ready refresh engine

Implemented:

- Added deterministic chart-ready refresh engine:
  - weekly pipeline rows from shared metric/report engines
  - customer theme rows from theme ranking, breakdown, and curated evidence
    paths
  - pipeline trend rows from analytics snapshot trend calculations
- Added `MongoDBClient.replace_chart_ready_rows()` to replace one dashboard
  refresh scope at a time. This prevents stale chart rows from lingering after
  source data changes.
- Added CLI command:
  - `deal-intel mongo refresh-chart-ready --target all --as-of YYYY-MM-DD`
  - dry-run by default
  - `--apply` required for MongoDB writes
- Kept MDB-2 CLI-only. No MCP admin write tool was added yet.
- Guardrails:
  - no LLM calls
  - no embedding calls
  - chart rows exclude raw notes, raw interaction content, contacts, and
    embeddings

Validation:

- `pytest tests/test_chart_ready_refresh.py tests/test_chart_ready_contracts.py tests/test_mongo_contracts.py tests/test_atlas_charts.py -q -p no:cacheprovider --basetemp .tmp\pytest-mdb2-targeted`
  -> 42 passed.
- `ruff check src/deal_intel/chart_ready_refresh.py src/deal_intel/chart_ready_contracts.py src/deal_intel/storage/mongodb.py src/deal_intel/cli.py tests/test_chart_ready_refresh.py tests/test_chart_ready_contracts.py`
  -> passed.
- `git diff --check` -> passed.


### MongoDB Atlas/Pro MDB-3 chart-ready Atlas specs

Implemented:

- Added parallel chart-ready Atlas specs:
  - `atlas/chart_ready/weekly_pipeline_review.v1.json`
  - `atlas/chart_ready/pipeline_trend.v1.json`
  - `atlas/chart_ready/customer_themes.v1.json`
- Added packaged copies under
  `src/deal_intel/resources/atlas/chart_ready/`.
- Extended `deal_intel.reports.atlas_charts` with `source="raw"` and
  `source="chart-ready"` support. Raw aggregation specs remain the default and
  are preserved for compatibility/reference.
- Added CLI support:
  - `deal-intel render-atlas-dashboard --source chart-ready --as-of YYYY-MM-DD`
- Updated [atlas-charts.md](atlas-charts.md) so the recommended setup path is
  now:
  1. run `mongo refresh-chart-ready` dry-run;
  2. apply refresh after checking row counts;
  3. build Atlas Charts from `dashboard_*` collections with short filters and
     ordinary field encoding.

Validation:

- `pytest tests/test_atlas_charts.py tests/test_cli_atlas_charts.py tests/test_chart_ready_contracts.py -q -p no:cacheprovider --basetemp .tmp\pytest-mdb3-targeted`
  -> 39 passed.


### MongoDB Atlas/Pro MDB-4 doctor chart-ready checks

Implemented:

- Added read-only chart-ready collection checks to `MongoDBClient`:
  - collection presence
  - current schema row count
  - latest refresh scope
  - latest generated timestamp
  - chart-level row counts for the latest scope
- Extended `deal-intel mongo doctor` to report one check per chart-ready
  collection:
  - `dashboard_weekly_pipeline_chart_ready`
  - `dashboard_customer_themes_chart_ready`
  - `dashboard_pipeline_trend_chart_ready`
- Missing or empty chart-ready collections are warnings, not failures. This
  keeps Mongo readiness separate from dashboard refresh state while still
  surfacing the next action:
  `deal-intel mongo refresh-chart-ready --target ... --as-of YYYY-MM-DD`.

Validation:

- `pytest tests/test_mongo_contracts.py tests/test_chart_ready_contracts.py tests/test_chart_ready_refresh.py -q -p no:cacheprovider --basetemp .tmp\pytest-mdb4-targeted`
  -> 29 passed.
- `ruff check src/deal_intel/mongo_doctor.py src/deal_intel/storage/mongodb.py tests/test_mongo_contracts.py`
  -> passed.


### MongoDB Atlas/Pro MDB-5 static vector-search hardening

Implemented:

- Hardened the Pro Atlas Vector Search path before live M10+ smoke:
  - versioned `deal_summary_vector` index specs are now validated for
    collection, index name, embedding path, dimensions, similarity, search
    settings, and M10+ minimum tier;
  - invalid dimension overrides are rejected before building
    `createSearchIndexes` commands;
  - `search_deals` now uses the vector-index `maxLimit` contract instead of a
    hardcoded limit;
  - Atlas search results are allowlisted at the tool layer so raw notes,
    interaction content, contacts, embeddings, and unexpected internal fields
    cannot leak even if a storage projection changes;
  - direct `MongoDBClient.search_by_embedding()` calls reject empty embeddings
    before issuing an aggregation and clamp limits to the static index
    contract.
- Improved Pro readiness diagnostics:
  - `config_doctor` and `mongo doctor` now include the expected Atlas Vector
    Search index summary: name, collection, embedding path, dimensions,
    similarity, and M10+ requirement;
  - `deal-intel mongo apply-vector-index --json` includes the same
    secret-safe index summary in dry-run output.
- Live Atlas behavior is still intentionally unverified until a disposable M10+
  cluster is available.

Validation:

- `pytest tests/test_atlas_vector_indexes.py tests/test_search_deals_startup.py tests/test_archived_read_paths.py tests/test_config_doctor.py tests/test_mongo_contracts.py -q -p no:cacheprovider --basetemp .tmp\pytest-mdb5-static-targeted`
  -> 61 passed, 1 warning.
- `ruff check .`
  -> passed.
- `deal-intel mongo apply-vector-index --json`
  -> dry-run succeeded with index summary for `deal_summary_vector`.
- `deal-intel mongo apply-vector-index --dimensions 0 --json`
  -> returned structured `ok: false` JSON instead of a traceback.
- `pytest -q -p no:cacheprovider --basetemp .tmp\pytest-mdb5-static-full`
  -> 699 passed, 1 warning.


### Product / solution context layer

Host-app live smoke on 2026-06-17 (complete; smoked on MCPB `0.2.0`, shipped as
`0.2.1`):

- Confirmed live in the host app: index -> retrieve works across all four indexed
  docs; a query for "ideal customer profile and key value propositions" returned
  the overview/security/AI sources with the seller-side "not customer evidence /
  do not raise qualification scores" tagging preserved end to end.
- Core invariant validated live on a disposable `create_deal` deal: `add_interaction`
  reported and stored `product_context_refs` (metadata only, not raw text) with
  `product_context_used: true`, while MEDDPICC scoring drew evidence only from
  customer-stated quotes (`source_confidence: customer_stated`,
  `score_policy: confirmed_evidence`). Product context did not raise any dimension
  score, theme count, or fill gaps. (No `create_sample_data` tool exists; the
  disposable-deal flow is `create_deal` -> verify -> `archive_deal`/`delete_deal`.)
- `analyze_deal` confirmed live in the host (initially slow due to LLM latency, then
  completed); its refs-only, no-raw-text strategy behavior held and is also covered
  deterministically by `tests/test_analyze_deal.py`.
- Smoke-driven fixes applied and shipped in the post-smoke `0.2.1` build (bumped
  `mcpb/manifest.json` + `pyproject.toml` to `0.2.1`, repacked
  `mcpb/deal-intel-mcp-0.2.1.mcpb`; final v2 integration later refreshed
  `release/latest/` to `0.2.1`):
  - Fixed a stale-config bug: `_context.config()` caches the loaded config for the
    process lifetime, so a `update_config` write (e.g. product-context source
    dirs) did not take effect in the same running session and the indexer kept
    resolving to the default source dir. `update_config` now calls a new
    `_context.reset_config()` after a confirmed write so the next tool call
    reloads `~/.deal-intel/config.yaml`. Added targeted tests for write-resets-
    cache and dry-run-keeps-cache.
  - Removed the product-context fields from the MCPB installer form and the
    forwarded env block. Product context is now a runtime-only setting (via
    `update_config` or direct env), so first-run setup is not cluttered.
  - Softened the first-run experience: when the default product-context source
    folder is absent, the indexer now emits a `product_context_not_configured`
    guidance message (with a `how_to_configure` hint) instead of the
    error-flavored `source_dir_missing` warning. A genuinely missing
    user-configured folder still warns. Added targeted tests for both paths.
- Known gap (deferred): `config_doctor` does not surface the effective product-
  context source directory; only the config-file path is shown, and `config show`
  is CLI-only (not an MCP tool). Tracked under the backlog config-doctor/status
  visibility follow-up.

CLI pre-smoke on 2026-06-17 (before host-app live smoke):

- Ran an isolated CLI pre-smoke from a `codex/product-context-layer` git worktree
  (env-isolated: `PYTHONPATH=<worktree>/src` with an existing interpreter, so the
  parallel `codex/mongodb-atlas-pro` checkout and the local
  `~/.deal-intel/config.yaml` were untouched; cfg passed in-process, not persisted).
- Multi-format source set under `.tmp-product-context/sources/` covering all four
  supported binary/text paths (`notion-ai.pdf`, `notion-enterprise-overview.md`,
  `notion-enterprise-security.json`,
  `notion-enterprise-integrations-competitive.docx`):
  - dry-run did not embed or write (`storage_written: false`, `would_index: 4`).
  - real index produced `indexed: 4`, `indexed_chunks: 10`, all chunks embedded,
    with all four formats parsed (pdf via pypdf, docx via stdlib, md, json).
  - re-run reused cache (`unchanged: 4`, `indexed: 0`, zero embed calls).
  - `retrieve_product_context` returned bounded snippets plus source metadata, not
    raw full documents.
  - Note: ranking used a coarse keyword stub embedding, so cross-document ordering
    is not representative; host-app smoke with a real embedding model still owns
    retrieval-quality validation. `add_interaction`/`analyze_deal` refs invariants
    were covered deterministically by their test suites in this pass, not a live
    LLM run (that remains the host-app smoke's job).
- Validation (worktree interpreter, `PYTHONPATH=<worktree>/src`):
  - targeted: `pytest tests/test_product_context.py tests/test_add_interaction.py
    tests/test_analyze_deal.py tests/test_config_writer.py tests/test_env_config.py
    tests/test_mcpb_manifest.py tests/test_tool_surfaces.py -q -p no:cacheprovider
    --basetemp=.tmp/pytest-pc-presmoke`: 102 passed, 1 warning.
  - full regression: `pytest -q -p no:cacheprovider
    --basetemp=.tmp/pytest-pc-full`: 696 passed, 1 warning.
  - `ruff check .`: passed.
  - `mcpb validate mcpb/manifest.json`: schema validation passes.
- Packaged the product-context bundle as `0.2.0` for the host-app live smoke
  (bumped `mcpb/manifest.json` and `pyproject.toml`, updated the manifest-version
  test and current-version doc lines). The smoke artifact is built into the
  gitignored build dir as `mcpb/deal-intel-mcp-0.2.0.mcpb`. At that pre-smoke
  checkpoint, `release/latest/` stayed on `0.1.15` because `0.2.0` was a smoke
  build, not a published release. This is superseded by the final v2 integration
  entry above, which publishes `0.2.1`.
  Re-ran the full suite (696 passed), `ruff` (passed), and `mcpb validate`
  against the bumped manifest.

Follow-up on 2026-06-17:

- Raised the default product-context source file limit from 25MB to 100MB and
  made source size/chunk budgets configurable:
  - `product_context.max_source_file_mb`
  - `product_context.max_note_mb`
  - `product_context.max_chunks_per_file`
  - `product_context.max_chunks_per_run`
- Added partial-indexing guardrails for large product catalogs. When a catalog
  exceeds per-file or per-run chunk budgets, the indexer records
  `counts.partial_indexed`, warning codes, and cache metadata rather than
  silently treating the file as fully indexed.
- Exposed the new product-context limits through `update_config`, runtime env
  loading, and MCPB installer config fields.
- Historical note: this intermediate product-context branch refresh touched
  `release/latest/deal-intel-mcp-0.1.15.mcpb`; final v2 integration later
  replaced it with `release/latest/deal-intel-mcp-0.2.1.mcpb`.
- Smoke:
  - A temporary Notion AI page PDF under `.tmp-product-context/` indexed and
    retrieved successfully with `indexed_chunks: 5`.
- Live host-app smoke notes:
  - Completed before final v2 integration and kept here as the expected
    behavior contract for future product-context regressions.
  - Expected effect: product/solution context should help `add_interaction`
    and `analyze_deal` interpret seller-side terminology, ICP, value
    propositions, disqualifiers, competitor positioning, and product fit more
    accurately.
  - Non-goal: product context must not become customer-stated evidence. It
    must not directly raise qualification scores, customer-theme counts,
    BI/report metrics, or deal summary embeddings.
  - Success criteria:
    - MCPB/full install loads the product-context tools and `config_doctor`
      remains ready.
    - `config show` or `config_doctor` makes the effective product-context
      source directories understandable enough for a host app to guide users.
    - A configured source folder containing at least one PDF and one text-like
      note indexes successfully; a second unchanged run reuses cache.
    - `get_product_context` returns relevant bounded snippets and metadata,
      not full raw documents.
    - `add_interaction` reports product-context refs when relevant, stores refs
      only, and does not raise scoring from product context alone.
    - `analyze_deal` can use product-context refs for strategy interpretation
      without returning or storing raw product text.
    - Natural-question smoke still passes after indexing.
  - Watch points:
    - Host apps may pass Windows paths, escaped backslashes, or spaces
      differently from CLI tests.
    - MCPB installer config must forward source dirs and size/chunk limits as
      expected.
    - Large PDFs may be partial-indexed; this is acceptable only when warning
      codes and counts are clear.
    - Scanned PDFs may extract little text and should produce understandable
      warnings rather than misleading empty success.
    - Embedding/OAuth readiness can fail independently from storage readiness.
    - Secret-shaped files or notes must be skipped/rejected without leaking
      source content.
    - Generic product wording can over-match; retrieved context must remain
      seller-side guidance, not evidence.
    - Cache invalidation should reprocess modified files while leaving
      unchanged files untouched.
- Validation:
  - `pytest tests/test_product_context.py tests/test_config_writer.py tests/test_env_config.py tests/test_mcpb_manifest.py -q -p no:cacheprovider --basetemp=.pytest-product-context-limits`:
    49 passed, 1 warning.
  - `ruff check .`:
    passed.
  - `mcpb validate mcpb\manifest.json`:
    passed.

- Added first-pass DOCX parsing for product context indexing. The parser reads
  Word document paragraphs from `word/document.xml` with the Python standard
  library, so no new runtime dependency is required.
- `pptx` and `xlsx` remain warning-only and are still tracked as future parser
  work.
- Connected indexed product context to `analyze_deal`.
  - The strategy prompt may use bounded seller-side snippets for product fit,
    positioning, ICP, competitor, or disqualifier context.
  - The saved deal stores only `bd_strategy_product_context_refs`, not raw
    product text.
  - Deterministic review/report paths remain product-context-free.
- Validation:
  - `pytest tests/test_product_context.py -q -p no:cacheprovider --basetemp .tmp\pytest-product-context-docx`:
    13 passed, 1 warning.
  - `pytest tests/test_analyze_deal.py tests/test_product_context.py tests/test_add_interaction.py -q -p no:cacheprovider --basetemp .tmp\pytest-product-context-analyze-targeted`:
    30 passed, 1 warning.
  - `pytest tests/test_analyze_deal.py tests/test_product_context.py tests/test_add_interaction.py tests/test_tool_surfaces.py tests/test_mcpb_manifest.py -q -p no:cacheprovider --basetemp .tmp\pytest-product-context-strategy-targeted`:
    74 passed, 1 warning.
  - `pytest tests/test_product_context.py tests/test_add_interaction.py tests/test_tool_surfaces.py tests/test_mcpb_manifest.py tests/test_config_writer.py -q -p no:cacheprovider --basetemp .tmp\pytest-product-context-docx-targeted`:
    88 passed, 1 warning.
  - `pytest -q -p no:cacheprovider --basetemp .tmp\pytest-product-context-docx-full-rerun`:
    689 passed, 1 warning.
  - `pytest -q -p no:cacheprovider --basetemp .tmp\pytest-product-context-strategy-full`:
    691 passed, 1 warning.
  - `ruff check .`:
    passed.
  - `mcpb validate mcpb\manifest.json`:
    passed.

Implemented:

- Added a local seller-side product context cache under
  `~/.deal-intel/product-context`.
- Added config defaults for source dirs, cache dir, retrieval limits, and first
  supported file types: `txt`, `md`, `json`, `csv`, `pdf`, and `docx`.
- Added safe source-folder configuration for product context:
  - `update_config(product_context_source_dirs=...)`
  - `DEAL_INTEL_PRODUCT_CONTEXT_SOURCE_DIRS` for MCPB/runtime env injection
  - `config show` now surfaces the effective product-context source dirs.
  - Cache location remains engine-managed by default.
- Added `src/deal_intel/product_context.py` for scanning, parsing, chunking,
  secret scanning, embedding, cache reuse, and retrieval.
- Added MCP tools:
  - `add_product_context_note`
  - `index_product_context`
  - `get_product_context`
- Added tool catalog grouping and intent aliases:
  - `context.note.add`
  - `context.index`
  - `context.get`
- Added managed note intake for pasted product/solution text.
  - `add_product_context_note` is dry-run-first and writes only managed
    Markdown source files under the configured product-context source
    directory.
  - Apply mode requires `confirmed_by_user=true`.
  - The tool rejects secret-shaped content and does not call LLMs, embeddings,
    MongoDB, or indexing automatically.
- Added user/agent-facing UX guidance in `README.md` and `AI_START_HERE.md`
  for the two normal product-context flows:
  folder-based docs and pasted managed notes.
- Connected product context to `add_interaction`.
  - The LLM extraction prompt can receive a bounded seller/product context
    block when relevant chunks are indexed.
  - The prompt explicitly states that product context is seller-side knowledge,
    not customer-stated evidence.
  - Stored interactions keep only `product_context_refs` metadata, not raw
    product snippets.

Guardrails:

- Product context does not directly increase qualification scores.
- Product context is not counted as customer-theme evidence.
- Product context is not mixed into deal `summary_embedding`.
- Product context is not used in BI/report metric calculation paths.
- Secret-shaped source files are skipped.
- Secret-shaped pasted notes are rejected before writing.
- Presentation and spreadsheet files (`pptx`, `xlsx`) are warning-only for the
  first pass.

Validation so far:

- `pytest tests/test_product_context.py tests/test_add_interaction.py tests/test_tool_surfaces.py tests/test_mcpb_manifest.py -q -p no:cacheprovider --basetemp .tmp\pytest-product-context-targeted`:
  64 passed, 1 warning.
- `pytest tests/test_product_context.py tests/test_add_interaction.py tests/test_tool_surfaces.py tests/test_mcpb_manifest.py -q -p no:cacheprovider --basetemp .tmp\pytest-product-context-targeted-rerun`:
  64 passed, 1 warning.
- `pytest -q -p no:cacheprovider --basetemp .tmp\pytest-product-context-full-rerun`:
  678 passed, 1 warning.
- `ruff check .`:
  passed.
- `mcpb validate mcpb\manifest.json`:
  passed.
- `deal-intel smoke-natural-questions --as-of 2026-06-10`:
  OK true, 12/12 questions passed.
- `pytest tests/test_config_writer.py tests/test_config_doctor.py tests/test_env_config.py tests/test_product_context.py tests/test_mcpb_manifest.py -q -p no:cacheprovider --basetemp .tmp\pytest-product-context-config`:
  49 passed, 1 warning.
- Targeted Ruff for config/product-context setting files:
  passed.
- `pytest tests/test_product_context.py tests/test_tool_surfaces.py tests/test_mcpb_manifest.py -q -p no:cacheprovider --basetemp .tmp\pytest-product-context-note`:
  56 passed, 1 warning.
- `pytest tests/test_config_doctor.py tests/test_sample_data.py tests/test_tool_surfaces.py tests/test_mcpb_manifest.py -q -p no:cacheprovider --basetemp .tmp\pytest-product-context-note-counts`:
  65 passed, 1 warning.
- `pytest -q -p no:cacheprovider --basetemp .tmp\pytest-product-context-note-full-rerun`:
  688 passed, 1 warning.
- Targeted Ruff for product-context note files:
  passed.
- `ruff check .`:
  passed.
- `mcpb validate mcpb\manifest.json`:
  passed.
- `deal-intel smoke-natural-questions --as-of 2026-06-10`:
  OK true, 12/12 questions passed.

### QF-11 custom framework end-to-end smoke

Implemented:

- Added `tests/test_qualification_framework_e2e.py` as a thin integration
  smoke for custom qualification framework behavior.
- Added config lifecycle coverage:
  copy a built-in template to a custom key, store it in user config, activate
  it, use it in `add_interaction`, revise the framework, detect stale
  interaction framework hashes through `backfill_qualification_reextract`, and
  delete the inactive custom framework safely.
- The smoke runs the same custom-framework deal through:
  `get_deal_review`, `get_deal_gaps`, `get_metrics`, `export_report`,
  `search_deals`, and `build_analytics_snapshot`.
- The test intentionally includes a high-scoring `meddpicc_latest`
  compatibility snapshot to verify active-framework paths do not accidentally
  fall back to MEDDPICC values.
- The test also asserts public payloads do not expose raw notes, raw
  interaction content, contacts, or embeddings.

Validation so far:

- `pytest tests/test_qualification_framework_e2e.py -q -p no:cacheprovider --basetemp .tmp\pytest-qf11-e2e`:
  2 passed.
- `pytest tests/test_qualification_framework.py tests/test_qualification_config.py tests/test_qualification_extraction.py tests/test_qualification_snapshot.py tests/test_qualification_framework_e2e.py tests/test_add_interaction.py tests/test_backfill_qualification.py tests/test_backfill_qualification_reextract.py tests/test_deal_review.py tests/test_deal_gaps.py tests/test_get_metrics.py tests/test_weekly_pipeline_report.py tests/test_weekly_pipeline_markdown.py tests/test_export_report.py tests/test_search_deals_startup.py tests/test_analytics_snapshots.py tests/test_data_quality_reporting.py -q -p no:cacheprovider --basetemp .tmp\pytest-qf11-targeted`:
  209 passed, 1 warning.
- `pytest -q -p no:cacheprovider --basetemp .tmp\pytest-qf11-full`:
  668 passed, 1 warning.
- `ruff check .`:
  passed.
- `deal-intel smoke-natural-questions --as-of 2026-06-10`:
  OK true, 12/12 questions passed.

### QF-10 generic qualification compatibility sweep

Implemented:

- Added a tracked QF-10 audit/classification section to
  [qualification-framework-v2.md](qualification-framework-v2.md).
- Moved analytics snapshot creation to `select_qualification_snapshot(...)`.
  New snapshots now include generic `qualification_*` fields while preserving
  `health_pct`/`health_band` aliases.
- Kept MEDDPICC snapshot aliases, but for non-MEDDPICC active frameworks
  `meddpicc_*` snapshot fields are empty/null rather than fabricated from
  unrelated dimensions.
- Added generic qualification metadata to semantic search results and MongoDB
  search projections while keeping `health_pct`/`gaps` aliases.
- Marked MEDDPICC-specific `get_insights` modes as legacy compatibility paths
  with `framework_scope: meddpicc_legacy`; `pipeline_overview` remains generic.
- Updated architecture and baseline docs for the new generic snapshot/search
  behavior.

Validation:

- `pytest tests/test_analytics_snapshots.py -q -p no:cacheprovider`:
  10 passed.
- `pytest tests/test_search_deals_startup.py -q -p no:cacheprovider`:
  14 passed, 1 warning.
- `pytest tests/test_data_quality_reporting.py -q -p no:cacheprovider`:
  16 passed, 1 warning.
- `pytest tests/test_analytics_snapshots.py tests/test_search_deals_startup.py tests/test_data_quality_reporting.py tests/test_mongo_contracts.py tests/test_archived_read_paths.py tests/test_pipeline_timing.py tests/test_get_metrics.py tests/test_pipeline_metrics_summary.py tests/test_pipeline_trends.py -q -p no:cacheprovider --basetemp .tmp\pytest-qf10-targeted`:
  128 passed, 1 warning.
- `pytest -q -p no:cacheprovider --basetemp .tmp\pytest-qf10-full`:
  666 passed, 1 warning.
- `ruff check .`:
  passed.
- `deal-intel smoke-natural-questions --as-of 2026-06-10`:
  OK true, 12/12 questions passed.

Notes:

- `tests/test_mongo_contracts.py -q -p no:cacheprovider` initially hit the
  known Windows temp permission issue under `%LOCALAPPDATA%\Temp`; rerunning
  with repo-local `--basetemp .tmp\pytest-qf10-mongo-contracts` passed.

### Architecture developer map expansion

Implemented:

- Expanded [architecture.md](architecture.md) with a developer navigation map.
- Added runtime entry point ownership for MCP server, CLI, context, config
  loading, MCPB launcher, and packaged resources.
- Added CLI command family mapping for config, smoke, Mongo operations, local
  data, taxonomy cleanup, qualification maintenance, Atlas dashboards, and QA
  smoke commands.
- Added an MCP tool ownership index covering canonical tools, intent aliases,
  owner modules, inputs, outputs/side effects, adjacent tests, and "do not
  break" notes.
- Added a major internal engine index for config/profile, tool surface,
  storage, qualification, interaction extraction, metrics, review/gaps,
  reports, Atlas dashboards, customer themes, search/vector, usage, user
  memory, and Mongo operations.
- Added change playbooks that map common edits to the files and tests that
  should be checked before closing the work.

Validation:

- Documentation-only change.
- Verified new architecture headings with `rg`.
- Spot-checked the rendered Markdown source around the new tables.

### QF-9 tool namespace / customer theme cleanup

Implemented:

- Kept existing customer-theme tool names for compatibility.
- Added user-intent grouping and tool-selection guidance to `get_tool_catalog`.
- Added short intent alias metadata to `get_tool_catalog` tool rows:
  `canonical_tool`, `namespace`, and `intent_alias`. These aliases are
  discovery hints only, not alternate callable MCP tool names.
- Added customer-theme workflow hints to ranking, comparison, and evidence
  responses.
- Moved `get_customer_themes` from the legacy Mongo aggregation path onto the
  restricted `list_deals_for_metrics()` read path.
- Exposed `get_customer_themes` in sample mode so customer-theme ranking starts
  from the same tool in sample/full profiles. Counts at that QF-9 checkpoint
  were `sample=24`, `standard=35`, `developer=38`.

Validation:

- `pytest tests/test_tool_surfaces.py tests/test_customer_themes.py tests/test_customer_theme_insights.py tests/test_mcpb_manifest.py tests/test_storage_backend_contract.py -q --basetemp .tmp\pytest-qf9-targeted`:
  70 passed, 1 warning.
- `mcpb validate mcpb\manifest.json`:
  passed.
- `pytest tests/test_cli_config_profiles.py tests/test_tool_surfaces.py -q --basetemp .tmp\pytest-qf9-counts`:
  37 passed, 1 warning.
- `pytest -q --basetemp .tmp\pytest-qf9-full-rerun`:
  660 passed, 1 warning.
- `ruff check .`:
  passed.
- `deal-intel smoke-natural-questions --as-of 2026-06-10`:
  OK true, 12/12 questions passed.

### QF-8 compatibility cleanup

Implemented:

- Updated public MCP tool docstrings so active-framework qualification is the
  generic concept and MEDDPICC is described as the bundled default framework.
- Updated MCPB manifest descriptions for `add_interaction`, `get_deal`, and
  package metadata to avoid MEDDPICC-only product positioning.
- Updated README, AI_START_HERE, and baseline contracts to separate canonical
  qualification language from legacy/default-framework `meddpicc*`
  compatibility fields.
- Kept storage fields and old compatibility contracts intact. Broad namespace
  cleanup remains deferred to QF-9.

Validation:

- `pytest tests/test_tool_surfaces.py tests/test_mcpb_manifest.py -q --basetemp .tmp\pytest-qf8-targeted`:
  41 passed, 1 warning.
- `mcpb validate mcpb\manifest.json`:
  passed.
- Stale public wording scan for MEDDPICC-only current-language phrases:
  no active public-surface hits; remaining hits are QF plan examples or older
  status archive entries.
- `pytest -q --basetemp .tmp\pytest-qf8-full`:
  661 passed, 1 warning.
- `ruff check .`:
  passed.
- `deal-intel smoke-natural-questions --as-of 2026-06-10`:
  OK true, 12/12 questions passed.

### QF-7c qualification backfill MCP surface

Implemented:

- Added MCP tool `backfill_qualification`.
  - Standard/developer surface only.
  - Dry-run by default.
  - No LLM calls and no raw interaction content reads.
  - Apply mode requires `dry_run=false` and `confirmed_by_user=true`.
- Added MCP tool `backfill_qualification_reextract`.
  - Standard/developer surface only.
  - Dry-run by default and does not initialize the LLM provider in dry-run.
  - Defaults to `max_llm_calls=30`.
  - Apply mode may call the configured LLM once per selected interaction and
    uses the dedicated raw-content maintenance read path.
  - Responses never include raw interaction content.
- Updated MCP tool-surface contracts and MCPB manifest tool declarations.
- Surface counts at that QF-7c checkpoint were `sample=24`, `standard=35`,
  `developer=38`.

Validation:

- `pytest tests/test_backfill_qualification.py tests/test_backfill_qualification_reextract.py tests/test_tool_surfaces.py tests/test_mcpb_manifest.py tests/test_config_doctor.py tests/test_sample_data.py -q --basetemp .tmp\pytest-qf7c-targeted`:
  82 passed, 1 warning.
- `pytest tests/test_backfill_qualification.py tests/test_backfill_qualification_reextract.py tests/test_tool_surfaces.py tests/test_mcpb_manifest.py tests/test_config_doctor.py tests/test_sample_data.py -q --basetemp .tmp\pytest-qf7c-targeted-rerun`:
  82 passed, 1 warning.
- `mcpb validate mcpb\manifest.json`:
  passed.
- `pytest -q --basetemp .tmp\pytest-qf7c-full`:
  660 passed, 1 warning.
- `ruff check .`:
  passed.
- Runtime registration smoke:
  developer surface exposed 38 tools at that checkpoint and included
  `backfill_qualification` plus `backfill_qualification_reextract`.

### QF-7b qualification LLM re-extraction backfill

Implemented:

- User decisions:
  - default scope is scoring-eligible interactions only;
  - one apply run defaults to at most 30 LLM calls;
  - expose core + CLI first, defer MCP surface to QF-7c.
- Added framework fingerprints so newly extracted evidence can be checked for
  stale framework definitions later.
- `add_interaction` now stores `qualification_framework_hash` beside newly
  extracted evidence.
- Added dedicated raw-content maintenance read/write storage methods:
  `list_deals_for_qualification_reextract(...)` and
  `update_deal_qualification_reextraction(...)`.
- Added core module `tools/backfill_qualification_reextract.py`.
- Added CLI command: `deal-intel backfill-qualification-reextract`.
- The command defaults to dry-run. Actual LLM calls and writes require
  `--apply --confirmed-by-user`.
- Default `--max-llm-calls` is 30.
- The dry-run response reports selected interaction count and estimated input
  characters without exposing raw content.
- Apply mode stores usage under `interaction.qualification_backfill_usage`, and
  `get_usage` now includes that cost/usage metadata.
- MCP exposure is intentionally deferred to QF-7c.

Validation:

- `pytest tests/test_backfill_qualification_reextract.py tests/test_usage.py -q --basetemp .tmp\pytest-qf7b-targeted-rerun`:
  15 passed.
- `pytest tests/test_backfill_qualification_reextract.py tests/test_backfill_qualification.py tests/test_add_interaction.py tests/test_usage.py tests/test_storage_backend_contract.py tests/test_local_sample_backend.py tests/test_qualification_snapshot.py -q --basetemp .tmp\pytest-qf7b-wide`:
  70 passed, 1 warning.
- `pytest -q --basetemp .tmp\pytest-qf7b-full-rerun`:
  655 passed, 1 warning.
- `ruff check .`:
  passed.

### QF-7a qualification snapshot recompute backfill

Implemented:

- Added a recompute-only qualification backfill path:
  `tools/backfill_qualification.py`.
- Added CLI command: `deal-intel backfill-qualification`.
- The command defaults to dry-run. Actual writes require `--apply` plus
  `--confirmed-by-user`.
- This path performs no LLM calls and does not read raw interaction content.
  It recomputes `meddpicc_latest` and `qualification_latest` from already
  stored scoring evidence.
- Deals with no scoring evidence are skipped instead of writing a false
  zero-health/all-gap snapshot.
- Custom-framework deals that only have legacy MEDDPICC evidence are flagged as
  `needs_reextraction` for the later QF-7b LLM re-extraction path.
- Added patch-only storage method
  `update_deal_qualification_snapshots(...)` for MongoDB and local personal
  storage so restricted BI projections are never written back as whole deal
  replacements.

Design notes:

- QF-7a is intentionally recompute-only. It covers weight, threshold, stage
  context, and active-framework metadata changes when the required evidence is
  already stored.
- QF-7b remains separate because it must read `interaction.raw_content`, call
  the configured server-side LLM, track usage/cost, and handle partial
  extraction failures.

Validation:

- `pytest tests/test_backfill_qualification.py tests/test_storage_backend_contract.py -q --basetemp .tmp\pytest-qf7a-targeted`:
  15 passed.
- `pytest tests/test_backfill_qualification.py tests/test_qualification_snapshot.py tests/test_add_interaction.py tests/test_update_stage.py tests/test_storage_backend_contract.py tests/test_local_sample_backend.py -q --basetemp .tmp\pytest-qf7a-wide`:
  65 passed, 1 warning.
- `pytest -q --basetemp .tmp\pytest-qf7a-full`:
  645 passed, 1 warning.
- Targeted Ruff over touched QF-7a files:
  passed.
- `ruff check .`:
  passed.
- `git diff --check`:
  no whitespace errors; Windows LF/CRLF warnings only.

### QF-6 report/export/Atlas qualification read path

Implemented:

- `weekly_pipeline` report rows now select the active qualification snapshot
  through `schema/qualification_read.py`, preferring `qualification_latest` and
  falling back to legacy `meddpicc_latest`.
- Weekly report rows expose canonical qualification fields:
  `qualification_framework`, `qualification_framework_display_name`,
  `qualification_source_field`, `qualification_health_pct`,
  `qualification_quality_pct`, `qualification_coverage_pct`, and
  `qualification_gaps`.
- Existing `health_pct`, `health_band`, and `meddpicc_gaps` aliases are
  preserved. `meddpicc_gaps` is only populated for MEDDPICC-backed rows.
- `export_data` open/all/closed datasets now include qualification columns so
  Excel/CSV ledgers can follow custom frameworks without losing legacy health
  aliases.
- Weekly Markdown report wording now says qualification gap/health where the
  active framework may not be MEDDPICC.
- Weekly Atlas chart specs now read `qualification_latest.health_pct`,
  `qualification_latest.filled_count`, and `qualification_latest.gaps` first,
  with `meddpicc_latest` fallback for old/sample data.
- Added `qualification_gap_distribution` while keeping
  `meddpicc_gap_distribution` as a legacy-compatible chart id.

Design notes:

- This migrates the human report, CSV ledger, and weekly Atlas dashboard
  surfaces. Analytics snapshots and MEDDPICC-specific `get_insights` aggregation
  modes remain separate follow-up work.
- `export_report` still returns deterministic data packs and host-app polish
  prompts; it does not call an LLM.

Validation:

- `pytest tests/test_weekly_pipeline_report.py tests/test_weekly_pipeline_markdown.py tests/test_export_data.py -q --basetemp .tmp\pytest-qf6-report-targeted`:
  25 passed.
- `pytest tests/test_weekly_pipeline_report.py tests/test_weekly_pipeline_markdown.py tests/test_export_data.py tests/test_export_report.py tests/test_atlas_charts.py tests/test_cli_atlas_charts.py -q --basetemp .tmp\pytest-qf6-targeted`:
  59 passed, 1 warning.
- `pytest tests/test_weekly_pipeline_report.py tests/test_weekly_pipeline_markdown.py tests/test_export_data.py tests/test_export_report.py tests/test_atlas_charts.py tests/test_cli_atlas_charts.py tests/test_dashboard_crosscheck.py tests/test_pipeline_metrics_summary.py tests/test_get_metrics.py tests/test_data_quality_reporting.py -q --basetemp .tmp\pytest-qf6-wide`:
  92 passed, 1 warning.
- `pytest -q --basetemp .tmp\pytest-qf6-full`:
  636 passed, 1 warning.
- `ruff check .`:
  passed.
- `git diff --check`:
  no whitespace errors; Windows LF/CRLF warnings only.

### QF-5c pipeline metrics qualification read path

### QF-5c pipeline metrics qualification read path

Implemented:

- `build_pipeline_health_summary()` now selects the active qualification
  snapshot through `schema/qualification_read.py` instead of reading
  `meddpicc_latest` directly.
- `get_metrics(metric_type="pipeline_health")` now reflects
  `qualification_latest` when present, with `meddpicc_latest` preserved as the
  legacy/sample fallback.
- `get_insights(query_type="pipeline_overview")` also reflects the active
  qualification snapshot because it uses the shared pipeline metric engine.
- Existing metric field names such as `avg_health_pct`, `health_bands`, and
  `health_coverage_pct` are intentionally preserved as compatibility aliases.

Design notes:

- This is intentionally scoped to the official pipeline-health metric surface.
- Direct Mongo aggregation insight paths such as `win_patterns`,
  `loss_patterns`, `compare_won_lost`, `gap_frequency`, and
  `industry_benchmark` still use MEDDPICC compatibility fields and should be
  migrated separately if they remain part of the v2 public surface.
- Reports, exports, Atlas chart specs, and analytics snapshots remain QF-6
  work.

Validation:

- `pytest tests/test_pipeline_metrics_summary.py tests/test_get_metrics.py tests/test_data_quality_reporting.py -q --basetemp .tmp\pytest-qf5c-targeted-rerun`:
  31 passed, 1 warning.
- `pytest tests/test_pipeline_metrics_summary.py tests/test_get_metrics.py tests/test_data_quality_reporting.py tests/test_dashboard_crosscheck.py tests/test_metric_contract.py tests/test_pipeline_timing.py tests/test_export_report.py -q --basetemp .tmp\pytest-qf5c-wide`:
  119 passed, 1 warning.
- `pytest -q --basetemp .tmp\pytest-qf5c-full`:
  633 passed, 1 warning.
- `ruff check .`:
  passed.

### QF-5b deal gaps and list views qualification read path

Implemented:

- Added `src/deal_intel/schema/qualification_read.py` as the shared
  deterministic read helper for selecting the active qualification snapshot.
- `build_deal_review()`, `build_deal_gaps_summary()`, and `list_deals` now use
  the same helper:
  - prefer `qualification_latest` when valid;
  - fall back to legacy `meddpicc_latest` for old/sample data.
- `get_deal_gaps` now returns active-framework qualification metadata:
  `qualification`, `qualification_framework`,
  `qualification_framework_display_name`, `qualification_source_field`,
  `qualification_health_pct`, `qualification_quality_pct`,
  `qualification_coverage_pct`, `qualification_filled_count`,
  `qualification_total_count`, and `qualification_gaps`.
- `list_deals` now surfaces the same generic qualification fields while
  preserving legacy-friendly aliases: `health_pct`, `filled_count`, and
  `gaps`.
- Custom-framework qualitative gaps are emitted as
  `qualification.<dimension>` / `qualification:<dimension>` instead of
  fabricating MEDDPICC fields.
- `attention:at_risk` messaging now names the active framework instead of
  hardcoding MEDDPICC.
- Gap actionability treats `qualification.*` qualitative gaps the same way as
  `meddpicc.*`: observation-only by default unless the gap is objective timing
  or data-quality evidence.

Design notes:

- MEDDPICC payload compatibility is intentionally preserved. Existing
  `meddpicc:*` gap IDs still appear for MEDDPICC data.
- This subtask does not migrate pipeline metrics, insights, reports, exports,
  Atlas chart specs, or analytics snapshots.
- The shared helper is the future read-path anchor for the remaining QF
  migration units.

Validation:

- `pytest tests/test_deal_gaps.py tests/test_data_quality_reporting.py tests/test_deal_review.py -q --basetemp .tmp\pytest-qf5b-targeted`:
  38 passed, 1 warning.
- `pytest tests/test_deal_gaps.py tests/test_get_deal_gaps.py tests/test_deal_review.py tests/test_data_quality_reporting.py tests/test_pipeline_timing.py tests/test_zero_config_sample_fixture.py tests/test_local_sample_backend.py -q --basetemp .tmp\pytest-qf5b-wide`:
  107 passed, 1 warning.
- `ruff check src/deal_intel/schema/deal_review.py src/deal_intel/schema/deal_gaps.py src/deal_intel/schema/qualification_read.py src/deal_intel/schema/gap_actionability.py src/deal_intel/tools/list_deals.py tests/test_deal_gaps.py tests/test_data_quality_reporting.py`:
  passed.

### QF-5a deal review qualification read path

Implemented:

- Updated deterministic `build_deal_review()` so it prefers canonical
  `qualification_latest` when present and falls back to legacy
  `meddpicc_latest` for old data.
- Added a top-level `qualification` summary to deal-review responses with the
  active framework key, display name, source field, health, quality, coverage,
  filled count, total count, and open gaps.
- Kept legacy compatibility aliases such as `legacy_health_pct`,
  `filled_meddpicc_count`, and `total_meddpicc_count` while adding generic
  `qualification_*` interpretation fields.
- Generalized scorecard, known signals, confirmed risks, and recommended
  questions to use custom framework dimension labels and metadata.
- For non-MEDDPICC frameworks, deal-review gap observations now use
  `qualification.<dimension>` fields instead of fabricating `meddpicc.*`
  fields.
- Extended qualification snapshots with safe dimension metadata so review
  output can preserve labels, suggested questions, CTA policy, and weighting.
- Updated data-quality health assessment so a valid `qualification_latest`
  counts as structured qualification evidence even when `meddpicc_latest` is
  empty.

Design notes:

- This is intentionally scoped to `get_deal_review` / `build_deal_review`.
  `get_deal_gaps`, `list_deals`, metrics, reports, and charts still need their
  own QF migration passes.
- Existing MEDDPICC review payloads remain compatible. The new generic fields
  are additive.
- Custom framework qualitative gaps remain observation-oriented unless an
  objective timing/data-quality gap is present. This preserves the current
  CTA-safety policy.

Validation:

- `pytest tests/test_deal_review.py tests/test_qualification_snapshot.py -q --basetemp .tmp\pytest-qf5a-targeted`:
  23 passed, 1 warning.
- `pytest tests/test_deal_review.py tests/test_cli_deal_review_smoke.py tests/test_zero_config_sample_fixture.py tests/test_deal_gaps.py tests/test_metric_contract.py tests/test_pipeline_metrics_summary.py tests/test_add_interaction.py tests/test_update_stage.py -q --basetemp .tmp\pytest-qf5a-wide`:
  107 passed, 1 warning.
- `pytest -q --basetemp .tmp\pytest-qf5a-full`:
  628 passed, 1 warning.
- `ruff check src/deal_intel/schema/deal_review.py src/deal_intel/schema/qualification.py src/deal_intel/schema/metrics.py tests/test_deal_review.py`:
  passed.
- `ruff check .`:
  passed.

### QF-4b interaction extraction generalization

Implemented:

- Connected `add_interaction` to the active qualification framework resolved
  from effective config.
- Embedded the active framework extraction contract into the interaction LLM
  prompt for non-MEDDPICC frameworks.
- Normalized LLM-produced `qualification` output through
  `normalize_qualification_extraction()` before storage.
- Stored confirmed custom-framework evidence in `interaction.qualification`.
- Stored outbound/internal/unconfirmed custom-framework evidence in
  `interaction.unconfirmed_qualification` without changing
  `qualification_latest`.
- Preserved legacy `interaction.meddpicc` extraction and
  `meddpicc_latest` compatibility while allowing non-MEDDPICC
  `qualification_latest` to use only `interaction.qualification`.
- Added preflight validation for invalid active framework config before any
  LLM call is made.
- Updated the interaction-analysis parser so a response containing
  `qualification` but no `meddpicc` is not mistaken for legacy MEDDPICC-only
  output.

Design notes:

- MEDDPICC remains the compatibility read path. When `active_framework` is
  `meddpicc`, `qualification_latest` still reads `interaction.meddpicc`.
- Non-MEDDPICC frameworks write and read `interaction.qualification`; MEDDPICC
  evidence is not force-mapped into unrelated frameworks.
- Unknown or invalid custom dimension output is dropped with structured
  warnings rather than contaminating the score engine.

Validation:

- `pytest tests/test_add_interaction.py tests/test_qualification_extraction.py tests/test_qualification_snapshot.py -q --basetemp .tmp\pytest-qf4b-targeted`:
  31 passed, 1 warning.
- `pytest tests/test_add_interaction.py tests/test_qualification_extraction.py tests/test_qualification_snapshot.py tests/test_qualification_framework.py tests/test_qualification_config.py tests/test_update_stage.py tests/test_tool_surfaces.py -q --basetemp .tmp\pytest-qf4b-wide`:
  123 passed, 1 warning.
- `pytest -q --basetemp .tmp\pytest-qf4b-full`:
  627 passed, 1 warning.
- `ruff check .`:
  passed.

### QF-4a generic qualification extraction contract

Implemented:

- Added `src/deal_intel/schema/qualification_extraction.py` as the pure
  framework-aware extraction contract layer.
- Added `build_qualification_extraction_contract()` and
  `render_qualification_extraction_prompt_block()` so future LLM prompts can be
  generated from the active qualification framework.
- Added `normalize_qualification_extraction()` to normalize LLM-like output
  into stored `interaction.qualification` evidence while dropping unsafe or
  invalid dimension data with structured warnings.
- Preserved `interaction.qualification` and `interaction.unconfirmed_qualification`
  through `normalize_interaction_record()`. This closes the storage/read-path
  gap between QF-3 snapshots and future QF-4 extraction.

Design notes:

- QF-4a does not yet change the `add_interaction` LLM prompt or write
  `interaction.qualification` at runtime.
- Missing dimensions stay missing rather than receiving a neutral score.
- Secret-like text is not echoed in normalized evidence or warnings.
- Invalid LLM output is handled at the boundary so
  `compute_qualification_latest()` receives only clean score evidence.

Validation:

- `pytest tests/test_qualification_extraction.py tests/test_qualification_snapshot.py tests/test_add_interaction.py -q --basetemp .tmp\pytest-qf4a-targeted`:
  29 passed, 1 warning.
- `pytest tests/test_qualification_extraction.py tests/test_qualification_snapshot.py tests/test_qualification_framework.py tests/test_qualification_config.py tests/test_add_interaction.py -q --basetemp .tmp\pytest-qf4a-wide`:
  80 passed, 1 warning.
- `pytest -q --basetemp .tmp\pytest-qf4a-full`:
  625 passed, 1 warning.
- `ruff check .`:
  passed.
- MCP registration smoke was not required because QF-4a adds no MCP tools.

### QF-2c immutable qualification presets

Implemented:

- Protected built-in qualification framework keys from user-config overwrite.
- `update_qualification_framework(template_key=<preset>)` now activates the
  preset without storing a mutable copy under `qualification.frameworks`.
- Added `copy_as_key` and `copy_display_name` to
  `update_qualification_framework` so users can clone a preset before editing.
- `framework_json` payloads that reuse built-in keys now fail with
  `PRESET_FRAMEWORK_IMMUTABLE`.
- `list_qualification_frameworks` marks stored preset-key overrides as ignored.
- `delete_qualification_framework` can remove an ignored stored preset override
  while preserving the active built-in preset.
- Updated defaults comments to describe `meddpicc.weights` as legacy
  compatibility config rather than the v2 framework customization path.

Design notes:

- Built-in templates are recoverable presets. Customization should create a new
  framework key from a preset copy.
- `qualification_latest` resolves active built-in keys from bundled templates
  first. User-configured frameworks that reuse preset keys are ignored.
- Legacy `meddpicc_latest` still honors the legacy `meddpicc.weights` and
  `meddpicc.gap_threshold` path until that compatibility surface is retired.

Validation:

- `pytest tests/test_qualification_config.py tests/test_tool_surfaces.py tests/test_mcpb_manifest.py --basetemp .tmp\pytest-qf2c-targeted -q`:
  65 passed, 1 warning.
- `pytest -q --basetemp .tmp\pytest-qf2c-full`:
  615 passed, 1 warning.
- `ruff check .`:
  passed.

### QF-2b qualification framework manager tools

Implemented:

- Added safe framework lifecycle helpers in `src/deal_intel/qualification_config.py`:
  - list built-in and user-configured frameworks;
  - switch `qualification.active_framework`;
  - delete stored custom frameworks.
- Added MCP tools:
  - `list_qualification_frameworks`
  - `set_active_qualification_framework`
  - `delete_qualification_framework`
- Added the tools to the standard/developer surfaces and MCPB manifest while
  keeping the sample surface unchanged.
- Updated current tool counts to `sample=23`, `standard=33`,
  `developer=36`.

Design notes:

- Framework manager writes are dry-run-first and require
  `confirmed_by_user=true`.
- Built-in templates cannot be deleted.
- Active frameworks cannot be deleted until another framework is selected.
- These tools only update non-secret user config. They do not call LLMs, touch
  MongoDB, update embeddings, or recompute historical deals.

Validation:

- `pytest tests/test_qualification_config.py tests/test_tool_surfaces.py tests/test_mcpb_manifest.py tests/test_config_doctor.py tests/test_sample_data.py --basetemp .tmp\pytest-qf2b-targeted -q`:
  82 passed, 1 warning.
- `pytest -q --basetemp .tmp\pytest-qf2b-full`:
  611 passed, 1 warning.
- `ruff check .`:
  passed.
- Tool surface smoke:
  `sample=23`, `standard=33`, `developer=36`, registered contracts `36`.

### QF-3b persist canonical qualification snapshot

Implemented:

- Added `resolve_active_qualification_framework(cfg)` so write paths can resolve
  the active framework from effective config without reading files directly.
- Added `src/deal_intel/tools/qualification_snapshot.py` as the shared write-path
  helper for rebuilding legacy `meddpicc_latest` and canonical
  `qualification_latest` together.
- `create_deal` now initializes `qualification_latest: {}`.
- `add_interaction` now persists and returns `qualification_latest`.
- `update_stage` now recomputes `qualification_latest` when stage changes
  affect gap context.
- MongoDB deals schema now documents optional `qualification_latest`.

Design notes:

- Existing BI/report/review read paths continue to use `meddpicc_latest`.
- Non-MEDDPICC frameworks consume `interaction.qualification` evidence only.
  MEDDPICC evidence is not force-mapped into unrelated custom frameworks.

Validation:

- `pytest tests/test_qualification_config.py tests/test_qualification_snapshot.py tests/test_add_interaction.py tests/test_update_stage.py tests/test_pipeline_timing.py tests/test_mongo_contracts.py --basetemp .tmp\pytest-qf4-targeted -q`:
  102 passed, 1 warning.
- `pytest -q --basetemp .tmp\pytest-qf3b-full`:
  602 passed, 1 warning.
- `ruff check .`:
  passed.

### QF-3 generic qualification snapshot engine

Implemented:

- Added `src/deal_intel/schema/qualification.py` with the pure
  `compute_qualification_latest(...)` engine.
- Added `src/deal_intel/schema/stages.py` so qualification framework validation
  and MEDDPICC compatibility can share stage constants without circular imports.
- Reworked `compute_meddpicc_latest(...)` into a compatibility wrapper over the
  generic engine while preserving the existing `meddpicc_latest` output shape.
- Added `compute_meddpicc_qualification_latest(...)` for future canonical
  `qualification_latest` consumers.
- Added `tests/test_qualification_snapshot.py` covering:
  - legacy MEDDPICC shape/math compatibility;
  - quality vs coverage vs uncertainty separation;
  - generic `qualification` evidence fields;
  - stage-aware gap rules and won-stage gap suppression;
  - disabled dimensions;
  - no mutation of framework templates.

Validation:

- `pytest tests/test_qualification_snapshot.py tests/test_qualification_framework.py tests/test_add_interaction.py tests/test_analytics_snapshots.py --basetemp .tmp\pytest-qf3-targeted -q`:
  49 passed, 1 warning.
- `pytest tests/test_metric_contract.py tests/test_pipeline_metrics_summary.py tests/test_deal_review.py tests/test_deal_gaps.py tests/test_get_metrics.py tests/test_export_report.py tests/test_export_data.py tests/test_weekly_pipeline_report.py tests/test_weekly_pipeline_markdown.py --basetemp .tmp\pytest-qf3-regression -q`:
  106 passed, 1 warning.
- `pytest -q --basetemp .tmp\pytest-qf3-full`:
  591 passed, 1 warning.
- `ruff check src/deal_intel/schema/qualification.py src/deal_intel/schema/meddpicc.py src/deal_intel/schema/qualification_framework.py src/deal_intel/schema/stages.py tests/test_qualification_snapshot.py`:
  passed.
- `ruff check .`:
  passed.

Notes:

- This unit intentionally does not write `qualification_latest` into deals yet.
  Existing read/report/metric paths still consume `meddpicc_latest`.
- The next QF step should decide whether to persist `qualification_latest` in
  write paths first or adapt deterministic read paths first.

### QF-2 qualification framework config tools

Implemented:

- Added `src/deal_intel/qualification_config.py` as the shared helper for
  framework template listing, static validation, and dry-run-first config
  writes.
- Added three MCP tools:
  - `get_qualification_templates`
  - `validate_qualification_framework`
  - `update_qualification_framework`
- Added the tools to the standard/developer surfaces and MCPB manifest while
  keeping the sample surface unchanged.
- Added targeted tests for template listing, validation, dry-run/apply config
  writes, confirmation gating, backup creation, secret rejection, invalid
  existing config handling, MCP wrapper behavior, tool surfaces, and MCPB
  manifest alignment.
- Updated documented tool counts to `sample=23`, `standard=30`,
  `developer=33`.

Validation:

- `pytest tests/test_qualification_framework.py tests/test_qualification_config.py tests/test_tool_surfaces.py tests/test_mcpb_manifest.py --basetemp .pytest-qf2 -q`:
  70 passed.
- `ruff check src/deal_intel/qualification_config.py src/deal_intel/schema/qualification_framework.py src/deal_intel/mcp_server.py src/deal_intel/tool_surfaces.py tests/test_qualification_config.py tests/test_qualification_framework.py tests/test_tool_surfaces.py tests/test_mcpb_manifest.py`:
  passed.

Notes:

- This is the non-LLM safe path. `suggest_qualification_framework` is deferred
  to QF-2b so LLM cost, prompt quality, and safety can be tested separately.
- The new update tool writes only validated non-secret config and does not
  recompute historical deal scores.
- A plain pytest run hit the known Windows temp permission issue under
  `%LOCALAPPDATA%\Temp\pytest-of-<user>`; rerunning with a workspace
  basetemp validated the tests themselves.

### QF-1 framework contract and validator

Implemented:

- Added `src/deal_intel/schema/qualification_framework.py` with the v2
  qualification framework contract.
- Added validated built-in templates: `meddpicc`, `simple_b2b`, `pilot_poc`,
  `enterprise_procurement`, and `product_led_sales`.
- Added static validation for framework keys, dimension keys, required labels
  and extraction hints, positive weights, fixed v2 score scale `0-5`, minimum
  enabled dimension count, CTA policy, secret-shaped strings, invalid stage
  rules, and unscorable extraction hints.
- Added `tests/test_qualification_framework.py` covering the validator failure
  modes and confirming the MEDDPICC template matches the v1 default weights.

Validation:

- `pytest tests/test_qualification_framework.py -q`: 24 passed.
- `ruff check src/deal_intel/schema/qualification_framework.py tests/test_qualification_framework.py`:
  passed.

Notes:

- This is still runtime-neutral. No MCP tool, storage schema, extraction prompt,
  metric, report, or existing `meddpicc_latest` behavior changed.
- The next recommended unit is QF-2: template/validator MCP tools and safe
  config update workflow.

### Qualification framework v2 execution plan

Implemented:

- Added [qualification-framework-v2.md](qualification-framework-v2.md) as the
  execution plan for MEDDPICC abstraction / qualification framework v2.
- Split the work into QF-0 through QF-9 units with design, implementation,
  verification gates, and corner-case checks.
- Included the revised UX direction that framework customization needs
  templates and wizard-style assistance, not only schema constraints.
- Linked the plan from [backlog.md](backlog.md).

Notes:

- This is a planning/documentation change only. No runtime framework behavior,
  MCP tool contract, or storage schema changed.
- The next recommended implementation unit is QF-1: framework contract,
  built-in templates, and static validator.

### Architecture developer map kickoff

Implemented:

- Started the post-v1 architecture-map expansion in
  [architecture.md](architecture.md).
- Replaced the stale hardcoded MCP tool count with source-of-truth pointers:
  `src/deal_intel/mcp_server.py` for runtime registration and
  `src/deal_intel/tool_surfaces.py` for profile/tool-surface contracts.
- Added a user-intent tool namespace map covering Config/Diagnostics, Intake,
  Lifecycle/CRUD, Read/Query, Export/Artifacts, Customer Themes,
  Search/Strategy, User Memory, and Sample/Admin.
- Recorded the v2 refactor ordering decision: design the future namespace map
  first, implement qualification-framework abstraction before broad tool
  renames, then consolidate/rename tools in a compatibility-aware pass.

Notes:

- This is a documentation/developer-map change only. No runtime tool names or
  contracts changed.

### Tool catalog for truncated host discovery

Implemented:

- Added the read-only MCP tool `get_tool_catalog(include_hidden=false)`.
- The tool returns the resolved surface, visible tool count, registered tool
  count, category grouping, per-tool visibility metadata, and guidance for
  common tool-selection confusion.
- This addresses host-app behavior where a tool search may show only the top
  few matching tools even though the MCP server loaded the full surface.
- Bumped package and MCPB manifest version to `0.1.14`.
- Tool-surface counts were updated for that release; current counts are
  tracked in [baseline.md](baseline.md).

Notes:

- This is a host-discovery UX fix, not evidence that v0.1.13 loaded only five
  tools. The host search UI can truncate results independently of the MCP
  server's actual `list_tools()` result.

Validation:

- `pytest -q -p no:cacheprovider --basetemp .pytest-tool-catalog-full`: 546 passed.
- `ruff check .`: passed.
- `mcpb validate mcpb/manifest.json`: passed.

### Full-profile demo sample dataset

Implemented:

- Added a generated 22-deal fictional full-profile sample dataset as a bundled
  package resource.
- Reworked `create_sample_data` to load the public sample from package
  resources instead of constructing a smaller inline Python fixture.
- Kept the existing safety model: `full` mode starts empty for new users,
  sample seeding is opt-in, writes target the demo database, dry-run remains
  the default, and actual writes still require explicit confirmation.
- Removed raw notes, raw interaction content, contacts, embeddings, legacy KRW
  shadow fields, and internal metadata history from the bundled sample payload.

Notes:

- This dataset is for Atlas-backed demos and public screenshots. It is separate
  from the zero-config `local_sample` fixture.
- This change is packaged as `0.1.15`.

Validation:

- `pytest tests/test_sample_data.py tests/test_mcpb_manifest.py -q
  -p no:cacheprovider --basetemp .pytest-full-sample-targeted`: `16 passed`,
  `1` third-party deprecation warning.
- `ruff check src/deal_intel/tools/sample_dataset.py tests/test_sample_data.py
  tests/test_mcpb_manifest.py`: passed.
- `mcpb validate mcpb/manifest.json`: passed.
- `pytest -q -p no:cacheprovider --basetemp .pytest-full-sample-full`:
  `547 passed`, `1` third-party
  deprecation warning.
- `ruff check .`: passed.
- `git diff --check`: passed.
- `pip wheel . --no-deps --no-build-isolation --no-cache-dir --wheel-dir
  .tmp-wheel`: passed.
- Wheel inspection confirmed
  `deal_intel/resources/sample_datasets/weekly_pipeline_demo.v2.json` is
  included.

### Post-v1 roadmap finalized

Implemented:

- Replaced the old v1-to-v2 backlog order with a post-v1 roadmap centered on
  product depth and extensibility before no-clone packaging.
- Set the post-v1 priority order:
  1. public v1 release and feedback capture;
  2. developer-focused `docs/architecture.md` expansion;
  3. qualification-framework abstraction with MEDDPICC as the default;
  4. tool namespace and customer-theme workflow cleanup;
  5. MongoDB Pro path;
  6. report quality v2;
  7. deal review quality v2;
  8. broader usage/cost tracking;
  9. full npx bootstrapper.
- Updated the distribution plan so `npx` is framed as a future full
  bootstrapper, not a thin wrapper or immediate post-v1 priority.

Rationale:

- The highest post-v1 risk is hardcoded product assumptions becoming expensive
  to undo, especially qualification-framework assumptions.
- Architecture documentation should be expanded before large v2 changes so AI
  agents and human contributors can find the right modules, contracts, tests,
  and coupling points quickly.
- Packaging convenience remains important, but it should not outrank framework
  abstraction, tool-surface cleanup, MongoDB Pro validation, or report/review
  quality.

### v1 public README positioning and English install guide

Implemented:

- Revised README positioning for public audiences such as r/mcp, HN, and
  MongoDB community readers.
- Reframed the project as a self-owned deal memory layer and lightweight first
  CRM-like layer for solo founders and early teams, rather than a generic sales
  SaaS or mature Salesforce replacement.
- Added explicit "What it does" and "What it is not" sections to make scope and
  limitations clear.
- Moved MEDDPICC from the first-line pitch into the internal deal-health
  explanation.
- Added [AI_FULL_INSTALL_GUIDE.md](../AI_FULL_INSTALL_GUIDE.md), an English
  full-mode install guide for AI-assisted setup.
- Updated [AI_START_HERE.md](../AI_START_HERE.md) to prefer the English guide
  while keeping the Korean guide linked.
- Added MIT customization guidance to README, AI agent setup docs, and the
  public demo script: forks/custom workflows are welcome, but license and
  attribution notices should be preserved and meaningful local changes should be
  recorded for future agents.

Validation:

- Public-surface scan found no personal path/name exposure. Secret-like matches
  were limited to `.env.example` placeholders and redaction tests.

### v1 polish wrap-up: install guide and public demo copy

Implemented:

- Rewrote [AI_FULL_INSTALL_GUIDE.ko.md](../AI_FULL_INSTALL_GUIDE.ko.md) as a
  clean UTF-8 Korean full-mode setup guide for AI-assisted non-developer
  installation.
- Added platform/sandbox guidance for Windows, macOS, and AI-host DNS/network
  limitations.
- Added a short copy-paste public/community post draft to
  [public-demo-script.md](public-demo-script.md).

Validation:

- Public-surface scan found no personal path/name exposure. Secret-like matches
  were limited to `.env.example` placeholders and redaction tests.
- Tool-surface/MCPB contract tests:
  `pytest tests/test_tool_surfaces.py tests/test_mcpb_manifest.py -q
  --basetemp=.tmp\pytest-v1-final-packaging`: `30 passed, 1 warning`.
- MCPB packaging:
  - `mcpb validate manifest.json`: passed.
  - `mcpb pack . deal-intel-mcp-0.1.13.mcpb`: created package.
  - `mcpb info deal-intel-mcp-0.1.13.mcpb`: package inspected, unsigned
    warning only.

### v1 final readiness run

Result: pass.

Validation:

- Launch hygiene scan:
  - Searched for personal paths/names and obvious committed secrets.
  - Findings were limited to placeholder examples and secret-redaction tests.
- Full regression:
  `pytest -q --basetemp=.tmp\pytest-v1-final-readiness`:
  `544 passed, 1 warning`.
- Ruff:
  `ruff check .`: `All checks passed`.
- Natural question smoke:
  `DEAL_INTEL_STORAGE_BACKEND=local_sample smoke-natural-questions
  --as-of 2026-06-10 --output-dir .tmp\v1-final-natural-local`:
  `OK: True`, `12` questions passed, no sensitive failures, no blocked
  questions.
- Deal review audit:
  `DEAL_INTEL_STORAGE_BACKEND=local_sample smoke-deal-review-audit
  --as-of 2026-06-10 --limit 50`: quality rules passed, sensitive field check
  passed, `12` sample deals reviewed.
- MCP/tool contract:
  `pytest tests/test_tool_surfaces.py tests/test_mcpb_manifest.py -q
  --basetemp=.tmp\pytest-v1-final-surface`: `30 passed, 1 warning`.
- MCPB manifest:
  `mcpb validate mcpb\manifest.json`: manifest schema validation passed.
- Config doctor:
  `config doctor --offline --json`: passed for `full`/`mongo`, standard
  surface, `26` tools.
  Live `config doctor --json`: passed after running outside the sandbox because
  sandbox DNS blocked Atlas resolution.
- Report/dashboard cross-check:
  `crosscheck-weekly-dashboard --as-of 2026-06-10 --output-dir
  .tmp\v1-final-report`: passed; `get_metrics`, report CSV/Markdown, and Atlas
  chart pipelines matched with no mismatches.

Notes:

- The sandboxed live config check failed on DNS resolution, but the same command
  passed outside the sandbox. This is an environment/network constraint, not a
  code/config failure.
- Relative report output directories are intentionally scoped under
  `~/.deal-intel`, which avoids the previous repo-local `outputs/reports`
  permission issue.

### v1 polish: tool-selection guidance and public demo script

Implemented:

- Tightened MCP tool descriptions for high-traffic adjacent tools:
  - `get_deal_review` as the default one-deal status/risk/uncertainty review;
  - `analyze_deal` as optional LLM-generated BD strategy that may persist
    `bd_strategy`;
  - `export_report` as manager/team meeting reports with a host-app polish
    prompt;
  - `export_data` as Excel/CSV ledgers and record exports;
  - customer-theme tools split as ranking, breakdown, and evidence.
- Clarified `backfill-customer-themes` as a maintenance/migration command, not
  normal daily intake, and documented that large historical runs may incur
  server-side LLM cost.
- Added [public-demo-script.md](public-demo-script.md), a five-question demo
  path for public/community posts and first-look walkthroughs.
- Linked the public demo script from README and AI_START_HERE.
- Updated MVP readiness notes now that usage visibility and report/data-export
  polish are implemented.

Validation:

- Targeted:
  `pytest tests/test_tool_surfaces.py tests/test_mcpb_manifest.py -q
  --basetemp=.tmp\pytest-tool-guidance`: `30 passed, 1 warning`.
- Targeted Ruff:
  `ruff check src\deal_intel\mcp_server.py src\deal_intel\cli.py`:
  `All checks passed`.

### v1 polish: split spreadsheet data export from human reports

Implemented:

- Added `export_data`, a deterministic CSV/Excel export layer separate from
  human-facing `export_report`.
- Added `deal_intel.reports.data_export.build_data_export` with three datasets:
  `open_deals`, `all_deals`, and `closed_deals`.
- Registered `export_data` in MCP and tool-surface contracts for sample,
  standard, and developer surfaces.
- Updated reporting architecture docs to treat:
  - `export_data` as spreadsheet/ledger data extraction;
  - `export_report` as the human report/document layer;
  - deterministic metrics/data packs as the source of truth for any
    host-assisted report prose.
- Updated baseline, query audit, and tool-surface docs with the new contract.
- Added report-facing briefing fields to `weekly_pipeline` Markdown/export
  output:
  - `briefing`
  - `briefing_sections`
  - `host_report_prompt`
- Added a meeting agenda section to weekly pipeline Markdown.
- Documented that host-app prose polishing may improve readability, but
  deterministic metrics, company names, stages, amounts, health scores, and
  warning codes remain the source of truth.

Validation:

- Targeted:
  `pytest tests/test_export_data.py tests/test_tool_surfaces.py
  tests/test_mcpb_manifest.py tests/test_config_doctor.py
  tests/test_cli_config_profiles.py tests/test_sample_data.py -q
  --basetemp=.tmp\pytest-export-data-expanded`: `61 passed, 1 warning`.
- Report regression:
  `pytest tests/test_export_report.py tests/test_weekly_pipeline_report.py
  tests/test_weekly_pipeline_markdown.py -q
  --basetemp=.tmp\pytest-report-regression-after-export-data`:
  `29 passed, 1 warning`.
- Full regression:
  `pytest -q --basetemp=.tmp\pytest-export-data-full`:
  `544 passed, 1 warning`.
- Ruff:
  `ruff check .`: `All checks passed`.
- Local sample smoke:
  `export_data(dataset="open_deals", as_of="2026-06-10")` with an explicit
  workspace output directory generated a CSV successfully (`row_count=8`).
- Report host-prompt regression:
  `pytest tests/test_weekly_pipeline_markdown.py tests/test_export_report.py -q
  --basetemp=.tmp\pytest-report-host-prompt-rerun`: `20 passed, 1 warning`.
- Targeted report Ruff:
  `ruff check src\deal_intel\reports\markdown_summary.py
  src\deal_intel\tools\export_report.py tests\test_weekly_pipeline_markdown.py
  tests\test_export_report.py`: `All checks passed`.
- Full regression after report-host-prompt polish:
  `pytest -q --basetemp=.tmp\pytest-report-export-full`:
  `544 passed, 1 warning`.
- Full Ruff after report-host-prompt polish:
  `ruff check .`: `All checks passed`.
- Local sample report smoke:
  `export_report(report_type="weekly_pipeline", as_of="2026-06-10",
  language="ko")` generated CSV and Markdown successfully (`row_count=8`) and
  returned `briefing` plus `host_report_prompt`.

Note:

- A sandbox-only smoke using a relative `.tmp/...` output path failed because
  relative output paths are intentionally scoped under `~/.deal-intel/`, and
  this Codex sandbox cannot write to the user home directory. Re-running with a
  workspace absolute path passed.

Open follow-up:

- `export_report` still writes a compatibility CSV artifact. The human report
  layer now exposes a host-app polish prompt, but a future unit may still add a
  DOCX/PDF writer if file-native executive reports become important.

## Previous Update - 2026-06-14

### v1 polish: weekly pipeline Markdown narrative

Implemented:

- Reworked `weekly_pipeline` Markdown from a raw section dump into a meeting
  narrative:
  - executive summary;
  - core KPI table;
  - key deal watchlist;
  - stage breakdown;
  - issues to watch, split into objective action items and judgment-sensitive
    gap observations;
  - next-week action flow;
  - customer evidence and data-quality appendices.
- Kept the CSV/report row contract unchanged. Markdown now owns presentation
  and deterministic narrative only; row builders and metric modules remain the
  source of truth for business semantics.
- Changed Markdown artifact writes to `utf-8-sig` so generated `.md` reports
  open more reliably in Windows desktop apps.
- Updated `docs/reports.md` and `docs/architecture.md` to record the narrative
  responsibility boundary.

Validation:

- Targeted:
  `pytest tests/test_weekly_pipeline_markdown.py tests/test_export_report.py -q
  --basetemp=.tmp\pytest-report-polish`: `20 passed, 1 warning`.
- Markdown BOM fix:
  `pytest tests/test_export_report.py tests/test_weekly_pipeline_markdown.py -q
  --basetemp=.tmp\pytest-markdown-bom`: `20 passed, 1 warning`.
- Full regression:
  `pytest -q --basetemp=.tmp\pytest-report-narrative-full`: `538 passed,
  1 warning`.
- Ruff:
  `ruff check .`: `All checks passed`.

### Architecture documentation discipline

Implemented:

- Added a concrete reporting data-pipeline section to `docs/architecture.md`.
- Documented the responsibilities of `export_report`, `weekly_pipeline`,
  `markdown_summary`, `csv_export`, `markdown_export`, `pipeline_trend`,
  Atlas chart rendering, and dashboard cross-checking.
- Clarified that `markdown_summary` renders human-facing Markdown and computes
  Markdown-level summary metrics from report rows, while BI-wide metric
  semantics should stay in `schema.metrics`, `schema.pipeline_metrics`, report
  row builders, or trend calculators.
- Added an AGENTS/CLAUDE working-loop rule: changes to data pipelines,
  calculators, report/export flows, storage read paths, MCP orchestration, or
  module responsibility boundaries must update `docs/architecture.md`.

Decision:

- Promoted the architecture-documentation habit into the reusable local Codex
  skill `architecture-map` and linked it from AGENTS/CLAUDE.

### v1 polish: report language setting

Implemented:

- Added `reporting.language` with supported values `en` and `ko`.
- `weekly_pipeline` Markdown now localizes report headings, KPI labels, stage
  labels, health bands, attention reasons, objective actions, gap
  actionability, warning labels, and source labels.
- `pipeline_trend` Markdown now localizes its title, KPI table labels, and
  stage-change section labels.
- `export_report` returns `language` and validates invalid language config
  before storage reads.
- `update_config` can now preview/apply `reporting_language` so Claude/Codex
  App users can switch report language without hand-editing config files.

Validation:

- Targeted:
  `pytest tests/test_weekly_pipeline_markdown.py tests/test_export_report.py
  tests/test_config_writer.py tests/test_config_doctor.py -q -p
  no:cacheprovider --basetemp .tmp\pytest-report-language`: `47 passed,
  1 warning`.
- Ruff targeted report/config files: `All checks passed`.

### v1 readiness gate rerun

Validation:

- Full regression:
  `pytest -q -p no:cacheprovider --basetemp .tmp\pytest-v1-readiness`:
  `533 passed, 1 warning`.
- Ruff:
  `ruff check .`: `All checks passed`.
- Config doctor:
  `config doctor --offline`: `OK`, profile `full`, storage `mongo`, tool
  surface `standard`, `25` exposed tools, storage ping skipped as expected.
- Full profile smoke:
  `smoke-profile --profile full --offline`: `OK`; no writes, no LLM
  completions, no embeddings, no Atlas admin calls.
- Sample profile smoke:
  `DEAL_INTEL_STORAGE_BACKEND=local_sample smoke-profile --profile sample`:
  `OK`, `21` exposed tools.
- Natural-question smoke:
  `DEAL_INTEL_STORAGE_BACKEND=local_sample smoke-natural-questions --as-of
  2026-06-10 --output-dir .tmp\v1-readiness-natural`: `OK`, `12/12` pass,
  no sensitive failures, no blocked questions.
- Report export default-path smoke:
  local-sample `export_report(report_type="weekly_pipeline", as_of="2026-06-10")`
  succeeded with `USERPROFILE` pointed at `.tmp`; output resolved under
  `.tmp\.deal-intel\reports`, confirming the user-home default path policy.
- MCPB manifest:
  `mcpb validate mcpb\manifest.json`: manifest schema validation passes.
- Hygiene scan:
  no tracked personal path / stale tool-count matches. Expected placeholder
  matches remain only in `.env.example`, install docs, and secret-redaction
  tests.

### v1 polish: README / AI start scan

Implemented:

- Scanned `README.md` and `AI_START_HERE.md` for stale tool counts, personal
  local paths, old environment names, and sample/full guidance drift.
- Clarified that users should clone/download the repository and run install
  commands from the repository root.
- Added an explicit `python -m deal_intel.cli ...` fallback when the
  `deal-intel` console script is not on PATH.
- Added the missing install step to `AI_START_HERE.md` for agents helping a
  fresh user.

Validation:

- Targeted:
  `pytest tests/test_tool_surfaces.py tests/test_mcpb_manifest.py -q -p
  no:cacheprovider --basetemp .tmp\pytest-readme-ai-scan`:
  `30 passed, 1 warning`.
- Ruff:
  `ruff check .`: `All checks passed`.
- Hygiene scan:
  no README/AI_START matches for personal local paths, old environment names,
  or stale tool-count phrasing.

### v1 polish: output path hardening

Implemented:

- Hardened report output path resolution so relative `output_dir` values are
  scoped under `~/.deal-intel/` instead of the current working directory.
- Preserved absolute paths and `~` paths as explicit user choices.
- Mapped the legacy relative `outputs/reports` value to
  `~/.deal-intel/reports` to avoid MCPB/host-app write failures.
- Moved the default natural-question smoke output directory from repo-local
  `outputs/smoke/...` to `~/.deal-intel/smoke/...`.
- Updated report docs to explain relative-path scoping.
- Aligned report export polish details:
  - `export_report` docs now mention both `weekly_pipeline` and
    `pipeline_trend`.
  - direct CSV export expands `~` like Markdown export.
  - output directory strings with control characters fail preflight.

Validation:

- Targeted:
  `pytest tests/test_export_report.py tests/test_cli_deal_review_smoke.py -q
  -p no:cacheprovider --basetemp .tmp\pytest-output-paths`:
  `24 passed, 1 warning`.
- Targeted report polish:
  `pytest tests/test_export_report.py tests/test_csv_export.py
  tests/test_cli_deal_review_smoke.py -q -p no:cacheprovider --basetemp
  .tmp\pytest-report-polish`: `31 passed, 1 warning`.
- Full regression:
  `pytest -q -p no:cacheprovider --basetemp .tmp\pytest-report-polish-full`:
  `533 passed, 1 warning`.
- Ruff:
  `ruff check .`: `All checks passed`.

### v1 polish: tool selection and usage visibility

Implemented:

- Clarified high-traffic MCP tool descriptions so host AIs can choose between
  adjacent tools more reliably.
- Repositioned `get_deal_review` as the default LLM-free one-deal review tool.
- Repositioned `analyze_deal` as optional server-side LLM strategy generation
  that may persist `bd_strategy`.
- Added persisted LLM usage metadata for new `add_interaction` calls and
  `analyze_deal` strategy generation.
- Added `get_usage` MCP tool and `deal-intel usage` CLI command.
- `get_usage` summarizes usage by provider, tool, and operation, with
  date-window filters.
- Cost estimates are conservative: ChatGPT OAuth is treated as subscription
  backed with zero incremental API estimate; API-provider costs are calculated
  only when `usage.pricing` is configured.
- Updated tool-surface counts to `sample=21`, `standard=25`,
  `developer=28`.

Validation:

- Targeted:
  `pytest tests/test_usage.py tests/test_add_interaction.py
  tests/test_local_sample_backend.py tests/test_tool_surfaces.py
  tests/test_mcpb_manifest.py -q -p no:cacheprovider --basetemp
  .tmp\pytest-p2-targeted`: `64 passed, 1 warning`.
- Full regression:
  `pytest -q -p no:cacheprovider --basetemp .tmp\pytest-p2-full`:
  `528 passed, 1 warning`.
- Ruff:
  `ruff check .`: `All checks passed`.
- CLI smoke:
  `DEAL_INTEL_STORAGE_BACKEND=local_sample deal-intel usage --json`: `ok=true`
  with `no_persisted_usage_metadata_found`, as expected for bundled sample data
  before any new server-side LLM usage is written.
- Hygiene scan:
  no tracked personal path / stale tool-count matches found outside generated
  output folders.

### Public launch hygiene stream

Documented:

- Created a reusable Codex `launch-hygiene` skill for public-release hygiene
  audits.
- Added `Public Launch Hygiene` to `docs/backlog.md`.
- Added a public launch hygiene gate to `docs/mvp-readiness.md`.

Decision:

- Treat launch hygiene as a v1 release gate, not as packaging polish.
- Run it before v1.0 tagging, package handoff, MCPB rebuilds, or major install
  guide changes.
- Use explicit scans for personal/local leakage, secret/config handling,
  fresh-clone reproducibility, doc/code alignment, and generated artifact
  hygiene.
- Avoid reintroducing exact private local identifiers into tracked docs. Use
  placeholder scan terms and keep concrete local values in ignored local config
  only.

### MCP tool design roadmap triage

Documented:

- Added `MCP Tool Design Cleanup` to `docs/backlog.md`.
- Updated `docs/mvp-readiness.md` so v1 polish focuses on tool-description and
  first-run guidance, not disruptive tool renaming.

Decision:

- Treat tool-description guidance as v1 polish because it directly reduces AI
  host confusion when choosing between adjacent tools.
- Treat customer-theme consolidation as post-v1. It is a real design cleanup,
  but current natural-question smoke already passes and the workflow should be
  shaped with real host usage traces.
- Keep `update_deal` as-is for v1 while it remains one coherent confirmed
  metadata-correction workflow. Revisit only if unrelated decision types enter
  the tool.
- Defer response verbosity controls and broad tool namespace changes to
  post-v2 or later. They are useful only after real traces show token pressure
  or a breaking-version cleanup is already planned.

### Cost-aware host LLM boundary

Documented:

- Added the host-app vs server-side LLM responsibility split to
  `docs/architecture.md`.
- Added a user-facing README note that read-only BI/review/reporting tools are
  designed to be LLM-free and should let Claude/Codex/ChatGPT perform the final
  explanation layer.
- Added a backlog stream for LLM cost and host-app delegation.

Decision:

- Use the host app LLM for explanation, synthesis, confirmation questions,
  setup guidance, and one-off wording from deterministic MCP outputs.
- Keep server-side LLM usage for persistent structured data creation:
  `add_interaction`, theme extraction/backfill, and explicit strategy
  generation.
- Future tools that call the server-side LLM must document cost/latency and
  provide lower-cost alternatives where useful.
- Do not merge the two current `add_interaction` LLM calls yet. GPT-5.4 mini
  cost is low enough at the expected one-person/small-team BD usage level that
  the quality and parsing risk is not justified. A busy day with roughly 20
  emails and 5 meetings is expected to stay around a few hundred KRW; ordinary
  usage should usually be lower, with monthly spend likely in the
  low-thousands KRW range at this scale.
- Keep batch/deferred interaction processing as long-term evidence of possible
  compute optimization, not a near-term v1 task.

Candidate implementation:

- Keep `get_deal_review` as the default LLM-free deal review surface and treat
  `analyze_deal` as an explicit optional strategy-generation tool.
- Add a v1 polish usage tool for LLM call counts, token usage, and estimated
  provider spend from the MCP surface.
- Keep customer-theme backfill as an explicit maintenance/admin flow and
  document that it may incur LLM cost over historical meetings.

### MCP safe config update tool

Implemented:

- Added MCP `update_config` for Claude/Codex App users who need to change safe
  non-secret settings without manually editing `~/.deal-intel/config.yaml`.
- Supported allowlisted fields:
  `llm.provider`, `llm.chatgpt_oauth_model`, `llm.openai_api_model`,
  `reporting.output_dir`, `reporting.timezone`, and `tools.surface`.
- Kept the tool dry-run-first. Actual writes require
  `confirmed_by_user=true`.
- Back up existing user config before writing.
- Reject MongoDB URIs, API-key-shaped strings, multi-line path values, invalid
  timezones, and invalid tool surfaces.
- Keep `config_doctor` and `update_config` visible even when tool-surface
  config is invalid, so setup can be diagnosed and repaired from the MCP
  client.
- Updated MCPB/package metadata to `0.1.13` and the tool-surface counts to:
  `sample=20`, `standard=24`, `developer=27`.

Reason:

- Claude Desktop full-mode smoke showed that `config_doctor` could diagnose
  setup, but the MCP surface had no way to change safe runtime settings such as
  report output path or model/provider selection. That forced non-developer
  users back into manual YAML editing.

Validation:

- Targeted regression:
  `pytest tests/test_config_writer.py tests/test_config_doctor.py
  tests/test_tool_surfaces.py tests/test_mcpb_manifest.py
  tests/test_sample_data.py tests/test_export_report.py -q`:
  `71 passed, 1 warning`.
- Full regression:
  `pytest -q`: `522 passed, 1 warning`.
- `ruff check .`: passed.
- `git diff --check`: no whitespace errors; only expected Windows line-ending
  conversion warnings.

### Report output default and MCPB secret-source note

Implemented:

- Changed the default report artifact directory from repo-local
  `outputs/reports` to user-home `~/.deal-intel/reports`.
- Updated editable and packaged defaults:
  `config/defaults.yaml` and `src/deal_intel/resources/defaults.yaml`.
- Kept explicit `output_dir` behavior unchanged.
- Documented the developer-facing runtime secret model in
  `docs/config-profiles.md`: MCPB sensitive fields are injected as environment
  variables by Claude Desktop and are not written back to `.env`.

Reason:

- A Claude Desktop full-mode smoke found `export_report` could fail with
  `WinError 5` on the repo-local default path. User-home output is a safer
  non-developer default.

Validation:

- `pytest tests/test_export_report.py tests/test_config_profiles.py -q
  --basetemp .pytest-temp\report-default`: `20 passed, 1 warning`.
- `pytest -q --basetemp .pytest-temp\full-report-default`:
  `517 passed, 1 warning`.
- `ruff check .`: passed.

### v1.0 readiness sweep

Automated gates:

- `config doctor --offline`: passed for `full`
  (`storage=mongo`, `tools=standard`, `llm=chatgpt_oauth`, `MONGODB_URI`
  configured).
- `smoke-profile --profile full --offline`: passed.
- Tool surface/MCPB manifest targeted regression:
  `29 passed, 1 warning`.
- `ruff check .`: passed.
- Natural question smoke:
  `OK: True`, `questions=12`, `direct=6`, `derived=6`, no sensitive failures,
  no blocked questions. Output:
  `outputs\smoke\natural-question-pack-20260614_011011`.
- Weekly report export smoke in local sample mode: passed, `row_count=8`,
  generated CSV/Markdown under `outputs\readiness-sweep`.
- Live Atlas storage ping: passed after running outside the sandbox.
- `mongo doctor --json`: `ok=true`, indexes present, storage ping pass.

Fix made during sweep:

- Deal review audit originally flagged a lost deal with confirmed risks as
  `confirmed_risks_without_actions`.
- Adjusted the audit rule so confirmed risks require recommended actions only
  on open deals. Terminal `won`/`lost` risks can remain postmortem/context
  evidence without forcing a next action.
- Targeted deal review regression:
  `13 passed`.
- Deal review audit smoke now passes with no quality rule failures.

Live Mongo warning closure:

- Applied the `deals` and `analytics_snapshots` schema validators to live Atlas
  after dry-run review.
- Follow-up `mongo doctor --json` returned `ok=true`, `failed_checks=0`,
  `warning_checks=0`, `skipped_checks=0`, and no `next_actions`.

### First-run documentation alignment

Implemented:

- Rewrote `AI_START_HERE.md` as a shorter first-run card for AI assistants.
- Made the setup posture explicit:
  - human-facing default is `full`,
  - `sample` is an optional zero-config trial/demo path,
  - `pro` is a paid-infra upgrade path.
- Added a README pointer telling users and AI assistants to start from
  `AI_START_HERE.md`.
- Added a full-mode setup preparation prompt covering MongoDB Atlas signup,
  Free/M0 cluster setup, `MONGODB_URI`, MCP client choice, and LLM credential
  options.
- Added MongoDB Atlas signup/free-cluster links to README and MCPB install
  docs.
- Updated the MVP readiness checklist with current v1.0-relevant surfaces:
  user-memory tools, industry metadata split, canonical `add_interaction`,
  local personal mode, and MCPB `0.1.13`.
- Updated the distribution plan with the current tool-surface counts:
  `sample=20`, `standard=24`, `developer=27`.

Validation:

- Documentation scan confirmed no stale first-run sample-oriented wording or
  old `sample=17`, `standard=21`, `developer=24` counts in the active
  first-run docs.
- Natural question smoke passed:
  `OK: True`, `questions=12`, `direct=6`, `derived=6`, no sensitive failures,
  no blocked questions. Output:
  `<local-output-dir>\\smoke\\natural-question-pack-20260614_010543`.

### User memory MCP tools

Implemented:

- Clarified that user-created `user_docs` files can also be created by an AI
  assistant when the user explicitly asks for a new memory document.
- Added the MCP user-memory policy:
  - use narrow memory tools instead of a general-purpose file editor,
  - allow built-in categories and safe custom Markdown document slugs,
  - restrict writes to `user_docs/` or a configured user-memory directory,
  - append by default,
  - reject unsafe paths and executable/non-Markdown targets,
  - mask or reject secret-shaped values before writing.
- Added shared `user_memory` path/slug/secret-scan logic.
- Added MCP `get_user_memory` for read-only assistant context loading.
- Added MCP `record_user_memory` for append-only durable feedback capture.
- Exposed both tools in sample, standard, and developer surfaces.
- Updated the MCPB manifest and tool-surface contracts. Current counts:
  `sample=20`, `standard=24`, `developer=27`.

Validation:

- Targeted regression:
  `41 passed, 1 warning` with `--basetemp .tmp-pytest`.

## Latest Update - 2026-06-13

### User memory samples

Implemented:

- Added `user_docs/` as repo-local memory for non-developer users who want an
  AI assistant to tune Deal Intelligence to their sales motion over time.
- Clarified the identity split:
  - `docs/` is developer reference for building and maintaining custom tools.
  - `user_docs/` is user memory for preferences, feedback, and operating
    context.
- Added sample templates for:
  - operating preferences,
  - metric tuning feedback,
  - taxonomy feedback,
  - report review feedback,
  - evidence policy.
- Updated the documentation map so agents can find `user_docs` without reading
  the entire implementation history.

Validation:

- Documentation-only change.

Next:

- When a real user gives repeated feedback, copy the relevant sample to a
  non-sample file under `user_docs/` and let the AI assistant propose
  config, taxonomy, report, or scoring changes from that accumulated context.

### Industry metadata backfill I4

Implemented:

- Added `backfill-industry-tags` CLI for older rows that predate the
  `industry_tags` and `customer_segment` split.
- The command is dry-run by default.
- Real writes require `--apply --confirmed-by-user`.
- The backfill now normalizes recognizable mixed labels into `industry`,
  `industry_tags`, and `customer_segment` instead of sending them to human
  review by default.
- Missing industry is no longer treated as a dead-end skip. If the company name
  carries a recognizable signal, the tool creates a medium-confidence draft
  classification. Otherwise it returns a web research query and recommended
  `update_deal` follow-up so the AI client can resolve the row instead of
  handing the work back as vague human review.
- Unmapped non-empty labels become low-confidence custom industry drafts with
  warnings, so the record remains usable while still making uncertainty visible.
- `create_deal` and `update_deal` use the same automatic industry metadata
  classifier for mixed labels such as `보험·금융·대기업`.
- `create_deal` also uses company-name inference when the industry input is
  omitted but the company name contains an obvious taxonomy signal.
- Actual writes go through `update_deal`, so `deal_metadata_history` records the
  change.

Validation:

- I4 targeted regression:
  `82 passed, 1 warning`.
- Full regression:
  `503 passed, 1 warning`.
- Ruff:
  `All checks passed`.
- Live Atlas dry-run before apply:
  `22` candidates, `0` research rows, `0` skipped rows, `0` errors.
- Live Atlas apply:
  `22` rows applied through `update_deal`, `0` errors.
- Live Atlas post-apply dry-run:
  `0` candidates, `22` clean rows.
- Customer Themes Atlas aggregation smoke:
  `pain_by_industry=41` rows and `pain_by_industry_tag=46` rows.

Next:

- I4 is complete. If future rows have missing industry, the dry-run will return
  research rows to resolve with web lookup followed by `update_deal`. If that
  becomes common enough, add a dedicated web-enrichment MCP tool later.

### Industry tags Atlas chart I3

Implemented:

- Added `pain_by_industry_tag` to the versioned Customer Themes Atlas Charts
  spec.
- Kept the existing `pain_by_industry` chart as the primary-industry view.
- Made `pain_by_industry_tag` unwind `industry_tags`, so a cross-industry deal
  can appear in multiple semantic tag groups.
- Synced the packaged dashboard resource copy with the repo spec.
- Updated Atlas Charts docs, README, and Korean README to point users to the
  versioned Customer Themes spec and optional tag chart.

Validation:

- Atlas chart targeted regression:
  `21 passed`.
- Full regression:
  `489 passed, 1 warning`.
- Ruff:
  `All checks passed`.

Manual Atlas UI step:

- Render
  `render-atlas-dashboard --dashboard customer_themes --chart-id pain_by_industry_tag`
  and paste the pipeline into a new optional Customer Themes chart if the
  dashboard needs tag-level comparison.

### Industry tags read behavior I2

Implemented:

- Made Customer Themes `industry` filters match either the primary `industry`
  or `industry_tags`, so cross-industry accounts can be found semantically
  without changing primary-industry pipeline metrics.
- Added `group_by="industry_tag"` to Customer Theme breakdowns.
- Added safe `industry_tags` output to Customer Theme evidence rows,
  `list_deals`, and both Python-cosine and Atlas-vector `search_deals` results.
- Kept forecast, pipeline value, expected-close defaults, and primary industry
  grouping on the single primary `industry`.
- Updated MCP contract docs, metrics docs, README, Korean README, and backlog
  wording to mark tag-aware read behavior as implemented.

Validation:

- I2 targeted regression:
  `74 passed, 1 warning`.
- Full regression:
  `487 passed, 1 warning`.
- Ruff:
  `All checks passed`.

Next:

- Review the existing Atlas Customer Themes dashboard later if an
  `industry_tag` visual cut becomes useful in practice.
- Keep the older-row `industry_tags` backfill as a future operator task.

### Industry tags foundation I0/I1

Implemented:

- Added shared `schema.industry_taxonomy` normalization so taxonomy audit,
  `create_deal`, and `update_deal` use one industry rule source.
- Added `industry_tags` to create/update MCP contracts and internal handlers.
- Enforced the primary industry invariant: the single `industry` is always
  included in `industry_tags` when industry metadata is written.
- Normalized clear aliases such as Korean manufacturing and fintech labels to
  `Manufacturing` and `Finance`.
- Initial implementation rejected ambiguous primary industry input with a
  preflight error. I4 later replaced the tool-entrypoint behavior with automatic
  mixed-label classification for recognizable labels.
- Kept tag input flexible: compound tags can expand into multiple canonical
  tags, and unknown custom tags are preserved with `taxonomy_warnings`.
- Added `industry_tags` to Mongo validators, safe Mongo projections,
  analytics snapshots, zero-config fixture data, demo sample data, README, and
  metric/baseline docs.

Validation:

- Targeted industry/taxonomy/write/snapshot/schema regression:
  `93 passed, 1 warning`.
- Local sample/add interaction regression:
  `29 passed, 1 warning`.
- Full regression:
  `481 passed, 1 warning`.
- Ruff:
  `All checks passed`.

Next:

- Continue with I2 tag-aware read behavior. Completed in the section above.

### Industry / customer segment split

Implemented:

- Added optional `customer_segment` support across create/update/read/report
  paths:
  - `create_deal`
  - `update_deal`
  - `list_deals`
  - `search_deals`
  - `get_deal_review`
  - `get_deal_gaps`
  - weekly pipeline rows/CSV
  - analytics snapshots
  - customer-theme evidence rows
- Kept `industry` as the true business vertical and documented
  `customer_segment` for maturity, account segment, ownership, funding stage,
  and similar labels.
- Added expected-close config support for `days_by_segment`, checked before
  `days_by_industry`.
- Added `config_segment` as a valid estimated close-date source.
- Updated Mongo validator resources for `deals` and `analytics_snapshots`.
- Updated zero-config and demo sample data so industry and segment values are
  no longer mixed.
- Added read-only CLI audit support:
  `deal-intel audit-taxonomy`.
  - The audit detects suspicious mixed industry values.
  - It suggests `industry` and `customer_segment` cleanup payloads.
  - It does not write to storage.
  - Human-review rows include a sensemaking explanation: why the system stopped,
    what to check, and why an automatic split could distort reporting.
- Added confirmed cleanup CLI support:
  `deal-intel apply-taxonomy-cleanup`.
  - Dry-run by default.
  - Uses `update_deal` for writes so metadata history and confirmation rules are
    preserved.
  - Requires `--apply --confirmed-by-user` for storage writes.
  - Excludes human-review rows by default; high-confidence rows are the default
    apply set.
- Documented live data taxonomy cleanup/backfill as an explicit operator step.

Validation:

- Targeted tests:
  `107 passed, 1 warning`.
- Taxonomy audit targeted tests:
  `6 passed`.
- Taxonomy cleanup/update targeted tests:
  `22 passed, 1 warning`.
- Failed full regression on the first run because packaged defaults and demo
  sample rows were not fully synchronized; both were corrected.
- Fix-targeted tests:
  `12 passed, 1 warning`.
- Full regression:
  first run failed because the default Windows pytest temp directory was not
  readable; rerun with `--basetemp=.tmp\pytest-full` passed:
  `473 passed, 1 warning`.
- Ruff:
  `All checks passed`.
- Local sample CLI smoke:
  `deal-intel audit-taxonomy --limit 5` scanned 12 deals and found 0 taxonomy
  issues, as expected after fixture cleanup.
- Live Atlas smoke:
  - `deal-intel apply-taxonomy-cleanup --limit 50` found 22 issue rows:
    12 high-confidence candidates and 10 human-review rows.
  - `deal-intel apply-taxonomy-cleanup --limit 50 --apply --confirmed-by-user`
    applied 12 high-confidence rows through `update_deal` with 0 errors.
  - Post-apply dry-run found 10 remaining issue rows under the older strict
    taxonomy policy. I4 later changed recognizable mixed labels to auto
    classification candidates.

## Previous Update - 2026-06-13

### Auxiliary Mongo collection validators

Implemented:

- Generalized MongoDB schema validation contracts from deals-only helpers to
  managed collection helpers in `src/deal_intel/mongo_contracts.py`.
- Added permissive v1 validator resources:
  - `src/deal_intel/resources/mongo/analytics_snapshots.v1.json`
  - `src/deal_intel/resources/mongo/delete_audit_logs.v1.json`
- Added generic MongoDB client methods:
  - `check_collection_schema_validation(collection)`
  - `check_schema_validations()`
  - `collection_schema_command(collection)`
  - `apply_collection_schema_validation(collection)`
- Kept existing deals wrappers for compatibility:
  `check_deals_schema_validation()`, `deals_schema_command()`, and
  `apply_deals_schema_validation()`.
- Extended `mongo doctor` to report:
  - `deals_schema`
  - `analytics_snapshots_schema`
  - `delete_audit_logs_schema`
- Extended `deal-intel mongo apply-schema` with:
  - `--collection deals` (default)
  - `--collection analytics_snapshots`
  - `--collection delete_audit_logs`
  - `--collection all`

Behavior:

- All validators use `validationAction: warn` and
  `validationLevel: moderate`.
- The new validators are intentionally permissive and keep
  `additionalProperties: true` so MVP field evolution is not blocked.
- `apply-schema` remains dry-run by default.
- Live Atlas apply was performed after user confirmation with
  `deal-intel mongo apply-schema --collection all --apply --json`.

Validation:

- Targeted Mongo contract/index/snapshot/lifecycle tests:
  `38 passed, 1 warning`.
- Targeted Ruff:
  `All checks passed`.
- Full regression:
  `464 passed, 1 warning`.
- Full Ruff:
  `All checks passed`.
- CLI dry-runs passed:
  - `deal-intel mongo apply-schema --collection analytics_snapshots --json`
  - `deal-intel mongo apply-schema --collection delete_audit_logs --json`
  - `deal-intel mongo apply-schema --collection all --json`
- Live Atlas read-only smoke:
  - Before apply, `deal-intel mongo doctor --json` returned `ok=true` with
    expected warnings for missing auxiliary validators.
  - The first apply attempt failed with DNS timeout before completion.
  - The unsandboxed retry applied all three validators successfully:
    `deals`, `analytics_snapshots`, and `delete_audit_logs`.
  - Post-apply `deal-intel mongo doctor --json` returned `ok=true`,
    `failed_checks=0`, `warning_checks=0`, and all three schema checks passed.

## Previous Update - 2026-06-12

### F-Mongo operational contracts

Implemented:

- Extracted the MongoDB index contract into
  `src/deal_intel/mongo_contracts.py`.
- Updated `MongoDBClient.ensure_indexes()` to apply the shared index contract
  instead of hard-coded inline index definitions.
- Added read-only Mongo readiness checks:
  `MongoDBClient.check_indexes()` and
  `MongoDBClient.check_deals_schema_validation()`.
- Added a permissive v1 deals collection validator resource:
  `src/deal_intel/resources/mongo/deals.v1.json`.
- Added CLI admin surfaces:
  - `deal-intel mongo doctor`
  - `deal-intel mongo doctor --json`
  - `deal-intel mongo doctor --offline`
  - `deal-intel mongo apply-indexes --json`
  - `deal-intel mongo apply-indexes --apply`
  - `deal-intel mongo apply-schema --json`
  - `deal-intel mongo apply-schema --apply`
- Added Pro vector-index CLI skeleton:
  - `deal-intel mongo apply-vector-index --json`
  - `deal-intel mongo apply-vector-index --apply`
- Updated `MongoDBClient.ensure_vector_index()` so Atlas Vector Search setup
  failures are not silently swallowed. Duplicate/already-existing indexes are
  reported as OK.

Behavior:

- `mongo doctor` is read-only.
- `apply-indexes` and `apply-schema` are dry-run by default.
- `apply-vector-index` is dry-run by default and should be used only on M10+
  Pro clusters when `--apply` is passed.
- The deals schema validator starts with `validationAction: warn` and
  `validationLevel: moderate` so it catches obvious drift without blocking the
  fast-changing MVP schema.
- No MCP tool surface was added; this is CLI/admin functionality first.

Validation:

- F-Mongo targeted tests: `12 passed`.
- Targeted Ruff: `All checks passed`.
- Full regression: `456 passed, 1 warning`.
- Full Ruff: `All checks passed`.
- CLI dry-runs passed:
  - `deal-intel mongo doctor --offline --json`
  - `deal-intel mongo apply-indexes --json`
  - `deal-intel mongo apply-schema --json`
- Live Atlas write smoke:
  - `deal-intel mongo apply-schema --apply --json` applied the validator.
  - The first JSON output failed because PyMongo returned a non-JSON
    `Timestamp`; the command result was confirmed by `mongo doctor`, and the
    CLI now serializes Mongo command responses with `default=str`.
  - The live apply output was rerun after the fix and now returns a safe result
    summary with `ok` and `operationTime`, without raw `$clusterTime.signature`
    metadata.
- Live Atlas read-only smoke passed after unsandboxed retry:
  - ping succeeded,
  - expected ordinary indexes are present,
  - deals collection validator now matches the v1 contract.

Not applied:

- `deal-intel mongo apply-vector-index --apply` was not run because the current
  full/M0 path should stay on Python cosine. Run it only on a prepared M10+
  Pro cluster.

### v1.0 distribution readiness D1 first pass

Implemented:

- Aligned README, Korean README, AI start guide, MVP readiness checklist, and
  distribution plan on the full-by-default external trial flow.
- Clarified that `sample` is an optional zero-config AI/demo evaluation path,
  not the default human-facing install path.
- Updated the MCPB install surface so `storage_backend` defaults to `mongo`;
  users choose `local_sample` only for zero-config demos.
- Corrected public tool-surface counts to the runtime contract:
  `sample=17`, `standard=21`, `developer=24`.
- Reframed distribution D1 as external MVP trial readiness before uvx/npx
  wrapper work.

Validation:

- `config profiles`: passed.
- `config doctor --offline`: passed, current effective profile `full`.
- `smoke-profile --profile full --offline`: passed.
- Tool surface and MCPB manifest targeted tests: `29 passed`.
- Earlier optional zero-config sample checks in this slice also passed:
  `config init --profile sample --dry-run`, `smoke-profile --profile sample`,
  temporary local sample `storage-status`, and local sample natural-question
  smoke `12/12`.

Notes:

- This was a first-run distribution readiness slice, not a deep MongoDB feature
  validation slice. Human-facing setup should start with `full`; optional
  `sample` checks protect only the no-MongoDB demo/evaluation path.
- Live `storage-status`/Atlas ping was not rerun after the doc correction
  because this environment previously hit MongoDB DNS/network resolution.
- Claude Desktop MCPB reinstall smoke was not rerun in this slice.

### Pro profile skeleton planning and P-Pro.1/P-Pro.2 start

Decisions:

- `pro` stays an upgrade path, not the default first-run profile.
- `pro` uses `openai_api` by default with `gpt-5.4-mini` to reduce API cost
  pressure. The model can still be overridden in user config.
- Atlas Vector Search failures must not silently fall back to Python cosine.
  Repeatable failures should be recorded in
  [pro-fallback-errors.md](pro-fallback-errors.md).
- The current target is skeleton plus guardrails. Live OpenAI API and Atlas
  Vector Search smoke will run later when disposable paid infra is available.
- MongoDB ecosystem features that work on Atlas Free/M0 and improve ordinary
  real-data operation should be implemented in `full`; `pro` is reserved for
  paid infrastructure, cost-bearing defaults, or scale/admin paths beyond Free/M0.

Implemented in this slice:

- Added a versioned Atlas Vector Search index spec:
  `atlas/vector_indexes/deal_summary_vector.v1.json`.
- Added package resource copy under
  `src/deal_intel/resources/atlas/vector_indexes/`.
- Added `deal_intel.atlas_vector_indexes` as the source loader for future
  doctor/check/apply tooling.
- Updated OpenAI API defaults to `gpt-5.4-mini`.
- Confirmed `search_deals` in `atlas` mode returns a structured error instead
  of silently falling back to Python cosine.

Validation:

- P-Pro.1/P-Pro.2 targeted tests: `65 passed`
- Targeted Ruff: `All checks passed`
- `smoke-profile --profile pro --offline --json`: profile contract passed;
  overall `ok=false` is expected until `OPENAI_API_KEY` is configured.

### Currency abstraction implementation

Implemented:

- Replaced currency-specific canonical amount fields with generic amount/currency
  fields across schema, tools, metrics, reports, local sample data, analytics
  snapshots, and tests.
- Added `deal_value.default_currency` with `KRW` as the default.
- Added `deal_size_currency` to create/update/list/search/deal review/deal gaps
  surfaces and report rows.
- Updated pipeline value summaries to expose `currency`, `currencies`,
  `mixed_currency`, and `amount_by_currency`.
- Mixed currencies are not silently summed in Python metrics or Markdown
  reports.

Validation:

- C1 targeted metric/schema tests: `91 passed`
- C2 storage/sample/snapshot tests: `72 passed`
- C3 report/Atlas/get_insights tests: `61 passed`
- Targeted Ruff checks: `All checks passed`
- Full regression: `436 passed, 1 warning`
- Full Ruff: `All checks passed`
- Natural question smoke: `12/12 pass`
- Deal review smoke: `2/2 pass`, sensitive field check passed

Remaining note:

- Atlas Charts are still best treated as single-reporting-currency dashboards;
  mixed-currency operation should use Python metric/report outputs for the
  authoritative breakdown.

### Product roadmap adjustment before Pro work

Decision:

- Repositioned the product as an AI-assisted sales/deal-intelligence record and
  review tool for one-person or small AI teams that need customizable sales
  metrics without adopting a full CRM.
- Moved currency abstraction ahead of Pro infrastructure work.
- Because there are currently no external users, the preferred currency plan is
  a clean canonical schema migration instead of keeping `_krw` fields as a
  long-lived public API.
- Deferred full MEDDPICC/qualification-framework abstraction until after v1.0.
  It should be handled as v2.0 work on a dedicated branch or separate repo if
  needed.

Updated roadmap:

1. Currency abstraction.
2. Pro profile skeleton and MongoDB/Atlas Vector Search upgrade path.
3. v1.0 distribution decision.
4. Deal Review and CSV/report quality improvements.
5. Other MVP polish and issue fixes.
6. Qualification framework abstraction for v2.0.

Docs:

- Added Product Roadmap, Currency Abstraction, and Qualification Framework
  Abstraction sections to `docs/backlog.md`.
- Updated `docs/mvp-readiness.md` so currency schema cleanup is a v1.0
  yellow item and MEDDPICC abstraction is explicitly deferred.

## Previous Update - 2026-06-11

### Package-data readiness for future uvx/npx distribution

Implemented:

- Added package resources for `config/defaults.yaml` and Atlas chart specs.
- Updated config loading to use repo-root defaults first, then packaged
  defaults when running outside a git checkout.
- Updated Atlas chart loading to use repo-root specs first, then packaged chart
  specs.
- Added package-data metadata in `pyproject.toml`.
- Aligned `pyproject.toml` version with `mcpb/manifest.json` (`0.1.12`).
- Added resource drift and fallback tests for config defaults and dashboard
  specs.

Verification:

- Targeted config/Atlas/MCPB regression:
  `30 passed`
- Targeted Ruff:
  `All checks passed`
- Wheel build:
  `deal_intel_mcp-0.1.12-py3-none-any.whl`
- Wheel resource inspection:
  packaged defaults and all 3 Atlas chart specs present
- Wheel target-install smoke:
  loaded `deal_intel._env` from `.tmp/wheel-install`, read packaged defaults,
  and loaded the Weekly Pipeline Review spec
- Full pytest:
  `433 passed`, `1 warning`
- Ruff:
  `All checks passed`

### Distribution plan

Implemented:

- Added `docs/distribution-plan.md`.
- Recorded the current MVP stance: git clone remains acceptable for the first
  MVP, while npx/uvx wrappers should not preempt sample/local readiness.
- Documented the package portability constraint: repo-root `config/defaults.yaml`
  reads must be refactored before a clean wheel/uvx path.
- Recommended sequence: package-data readiness, uvx/Python-native distribution,
  then npx as a thin convenience wrapper.
- Linked the plan from the docs map and backlog.

### Zero-config sample/local UX polish

Implemented:

- Improved local-to-Mongo dry-run UX for empty local personal stores.
- `migrate_local_data` now skips target MongoDB readiness checks when
  `dry_run=true` and there are no local personal deals to migrate.
- Documented the skip behavior in README and the local storage contract.

Verification:

- Targeted local-data/storage/profile regression:
  `22 passed`, `1 warning`
- Local sample CLI smoke:
  `local-data migrate-to-mongo` returns an empty dry-run preview without DNS
  timeout when there are no local personal deals.
- Targeted Ruff:
  `All checks passed`
- Full pytest:
  `428 passed`, `1 warning`
- Ruff:
  `All checks passed`

### MVP readiness checklist

Implemented:

- Added `docs/mvp-readiness.md` as the external MVP readiness
  checklist.
- Captured required gates for full tests, Ruff, sample profile smoke, natural
  question smoke, deal review audit, tool surface/MCPB contract checks, local
  personal data safety, and MCPB package smoke.
- Separated green, yellow, not-MVP-blocking, and deferred-after-MVP items so
  wrapper/pro-infra work does not obscure the current MVP path.
- Added a lightweight friend/evaluator trial script and sign-off template.
- Linked the checklist from the docs map.

### Natural Smoke QA expansion

Implemented:

- Expanded `smoke-natural-questions` from 9 to 12 deterministic questions.
- Added coverage for pipeline trend, deal-review actionability separation, and
  interaction source coverage.
- Kept the pack LLM-free and read-only against deal data; it only writes local
  smoke artifacts.
- Updated tests so the smoke pack fails if the expanded question set shrinks,
  blocks, or leaks sensitive fields.

Verification:

- Targeted natural-smoke/trend/metrics regression:
  `34 passed`, `1 warning`
- Targeted Ruff:
  `All checks passed`
- Local sample natural-question smoke:
  `questions=12`, `answerability=derived=6,direct=6`,
  `source_evidence=2 (email_thread=1, user_interview=1)`,
  `actionable=4`, `observations=6`, `risks=3`
- Full pytest:
  `427 passed`, `1 warning`
- Ruff:
  `All checks passed`

### P3.7 interaction intake MVP closeout

Implemented:

- Added `source_policy` to `add_interaction` responses so MCP clients can
  explain whether the submitted interaction was treated as confirmed evidence
  or stored as unconfirmed context.
- Kept `source_policy` response-only; persisted interaction records keep source
  metadata, but restricted BI/list/report paths do not carry extra policy text
  or raw interaction content.
- Clarified README and AI-start guidance for meeting notes, email threads, user
  interviews, call summaries, and internal notes.
- Updated the MCP baseline contract for the new response field.

Verification:

- Targeted interaction/surface/fixture/natural-smoke regression:
  `49 passed`, `1 warning`
- Targeted Ruff:
  `All checks passed`
- Local sample natural-question smoke:
  `questions=9`, `answerability=derived=4,direct=5`,
  `source_evidence=2 (email_thread=1, user_interview=1)`
- Full pytest:
  `427 passed`, `1 warning`
- Ruff:
  `All checks passed`

### P3.6 source-aware evidence rendering

Implemented:

- Added shared source-label formatting for curated customer evidence.
- Added `source_label` to `get_customer_theme_evidence` rows.
- Preserved source metadata on weekly pipeline primary pain and decision
  criteria rows.
- Added a Customer Evidence section to weekly pipeline Markdown summaries.
- Added a Source Evidence section to natural-question smoke `summary.md`.
- Updated the Customer Themes Atlas evidence drill-down spec to project
  `interaction_type`, `source_confidence`, `source_label`, `subject`, and
  `interaction_date`.

Verification:

- Targeted reporting/theme/smoke/Atlas regression:
  `48 passed`, `1 warning`
- Local sample natural-question smoke:
  `questions=9`, `source_evidence=2 (email_thread=1, user_interview=1)`,
  Source Evidence section rendered with meeting/email/interview labels
- Full pytest:
  `427 passed`, `1 warning`
- Ruff:
  `All checks passed`

### P3.5 source-aware theme evidence filters

Implemented:

- Added `interaction_type` and `source_confidence` filters to
  `get_customer_theme_evidence`.
- Supported exact source filtering for built-in interaction types:
  `meeting`, `email_thread`, `user_interview`, `call_summary`, and
  `internal_note`.
- MCP tool validation also honors config-registered custom interaction types.
- Preserved legacy compatibility by treating old meeting-derived theme rows as
  `interaction_type=meeting`.
- Updated the natural-question smoke pack so the email/interview evidence
  question calls the native source filters instead of only post-filtering rows.

Verification:

- Targeted theme/fixture/natural-smoke regression:
  `28 passed`, `1 warning`
- Full pytest:
  `425 passed`, `1 warning`
- Ruff:
  `All checks passed`
- Local sample natural-question smoke:
  `questions=9`, `source_evidence=2 (email_thread=1, user_interview=1)`

### P3.4 sample interaction evidence UX

Implemented:

- Added canonical `interactions` records to the bundled zero-config fixture
  while keeping legacy `meetings` for read compatibility.
- Added one inbound `email_thread` sample and one `user_interview` sample with
  curated customer-theme evidence, source confidence, subject, and interaction
  metadata.
- Extended `get_customer_theme_evidence` rows with safe source metadata:
  `interaction_id`, `interaction_date`, `interaction_type`,
  `source_confidence`, and `subject`.
- Added natural-question smoke coverage for:
  "Which customer themes are supported by email or user interview evidence?"

Verification:

- Targeted fixture/theme/smoke regression:
  `25 passed`, `1 warning`
- Local sample natural-question smoke:
  `questions=9`, `answerability=derived=4,direct=5`,
  `source_evidence=2 (email_thread=1, user_interview=1)`

### P3.3 single public interaction intake

Implemented:

- Promoted `add_interaction` as the only public/customer-evidence intake path
  on the `sample` and `standard` MCP surfaces.
- Kept `add_meeting` registered only on the `developer` surface as a
  deprecated compatibility alias for `add_interaction` with
  `interaction_type: meeting`.
- Updated tests so primary meeting-note behavior is exercised through
  `add_interaction(interaction_type="meeting")`.
- Updated README, MCPB manifest text, baseline/tool-surface docs, and
  AGENTS/CLAUDE rules so new users and fork authors see one clear intake
  concept.

Verification:

- Targeted surface/intake/profile/bundle/local regression:
  `100 passed`, `1 warning`
- Full pytest:
  `423 passed`, `1 warning`
- Ruff:
  `All checks passed`
- Runtime surface count smoke:
  `sample=17`, `standard=21`, `developer=24`; `add_meeting` hidden from
  sample/standard and present only in developer
- MCPB manifest validation:
  `Manifest schema validation passes!`
- Diff whitespace check:
  `git diff --check` passed with Git line-ending normalization warnings only

### P3.2 canonical interaction storage

Implemented:

- Added `schema.interactions` as the canonical interaction helper layer.
- New `add_interaction` writes now append only to `deal.interactions`; they no
  longer dual-write to `deal.meetings`.
- `add_meeting` is now a backward-compatible wrapper over canonical
  `interaction_type: meeting` intake. It keeps returning `meeting_id`, but the
  stored record lives under `interactions`.
- Legacy `meetings` remain supported as read fallback. If a deal has both
  `interactions` and old `meetings`, read helpers merge them and de-duplicate
  matching ids so historical evidence is not lost.
- Custom interaction types are config-registered rather than free-form:
  `interactions.custom_types: ["security_review"]`.
- Local/full/pro storage preserves `interactions.raw_content` for future
  security/redaction modules and forked workflows, while restricted BI/list/
  report/delete-audit paths exclude it.
- `list_deals`, `update_stage`, weekly reports, deal analysis, customer-theme
  flattening, and data-quality checks now read through interaction helpers.

Verification so far:

- Canonical interaction targeted regression:
  `94 passed`, `1 warning`
- Reporting/review/read-path targeted regression:
  `77 passed`, `1 warning`
- Full pytest:
  `422 passed`, `1 warning`
- Ruff:
  `All checks passed`
- Runtime surface count smoke:
  `sample=18`, `standard=22`, `developer=24`

Follow-up:

- P3.3 should reduce `add_meeting` from a compatibility wrapper to a
  deprecated alias and eventually remove it from default user-facing tool
  surfaces. `add_interaction(interaction_type="meeting")` should become the
  single clear intake path for new users and forked implementations.
- Detailed P3.3 implementation units are tracked in
  [backlog.md](backlog.md#customer-interaction-intake) under "single intake
  surface".

### P3.1 customer interaction intake contract

Implemented:

- Added MCP tool `add_interaction`.
- Supported interaction types:
  `meeting`, `email_thread`, `user_interview`, `call_summary`, and
  `internal_note`.
- Supported directions:
  `inbound`, `outbound`, `mixed`, and `internal`.
- Stored interactions as meeting-compatible evidence so existing
  MEDDPICC/customer-theme/report paths keep working without a migration.
- Added source metadata:
  `interaction_type`, `direction`, `source_confidence`, `participants`, and
  `subject`.
- Preserved `add_meeting` as the simpler backward-compatible meeting-note
  entry point.
- Added scoring safety for weak sources:
  `outbound_unconfirmed` and `internal` inputs are saved as unconfirmed
  structured interaction evidence but do not update MEDDPICC health or
  customer-theme counts by default.
- Kept local sample privacy behavior: no embedding warmup, no persisted raw
  content, and bundled fixture records remain read-only.
- Bumped MCPB manifest to `0.1.12`.
- Updated current runtime surface count:
  `sample=18`, `standard=22`, `developer=24`.

Verification:

- P3.1 targeted interaction/surface/profile/bundle/local tests:
  `68 passed`, `1 warning`
- Targeted Ruff:
  `All checks passed`
- Full pytest:
  `419 passed`, `1 warning`
- Full Ruff:
  `All checks passed`
- MCPB manifest contract:
  `6 passed`
- Runtime surface count smoke:
  `sample=18`, `standard=22`, `developer=24`, `server=24`
- Diff whitespace check:
  `git diff --check`

### P3.0 sample/local note intake surface

Implemented:

- Exposed `add_meeting` on the `sample` MCP surface so local/sample users can
  add notes to user-created local personal deals when the configured LLM
  provider is ready.
- Kept bundled fictional fixture deals immutable; `add_meeting` cannot promote
  fixture records into local personal storage.
- Skipped embedding provider initialization for `add_meeting` when the storage
  backend is `local_sample`.
- Preserved local privacy behavior: local personal persistence strips raw
  notes, contacts, and embeddings while keeping extracted summaries,
  MEDDPICC signals, and customer themes.
- Updated profile/docs language so sample mode is described as mostly
  LLM-free with optional LLM-backed note intake, not as strictly LLM-free.
- Updated current runtime surface count:
  `sample=17`, `standard=21`, `developer=23`.

Verification:

- P3.0 targeted regression:
  `66 passed`, `1 warning`
- Full pytest:
  `410 passed`, `1 warning`
- Ruff:
  `All checks passed`
- Runtime surface count smoke:
  `sample=17`, `standard=21`, `developer=23`
- Diff whitespace check:
  `git diff --check`

### Deal review v2 rendering alignment

Implemented:

- Added shared gap actionability classification.
- Reused it in `get_deal_gaps`, `get_deal_review`, weekly pipeline rows, and
  weekly Markdown reports.
- `get_deal_gaps` rows now expose `actionable_gaps` and `gap_observations` in
  addition to the original `gaps` list.
- Weekly pipeline rows now expose `objective_action_items` and
  `gap_observations`.
- Weekly Markdown now renders separate Objective Action Items and Gap
  Observations sections.
- `attention:overdue`, stuck, and stalled are CTA-safe. MEDDPICC gaps and
  `attention:at_risk` are observation-only because they require account/BD
  judgment before prescribing action.

Verification:

- Targeted rendering/gaps/deal-review tests: `53 passed`, `1 warning`
- Targeted Ruff: `All checks passed`
- Local sample `export_report(weekly_pipeline)` smoke: passed, generated CSV
  and Markdown under `.tmp/v2-rendering-smoke-2`
- Local sample `smoke-natural-questions`: passed, `8` questions, no sensitive
  failures, final payload under `.tmp/natural-v2-rendering-smoke-3`
- Local sample `smoke-deal-review`: passed for `2` deals
- Full pytest: `408 passed`, `1 warning`
- Full Ruff: `All checks passed`

### Deal review quality v2

Implemented:

- Added `review_version: "v2"` to deterministic deal reviews.
- Added a top-level `assessment` summary that separates health quality,
  evidence coverage, uncertainty, confirmed risk level, review band, and alert
  level.
- Split gap output into `actionable_gaps` for objective CTA-safe items such as
  overdue timing, and `gap_observations` for judgment-sensitive MEDDPICC gaps
  such as competition, champion quality, economic buyer mapping, and decision
  criteria.
- Added per-gap `actionability` and `cta_policy` so reports and natural
  language answers can avoid turning qualitative gaps into overconfident
  instructions.
- Made deal-review evidence coverage thresholds configurable under
  `deal_review.evidence_coverage.low_max` and
  `deal_review.evidence_coverage.high_min`.
- Extended the deal-review smoke audit so it catches v2 contract regressions,
  judgment-sensitive gaps promoted into CTAs, and non-CTA gaps leaking into
  actionable output.

Verification:

- Targeted deal-review tests: `26 passed`, `1 warning`
- Targeted Ruff: `All checks passed`
- Full pytest: `406 passed`, `1 warning`
- Full Ruff: `All checks passed`

### Planning note: customer interaction intake

Added to [backlog.md](backlog.md):

- A high-priority Customer Interaction Intake stream.
- Direction: keep `add_meeting` compatible, then introduce `add_interaction`
  for meeting notes, email threads, user interviews, call summaries, and
  internal notes.
- Rationale: local/sample mode is useful enough that broadening the input
  surface is now more valuable than another dashboard/report. Source metadata
  also supports the upcoming unknown-first scoring and uncertainty work.

Recommended priority:

1. Finish/continue Deal Review Quality calibration.
2. Implement `add_interaction` contract and source-aware extraction.
3. Then return to reporting polish, Pro infrastructure, or MongoDB ecosystem
   upgrades.

### Planning note: CTA eligibility for gaps

Added to [backlog.md](backlog.md):

- Deal Review/Reporting should separate objective CTA triggers from
  judgment-sensitive gap observations.
- Objective triggers can still become explicit actions: overdue dates, missed
  commitments, missing terminal close metadata, or obvious initiation steps.
- Qualitative MEDDPICC gaps such as competition, champion quality, economic
  buyer mapping, or decision criteria should usually be rendered as gap points
  unless the account evidence makes the next action objectively clear.
- Candidate implementation: add `actionability` or `cta_policy` to gap rows
  so reports can render `cta_allowed`, `observation_only`, and
  `needs_human_judgment` differently.

### Planning note: account people graph

Added to [backlog.md](backlog.md):

- Medium-long-term Account People Graph stream.
- Direction: eventually track Champion, Economic Buyer, decision committee,
  procurement, security, legal, and blockers as company/account-indexed people
  intelligence.
- Keep it deferred until deal review quality and customer interaction intake
  are stable. The near-term design constraint is only to preserve source and
  confidence metadata so people extraction can become trustworthy later.

### MCPB Claude Desktop smoke and UTF-8 hardening

Observed:

- Claude Desktop loaded the MCPB extension successfully in `sample` profile
  with `local_sample` storage and the then-current 16 sample-surface tools.
  Current sample surface count is 17 after P3.0.
- `config_doctor`, `list_deals`, `get_metrics`, `get_deal_review`,
  customer-theme analysis, report export, delete dry-run safety, and
  update-stage guidance all worked against bundled sample data.
- One generated Korean progress phrase showed a replacement character in the
  word "heatmap". Tool JSON payloads and sample data did not show broad
  corruption.

Implemented:

- Bumped MCPB manifest to `0.1.11`.
- Added `PYTHONUTF8=1` alongside `PYTHONIOENCODING=utf-8` in MCPB runtime env.
- Removed Korean examples/descriptions from MCP tool docstrings so Claude's
  tool metadata path is English-only.

Verification so far:

- MCPB/tool-surface targeted regression:
  `27 passed`, `1 warning`
- Targeted Ruff:
  `All checks passed`
- MCP tool metadata Korean/replacement-character scan:
  no matches in `mcp_server.py`, MCPB manifest, MCPB README, or manifest tests.
- Full pytest:
  `404 passed`, `1 warning`
- Final Ruff:
  `All checks passed`
- MCPB CLI:
  `mcpb validate manifest.json`
- MCPB artifact:
  `deal-intel-mcp-0.1.11.mcpb`, `size=5.30 KB`,
  `shasum=bbf9099225cb1fbfb01a82c1f7bf54832a7a997b`

Notes:

- The 0.1.11 bundle is still unsigned.

### O3 Mongo index contract

Implemented:

- Added `deals.archived_stage_updated`:
  `(archived, deal_stage, updated_at desc)` for visible list views with stage
  filters and newest-first sorting.
- Added `analytics_snapshots.analytics_snapshot_as_of_occurred_created`:
  `(as_of, occurred_at, created_at)` for pipeline trend range/sort reads and
  Atlas trend charts.
- Preserved existing indexes, including `deal_id_unique`,
  `analytics_snapshot_event_id_unique`, `archived_updated`, and
  `sample_batch`.
- Added targeted index contract tests and updated
  [query-audit.md](query-audit.md) and [backlog.md](backlog.md).

Verification so far:

- O3 targeted regression:
  `14 passed`
- Targeted Ruff:
  `All checks passed`
- Full pytest:
  `404 passed`, `1 warning`
- Final Ruff:
  `All checks passed`
- Live Atlas index creation/explain smoke:
  not run; keep this optional and production-safe.

### O2 BI read projection and Atlas visibility hardening

Implemented:

- Added leading `archived != true` filters to every Weekly Pipeline Atlas chart
  pipeline.
- Hardened `MongoDBClient.list_deals()` projection to exclude
  `contacts` and `summary_embedding` in addition to `_id` and
  `meetings.raw_notes`.
- Added regression tests for Weekly Pipeline chart visibility filters and
  list-view projection.
- Deferred `list_deals_for_metrics()` allowlist conversion until
  BI/review/report field contracts stabilize.
- Updated [query-audit.md](query-audit.md), [atlas-charts.md](atlas-charts.md),
  and [backlog.md](backlog.md).

Verification so far:

- O2 targeted regression:
  `31 passed`, `1 warning`
- Targeted Ruff:
  `All checks passed`
- Full pytest:
  `402 passed`, `1 warning`
- Final Ruff:
  `All checks passed`
- Diff whitespace check:
  `git diff --check`
- CLI render smoke:
  `render-atlas-dashboard --as-of 2026-06-09 --chart-id pipeline_kpis --output .tmp/pipeline_kpis_o2.json`

### O1 Index / query / projection audit

Implemented:

- Added [query-audit.md](query-audit.md) as the current MongoDB read-path audit.
- Inventoried storage read methods, main MCP/report/chart consumers, query
  shapes, projection policy, and current index coverage.
- Confirmed that the main BI/metric/report/deal-review/deal-gap paths use
  restricted projections through `list_deals_for_metrics()` or
  `list_analytics_snapshots()`.
- Confirmed intentional full/raw read exceptions:
  `get_deal` for single-deal detail and `backfill-customer-themes` for
  maintainer LLM backfill.
- Identified O2 follow-up candidates:
  harden `list_deals()` projection, convert metrics projection to allowlist,
  and add archived visibility filters to Weekly Pipeline Atlas chart specs.
- Identified O3 follow-up candidates:
  list-view compound index and trend `as_of` range/sort index.

Verification:

- Documentation map updated.
- Diff whitespace check:
  `git diff --check`

### Z5.12 MCP bundle packaging contract check

Implemented:

- Added repo-local MCP bundle contract tests in
  `tests/test_mcpb_manifest.py`.
- Verified that `mcpb/manifest.json` tool names match
  `deal_intel.tool_surfaces` exactly.
- Verified that bundle installer fields map to runtime environment variables:
  storage backend, tool surface, MongoDB URI, LLM provider, Anthropic API key,
  OpenAI API key, and UTF-8 stdio.
- Verified that the bundled launcher delegates to the installed
  `deal_intel.mcp_server` module and returns an actionable editable-install
  hint when the package is not importable.
- Bumped the bundle manifest version to `0.1.10`.
- Updated `mcpb/README.md` so first-run install guidance reflects current
  sample/local personal mode, `tools_surface=auto`, and dry-run-first
  local-to-Mongo migration.

Verification:

- MCP bundle/config/tool-surface targeted regression:
  `44 passed`, `1 warning`
- Targeted Ruff:
  `All checks passed`
- Full pytest:
  `401 passed`, `1 warning`
- Final Ruff:
  `All checks passed`
- Diff whitespace check:
  `git diff --check`
- MCPB CLI smoke:
  `mcpb pack . deal-intel-mcp-0.1.10.mcpb`
- MCPB artifact contents:
  `manifest.json`, `README.md`, `server/launcher.py`
- MCPB artifact info:
  `size=5.29 KB`, `shasum=291b3f44b330d1fa8252d7917353f654d6695221`

Notes:

- The bundle is not signed yet; `mcpb info` reports `WARNING: Not signed`.

### Z5.11 local personal to MongoDB migration

Implemented:

- Added shared `migrate_local_data` migration engine.
- Added MCP tool `migrate_local_data`.
- Added CLI command `deal-intel local-data migrate-to-mongo`.
- Migration reads only user-created local personal deals from
  `storage.local_data_dir`.
- Bundled zero-config fixture records are never migrated.
- Migration is dry-run by default.
- Actual writes require explicit confirmation through MCP
  `confirmed_by_user=true`; the CLI equivalent is `--apply`.
- Existing target `deal_id` values are skipped by default.
- Existing target `deal_id` values are overwritten only with
  `overwrite=true` / `--overwrite`.
- Local delete audit logs stay local and are reported as a warning; they are
  not migrated.
- Updated MCP tool counts:
  `sample=17`, `standard=21`, `developer=23`.

Verification:

- Migration/tool-surface targeted regression:
  `56 passed`, `1 warning`
- Targeted Ruff:
  `All checks passed`
- Full pytest:
  `395 passed`, `1 warning`
- Final Ruff:
  `All checks passed`
- Diff whitespace check:
  `git diff --check`
- Manifest/surface count smoke:
  `manifest=23`, `sample=17`, `standard=21`, `developer=23`

### Config profiles Z5.8-Z5.10 tool surface runtime filtering

Implemented:

- Added `deal_intel.tool_surfaces` as the source contract for MCP tool
  visibility surfaces.
- Defined non-developer-first surfaces:
  `sample`, `standard`, and `developer`.
- Mapped `sample` profile to the `sample` surface, and `full`/`pro`/`custom`
  to the `standard` surface.
- Kept `sample` semantic-search-free and mostly LLM-free while allowing safe
  local personal create/update/stage/lifecycle writes. P3.0 later added
  optional LLM-backed `add_meeting` for user-created local personal deals.
- Kept real operator admin tools such as `delete_deal` in `standard`, relying
  on their existing dry-run, confirmation, exact-company, archive-gate safety
  contracts.
- Added [tool-surfaces.md](tool-surfaces.md) and linked it from the docs map.
- Updated [config-profiles.md](config-profiles.md) and [backlog.md](backlog.md)
  to mark tool filtering and local personal storage as implemented.
- Clarified user-facing sample-mode positioning: sample is a limited
  feature-test path with bundled fictional data, while real operation assumes
  MongoDB-backed `full` mode.
- Revised that positioning so `sample` is not read-only: mutable/resettable
  local personal data now supports small user datasets before MongoDB.
- Kept `sample_local_personal_target` as a backward-compatible matrix alias for
  the now-current sample tool set.
- Reordered the Z5 plan tree: the originally planned next step was
  config-driven MCP tool filtering, but mutable/resettable local personal
  storage now comes first so the filtered `sample` surface is actually useful
  for small user datasets.
- Added `storage.local_data_dir` to the config contract. The default planned
  local personal data directory is `~/.deal-intel/local-data`, and config tools
  can expose/override it through the sample profile.
- Added a later dry-run-first local personal data to MongoDB migration target
  to the Z5 plan tree.
- Added Z5.9a local personal read foundation:
  `storage.local_data_dir/deals.json` can provide user-created local deals.
  When local deals exist, bundled fixture data is treated as archived demo data
  and removed from active `local_sample` read paths.
- Added Z5.9b local personal safe write foundation:
  `LocalSampleClient.upsert_deal` persists to local `deals.json`, stripping
  sensitive fields before storage. `create_deal`, `update_stage`, and
  `update_deal` can now write local personal sample data.
- Added Z5.9c-1 local lifecycle safety:
  `archive_deal`, `restore_deal`, and `delete_deal` now work on local personal
  data. `delete_deal` preserves audit snapshots in `delete_audit_logs.json`
  before hard delete, keeps audit logs independent from deal storage, and
  blocks bundled fixture deal ids from being persisted through lifecycle writes.
- Added Z5.9c-2 local reset/export safety:
  `deal-intel local-data status`, `deal-intel local-data export`, and
  `deal-intel local-data reset` now inspect, export, and reset local personal
  data without touching bundled fixture data.
- `local-data reset` is dry-run by default.
- `local-data reset --force` clears only local personal deals in `deals.json`
  and preserves delete audit logs in `delete_audit_logs.json`.
- An empty local `deals.json` keeps bundled fixture data archived, so reset
  does not silently re-mix fictional sample data into the active working set.
- `local-data export` writes a secret-safe JSON snapshot without raw notes,
  contacts, or embeddings.
- Added Z5.10 config-driven MCP runtime filtering:
  `tools.surface: auto|sample|standard|developer`.
- Added `DEAL_INTEL_TOOLS_SURFACE` as a packaged/runtime override.
- Runtime `auto` resolves from the effective profile:
  `sample -> sample`, `full/pro/custom -> standard`.
- `sample` now exposes safe local personal write/admin tools alongside
  mostly LLM-free read/reporting tools.
- MCP `list_tools()` is filtered by surface and hidden `call_tool()` requests
  are blocked.
- Invalid `tools.surface` config exposes only `config_doctor` so the setup
  problem remains diagnosable.
- `config show` and `config doctor` now report configured/resolved tool
  surface and MCP tool count.
- Updated the MCP bundle manifest with `tools_surface` and
  `DEAL_INTEL_TOOLS_SURFACE`.

Verification:

- Tool surface/config/profile regression:
  `71 passed`, `1 warning`
- Local sample/personal read foundation:
  `12 passed`
- Local safe-write/config regression:
  `86 passed`, `1 warning`
- Local lifecycle safety:
  `17 passed`
- Local reset/export CLI safety:
  `21 passed`
- Lifecycle/config regression:
  `92 passed`, `1 warning`
- Local sample/config/profile regression:
  `45 passed`, `1 warning`
- Local data/config/profile regression:
  `68 passed`
- Tool surface runtime targeted regression:
  `61 passed`, `1 warning`
- Expanded MCP surface regression:
  `109 passed`, `1 warning`
- Runtime surface count smoke:
  `sample=17`, `standard=21`, `developer=23`
- Config CLI smoke:
  `config init --profile sample --dry-run` shows
  `storage.local_data_dir: ~/.deal-intel/local-data`
- Full pytest:
  `388 passed`, `1 warning`
- Diff whitespace check:
  `git diff --check`
- Ruff:
  `All checks passed`

### Config profiles Z5.7b smoke-profile CLI

Implemented:

- Added `deal_intel.profile_smoke` to build no-write first-run smoke reports
  from the Z5.7a matrix and shared config doctor.
- Added `deal-intel smoke-profile --profile sample|full|pro`.
- Added `--offline` to skip storage ping and `--json` for agent-readable
  structured output.
- Updated README and `AI_START_HERE.md` so first-run checks include
  `smoke-profile --profile sample`.
- Updated [config-profiles.md](config-profiles.md) and [backlog.md](backlog.md)
  to mark the CLI surface implemented and move the next candidate work to
  release packaging checks.

Verification:

- Profile smoke CLI targeted tests:
  `14 passed`
- Config/profile regression:
  `51 passed`, `1 warning`
- Full pytest:
  `351 passed`, `1 warning`
- CLI smoke:
  `smoke-profile --profile sample --json` returned `ok=true`
- Expected not-ready CLI smoke:
  `smoke-profile --profile pro --offline --json` returned exit code `1`
  because `OPENAI_API_KEY` is not configured; no live OpenAI or Atlas admin
  calls were attempted.
- Diff whitespace check:
  `git diff --check`
- Ruff:
  `All checks passed`

### Config profiles Z5.7a profile smoke matrix

Implemented:

- Added `deal_intel.profile_smoke_matrix` as the source contract for
  `sample`, `full`, and `pro` first-run smoke behavior.
- The matrix records each profile's managed config values, required setup,
  expected unconfigured offline fail/warn checks, no-live-call boundaries,
  write policy, and deferred checks.
- Added targeted tests that compare the matrix against profile patches,
  `config init --dry-run` output, and `config doctor` pass/warn/fail behavior.
- Updated [config-profiles.md](config-profiles.md) with the human-readable
  smoke matrix.
- Updated [backlog.md](backlog.md) so the next candidate unit is the future
  `deal-intel smoke-profile --profile sample|full|pro` CLI.

Verification:

- Profile smoke matrix targeted tests:
  `8 passed`
- Config profile/doctor/writer regression:
  `40 passed`, `1 warning`
- Full pytest:
  `345 passed`, `1 warning`
- CLI smoke:
  `config profiles`, `config init --profile sample --dry-run`,
  `config doctor --offline`
- ASCII check:
  new source/test/docs files passed
- Diff whitespace check:
  `git diff --check`
- Ruff:
  `All checks passed`

Notes:

- The first targeted pytest attempt failed before tests ran because Windows
  denied access to the default pytest temp root under AppData. Re-running with
  `TEMP`/`TMP` set to workspace `.tmp/pytest` passed.

### Config profiles Z5.6 packaging surface

Implemented:

- Reworked README onboarding to be sample-oriented at that milestone: profile inspection, sample
  dry-run, local sample smoke, then optional Claude Desktop / MongoDB setup.
- Updated `README.ko.md` with the same user-facing sample/full/pro flow.
- Updated `mcpb/README.md` for first-run `local_sample` installs.
- Bumped `mcpb/manifest.json` to `0.1.9`, added `storage_backend`, made
  `mongodb_uri` optional unless `storage_backend=mongo`, and later updated
  bundle metadata to the current 23-tool surface.
- Updated the documentation map, config-profile contract notes, and active
  backlog index.

Verification:

- Manifest JSON parse:
  `version=0.1.9`, `tools=23`, `storage_backend=local_sample`,
  `mongodb_required=False`
- Manifest/server tool-name comparison:
  `server=23`, `manifest=23`, `tool names match`
- CLI dry-run smoke:
  `deal-intel config init --profile sample --dry-run`
- CLI offline doctor smoke:
  `deal-intel config doctor --offline`
- English-source ASCII check:
  `README.md`, `AI_START_HERE.md`, `docs/README.md`, `docs/backlog.md`,
  `docs/config-profiles.md`, `mcpb/README.md`, `mcpb/manifest.json`
- Diff whitespace check:
  `git diff --check`
- Ruff:
  `All checks passed`

Not run:

- `mcpb validate manifest.json`; the `mcpb` CLI is not available on PATH in
  this environment.

### Config profiles Z5.5 AI start-here guide

Implemented:

- Added root-level `AI_START_HERE.md` for AI agents onboarding a new user.
- The guide enforced a sample-oriented flow before asking for MongoDB, API keys,
  Atlas Vector Search, or paid infrastructure.
- It points agents to `config profiles`, `config show`,
  `config init --profile sample --dry-run`, `config doctor --offline`,
  `storage-status`, and `smoke-natural-questions`.
- It tells agents to avoid overwriting existing user config and to use
  `config switch ... --force` only after explicit user approval.
- Linked the guide from `AGENTS.md`, `CLAUDE.md`, `docs/README.md`, and
  [config-profiles.md](config-profiles.md).

Verification:

- Docs are ASCII-only.
- Ruff:
  `All checks passed`

### Config profiles Z5.3 init/switch CLI

Implemented:

- Added `deal_intel.config_writer` for safe profile config writes.
- Added `deal-intel config init --profile sample|full|pro`.
- Added `deal-intel config switch sample|full|pro`.
- Added `--dry-run`, `--force`, and `--json` support for both commands.
- `init` writes a new user config when missing and refuses to overwrite an
  existing config unless `--force` is provided.
- `switch` changes only profile-managed keys:
  `storage.backend`, `mongodb.vector_search`, and `llm.provider`.
- Actual overwrite/switch operations back up the previous config with a
  timestamped `config.yaml.bak.YYYYMMDD-HHMMSS` file.
- Outputs show only profile-managed values and an offline doctor preview; they
  do not print custom config bodies or secrets.

Verification:

- Config writer targeted tests:
  `10 passed`
- Config CLI/doctor/storage regression:
  `30 passed`
- CLI dry-run smoke:
  `config init --profile sample --dry-run` succeeded without writing files
- Full pytest:
  `337 passed`, `1 warning`
- Ruff:
  `All checks passed`

### Config profiles Z5.4 config doctor

Implemented:

- Added `deal_intel.config_doctor` as the shared diagnostic engine for config
  readiness checks.
- Added `deal-intel config doctor`, `deal-intel config doctor --json`, and
  `deal-intel config doctor --offline`.
- Added the read-only MCP tool `config_doctor(offline=false)`.
- The doctor checks the effective profile, user config readability, storage
  backend, MongoDB URI, optional storage ping, vector-search mode, and LLM
  provider readiness without LLM calls, embeddings, or writes.
- Kept diagnostic output secret-safe: environment values, tokens, raw notes,
  contacts, and embeddings are not returned.

Verification:

- Config doctor targeted tests:
  `10 passed`
- Config/storage targeted regression:
  `19 passed`
- MCP registration and related regression:
  `75 passed`
- Full pytest:
  `327 passed`, `1 warning`
- Ruff:
  `All checks passed`
- CLI offline smoke:
  `ok=true`, `profile=full`, `storage_ping=skipped`
- CLI live storage smoke:
  returned a structured `storage_ping` failure because this environment hit a
  DNS timeout while resolving Atlas. No writes were attempted.

### Secret scan cleanup and debt audit

Implemented:

- Investigated the secret detection on commit `89d0aa0`; confirmed it was a
  false positive caused by realistic fake test/doc placeholders, not a real
  credential leak.
- Replaced API-key-shaped and credential-URI-shaped examples with neutral
  placeholders in `.env.example`, README files, and mcpb metadata.
- Updated config CLI tests to use scanner-safe sentinel values while still
  asserting that config output never echoes environment values.
- Recorded the failure mode in [lesson-learned.md](lesson-learned.md).

Audit notes:

- No `eval`, `exec`, `shell=True`, `pickle`, unsafe YAML load, or environment
  dumps were found in the reviewed source/test/doc paths.
- Sensitive fields such as raw meeting notes, contacts, and embeddings are
  intentionally excluded from reporting/metric/gap surfaces and covered by
  existing tests.
- Low-priority technical debt remains around broad best-effort exception
  handling in vector-index setup and malformed timestamp fallback paths.

Verification:

- Secret-like pattern scan:
  `no matches`
- Config/storage targeted tests:
  `22 passed`
- Full pytest:
  `317 passed`, `1 warning`
- Ruff:
  `All checks passed`

### Config profiles Z5.2 inspect CLI

Implemented:

- Added `deal-intel config profiles` for the one-package
  `sample/full/pro` profile catalog.
- Added `deal-intel config show` for the current inferred profile, user config
  path, selected effective config fields, and configured env-key status.
- Kept output secret-safe: environment values are never printed, only
  `configured: true/false`.
- Added `_env.user_config_path()` so CLI and tests do not need to duplicate the
  user config path.

Verification:

- Z5.2 targeted tests:
  `22 passed`
- Full pytest:
  `317 passed`, `1 warning`
- Ruff:
  `All checks passed`

### Config profiles Z5.1 profile contract

Implemented:

- Added `deal_intel.config_profiles` with one-codebase profile definitions for
  `sample`, `full`, and `pro`.
- Added reusable profile config patches for future config CLI commands.
- Added profile inference for effective config:
  `local_sample` -> `sample`, Mongo + Atlas vector search -> `pro`,
  otherwise `full`.
- Documented the Z5 plan in [config-profiles.md](config-profiles.md).

Verification:

- Z5.1 targeted tests:
  `17 passed`
- Full pytest:
  `312 passed`, `1 warning`
- Ruff:
  `All checks passed`

### Zero-config sample mode Z4 startup diagnostics

Implemented:

- Added `deal_intel.storage.diagnostics` with the shared local sample mode hint.
- Updated Mongo missing-URI `ping()` and runtime errors to explain both paths:
  set `MONGODB_URI` for Atlas, or use `DEAL_INTEL_STORAGE_BACKEND=local_sample`
  for bundled sample mode.
- Added `deal_intel.cli storage-status` for install checks, local demos, and
  agent smoke tests.
- Documented the zero-config sample quickstart in README and
  [storage-backends.md](storage-backends.md).

Verification:

- Z4 targeted tests:
  `25 passed`
- Local sample storage-status CLI smoke:
  `ok=true`, `storage_backend=local_sample`, `deal_count=12`,
  `snapshot_count=24`
- Local sample natural-question CLI smoke:
  `OK: True`, `derived=3`, `direct=5`, `Sensitive failures: none`,
  `Blocked questions: none`
- Full pytest:
  `300 passed`, `1 warning`
- Ruff:
  `All checks passed`

### Zero-config sample mode Z3 local sample backend

Implemented:

- Added `deal_intel.storage.local_sample.LocalSampleClient`.
- Added `storage.backend: mongo | local_sample` to defaults.
- Added `DEAL_INTEL_STORAGE_BACKEND=local_sample` as a temporary env override.
- Updated `_context.mongo()` to select `MongoDBClient` or `LocalSampleClient`
  while preserving the existing tool-call surface.
- Local sample mode now skips Mongo driver preload, Mongo index creation, and
  embedding warmup during MCP startup.
- `search_deals` now returns a structured unsupported-mode response in local
  sample mode before touching embeddings.
- Fixed the bundled fixture so the natural-question smoke pack's PayBridge
  question resolves to `PayBridge` instead of falling back to the first deal.

Verification:

- Z3 targeted tests:
  `28 passed`
- Local sample natural-question CLI smoke:
  `OK: True`, `derived=3`, `direct=5`, `Sensitive failures: none`,
  `Blocked questions: none`
  with `DEAL_INTEL_STORAGE_BACKEND=local_sample`
- Full pytest with workspace-local temp:
  `295 passed`
- Ruff:
  `All checks passed`

### Zero-config sample mode Z2 bundled fixture

Implemented:

- Added `deal_intel.storage.local_sample_fixture`.
- Added a safe bundled fictional data pack for MongoDB-free demos and agent
  smoke tests.
- Included 12 current deal documents across all canonical stages.
- Included all deal value statuses:
  `unknown`, `rough_estimate`, `customer_budget`, `quoted`, and
  `strategic_zero`.
- Added 7-day analytics snapshots so `pipeline_trend` can return meaningful
  movement without Atlas.
- Kept the fixture free of `meetings.raw_notes`, `contacts`, and
  `summary_embedding`.
- Added fixture validation and summary helpers for future zero-config
  diagnostics.

Verification:

- Zero-config sample fixture tests:
  `5 passed`
- Full pytest with workspace-local temp:
  `280 passed`
- Ruff:
  `All checks passed`

### Zero-config sample mode Z1 storage contract

Implemented:

- Added `deal_intel.storage.backend`.
- Defined the `local_sample_mvp` read-only storage contract before adding a
  `LocalSampleClient`.
- Added `SampleReadStorageBackend`, storage method contracts, capability
  reporting, and validation helpers.
- Fixed the first sample-mode support boundary:
  `ping`, `get_deal`, `list_deals`, `list_deals_for_metrics`, and
  `list_analytics_snapshots`.
- Documented deferred paths such as Mongo aggregations, semantic search,
  write tools, and admin/index setup in [storage-backends.md](storage-backends.md).

Verification:

- Storage backend contract tests:
  `6 passed`
- Full pytest with workspace-local temp:
  `275 passed`
- Ruff:
  `All checks passed`

### Natural question smoke CLI

Implemented:

- Added `deal-intel smoke-natural-questions`.
- The command runs a deterministic pack of eight realistic natural-language
  questions without requiring Claude Desktop or another MCP client.
- The pack combines existing read-only payloads from pipeline metrics, deal
  review, deal gaps, and customer-theme evidence.
- It writes `summary.md`, `summary.json`, and per-question JSON files under
  `outputs/smoke/...`.
- It is a developer/QA CLI, not a user-facing MCP tool.
- Raw meeting notes, contacts, and embeddings remain excluded from the saved
  artifacts.

Verification:

- CLI targeted tests:
  `12 passed`
- Full pytest with workspace-local temp:
  `269 passed`
- Ruff:
  `All checks passed`
- Live Atlas read-only smoke:
  `smoke-natural-questions --as-of 2026-06-10` returned `OK: True`,
  `derived=3`, `direct=5`, `Sensitive failures: none`, and
  `Blocked questions: none`
- Live smoke artifacts saved locally:
  `outputs/smoke/natural-question-pack-20260610_200827/summary.md`

### Deal review Calibration v2

Implemented:

- Tightened `verified_healthy`.
  - It now requires high evidence coverage, no missing information, no
    confirmed risk rows, and confirmed data quality.
  - Healthy-looking deals with open questions are downgraded to
    `promising_but_unproven`.
  - Healthy-looking deals with confirmed risk rows are downgraded to
    `watch_with_evidence`.
- Tightened `low` uncertainty.
  - Missing information, rough estimates, invalid value classification, or
    unconfirmed data quality now prevent `low` uncertainty.
- Added `forecast_confidence` to deal review interpretation.
  - Values include `quoted`, `strategic_zero`, `customer_indicated`,
    `estimated`, `unknown`, and `invalid`.
- Extended the audit smoke rules so `verified_healthy` and `low` uncertainty
  cannot hide open gaps, risk rows, or unconfirmed data.

Verification:

- Calibration targeted tests:
  `22 passed`
- Full pytest with workspace-local temp:
  `267 passed`
- Ruff:
  `All checks passed`
- Live Atlas read-only audit smoke:
  `smoke-deal-review-audit --as-of 2026-06-10 --limit 50` reviewed `22`
  deals and returned `Sensitive field check: passed`, `Quality rules: passed`
- 10-set live smoke artifacts saved locally:
  `outputs/smoke/deal-review-calibration-v2-20260610_175009/summary.md`

Observed calibration delta:

- Before v2:
  `verified_healthy=19`, `watch_with_evidence=2`, `low uncertainty=21`,
  `medium uncertainty=0`, `watch alert=8`
- After v2:
  `verified_healthy=10`, `watch_with_evidence=8`,
  `promising_but_unproven=3`, `low uncertainty=12`,
  `medium uncertainty=9`, `watch alert=11`

### Deal review audit smoke pack

Implemented:

- Added `deal-intel smoke-deal-review-audit`.
- The command audits selected deal reviews through the restricted metrics read
  path without requiring Claude Desktop or another MCP client.
- Supports `--company`, `--stage`, `--industry`, `--limit`, `--as-of`,
  `--json`, and `--fail-on-issues`.
- Summarizes alert levels, uncertainty levels, review bands, warnings, quality
  issue counts, and top review targets.
- Added deterministic quality rules for:
  - win-probability suppression
  - low-evidence healthy overconfidence
  - confirmed risk alert consistency
  - missing information follow-up questions
  - confirmed risk follow-up actions
  - closed-deal postmortem gap reporting
  - accidental percentage estimates in guidance
  - sensitive field exposure
- Fixed deal review alert interpretation so any confirmed risk row raises the
  review to at least `watch`.

Verification:

- Deal review audit CLI targeted tests:
  `10 passed`
- Related deal review regression tests:
  `21 passed`
- Full pytest with workspace-local temp:
  `266 passed`
- Ruff:
  `All checks passed`
- Live Atlas read-only audit smoke:
  `smoke-deal-review-audit --as-of 2026-06-10 --limit 50` reviewed `22`
  deals, returned `Sensitive field check: passed`, `Quality rules: passed`,
  and moved confirmed-risk rows from `alert=none` to `watch`

### Deal review local smoke CLI

Implemented:

- Added `deal-intel smoke-deal-review`.
- The command exercises the same read-only `get_deal_review` handler path
  without requiring Claude Desktop or another MCP client.
- Supports exact `--deal-id`, company substring `--company`, `--limit`,
  `--as-of`, and `--json`.
- Text output summarizes review band, alert level, uncertainty, evidence
  coverage, missing information, confirmed risks, recommended questions, and
  warnings.
- JSON output returns the full structured tool response for repeatable local
  smoke checks.
- Successful smoke output omits raw notes, contacts, embeddings, and even the
  restricted field names themselves.

Verification:

- New CLI targeted tests:
  `5 passed`
- Related deal review regression tests:
  `15 passed`
- Full pytest with workspace-local temp:
  `260 passed`
- Ruff:
  `All checks passed`
- Live Atlas read-only smoke:
  `smoke-deal-review --as-of 2026-06-10 --limit 2` returned two deal reviews
  and `Sensitive field check: passed`

### Deal review quality hardening

Implemented:

- Added `get_deal_review` MCP tool.
- Added deterministic `deal_review` calculation module.
- Separated legacy `health_pct` from MEDDPICC evidence coverage.
- Added `uncertainty_level`, `review_band`, and `alert_level`.
- Added explicit `missing_information`, `confirmed_risks`,
  `known_signals`, `recommended_questions`, and `recommended_actions`.
- Suppressed uncalibrated win-probability numbers in review responses.
- Kept the read path free of LLM calls, embedding calls, and MongoDB writes.
- Used the restricted metrics projection so raw notes, contacts, and
  embeddings remain excluded.

Verification:

- `tests/test_deal_review.py`:
  `10 passed`
- Related MCP/read-path regression tests:
  `54 passed`
- Full pytest with workspace-local temp:
  `255 passed`
- Ruff:
  `All checks passed`
- FastMCP registration smoke:
  `21` tools, `get_deal_review` registered
- Live Atlas read-only smoke:
  `deal_count=22`, `ok=true`, first reviewed deal returned
  `review_band=verified_healthy`, `alert_level=none`,
  `warnings=win_probability_suppressed`

### BI Reporting Milestone 6.1-M6.3 Customer Themes expansion

Implemented:

- Added `get_customer_theme_breakdown` MCP tool.
  - Compares curated customer themes by `stage`, `industry`, or `dimension`.
  - Supports `dimension`, `stage`, `industry`, `group_by`, and `top_k`.
- Added `get_customer_theme_evidence` MCP tool.
  - Returns curated evidence snippets for one `theme_key`.
  - Supports `dimension`, `stage`, `industry`, `limit`, and `min_importance`.
- Added pure `customer_theme_insights` calculation module for breakdown and
  drill-down behavior.
- Added versioned Atlas Charts spec:
  `atlas/charts/customer_themes.v1.json`.
- Added `Customer Themes Review` dashboard source over `deals`.
- Extended `render-atlas-dashboard` with `--dashboard customer_themes`.
- Kept the M6 read paths free of LLM calls, embedding calls, and MongoDB
  writes.
- Raw meeting notes, contacts, and embeddings remain excluded from the new
  read paths.

Verification:

- M6.1-M6.2 targeted tests:
  `18 passed`
- M6.3 Atlas chart targeted tests:
  `15 passed`
- M6 related regression tests:
  `69 passed`
- Full pytest with workspace-local temp:
  `245 passed`
- Ruff:
  `All checks passed`
- CLI render smoke:
  `render-atlas-dashboard --dashboard customer_themes --chart-id theme_overview`
  printed a rendered Atlas aggregation pipeline
- Live Atlas read-only smoke:
  `get_customer_theme_breakdown` returned `deals_analyzed=13`,
  `deals_with_evidence=13`, `group_count=4`; `get_customer_theme_evidence`
  returned `unique_deal_count=10`, `evidence_count=21`; Customer Themes Atlas
  aggregations returned rows for all 4 charts

### BI Reporting Milestone 5.8 Atlas trend chart

Implemented:

- Added versioned Atlas Charts spec:
  `atlas/charts/pipeline_trend.v1.json`.
- Added `Pipeline Trend Review` dashboard source over
  `analytics_snapshots`.
- Added chart pipelines:
  `trend_kpis` and `trend_delta_bars`.
- Extended `render-atlas-dashboard` with:
  `--dashboard pipeline_trend` and `--lookback-days`.
- Added `MongoDBClient.aggregate_analytics_snapshots()` for read-only Atlas
  pipeline smoke tests.
- No LLM, embedding, or MongoDB writes are used by the trend chart path.

Verification:

- M5.8 targeted tests:
  `20 passed`
- Related Atlas/report/trend regression tests:
  `34 passed`
- Full pytest with workspace-local temp:
  `234 passed`
- Ruff:
  `All checks passed`
- CLI render smoke:
  `render-atlas-dashboard --dashboard pipeline_trend --chart-id trend_kpis`
  wrote rendered JSON with no unresolved placeholders
- Live Atlas aggregation smoke:
  `trend_kpis=1 row`, `trend_delta_bars=3 rows`

Manual follow-up:

- Create or update the Atlas Charts dashboard named `Pipeline Trend Review`
  using [atlas-charts.md](atlas-charts.md). This is a manual Atlas UI step.

## History

### BI Reporting Milestone 5.7 trend CSV

Implemented:

- Added `export_report(report_type="pipeline_trend")`.
- Added `lookback_days`, default `7`, max `365`, for trend reports.
- Added pipeline trend CSV rows for KPI start/end/delta and stage movement.
- Added LLM-free Markdown summary for pipeline trend reports.
- Reused the M5.6 `build_pipeline_trend_summary()` calculator.
- Trend report reads only `analytics_snapshots` through
  `list_analytics_snapshots()` and does not read deal raw notes.
- No LLM, embedding, or MongoDB writes are used by the trend export path.

Verification:

- M5.7 targeted tests:
  `17 passed`
- Related report/trend regression tests:
  `33 passed`
- Full pytest with workspace-local temp:
  `228 passed`
- Ruff:
  `All checks passed`
- Live Atlas read-only smoke:
  `ok=true`, `report_type=pipeline_trend`, `snapshot_count=0`, `row_count=7`,
  expected sparse-history warnings returned, CSV/Markdown artifacts created

### OpenAI API LLM provider support

Implemented:

- Added `OpenAIAPIProvider` using the official OpenAI Responses API.
- Added `llm.provider: openai_api`.
- Added `llm.openai_api_model` and `llm.openai_api_reasoning_effort`.
- Added `OPENAI_API_KEY` support through `.env` and MCP bundle user config.
- Added `DEAL_INTEL_LLM_PROVIDER` as the explicit provider override while
  preserving legacy `DEAL_INTEL_USE_CHATGPT_OAUTH` behavior.
- Bumped the MCP bundle manifest to `0.1.8`.
- Kept the then-current MCP tool surface unchanged.

Verification:

- OpenAI provider targeted tests:
  `10 passed`
- Related LLM/provider regression tests:
  `27 passed`
- Full pytest with workspace-local temp:
  `226 passed`
- Ruff:
  `All checks passed`
- MCP bundle manifest JSON:
  valid
- Live OpenAI API smoke:
  not run because this environment does not currently have API credits/key;
  provider behavior is covered with mock HTTP tests.

### BI Reporting Milestone 5.6 pipeline_trend metric

Implemented:

- Added `get_metrics(metric_type="pipeline_trend")`.
- Added `lookback_days`, default `7`, max `365`.
- Added `MongoDBClient.list_analytics_snapshots()` with a restricted
  projection over `analytics_snapshots`.
- Added pure `build_pipeline_trend_summary()` calculator.
- Trend output compares the window start and end latest snapshots by deal.
- Trend output includes active/open counts, open pipeline value, average health,
  attention count, won/lost counts, stage transitions, and data sufficiency
  warnings.
- Duplicate `event_id` snapshots are ignored defensively by the calculator.
- No LLM, embedding, or MongoDB writes are used by the trend read path.

Verification so far:

- M5.6 targeted tests:
  `24 passed`
- Related BI regression tests:
  `21 passed`
- Full pytest with workspace-local temp:
  `216 passed`
- Ruff:
  `All checks passed`
- Live Atlas read smoke:
  `ok=true`, `metric_type=pipeline_trend`, `lookback_days=7`,
  `snapshot_count=0`, expected insufficiency warnings returned

### BI Reporting Milestone 5.1-5.5 analytics snapshot foundation

Implemented:

- Added an internal `analytics_snapshots` write model for trend analysis.
- Added idempotent snapshot storage keyed by `event_id`.
- Added snapshot indexes for `event_id`, `deal_id + occurred_at`, and
  `event_type + occurred_at`.
- Connected snapshots to `create_deal`, `add_meeting`, and `update_stage`.
- Snapshot failures do not block the original deal mutation; tool responses
  include an `analytics_snapshot` warning object instead.
- Snapshot documents store only lightweight BI state:
  deal metadata, value fields, stage, health band, MEDDPICC gaps, timing, and
  attention reasons.
- Snapshot documents do not store raw meeting notes, contacts, or embeddings.

Verification so far:

- New targeted tests:
  `6 passed`
- Related regression tests:
  `58 passed`
- Full pytest with workspace-local temp:
  `203 passed`
- Ruff:
  `All checks passed`
- Live Atlas write smoke:
  first insert `true`, duplicate insert `false`, found before cleanup `1`,
  cleanup deleted `1`

### BI Reporting Milestone 4.4 onboarding/demo sample data

Implemented:

- Added MCP tools: `create_sample_data`, `delete_sample_data`.
- FastMCP registration target was updated for the then-current tool surface.
- Added `mongodb.demo_database`, default `deal_intel_demo`.
- Sample tools reject any demo database equal to the primary
  `mongodb.database`.
- `create_sample_data` writes fictional `weekly_pipeline_demo` deals only to
  the resolved demo database.
- `delete_sample_data` deletes only documents matching `is_sample=true` and
  the known `sample_batch_id`.
- Both tools default to `dry_run=true`.
- Actual create/delete requires `confirmed_by_user=true`.
- No LLM, embedding, or production database writes are used by the sample-data
  workflow.

Verification so far:

- Targeted tests with workspace-local temp:
  `32 passed`
- Command:
  `pytest tests/test_sample_data.py tests/test_get_metrics.py tests/test_export_report.py tests/test_get_deal_gaps.py tests/test_deal_lifecycle.py -q --basetemp .tmp\pytest-m44-targeted`
- Full pytest with workspace-local temp:
  `197 passed`
- Ruff:
  `All checks passed`
- Live Atlas demo DB dry-run smoke:
  `create_ok=true`, `create_storage_written=false`,
  `delete_ok=true`, `delete_storage_written=false`,
  demo database `deal_intel_demo`, existing sample count `0`

### BI Reporting Milestone 4.3 deal lifecycle safety layer

Implemented:

- Added MCP tools: `archive_deal`, `restore_deal`, `delete_deal`.
- FastMCP registration target is now 16 tools.
- `archive_deal` marks a deal archived and hides it from default BI/read paths.
- `restore_deal` returns an archived deal to default BI/read paths.
- `delete_deal` defaults to `dry_run=true`.
- Actual hard delete requires:
  - `confirmed_by_user=true`
  - exact `expected_company` match after trimming whitespace
  - non-empty `delete_reason`
  - already archived deal
- Hard delete writes one `delete_audit_logs` entry before deletion.
- Delete audit snapshots exclude `_id`, `contacts`, `summary_embedding`, and
  `meetings.raw_notes`.
- `get_deal` still returns archived deals and adds `warnings=["deal_archived"]`.

Archived read-path contract:

```json
{"archived": {"$ne": true}}
```

This keeps legacy documents visible when they do not have an `archived` field.

Updated read paths:

- `MongoDBClient.list_deals`
- `MongoDBClient.list_deals_for_metrics`
- `MongoDBClient.list_deals_for_theme_backfill`
- `MongoDBClient.get_deals_for_search`
- `MongoDBClient.search_by_embedding`
- `get_insights` direct aggregation paths
- `get_customer_themes` scope queries

Verification so far:

- Targeted tests with workspace-local temp:
  `49 passed`
- Command:
  `pytest tests/test_deal_lifecycle.py tests/test_archived_read_paths.py tests/test_data_quality_reporting.py tests/test_customer_themes.py tests/test_get_metrics.py tests/test_get_deal_gaps.py tests/test_export_report.py -q --basetemp .tmp\pytest-m43-targeted`
- Full pytest with workspace-local temp:
  `189 passed`
- Ruff:
  `All checks passed`
- Live Atlas read-only dry-run smoke:
  `ok=true`, `dry_run=true`, `storage_written=false`,
  visible deal count `22`, `would_delete=false`

### BI Reporting Milestone 4.2 update_deal metadata extension

Completed before M4.3:

- Extended `update_deal` beyond value fields to selected metadata:
  `company`, `industry`, `expected_close_date`, `actual_close_date`,
  `close_reason`.
- All mutations require `confirmed_by_user=true`.
- Value updates require `deal_size_note`.
- Metadata updates require `update_note` or fallback `deal_size_note`.
- `expected_close_date` is allowed only for open deals and records
  `expected_close_date_source=user_provided`.
- `actual_close_date` is allowed only for won/lost deals.
- `close_reason` is allowed only for lost deals.
- Stage transitions remain exclusively in `update_stage`.
- Metadata changes append `deal_metadata_history`.

Verification:

- Targeted `tests/test_update_deal.py`: `16 passed`
- Full pytest at completion: `176 passed`
- Ruff: passed
- Live Atlas no-op smoke: `ok=true`, `storage_written=false`, `changed=[]`

## Next

1. M6 Customer Themes expansion.
