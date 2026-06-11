# deal-intel-mcp

**English** | [Korean](README.ko.md)

A B2B sales-support MCP server: paste a meeting note and it scores the deal on MEDDPICC, then turns the result into pipeline metrics, reports, dashboards, and deal-review prompts.

You can start with a bundled sample dataset and no MongoDB to test the product
flow. In sample mode, you can also create and maintain a small local personal
dataset in `~/.deal-intel/local-data`, then export or reset it when testing gets
messy. The real team operating path assumes MongoDB-backed deal data: when you
are ready for shared team use, switch the same package to MongoDB Atlas-backed
full mode or to the paid-infra pro path. Drive it by talking - in Claude
Desktop, or in Codex with the MCP connected. No separate CRM app.

---

## Live demo

Two ways to look at the deal data you've accumulated.

### 1. MongoDB Atlas Charts - Weekly Pipeline Review

![Atlas Charts Weekly Pipeline Review dashboard](docs/images/atlas-dashboard.png)

Active/Attention deal counts, pipeline value by stage, MEDDPICC health-band distribution, gap distribution, and open pipeline value - all on one screen. Each chart's aggregation pipeline is generated with the `render-atlas-dashboard` CLI and pasted into Atlas Charts (see the "Atlas Charts Dashboard" section below).

### 2. Claude / Codex in-chat rendered analysis

![Claude in-chat rendered dashboard](docs/images/chat-dashboard.png)

It takes the raw MCP tool output and renders win rate, the stage funnel, Won vs Lost MEDDPICC gaps, data-quality coverage, and attention items right inside the conversation. It all starts from pasting in a single meeting note - no extra app.

> Company names and figures in these screens are all fictional demo data.

---

## What is this?

**MEDDPICC** is a deal-qualification framework used in B2B sales. It scores "is this customer actually likely to buy'" across seven dimensions.

| Dimension | What it measures |
|---|---|
| **M**etrics | The quantified impact the customer expects (ROI, cost-reduction %) |
| **E**conomic Buyer | Who actually holds budget authority |
| **D**ecision Criteria | What the vendor-selection criteria are |
| **D**ecision Process | How the internal approval process runs |
| **I**dentify Pain | The customer's core problem and its urgency |
| **C**hampion | Whether you have an internal advocate |
| **C**ompetition | How you fight competitors and the status quo |

Paste a meeting note and the LLM extracts these seven automatically. In sample
mode, the same analysis surfaces run against bundled fictional data. In full
mode, they persist real deal data in MongoDB Atlas and run pattern analysis on
top.

---

## Product profiles

One repo, one package, three operating profiles:

| Profile | Use it for | Requires |
|---|---|---|
| `sample` | Feature testing, friend review, agent smoke tests, and lightweight local personal use | Python package only |
| `full` | Real team data on MongoDB Atlas | `MONGODB_URI`, plus ChatGPT OAuth or an API key for LLM tools |
| `pro` | Paid-infra upgrade with Atlas Vector Search and API-key LLMs | Atlas M10+, vector index, `OPENAI_API_KEY` by default |

Start in `sample` to verify the experience. It begins with bundled fictional
data. Once you create your own local deal, the bundled fixture is archived from
the working view and your local personal dataset becomes the active dataset.
Some search and LLM-heavy paths remain limited in sample mode. Move to `full`
when you are ready to connect real MongoDB-backed team storage. Move to `pro`
only when paid infrastructure is intentional.

MCP tools are profile-filtered by default:

- `sample`: 15 zero-config/local personal tools
- `standard`: 20 normal real-data tools
- `developer`: all 22 tools, including demo seed/cleanup helpers

Use `tools.surface: developer` or `DEAL_INTEL_TOOLS_SURFACE=developer` only
when you intentionally want the full maintainer/debug surface.

---

## Install (5 minutes)

### Prerequisites

- Python 3.11+ in a conda environment
- Optional: Claude Desktop, when you want the MCP chat experience
- Optional for `full`: MongoDB Atlas URI
- Optional for LLM tools: ChatGPT Plus/Pro OAuth, `ANTHROPIC_API_KEY`, or
  `OPENAI_API_KEY`

### Steps

**Step 1 - Install the package**

```bash
# reuse the event-intel conda env
~/miniconda3/envs/event-intel/python.exe -m pip install -e ".[embedding]"
```

Adding `[embedding]` also installs `sentence-transformers` (for similar-deal search).

**Step 2 - Inspect the profiles**

```bash
deal-intel config profiles
deal-intel config show
```

**Step 3 - Preview sample mode**

```bash
deal-intel config init --profile sample --dry-run
deal-intel config doctor --offline
```

If no user config exists and the preview looks right, persist sample mode:

```bash
deal-intel config init --profile sample
```

If `~/.deal-intel/config.yaml` already exists, preview a profile switch instead:

```bash
deal-intel config switch sample --dry-run
```

Only apply `config switch ... --force` after you intentionally approve changing
the profile-managed keys.

**Step 4 - Run a local sample smoke**

```bash
deal-intel smoke-profile --profile sample
deal-intel storage-status
deal-intel smoke-natural-questions --as-of 2026-06-10
```

This path starts with bundled fictional data. It does not require MongoDB, paid
APIs, or Atlas Vector Search. For lightweight personal testing, sample mode can
persist user-created deals locally under `storage.local_data_dir`; real team
usage assumes MongoDB-backed full mode.

**Step 5 - Optional: connect Claude Desktop**

Build or install the MCP bundle from [`mcpb/README.md`](mcpb/README.md). The
bundle form lets you start with `local_sample` storage or connect `mongo`
storage for real data. Use `deal-intel config switch pro` later if you want the
Atlas Vector Search upgrade path.

For real Atlas-backed operation, copy `.env.example` to `.env` or fill the MCP
bundle form with:

```
MONGODB_URI=your-atlas-connection-string
ANTHROPIC_API_KEY=optional-if-using-anthropic
OPENAI_API_KEY=optional-if-using-openai-api
```

For ChatGPT subscribers, run OAuth login once:

```bash
deal-intel login-chatgpt
```

Then restart Claude Desktop.

You're done when the MCP tool list loads. The current server exposes 22 tools;
`src/deal_intel/mcp_server.py` and `docs/baseline.md` are the source of truth.

```
config_doctor
create_deal / add_meeting / get_deal / update_stage / update_deal
archive_deal / restore_deal / delete_deal
create_sample_data / delete_sample_data
list_deals / get_insights / get_metrics / get_deal_gaps / get_deal_review
export_report / get_customer_themes / get_customer_theme_breakdown
get_customer_theme_evidence / search_deals / analyze_deal
```

---

## Zero-config sample mode (no MongoDB)

If you only want to test the BI and deal-review flows, you can run the bundled
fictional sample dataset without MongoDB Atlas, API keys, or Atlas Vector
Search.

Temporary PowerShell session:

```powershell
$env:DEAL_INTEL_STORAGE_BACKEND='local_sample'
& "$HOME\miniconda3\envs\event-intel\python.exe" -m deal_intel.cli storage-status
& "$HOME\miniconda3\envs\event-intel\python.exe" -m deal_intel.cli smoke-natural-questions --as-of 2026-06-10
```

Persistent sample profile:

```bash
deal-intel config init --profile sample --dry-run
deal-intel config init --profile sample
```

Sample mode is intentionally limited, but it is no longer purely read-only.
Core dashboard, reporting, customer-theme, deal-review, create/update/stage,
and lifecycle flows can run against local personal data. LLM meeting ingestion,
semantic `search_deals`, Atlas Charts, and shared team operation still belong
to MongoDB-backed `full` or `pro` mode.

Local personal data defaults to `~/.deal-intel/local-data` and can be changed
with `storage.local_data_dir`.

Useful local-data commands:

```bash
deal-intel local-data status
deal-intel local-data export
deal-intel local-data reset          # dry-run
deal-intel local-data reset --force  # clears local deals, preserves delete audit logs
```

The bundled fictional fixture is immutable. After local personal deals exist,
the fixture is hidden from active reads instead of being mixed with your data.
Later, a dry-run-first local-to-MongoDB migration tool will let users graduate
from sample/local mode to `full` without retyping deals.

---

## Tool guide

The detailed guide below focuses on the core user-facing workflow. For the
complete current tool contract, read [`docs/baseline.md`](docs/baseline.md).

> **Tip**: In Claude Desktop, type the example sentences below verbatim or say something similar. You can find a `deal_id` with `create_deal` or `list_deals`.

---

### 1. `create_deal` - create a new deal

**When to use**: Run this first when you start engaging a new prospect.

**Example**:
```
Create a new deal for Hyundai Precision. Manufacturing industry, deal size 200M KRW.
```

**Parameters**:
| Parameter | Required | Description |
|---|---|---|
| `company` | required | Customer company name |
| `industry` | optional | Industry (e.g., "Manufacturing", "IT SaaS") |
| `deal_size_krw` | optional | Median expected contract size (in KRW, e.g., 200000000) |
| `deal_size_status` | required when an amount is given | Amount status: `unknown`, `rough_estimate`, `customer_budget`, `quoted`, `strategic_zero` |
| `deal_size_low_krw` / `deal_size_high_krw` | optional | Estimate range. Omitted -> treated as equal to the median in metrics |
| `deal_size_note` | optional | Rationale for the amount classification, or a user memo |
| `expected_close_date` | optional | Expected close date. Omitted -> config default applies |

**Example result**:
```json
{
  "ok": true,
  "deal_id": "a3f9...",
  "company": "Hyundai Precision",
  "deal_size_krw": 200000000,
  "deal_size_status": "rough_estimate",
  "expected_close_date": "2026-06-15",
  "expected_close_date_source": "config_default"
}
```

Remember this `deal_id`, or look it up later with `list_deals`.

If you omit the expected close date, a default of 7 days after creation is filled in. This is an operational default, not a confirmed schedule. A date you provide always takes precedence over config.

When you enter a deal amount, you must also set its status. If unknown, leave `deal_size_status="unknown"` and leave the amount blank. If only a positive amount is given, the tool asks which basis applies - sales estimate / customer budget / quote sent. If only 0 is given, it doesn't save immediately and asks whether it's a strategic free/reference deal or an undecided amount. If undecided, it's saved as `unknown` with the amount blanked. An intentional zero-KRW deal (free sample, reference win) is saved with `deal_size_krw=0` and `deal_size_status="strategic_zero"`. If you heard a customer budget or sent a quote, use `customer_budget` or `quoted` so it counts as a validated pipeline value in metrics.

```yaml
pipeline:
  expected_close:
    default_days: 7
    days_by_industry:
      public_sector: 60
      enterprise: 28

reporting:
  timezone: Asia/Seoul
```

Industry overrides apply on a case-insensitive exact match against the free-form `industry` value. Auto-dates use the business date in the reporting timezone, while stored audit timestamps stay in UTC.

---

### 2. `add_meeting` - add a meeting note

**When to use**: Right after a customer meeting. Paste the note as-is and the LLM extracts MEDDPICC automatically.

**Example**:
```
Add today's (2026-06-08) meeting note to Hyundai Precision, deal_id: a3f9...

Notes:
Met Director Kim (purchasing decision-maker). Current production-line defect rate
is 3.2%, causing ~1.5B KRW/yr loss. Our solution targets <=1.5%. Manager Park is in
favor internally. Competitor A is under review but costs 2x. Internal approval due
end of June.
```

**Parameters**:
| Parameter | Required | Description |
|---|---|---|
| `deal_id` | required | Target deal ID |
| `date` | required | Meeting date (YYYY-MM-DD) |
| `raw_notes` | required | Raw meeting notes (Korean or English both fine) |

**What the result includes**:
- `meddpicc` - scores + evidence extracted from this meeting
- `meddpicc_latest` - the deal's cumulative health_pct + per-dimension trend
- `summary` - a 2-3 sentence LLM-generated summary
- `customer_themes` - customer concerns / selection criteria extracted from this meeting
- `stage_suggestion` - filled only when the notes explicitly imply a stage transition (e.g., contract signed -> won, lost deal -> lost); otherwise `null`
- `embedding_stored` - whether the similar-deal-search embedding was stored

> **The stage never changes automatically.** Even if the notes say "contract signed," `add_meeting` does not change the stage directly - it only **suggests** via `stage_suggestion`. When Claude asks "shall I move this deal to won'", `update_stage` makes the actual change after you confirm. This is a deliberate separation to prevent wrong auto-closing.

---

### 3. `get_deal` - view deal details

**When to use**: To check a specific deal's full history, MEDDPICC scores, and meeting records.

**Example**:
```
Show me the full Hyundai Precision deal. deal_id is a3f9...
```

You get the raw notes, the per-meeting MEDDPICC extraction, and the cumulative health_pct.

---

### 4. `update_stage` - change the pipeline stage

**When to use**: When a deal moves to the next stage or the outcome is finalized.

```text
update_stage(deal_id, new_stage, actual_close_date="")
```

**Example**:
```
Move the Hyundai Precision deal to the proposal stage.
```

When moving to `won` or `lost`, you can specify the actual close date as `YYYY-MM-DD`. Omitted -> the processing day is stored. `expected_close_date` stays as the forecast, and `stage_history.entered_at` is the system audit time, kept distinct from the actual close date. Moving a closed deal back to an open stage clears `actual_close_date`.

**Stages** (in order):
```
discovery -> qualification -> proposal -> negotiation -> won / lost / stalled
```

**What the result includes**:
- `actual_close_date` - the real close date for Won/Lost
- `days_in_previous_stage` - how long it spent in the previous stage
- `stuck_threshold_days` - the stuck threshold for a new Active stage; otherwise `null`
- MEDDPICC gaps are recomputed per stage (e.g., a drop in Identify Pain at the proposal stage is not a gap - it's a positive signal that the pain is being resolved)

---

### 5. `update_deal` - fix an existing deal's amount classification

**When to use**: When an existing deal's `deal_size_status` is missing, or to save after the user confirms customer-budget / quote / strategic-zero.

The first version only edits deal-value fields, for safety. It does not touch company, industry, stage, meetings, or contacts.

**Example**:
```
The existing ArcanaGames deal has evidence of a closed contract, so save it as quoted.
Note the rationale as "CEO said let's sign today and paid same-day."
```

**Required conditions**:
- `confirmed_by_user=true`
- `deal_size_note` with the user's confirmation rationale or meeting evidence

Edits are logged to `deal_value_history`.

---

### 6. `list_deals` - see all deals at a glance

**When to use**: When you want the whole pipeline at a glance. Good for a weekly review.

**Example**:
```
Show me all deals, stuck ones first.
```

Or a specific stage only:
```
Show me only the deals in the proposal stage.
```

**Result**:
- `health_pct` - overall MEDDPICC score (0-100)
- `gaps` - list of weak, low-scoring dimensions
- `is_stuck` - whether the Active-stage dwell time exceeds the per-stage threshold
- `is_overdue` / `overdue_days` - whether an Open deal passed its expected close date
- `attention_reasons` - multiple reasons: `stalled`, `overdue`, `stuck`, `at_risk`
- `days_in_stage` - days spent in the current stage
- `data_quality` - per-deal missing/invalid/estimated fields and overall coverage
- `as_of`, `timezone`, `generated_at` - reporting base date and generation time

Specify `as_of="YYYY-MM-DD"` to re-run date-based calculations against the same base date. Stuck deals sort to the top.

---

### 7. `analyze_deal` - MEDDPICC gap analysis + BD strategy

**When to use**: When a deal is stuck or you're planning the next meeting. The LLM analyzes gaps and proposes concrete actions.

**Example**:
```
Analyze the Hyundai Precision deal. Where is it weak, and what should I do next meeting'
```

The result includes:
- a summary of current MEDDPICC health
- concrete responses per weak dimension
- a recommended agenda for the next meeting

---

### 8. `get_metrics` - current pipeline-health KPIs

**When to use**: For instant BI questions in Claude/Codex like "how's pipeline health right now'", "how many at-risk deals'", "show pipeline value and health by stage."

The first version supports only `pipeline_health`.

**Parameters**:
| Parameter | Required | Description |
|---|---|---|
| `metric_type` | optional | Currently only `pipeline_health` |
| `stage` | optional | Exact match against the stored stage |
| `industry` | optional | Exact match against the stored industry |
| `as_of` | optional | Base date for stuck/overdue calculation, `YYYY-MM-DD` |

**What the result includes**:
- `kpis`: active/open/stalled/terminal count, open value, avg health, coverage, stuck/overdue, attention count
- `stage_breakdown`: count/value/health/stuck/overdue in canonical stage order
- `health_bands`: healthy/watch/at_risk/unassessed counts
- `attention_reasons`: stalled/overdue/stuck/at_risk reason counts and unique attention-deal count
- `pipeline_values`, `win_rate`, `data_quality`, `warnings`

The BI path uses no LLM and no embedding. Raw notes, contacts, and vectors are excluded from the metric read path.

**Example**:
```
Tell me the current pipeline health
```
```
Show pipeline health for the proposal stage only
```
```
Show stuck/overdue status for IT-industry deals
```

---

### 9. `get_deal_gaps` - surface the customer intel you're still missing

**When to use**: When you want to know what you still need to confirm before pursuing, forecasting, or reviewing a deal.

This is not a table-completeness checker. It prioritizes missing or weak information by practical sales impact and forecast trust. It is read-only, uses no LLM, uses no embedding, and excludes raw notes, contacts, and vectors.

**Parameters**:
| Parameter | Required | Description |
|---|---|---|
| `as_of` | optional | Base date for stuck/overdue calculation, `YYYY-MM-DD` |
| `stage` | optional | Exact match against the stored stage |
| `industry` | optional | Exact match against the stored industry |
| `deal_id` | optional | Exact deal id. Returns that deal regardless of `min_priority` and `limit` |
| `min_priority` | optional | `low`, `medium`, or `high`. Defaults to `medium` |
| `limit` | optional | 1 to 50. Defaults to 10 |

**What the result includes**:
- `summary`: deal count, gap-deal count, priority counts, gap status/type counts
- `deals`: prioritized deals with health band, attention reasons, priority score, and gaps
- each gap includes reason, suggested question, and recommended action

**Example**:
```
What important customer information are we missing for active deals'
```
```
Show high-priority gaps for negotiation deals
```
```
For this deal_id, what should I confirm next'
```

---

### 10. `export_report` - generate a weekly pipeline report

**When to use**: When you need a file to share or for a meeting, like "make this week's pipeline report."

The first version supports only `weekly_pipeline` and produces CSV and Markdown with the same timestamp.

**Parameters**:
| Parameter | Required | Description |
|---|---|---|
| `report_type` | optional | Currently only `weekly_pipeline` |
| `output_dir` | optional | Save path. Omitted -> `reporting.output_dir` or `outputs/reports` |
| `stage` | optional | Exact match against the stored stage |
| `industry` | optional | Exact match against the stored industry |
| `as_of` | optional | Base date for stuck/overdue calculation, `YYYY-MM-DD` |

**What the result includes**:
- `csv_path`, `markdown_path`: absolute paths of the generated files
- `artifacts`: CSV/Markdown filename, path, encoding
- `metrics`, `warnings`, `row_count`

This is a BI/Reporting path, so it uses no LLM and no embedding.

**Example**:
```
Make this week's pipeline report
```
```
Export the proposal stage only as a weekly pipeline report
```

---

### Atlas Charts Dashboard - `Weekly Pipeline Review`

When you'd rather see it on screen than as CSV/Markdown, use the Atlas Charts dashboard. The dashboard aggregation spec and setup runbook are in [`docs/atlas-charts.md`](docs/atlas-charts.md).

Render command:

```bash
~/miniconda3/envs/event-intel/python.exe -m deal_intel.cli render-atlas-dashboard --as-of 2026-06-09 --output outputs/atlas_charts/weekly_pipeline_review_20260609.json
```

To paste a single chart into the Atlas Query bar:

```bash
~/miniconda3/envs/event-intel/python.exe -m deal_intel.cli render-atlas-dashboard --as-of 2026-06-09 --chart-id pipeline_kpis
```

The five managed chart ids are `pipeline_kpis`, `stage_breakdown`, `health_bands`, `attention_deals`, `meddpicc_gap_distribution`.

Cross-check the dashboard numbers:

```bash
~/miniconda3/envs/event-intel/python.exe -m deal_intel.cli crosscheck-weekly-dashboard --as-of 2026-06-09 --output-dir outputs/m3_3_crosscheck
```

---

### 11. `get_insights` - pipeline BI analysis

**When to use**: To aggregate all deal data and spot patterns. Good for monthly reviews and learning win/loss patterns.

You can specify `as_of`; the response includes `timezone` and a UTC `generated_at`. These label the current collection snapshot - they don't reconstruct historical document state.

**Seven analysis types**:

| query_type | What it tells you |
|---|---|
| `pipeline_overview` | Deal count / avg health / total size by stage |
| `win_patterns` | Average MEDDPICC scores of Won deals |
| `loss_patterns` | Average MEDDPICC scores of Lost deals |
| `compare_won_lost` | Per-dimension score gap between Won and Lost |
| `gap_frequency` | The dimensions most often missing in active deals |
| `industry_benchmark` | Avg health / win rate / deal size by industry |
| `stage_velocity` | Average dwell days per stage |

**Example**:
```
Show me the whole pipeline overview.
```
```
What's the MEDDPICC pattern difference between deals we win and deals we lose'
```
```
Which dimension is most often missing'
```

---

### 12. `search_deals` - semantic similar-deal search

**When to use**: When you want to reference how past deals in similar situations played out. Search in natural language.

**Example**:
```
Find deals where the customer struggled with cost reduction.
```
```
Show deals with a strong champion and a clear decision structure.
```
```
Any deals with a pattern similar to Hyundai Precision'
```

**How it works**:
1. Convert the query into a 384-dim vector
2. Compute cosine similarity against every deal's meeting-summary vector
3. Return them sorted by similarity, highest first

**What the result includes**:
- `score` - similarity (0-1, higher = more similar)
- `deal_stage`, `health_pct`, `gaps` - the deal's current state

> The local embedding model warms up in the background at server start. While it's loading, `warming_up: true` is returned, so retry after 5 seconds. After 30+ seconds it switches to a stalled error.

---

### 13. `get_customer_themes` - frequency of customer concerns / selection criteria

**When to use**: To group meeting evidence across deals and see the topics customers worry about most. It counts by unique deal (not by meeting) and returns representative companies and evidence.

**Example**:
```
Show the top 5 things customers worried about most across active deals.
```
```
Tell me the most frequent themes and evidence in Decision Criteria.
```

**Filters**:
- `dimension`: `all`, `identify_pain`, `decision_criteria`, `metrics`
- `stage`: `active`, `all`, or an individual deal stage
- `industry`: exact industry name
- `top_k`: up to 20

To backfill themes onto existing data, run this first:

```bash
~/miniconda3/envs/event-intel/python.exe -m deal_intel.cli backfill-customer-themes --apply
```

The Atlas Charts aggregation is in `scripts/atlas_charts_customer_themes.json`.

---

## Recommended workflow

```
1. Right after a meeting     -> add_meeting (paste the note)
2. On stage change           -> update_stage
3. Pre-meeting prep          -> analyze_deal (figure out the next agenda)
4. Before pursuing/forecast  -> get_deal_gaps (what's still missing)
5. Weekly review             -> list_deals (find stuck deals)
6. Pipeline KPIs             -> get_metrics pipeline_health
7. Monthly retro             -> get_insights compare_won_lost / stage_velocity
8. Reference similar cases   -> search_deals
9. Customer-concern analysis -> get_customer_themes
10. Dashboard                -> Atlas Charts Weekly Pipeline Review
```

---

## Architecture

Current source of truth:

- MCP server: `src/deal_intel/mcp_server.py`
- Current tool count: 22
- Detailed contract: [`docs/baseline.md`](docs/baseline.md)
- Documentation map: [`docs/README.md`](docs/README.md)

```
[Claude Desktop / Codex - natural-language input]
         | stdio JSON-RPC
         v
[deal-intel-mcp  FastMCP server  22 tools]
         |
         |-- LLM Provider
         |     |-- ChatGPT OAuth (default, Plus/Pro subscription)
         |     |-- Anthropic API (optional)
         |     `-- OpenAI API (optional)
         |
         |-- Embedding Provider
         |     `-- sentence-transformers all-MiniLM-L6-v2
         |          -> runs locally / no API key / 384 dims
         |
         `-- Storage
               |-- local_sample  : bundled fixture + local personal deals
               `-- MongoDB Atlas : real deals collection and analytics snapshots

search_deals
  |-- M0 default : reads summary_embedding, computes cosine in Python
  `-- M10+ option : uses the Atlas Vector Search index
```

### Deal document schema (key fields)

```json
{
  "deal_id": "uuid",
  "company": "Hyundai Precision",
  "industry": "Manufacturing",
  "deal_size_krw": 200000000,
  "deal_stage": "proposal",
  "expected_close_date": "2026-09-30",
  "expected_close_date_source": "user_provided",
  "actual_close_date": null,
  "stage_history": [
    {"stage": "discovery",     "entered_at": "2026-05-01T..."},
    {"stage": "qualification", "entered_at": "2026-05-15T..."},
    {"stage": "proposal",      "entered_at": "2026-06-01T..."}
  ],
  "meetings": [
    {
      "meeting_id": "uuid",
      "date": "2026-06-08",
      "raw_notes": "Met Director Kim. Defect rate 3.2% -> target 1.5%...",
      "summary": "2-3 sentence LLM-generated summary",
      "meddpicc": {
        "metrics":      {"score": 4, "evidence": "~1.5B KRW/yr loss"},
        "identify_pain": {"score": 5, "evidence": "defect rate 3.2%, line urgent"},
        "champion":     {"score": 3, "evidence": "Manager Park in favor"}
      }
    }
  ],
  "meddpicc_latest": {
    "health_pct": 72.4,
    "gaps": ["economic_buyer", "decision_criteria"],
    "metrics":       {"score": 4.0, "trend": "up"},
    "identify_pain": {"score": 5.0, "trend": "flat"},
    "champion":      {"score": 3.0, "trend": "up"}
  },
  "summary_embedding": [0.012, -0.034, ...],
  "created_at": "2026-05-01T...",
  "updated_at": "2026-06-08T..."
}
```

### Module structure

```
src/deal_intel/
  mcp_server.py         FastMCP entry point
  cli.py                typer CLI (login-chatgpt, backfill-customer-themes,
                        render-atlas-dashboard, crosscheck-weekly-dashboard,
                        smoke-deal-review, smoke-deal-review-audit,
                        smoke-natural-questions)
  _env.py               dotenv + 3-tier config merge
  _context.py           LLM / MongoDB / Embedding process singletons
  providers/
    llm.py              LLMProvider ABC + Anthropic + ChatGPTOAuth + factory
    embedding.py        EmbeddingProvider + SentenceTransformerProvider + factory
  schema/
    meddpicc.py         compute_meddpicc_latest, Deal/Meeting Pydantic models
    customer_themes.py  customer-theme taxonomy, parser, stage-signal validation
  storage/
    mongodb.py          MongoDBClient - CRUD + aggregation + semantic-search storage
  tools/
    create_deal.py
    add_meeting.py      MEDDPICC extraction + summary generation + embedding storage
    get_deal.py
    update_stage.py     stage_history logging + MEDDPICC recompute
    update_deal.py      edit deal-value fields after user confirmation
    list_deals.py       health_pct / gaps / stuck-flag aggregation
    get_metrics.py      pipeline_health KPIs / stage aggregation / warnings
    get_deal_gaps.py    read-only prioritized sales follow-up gaps
    export_report.py    weekly_pipeline CSV/Markdown export
    get_insights.py     7 BI queries plus legacy insight query
    get_customer_themes.py
                        aggregates customer concerns by unique deal count
    analyze_deal.py     MEDDPICC gap analysis + BD strategy via LLM
    search_deals.py     Python cosine by default / Atlas semantic search optional
```

### How MEDDPICC health_pct is computed

```
health_pct = sum(dim_avg x weight) / sum(5 x weight) x 100
```

Weights (tunable in `config/defaults.yaml`):

| Dimension | Weight | Why |
|---|---|---|
| champion | 2.0 | No internal momentum -> no deal |
| identify_pain / economic_buyer | 1.5 | Confirming the pain and reaching the budget holder are core |
| metrics / decision_criteria / decision_process | 1.0 | Standard |
| competition | 0.5 | Competition surfacing late is normal |

**Stage-aware gap adjustment** (applied automatically on `update_stage`):
- A drop in Identify Pain at the `proposal` / `negotiation` stage -> not a gap (signals the pain is being resolved)
- `won` deals -> no gaps

**Health-band configuration**:

Defaults are Healthy >=70, Watch >=40, At Risk <40. These classify the level of MEDDPICC validation, not win probability, and can be changed in `~/.deal-intel/config.yaml` once you've accumulated operational data.

```yaml
metrics:
  health_bands:
    healthy_min: 75
    watch_min: 45
  overdue:
    grace_days: 0
  win_rate:
    minimum_closed_sample: 10
```

The formal definitions of Active/Open/Stalled and unassessed handling are in [`docs/metrics.md`](docs/metrics.md).

---

## FAQ

**Q. Do my meeting notes have to be perfect?**
No. A rough memo of the essentials is fine. The LLM just skips dimensions with no evidence.

**Q. Do Korean meeting notes work?**
Yes. Mixed English/Korean works too.

**Q. Do I need MongoDB at all?**
Not for `sample`. You need MongoDB only when you want persistent real deal data
or Atlas Charts against your own database.

**Q. Do I need a paid MongoDB Atlas plan?**
No for first-run sample mode. For real team data, the core features work on the
free M0 plan today. `search_deals` computes with Python cosine on M0. As deal
volume grows you can switch to Atlas Vector Search on M10+.

**Q. search_deals returns nothing.**
Right after the server first starts, the local model may still be warming up - retry after 5 seconds. You also need at least one deal with a stored `summary_embedding` (run `add_meeting`).

**Q. Should I use ChatGPT OAuth, Anthropic, or OpenAI API?**
For quick personal use, ChatGPT OAuth is attractive if you already subscribe to
ChatGPT Plus/Pro. Anthropic and OpenAI API modes are better when you want
explicit API-key operation, team billing, or production-style deployment.
