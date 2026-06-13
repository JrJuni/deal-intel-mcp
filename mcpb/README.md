# mcpb - Claude Desktop bundle

This folder builds `deal-intel-mcp.mcpb`, a [Claude Desktop MCP Bundle](https://github.com/modelcontextprotocol/mcpb) for one-click install.

## Why .mcpb

The bundle ships the manifest + user-config schema. When the user double-clicks `deal-intel-mcp-{version}.mcpb`, Claude Desktop prompts for the required paths/keys via a UI form instead of asking the user to hand-edit JSON.

This bundle does not include the Python package or dependencies. Install the
project into Python first, then provide these fields:

- **`python_path`** - select the Python interpreter that already ran `pip install -e ".[embedding]"`. The editable install makes `deal_intel` importable without `PYTHONPATH`.
- **`storage_backend`** - choose `mongo` for real Atlas-backed data. Use
  `local_sample` only for zero-config sample/local personal mode.
- **`tools_surface`** - choose `auto` for profile-based filtering. Advanced
  users can select `sample`, `standard`, or `developer` explicitly.
- **`mongodb_uri`** - MongoDB Atlas connection string. Required only when
  `storage_backend=mongo`; M0 free tier works for the full profile.

API keys are optional in the form - the server also loads them from the repo's
`.env` as a fallback. ChatGPT OAuth is the default and does not require an API
key.

For the normal `full` install, prepare:

1. MongoDB Atlas account.
2. Free/M0 cluster and driver connection string.
3. Claude Desktop as the MCP client.
4. ChatGPT OAuth, Anthropic API key, or OpenAI API key for LLM-backed
   extraction/scoring.

MongoDB Atlas links:

- Sign up: <https://www.mongodb.com/cloud/atlas/register>
- Free cluster guide:
  <https://www.mongodb.com/docs/atlas/tutorial/deploy-free-tier-cluster/>

## Build

```bash
cd mcpb
mcpb validate manifest.json
mcpb pack . deal-intel-mcp-0.1.13.mcpb   # output goes into mcpb/ folder
mcpb info deal-intel-mcp-0.1.13.mcpb
```

`mcpb` CLI: `npm install -g @anthropic-ai/mcpb` (Node.js 18+).

The `.mcpb` output is gitignored (build artifact, version-stamped in filename).

## Install

1. Open Claude Desktop -> Settings -> Extensions
2. Drag `deal-intel-mcp-{version}.mcpb` onto the Extensions pane (or click "Install from file")
3. Fill the user_config form:
   - **Python interpreter path** - select the conda environment's `python.exe`
   - **Storage backend** - `mongo` for real Atlas data; `local_sample` only for zero-config sample mode
   - **MCP tool surface** - `auto` for normal installs; `sample`, `standard`,
     or `developer` only when intentionally overriding the profile default
   - **MongoDB Atlas URI** - required only when `Storage backend` is `mongo`
   - **LLM provider** - `chatgpt_oauth` by default; can be `anthropic` or `openai_api`
   - **Use ChatGPT Plus/Pro** - legacy checkbox kept for older installs; the LLM provider field wins when set
   - **Anthropic API key** - required only when using `anthropic`
   - **OpenAI API key** - required only when using `openai_api`
   - For `chatgpt_oauth`, run `deal-intel login-chatgpt` once in a terminal after install to authenticate
4. Restart Claude Desktop
5. Verify the MCP tool list loads. The current tool contract is documented in
   `docs/baseline.md` and implemented in `src/deal_intel/mcp_server.py`.

Suggested first install:

1. Set **Storage backend** to `mongo`.
2. Set **MCP tool surface** to `auto`.
3. Fill **MongoDB Atlas URI**. M0/free tier works for the `full` profile.
4. Restart Claude Desktop and run `config_doctor(offline=true)`.
5. Use the standard tool surface for real data.

Zero-config demo install:

1. Set **Storage backend** to `local_sample`.
2. Set **MCP tool surface** to `auto`.
3. Leave MongoDB/API-key fields blank.
4. Restart Claude Desktop and run `config_doctor(offline=true)`.
5. Try the bundled sample data. You can also create small local personal deals;
   once local personal data exists, active reads use that local dataset instead
   of the immutable bundled fixture.

## Validation in this repository

The repository includes contract tests for the bundle manifest and launcher:

```bash
<python> -m pytest tests/test_mcpb_manifest.py
```

These tests verify that the manifest tool list matches the registered MCP tool
surface contract, installer fields map to runtime environment variables, and
the launcher delegates to the installed `deal_intel.mcp_server` module.

Real `mcpb validate`, `mcpb pack`, and `mcpb info` checks still require the
external `mcpb` CLI.

## Version bump

1. Update `version` in `manifest.json`
2. Update `tools[]` if the MCP tool surface changed
3. Rebuild: `mcpb pack . deal-intel-mcp-{new_version}.mcpb`

**Note:** bundle `version` is an independent track from `pyproject.toml` version. Only bump when the install-surface (manifest fields / form) changes.
