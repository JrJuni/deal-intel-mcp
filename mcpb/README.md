# mcpb — Claude Desktop bundle

This folder builds `deal-intel-mcp.mcpb`, a [Claude Desktop MCP Bundle](https://github.com/modelcontextprotocol/mcpb) for one-click install.

## Why .mcpb

The bundle ships the manifest + user-config schema. When the user double-clicks `deal-intel-mcp-{version}.mcpb`, Claude Desktop prompts for the required paths/keys via a UI form instead of asking the user to hand-edit JSON.

This bundle does not include the Python package or dependencies. Install the
project into Python first, then provide these required fields:

- **`python_path`** — select the Python interpreter that already ran `pip install -e ".[embedding]"`. The editable install makes `deal_intel` importable without `PYTHONPATH`.
- **`mongodb_uri`** — MongoDB Atlas connection string (M0 free tier works).

API keys are optional in the form — the server also loads them from the repo's `.env` as a fallback.

## Build

```bash
cd mcpb
mcpb validate manifest.json
mcpb pack . deal-intel-mcp-0.1.7.mcpb   # output goes into mcpb/ folder
mcpb info deal-intel-mcp-0.1.7.mcpb
```

`mcpb` CLI: `npm install -g @anthropic-ai/mcpb` (Node.js 18+).

The `.mcpb` output is gitignored (build artifact, version-stamped in filename).

## Install

1. Open Claude Desktop → Settings → Extensions
2. Drag `deal-intel-mcp-{version}.mcpb` onto the Extensions pane (or click "Install from file")
3. Fill the user_config form:
   - **Python interpreter path** — select the conda environment's `python.exe`
   - **MongoDB Atlas URI** — required; format: `mongodb+srv://<user>:<pass>@<cluster>.mongodb.net/`
   - **Use ChatGPT Plus/Pro** — checked by default; run `deal-intel login-chatgpt` once in a terminal after install to authenticate
   - **Anthropic API key** — leave blank if using ChatGPT OAuth
4. Restart Claude Desktop
5. Verify all 18 tools appear, including `create_sample_data`, `delete_sample_data`, and `search_deals`

## Version bump

1. Update `version` in `manifest.json`
2. Update `tools[]` if the MCP tool surface changed
3. Rebuild: `mcpb pack . deal-intel-mcp-{new_version}.mcpb`

**Note:** bundle `version` is an independent track from `pyproject.toml` version. Only bump when the install-surface (manifest fields / form) changes.
