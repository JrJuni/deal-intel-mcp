# Distribution Plan: Git Clone, uvx, npx, and MCPB

This plan keeps MVP priorities straight:

1. The first external MVP can ship with an AI-assisted git-clone path.
2. No-git-clone wrappers are useful, but they should not block the current
   full-by-default MVP readiness path.
3. Wrapper work should be mechanical only after the Python package is safe to
   run outside a repo checkout.
4. Post-v1 wrapper work should produce a full bootstrapper, not a thin wrapper
   that merely moves the Python path problem into Node.js.

## Current MVP Distribution

Supported today:

- Git clone.
- Conda or existing Python 3.11+ interpreter.
- `pip install -e ".[dev,embedding]"` for development, or `pip install -e .`
  for a lightweight install.
- Claude Desktop MCPB bundle that points at the user-selected Python
  interpreter.
- `full` profile for the default human install path.
- `sample` profile for zero-config AI evaluation or demos.
- Safe user-memory tools for repo-local operating preferences and feedback.

This is acceptable for the first MVP because the target user can ask an AI
assistant to clone the repo, run setup commands, and configure Claude Desktop.
Point that assistant at `AI_START_HERE.md` first.

## Packaging Constraint

The Python package now has the first wheel/uvx-readiness layer, but wrappers
should still be treated as a follow-up distribution surface.

Current contract:

- Editable repo installs keep reading repo-root `config/defaults.yaml` and
  `atlas/charts/*.json` first.
- Wheel/uvx-style installs fall back to packaged resources under
  `deal_intel.resources`.
- `.env` is still loaded from the repo/runtime root, not from packaged
  resources.
- MCPB user-config secrets are injected as runtime environment variables when
  Claude Desktop starts the server; local CLI commands still need `.env` or
  shell environment variables for equivalent live checks.

Implication:

- A plain wheel or `uvx deal-intel-mcp` install has the config/dashboard
  resources it needs.
- A Node `npx` bridge can work around this by copying the npm package into a
  stable runtime directory and installing that copy in editable mode, but that
  adds a Node maintenance surface.

## Recommended Sequence

### D0. Package-data readiness

Goal: make the Python package runnable without assuming a git checkout.

Status: implemented as a first pass.

Tasks:

- Include `config/defaults.yaml` and required Atlas/chart specs as package
  data.
- Replace repo-root config reads with `importlib.resources` fallback logic.
- Keep `.env` loading from the runtime working directory or explicit user path,
  not from package resources.
- Keep `pyproject.toml`, MCPB manifest, and future npm package versions aligned.
- Add a wheel smoke:
  `python -m pip wheel . --no-deps --wheel-dir .tmp/wheelhouse`.
- Install that wheel into an isolated env or temp target and run
  `deal-intel config doctor --offline`.

Why first:

- This lowers risk for both `uvx` and `npx`.
- It also makes future PyPI packaging cleaner.

### D1. External MVP trial readiness

Goal: prove that the current git-clone plus editable-install path is clear
enough for a first external evaluator before adding wrapper maintenance.

Current status: first-pass checklist implemented; full sign-off still requires
the gates in `docs/mvp-readiness.md`.

Scope boundary: D1 is a first-run distribution gate, not deep MongoDB feature
validation. The human-facing trial should start in `full`. `sample` is an
optional zero-config path for AI evaluation or demos. MongoDB ecosystem work
must be validated against the `full` profile, with `pro` added only for
paid-infra paths such as Atlas Vector Search.

Tasks:

- Keep README, AI start guide, MCPB README, and this distribution plan aligned
  on the same full-by-default install story.
- Verify that `config doctor --offline` and
  `smoke-profile --profile full --offline` are the first recommended human
  setup checks.
- Keep `sample` smoke documented as an optional zero-config evaluation path.
- Keep tool surface counts aligned with the runtime contract:
  `sample=23`, `standard=27`, `developer=30`.
- Keep user-memory, canonical interaction intake, industry metadata, and local
  personal data commands represented in the MVP checklist.
- Record any live MongoDB or MCPB reinstall checks that could not be completed
  as non-blocking risks in `docs/status.md`.

MongoDB-backed feature checks belong outside D1:

- `smoke-profile --profile full --offline`
- current-config `config doctor --offline`
- targeted storage/index/schema tests
- bounded Atlas read/write smoke when the change touches live persistence

Why this comes before wrappers:

- It tests the experience users have today.
- It prevents npx/uvx work from covering over unclear product setup language.
- It gives a concrete checklist for friend-review and AI-assisted setup without
  turning the demo profile into the product default.

### D2. uvx/PyPI-style Python distribution

Goal: provide a Python-native no-repo command path.

Target UX after publish:

```bash
uvx deal-intel-mcp config doctor --offline
uvx deal-intel-mcp smoke-profile --profile sample
uvx deal-intel-mcp smoke-natural-questions --as-of 2026-06-10
```

Pros:

- Smallest conceptual surface for a Python MCP project.
- No Node bridge needed.
- Easier to keep versioning and dependencies in one ecosystem.

Cons:

- Requires users to have or install `uv`.
- Claude Desktop MCPB still needs a configured Python command or launcher.
- Needs package-data readiness first.

### D3. Full npx bootstrapper

Goal: provide a true no-git-clone command path once the product architecture is
stable enough for a broader non-developer install surface.

Target UX after npm publish:

```bash
npx deal-intel-mcp setup
npx deal-intel-mcp doctor
npx deal-intel-mcp smoke
npx deal-intel-mcp mcp
```

Pros:

- Familiar to many AI-assisted setup flows.
- Can guide Python discovery, package installation, config checks, sample/full
  profile selection, and MCP startup from one entry point.
- Can avoid requiring users to learn `uv`.

Cons:

- Still needs Python.
- Adds a second packaging ecosystem.
- Must be careful not to hide Python install failures behind Node errors.
- Should not become a second implementation of the app.
- Should not ship as a thin wrapper that still requires users to understand
  Python interpreter paths before they can try the product.

### D4. MCPB installer polish

Goal: make Claude Desktop install less brittle.

Tasks:

- Rebuild MCPB after manifest changes.
- Reinstall smoke in Claude Desktop.
- Keep MCPB user config labels friendly for non-developers.
- Decide whether signing is needed before broader external release.

## Which Distribution To Implement First?

Recommendation: **D1 external MVP readiness first. Defer no-clone wrappers
until after the post-v1 product-shape work.**

Reason:

- D0 already fixed the first package portability layer.
- D1 validates the current external trial path before new wrappers are added.
- The next high-priority work is product architecture and extensibility:
  architecture-map expansion, qualification-framework abstraction, tool/theme
  cleanup, MongoDB Pro path, and report/review quality.
- D2 can still be useful as a Python-native distribution layer and may become
  infrastructure for D3.
- D3 should be implemented as a full bootstrapper near the end of the post-v1
  sequence, not as the first packaging follow-up.

If the product goal shifts toward a Claude Desktop-first non-developer audience
before v2 architecture work finishes, revisit D3. The bar should still be a
complete guided bootstrapper, not a thin command alias.

## Acceptance Criteria

For any implemented distribution path:

- `sample` profile runs without MongoDB or API keys.
- `config doctor --offline` gives a useful result.
- Natural smoke runs on local sample data.
- The command path does not print secrets.
- The command path has a documented failure mode for missing Python, missing
  OAuth login, missing MongoDB URI, and missing API keys.
- The wrapper does not reimplement MCP tool behavior.

## Deferred

- Automatic Python installation.
- Automatic Claude Desktop config mutation.
- Signed release bundles.
- One-click GUI installer.
- Pro profile full live validation.
