# Lessons Learned

Append-only failure log. English is the source language. Korean summaries
belong only in `README.ko.md` and `AGENTS.ko.md`.

Use this file when a failure repeats or when a runbook needs historical
context. Prefer current code, tests, `docs/README.md`, and contract docs for
ordinary implementation work.

## Entry Format

```text
## [YYYY-MM-DD] Topic

Tried: what was attempted
Result: what failed and how it was observed
Lesson: what to do next time
Related: files or docs
```

---

## [2026-06-11] Secret scanner false positive from realistic placeholders

Tried: Use realistic fake values in docs and CLI config tests, including
API-key-shaped strings and credential-bearing MongoDB URI-shaped sentinels.

Result: Commit `89d0aa0` was flagged by secret scanning even though no real
credential was committed. The detector was correct: the fake values had the
same shape as production secrets.

Lesson:

- Do not use realistic provider key prefixes or credential-bearing MongoDB URI
  examples in fixtures or docs.
- Prefer neutral placeholders such as `replace-with-openai-api-key` and
  scanner-safe sentinel values such as `configured-openai-key-sentinel`.
- Keep tests asserting that config output does not echo secret values, but make
  the test inputs scanner-safe.

Related: `.env.example`, `README.md`, `README.ko.md`, `mcpb/manifest.json`,
`tests/test_cli_config_profiles.py`.

---

## [2026-06-08] mcpb Windows path quoting failure

Tried: Use `cmd.exe /c <launcher.bat path>` in the mcpb manifest so the bundle
could auto-discover a Python environment.

Result: Claude Desktop installed the extension under a path containing spaces.
Electron and `cmd.exe` quoting layers fought each other. Without quotes, the
path split at the space. With escaped quotes, the quote characters became part
of the path.

Lesson:

- Do not use `cmd.exe` as `mcp_config.command` for mcpb bundles.
- Use the user-selected Python interpreter directly:
  `"command": "${user_config.python_path}"`, `"args": ["-m", "<module>"]`.
- If auto-discovery is needed, implement it in Python rather than a batch file.

Related: `mcpb/manifest.json`.

---

## [2026-06-08] sentence_transformers pre-import caused startup timeout

Tried: Pre-import `sentence_transformers` inside `mcp_server.py::main()` to
avoid first-request worker-thread import issues.

Result: Importing torch and transformers took several seconds before FastMCP
opened stdio. Claude Desktop disconnected before the server was ready.

Lesson:

- Do not pre-import heavy ML frameworks during MCP startup.
- Only pre-import modules whose import time is comfortably below the startup
  budget.
- Keep embedding model creation lazy or backgrounded after stdio is ready.

Related: `src/deal_intel/mcp_server.py`,
`src/deal_intel/providers/embedding.py`.

---

## [2026-06-08] search_deals hung until the Claude Desktop timeout

Tried: Diagnose a `search_deals` request that hung for about four minutes.
Early guesses focused on MongoDB sockets and warmup duration.

Result: The real blocker was the `SentenceTransformer()` constructor checking
HuggingFace Hub without a bounded timeout. The warmup thread held the embedding
lock while waiting, and request-time `embed()` calls waited on the same lock.

Lesson:

- MCP handlers must check readiness before calling blocking embedding work.
- Return structured `warming_up` or `load_error` responses before embedding.
- Move index creation and other maintenance work out of the first tool-call
  path.
- Protect shared singleton initialization with locks.
- Keep offline-mode behavior explicit where network checks can hang.

Related: `src/deal_intel/providers/embedding.py`,
`src/deal_intel/mcp_server.py`, `src/deal_intel/_context.py`,
`tests/test_search_deals_startup.py`.

---

## [2026-06-08] CPU-only embedding load was slowed by device auto-detection

Tried: Load `SentenceTransformer(model_name)` without an explicit device.

Result: CPU-only environments spent extra time probing GPU/CUDA availability.

Lesson:

- In CPU-only local deployments, pass `device="cpu"` explicitly.
- Do not rely on device auto-detection when startup latency matters.

Related: `src/deal_intel/providers/embedding.py`.

---

## [2026-06-08] Warmup guard was documented but not enforced in the handler

Tried: Add background embedding warmup and document readiness behavior.

Result: `search_deals` still called `embed()` without checking readiness first.
Documentation said the guard existed, but the runtime handler did not enforce
it.

Lesson:

- Treat executable tests as ground truth, not completion notes.
- After adding background warmup, add protocol-level tests proving the handler
  returns immediately while the model is not ready.
- Keep idempotent DB maintenance out of user request paths.

Related: `src/deal_intel/mcp_server.py`, `src/deal_intel/_context.py`,
`tests/test_search_deals_startup.py`.

---

## [2026-06-08] Native ML import stalled from a background thread on Windows

Tried: Start FastMCP stdio and import native ML libraries for the first time
from a background thread.

Result: NumPy/SciPy native module initialization stalled with no useful CPU
activity. Loading the same stack from the main thread completed normally.

Lesson:

- On Windows, do not first-import native ML runtimes from a background thread.
- Pre-import lightweight native modules on the main thread when needed, then
  create the model in the background after startup.
- Surface warmup phase and elapsed time; after the configured budget, return a
  stalled warmup error instead of hanging.

Related: `src/deal_intel/mcp_server.py`,
`src/deal_intel/providers/embedding.py`.

---

## [2026-06-08] ChatGPT OAuth provider required Codex backend details

Tried: Reuse ChatGPT Plus/Pro subscription access through a local OAuth-backed
provider.

Result: Several backend-specific constraints were discovered:

- Required auth URL parameters were easy to miss.
- OAuth tokens worked against the ChatGPT Codex backend, not generic public API
  endpoints.
- Model names could not be guessed.
- Some common public API payload fields were rejected by the Codex backend.

Lesson:

- Do not let AI guess backend model names or payload fields.
- Use local CLI/config ground truth first.
- Regression-test absence of rejected fields so they are not accidentally
  reintroduced.
- Treat this provider as local convenience, not a stable public API contract.

Related: `src/deal_intel/providers/llm.py`.
