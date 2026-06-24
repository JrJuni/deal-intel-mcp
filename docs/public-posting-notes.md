# Public Posting Notes

Last reviewed: 2026-06-24.

This is a source-safe draft for LinkedIn posts and development retrospectives.
It summarizes verified post-v2 work without exposing private data, local
customer notes, secrets, or raw smoke logs.

## Current Positioning

`deal-intel-mcp` is a self-owned MCP backend for complex, conversation-heavy B2B
sales. It is strongest when the sales motion depends on customer evidence,
qualification gaps, stakeholders, buying process, risk, product-fit context,
and next actions.

It is not trying to cover every B2B motion. SKU-led wholesale, beauty/food
sample-to-reorder flows, commodity trading, and trade-promotion allocation are
different products: those care more about sell-through, channel ROI, inventory
velocity, and promotion spend than MEDDPICC-style deal qualification.

## Patch Notes Draft

Type: MINOR / public-trial readiness.

Theme: the project moved from "works as an MCP demo" toward "safer to try as a
real personal or small-team deal-intelligence layer."

### Added

- Product/solution context RAG: local seller-side product docs and managed
  pasted notes can guide extraction and strategy without counting as
  customer-stated evidence.
- HubSpot Deal import CSV: `export_data(dataset="hubspot_deals")` creates a
  manual HubSpot Deal import template without CRM API calls, Contacts,
  Companies, Salesforce sync, or account/person graph scope creep.
- CI/CD MVP evidence: basic CI, production tag guard, manual installed-package
  smoke workflow, and npm rerun guard now capture repetitive release evidence in
  GitHub Actions logs.
- MongoDB Atlas Terraform PoC: optional infrastructure template for repeatable
  `full`/`pro` Atlas setup experiments.

### Improved

- MCP safety posture: normal `get_deal` reads exclude raw notes, raw interaction
  content, contacts, and embeddings; `get_deal_raw` is developer-only and
  confirmation-gated.
- LLM cost guardrails: `add_interaction` has content-size and duplicate guards;
  `analyze_deal` is preview-by-default, has a short cooldown cache, and only
  persists strategy when explicitly confirmed.
- Tool selection: `get_tool_catalog` now carries intent aliases and workflow
  hints, including the customer-theme rank/compare/evidence flow, without
  breaking existing callable tool names.
- Release workflow: CI triage guidance now avoids full log ingestion and long
  `--watch` waits unless filtered evidence is insufficient.

### Fixed / Hardened

- Prompt-injection boundary: interaction extraction, strategy generation,
  historical re-extraction, and product-context snippets now treat source text
  as untrusted and ignore embedded instructions.
- User-memory path safety: default memory now lives under
  `~/.deal-intel/user-memory`; relative configured paths resolve under
  `~/.deal-intel`, not the MCP host working directory such as
  `C:\Windows\System32`.
- Test reliability: repo-local pytest temp directories are used where Windows
  temp permissions can be noisy.

### Deferred On Purpose

- No automatic CRM sync, OAuth, HubSpot API writes, Salesforce integration, or
  third-party MCP chaining yet.
- No account/company/person graph yet; current state remains deal-level.
- No generic memory platform yet; user memory remains append-only and explicit.
  A future context-pack layer should stay small, conflict-aware, and subordinate
  to tool contracts.
- No Dockerized remote MCP kit yet. Local/self-owned operation remains the
  current product shape.

## Retrospective Angles

- MCP servers need explicit safety boundaries because tool descriptions,
  filesystem access, API keys, and prompt-injection surfaces can all become
  part of the threat model.
- The useful line for this project is not "replace CRM"; it is "turn messy
  customer evidence into structured deal memory before a team is ready for a
  heavy CRM workflow."
- The biggest product-learning so far: the ICP is not all B2B. The tool fits
  complex direct sales much better than SKU/channel/sell-through businesses.
- The most useful automation was not full CD. It was small evidence automation:
  CI, smoke artifacts, and rerun guards that reduce repeated host-agent work.
