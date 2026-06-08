# Verification Baseline

BI and reporting work must compare its behavior against this baseline before
changing shared deal or MCP behavior.

## 2026-06-08 - Milestone 0.1

### Runtime

- Python: 3.11.15 (`event-intel` conda environment)
- FastMCP runtime registration: 9 tools
- MongoDB database: `deal_intel`
- Atlas read smoke: passed
- Deal count at smoke time: 10

The Atlas smoke performed only:

1. `ping`
2. `count_documents({})`
3. One deal read with a restricted projection

It did not write or update MongoDB data.

### Common Error Contract

All MCP boundaries return structured errors with:

```json
{
  "ok": false,
  "error_code": "INVALID_INPUT | NOT_FOUND | CONFIG_ERROR | RATE_LIMITED | UPSTREAM_ERROR | IO_ERROR | INTERNAL | STORAGE_ERROR | LLM_ERROR | LOGIN_REQUIRED",
  "stage": "preflight | storage | llm | analysis",
  "message": "human-readable message",
  "hint": null,
  "retryable": false
}
```

### MCP Tool Contracts

| Tool | Required inputs | Optional inputs | Success response | Persistence or external effects |
|---|---|---|---|---|
| `create_deal` | `company` | `industry`, `deal_size_krw`, `expected_close_date` | `ok`, `deal_id`, `company`, `expected_close_date`, `expected_close_date_source` | Applies the configured close-date default when omitted, upserts one deal, and initializes `discovery` stage history |
| `add_meeting` | `deal_id`, `date`, `raw_notes` | None | `ok`, `meeting_id`, `summary`, `meddpicc`, `meddpicc_latest`, `customer_themes`, `stage_suggestion`, `embedding_stored`, `usage` | Calls LLM, appends a meeting, recalculates deal signals, optionally stores an embedding, and upserts the deal |
| `update_stage` | `deal_id`, `new_stage` | `actual_close_date` | `ok`, `deal_id`, `old_stage`, `new_stage`, `actual_close_date`, `days_in_previous_stage`, `stuck_threshold_days` | Appends stage history, records the actual terminal date, recalculates stage-aware MEDDPICC gaps, and upserts the deal |
| `get_deal` | `deal_id` | None | `ok`, `deal` | Read only; includes full meeting history and raw notes |
| `list_deals` | None | `stage`, `limit` | `ok`, `as_of`, `deals`, `count` | Read only; returns health, stuck, overdue, and attention fields while excluding meeting raw notes |
| `get_insights` | `query_type` | None | `ok`, `query_type`, query-specific aggregate fields | Read-only MongoDB aggregation |
| `get_customer_themes` | None | `dimension`, `stage`, `industry`, `top_k` | `ok`, `filters`, `coverage`, `themes` | Read-only MongoDB counts and aggregation |
| `search_deals` | `query` | `limit` | `ok`, `query`, `result_count`, `results` | Generates a local query embedding and reads deal embeddings; may return a structured warmup response before search |
| `analyze_deal` | `deal_id` | None | `ok`, `deal_id`, `analysis`, `usage` | Calls LLM and attempts to persist `bd_strategy`; analysis still returns if that save fails |

`get_insights.query_type` currently supports:

- `pipeline_overview`
- `win_patterns`
- `loss_patterns`
- `compare_won_lost`
- `gap_frequency`
- `industry_benchmark`
- `stage_velocity`

`search_deals` has additional preflight outcomes:

- `warming_up: true`, `retryable: true` while the local model is loading
- `warming_up: false` with `CONFIG_ERROR` when the embedding dependency is absent
- `warming_up: false` with `UPSTREAM_ERROR` when warmup fails or stalls

### Test Baseline

Command:

```powershell
& "$HOME\miniconda3\envs\event-intel\python.exe" -m pytest
```

Result:

```text
17 passed, 1 warning in 1.24s
```

The warning is an external OpenTelemetry `SelectableGroups` deprecation warning.

### Historical Ruff Baseline

Command:

```powershell
& "$HOME\miniconda3\envs\event-intel\python.exe" -m ruff check .
```

Milestone 0.1 최초 측정 결과는 28개 기존 finding이었다.

| Area | Findings |
|---|---:|
| `scripts/smoke_test.py` | 3 |
| `src/deal_intel/providers/llm.py` | 1 |
| `src/deal_intel/schema/meddpicc.py` | 17 |
| `src/deal_intel/storage/identifiers.py` | 1 |
| `src/deal_intel/tools/analyze_deal.py` | 1 |
| `src/deal_intel/tools/create_deal.py` | 1 |
| `src/deal_intel/tools/get_insights.py` | 2 |
| `src/deal_intel/tools/list_deals.py` | 1 |
| `src/deal_intel/tools/update_stage.py` | 1 |

#### Current Quality Gate

Milestone 1 시작 전에 28개 finding을 모두 해결했다. 현재 gate는 다음과 같다.

```text
pytest -> 34 passed
ruff check . -> All checks passed
wheel build -> passed
FastMCP runtime registration -> 9 tools
MongoDB Atlas read smoke -> passed
```

이후 서브 태스크는 이 gate를 유지해야 한다.

### Privacy and Scope

- Baseline inspection must not print `MONGODB_URI`, OAuth tokens, raw meeting
  notes, contacts, or embeddings.
- Live verification is read only unless a later subtask explicitly requires a
  write smoke.
- This milestone does not change metrics, tool behavior, schemas, or stored
  documents.

### Gate Result

Milestone 0.1 passed:

- Runtime tool registration captured
- Existing success and error contracts recorded
- Full test baseline passed
- Existing Ruff debt isolated
- Existing Ruff debt subsequently resolved
- Live Atlas read path passed
