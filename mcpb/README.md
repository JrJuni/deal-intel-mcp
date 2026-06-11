# mcpb - Claude Desktop bundle

This folder builds `deal-intel-mcp.mcpb`, a [Claude Desktop MCP Bundle](https://github.com/modelcontextprotocol/mcpb) for one-click install.

## Why .mcpb

The bundle ships the manifest + user-config schema. When the user double-clicks `deal-intel-mcp-{version}.mcpb`, Claude Desktop prompts for the required paths/keys via a UI form instead of asking the user to hand-edit JSON.

This bundle does not include the Python package or dependencies. Install the
project into Python first, then provide these required fields:

- **`python_path`** - select the Python interpreter that already ran `pip install -e ".[embedding]"`. The editable install makes `deal_intel` importable without `PYTHONPATH`.
- **`mongodb_uri`** - MongoDB Atlas connection string (M0 free tier works).

API keys are optional in the form - the server also loads them from the repo's
`.env` as a fallback. ChatGPT OAuth is the default and does not require an API
key.

## Build

```bash
cd mcpb
mcpb validate manifest.json
mcpb pack . deal-intel-mcp-0.1.8.mcpb   # output goes into mcpb/ folder
mcpb info deal-intel-mcp-0.1.8.mcpb
```

`mcpb` CLI: `npm install -g @anthropic-ai/mcpb` (Node.js 18+).

The `.mcpb` output is gitignored (build artifact, version-stamped in filename).

## Install

1. Open Claude Desktop -> Settings -> Extensions
2. Drag `deal-intel-mcp-{version}.mcpb` onto the Extensions pane (or click "Install from file")
3. Fill the user_config form:
   - **Python interpreter path** - select the conda environment's `python.exe`
   - **MongoDB Atlas URI** - required for full/pro mode; paste your Atlas connection string
   - **LLM provider** - `chatgpt_oauth` by default; can be `anthropic` or `openai_api`
   - **Use ChatGPT Plus/Pro** - legacy checkbox kept for older installs; the LLM provider field wins when set
   - **Anthropic API key** - required only when using `anthropic`
   - **OpenAI API key** - required only when using `openai_api`
   - For `chatgpt_oauth`, run `deal-intel login-chatgpt` once in a terminal after install to authenticate
4. Restart Claude Desktop
5. Verify the MCP tool list loads. The current tool contract is documented in
   `docs/baseline.md` and implemented in `src/deal_intel/mcp_server.py`.

## Version bump

1. Update `version` in `manifest.json`
2. Update `tools[]` if the MCP tool surface changed
3. Rebuild: `mcpb pack . deal-intel-mcp-{new_version}.mcpb`

**Note:** bundle `version` is an independent track from `pyproject.toml` version. Only bump when the install-surface (manifest fields / form) changes.
