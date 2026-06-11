# Distribution Plan: Git Clone, uvx, npx, and MCPB

This plan keeps MVP priorities straight:

1. The first external MVP can ship with an AI-assisted git-clone path.
2. No-git-clone wrappers are useful, but they should not block sample/local MVP
   readiness.
3. Wrapper work should be mechanical only after the Python package is safe to
   run outside a repo checkout.

## Current MVP Distribution

Supported today:

- Git clone.
- Conda or existing Python 3.11+ interpreter.
- `pip install -e ".[dev,embedding]"` for development, or `pip install -e .`
  for a lightweight install.
- Claude Desktop MCPB bundle that points at the user-selected Python
  interpreter.
- `sample` profile for zero-config evaluation.

This is acceptable for the first MVP because the target user can ask an AI
assistant to clone the repo, run setup commands, and configure Claude Desktop.

## Packaging Constraint

The Python package is not fully wheel/uvx-safe yet.

Current constraint:

- `src/deal_intel/_env.py` resolves `_ROOT = Path(__file__).resolve().parents[2]`
  and reads `config/defaults.yaml` from the repo root.
- Atlas specs, config defaults, docs, and MCPB metadata currently live beside
  the repo, not as package resources.
- `pyproject.toml` version is not currently the same as `mcpb/manifest.json`.

Implication:

- A plain wheel or `uvx deal-intel-mcp` install would need packaged resource
  handling before it can behave like the editable repo install.
- A Node `npx` bridge can work around this by copying the npm package into a
  stable runtime directory and installing that copy in editable mode, but that
  adds a Node maintenance surface.

## Recommended Sequence

### D0. Package-data readiness

Goal: make the Python package runnable without assuming a git checkout.

Tasks:

- Include `config/defaults.yaml` and required Atlas/chart specs as package
  data.
- Replace repo-root config reads with `importlib.resources` fallback logic.
- Keep `.env` loading from the runtime working directory or explicit user path,
  not from package resources.
- Align `pyproject.toml`, MCPB manifest, and future npm package versions.
- Add a wheel smoke:
  `python -m pip wheel . --no-deps --wheel-dir .tmp/wheelhouse`.
- Install that wheel into an isolated env or temp target and run
  `deal-intel config doctor --offline`.

Why first:

- This lowers risk for both `uvx` and `npx`.
- It also makes future PyPI packaging cleaner.

### D1. uvx/PyPI-style Python distribution

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

### D2. npx wrapper

Goal: provide a familiar "try this command" path for users who already have
Node.js.

Target UX after npm publish:

```bash
npx deal-intel-mcp setup --python /path/to/python --profile sample
npx deal-intel-mcp doctor --python /path/to/python --offline
npx deal-intel-mcp smoke --python /path/to/python
```

Pros:

- Familiar to many AI-assisted setup flows.
- Can bundle a launcher that guides setup and copies runtime files.
- Can avoid requiring users to learn `uv`.

Cons:

- Still needs Python.
- Adds a second packaging ecosystem.
- Must be careful not to hide Python install failures behind Node errors.
- Should not become a second implementation of the app.

### D3. MCPB installer polish

Goal: make Claude Desktop install less brittle.

Tasks:

- Rebuild MCPB after manifest changes.
- Reinstall smoke in Claude Desktop.
- Keep MCPB user config labels friendly for non-developers.
- Decide whether signing is needed before broader external release.

## Which Distribution To Implement First?

Recommendation: **D0 first, then D1 uvx**.

Reason:

- D0 fixes the underlying package portability problem.
- D1 keeps the first no-git-clone path Python-native.
- npx remains useful later as a convenience wrapper, but it should delegate to
  the same package-ready Python entry points instead of carrying product logic.

If the product goal shifts toward a Claude Desktop-first non-developer audience,
then D2 can move ahead of D1, but it should still remain a thin wrapper.

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
