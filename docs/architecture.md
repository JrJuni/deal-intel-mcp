# Architecture

## 전체 흐름

```
[Claude Desktop / Codex — 자연어 입력]
         │ stdio JSON-RPC (FastMCP)
         ▼
[deal-intel-mcp 서버  18 tools]
         │
         ├─ LLM Provider ──────────────────────────────────────────────────
         │    add_meeting: MEDDPICC + customer_themes 추출 (구조화 JSON)
         │    add_meeting: 미팅 요약 2~3문장 생성
         │    analyze_deal: MEDDPICC 갭 분석 + BD 전략 생성
         │    ├── ChatGPT OAuth   gpt-5.5 / gpt-5.4 (기본)
         │    └── Anthropic       claude-sonnet-4-6 (선택)
         │
         ├─ Embedding Provider ───────────────────────────────────────────
         │    add_meeting: 딜 레벨 summary_embedding 생성·갱신
         │    search_deals: 쿼리 임베딩 후 Python cosine (M0 기본)
         │    └── sentence-transformers all-MiniLM-L6-v2
         │         로컬 CPU 실행 / API key 불필요 / 384 dims
         │
         └─ MongoDB Atlas M0 ─────────────────────────────────────────────
              deals collection
              ├── Regular Indexes
              │    deal_id_unique          : point lookup + uniqueness
              │    stage_updated           : {deal_stage, updated_at}
              │    updated_desc            : {updated_at}
              │    health_pct_desc         : {meddpicc_latest.health_pct}
              │    stage_customer_theme    : {deal_stage, customer_themes.theme_key}
              └── Optional Vector Search Index (M10+ 전환 시)
                   deal_summary_vector     : summary_embedding cosine 384d
```

## 18개 MCP 도구

| 도구 | LLM 호출 | Embedding | 주요 기능 |
|---|---|---|---|
| `create_deal` | 없음 | 없음 | 초기 금액 분류 검증, expected close 기본값 적용, 딜 생성, stage_history 초기화 |
| `add_meeting` | 2회 (분석 + 요약) | embed + store | MEDDPICC·고객 주제 추출, health_pct 재계산 |
| `get_deal` | 없음 | 없음 | 딜 전체 조회 |
| `update_stage` | 없음 | 없음 | stage_history 및 actual_close_date 기록, MEDDPICC 재계산 |
| `update_deal` | 없음 | 없음 | 사용자 확인 후 deal value·metadata 필드를 수정하고 history 기록 |
| `archive_deal` | 없음 | 없음 | 사용자 확인 후 딜을 archived 처리하여 기본 BI/read path에서 숨김 |
| `restore_deal` | 없음 | 없음 | 사용자 확인 후 archived 딜을 기본 BI/read path로 복구 |
| `delete_deal` | 없음 | 없음 | dry-run 기본 hard delete. archived 딜만 safe audit snapshot 저장 후 삭제 |
| `create_sample_data` | 없음 | 없음 | 별도 demo database에 fictional onboarding sample deal 생성 |
| `delete_sample_data` | 없음 | 없음 | 별도 demo database의 sample batch만 dry-run 기본으로 삭제 |
| `list_deals` | 없음 | 없음 | health, stuck, overdue, attention 사유 집계 |
| `get_metrics` | 없음 | 없음 | pipeline_health KPI, stage 집계, warning 반환 |
| `get_deal_gaps` | 없음 | 없음 | 고객 공략에 필요한 미확인 정보와 follow-up question 우선순위화 |
| `export_report` | 없음 | 없음 | weekly_pipeline CSV·Markdown 파일 생성 |
| `get_insights` | 없음 | 없음 | 7가지 BI 집계와 legacy insight query |
| `get_customer_themes` | 없음 | 없음 | 고객 고민 주제별 고유 딜 수·근거 집계 |
| `analyze_deal` | 1회 (전략) | 없음 | 갭 분석 + BD 전략 생성 |
| `search_deals` | 없음 | query embed | Python cosine 기본, M10+에서 `$vectorSearch` 선택 |

## Deal 도큐먼트 스키마

```json
{
  "deal_id":            "uuid",
  "company":            "현대정밀",
  "industry":           "제조",
  "deal_size_krw":      200000000,
  "deal_size_low_krw":  null,
  "deal_size_high_krw": null,
  "deal_size_status":   "quoted",
  "deal_size_note":     "proposal sent after pricing call",
  "deal_value_history": [
    {
      "updated_at": "2026-06-09T00:00:00+00:00",
      "source": "update_deal",
      "deal_size_krw": 200000000,
      "deal_size_status": "quoted",
      "deal_size_note": "proposal sent after pricing call"
    }
  ],
  "deal_stage":         "proposal",
  "expected_close_date": "2026-09-30",
  "expected_close_date_source": "user_provided",
  "actual_close_date":   null,
  "contacts":           [],

  "stage_history": [
    {"stage": "discovery",     "entered_at": "2026-05-01T00:00:00+00:00"},
    {"stage": "qualification", "entered_at": "2026-05-15T00:00:00+00:00"},
    {"stage": "proposal",      "entered_at": "2026-06-01T00:00:00+00:00"}
  ],

  "meetings": [
    {
      "meeting_id":  "uuid",
      "date":        "2026-06-08",
      "raw_notes":   "김 이사 미팅. 불량률 3.2%...",
      "summary":     "LLM 생성 2~3문장 요약",
      "meddpicc": {
        "metrics":       {"score": 4, "evidence": "연간 15억 손실"},
        "identify_pain": {"score": 5, "evidence": "불량률 3.2%"},
        "champion":      {"score": 3, "evidence": "박 부장 찬성"}
      },
      "customer_themes": [
        {
          "theme_key": "operational_efficiency",
          "label": "운영 효율·자동화",
          "dimension": "identify_pain",
          "evidence": "수작업 보고에 매주 8시간 소요",
          "importance": 4
        }
      ]
    }
  ],

  "customer_themes": [
    {
      "theme_key": "operational_efficiency",
      "label": "운영 효율·자동화",
      "dimension": "identify_pain",
      "evidence": "수작업 보고에 매주 8시간 소요",
      "importance": 4,
      "meeting_id": "uuid",
      "meeting_date": "2026-06-08"
    }
  ],

  "meddpicc_latest": {
    "health_pct": 72.4,
    "gaps":       ["economic_buyer", "decision_criteria"],
    "metrics":       {"score": 4.0, "trend": "up"},
    "economic_buyer":{"score": 1.5, "trend": "flat"},
    "decision_criteria": {"score": 1.0, "trend": "flat"},
    "decision_process":  {"score": 3.0, "trend": "up"},
    "identify_pain":     {"score": 5.0, "trend": "flat"},
    "champion":          {"score": 3.0, "trend": "up"},
    "competition":       {"score": 2.0, "trend": "flat"}
  },

  "summary_embedding": [0.012, -0.034, "... 384 floats"],

  "created_at": "2026-05-01T00:00:00+00:00",
  "updated_at": "2026-06-08T12:00:00+00:00"
}
```

## 모듈 구조

```
src/deal_intel/
  mcp_server.py         FastMCP 진입점 — 18개 tool 등록
                        native ML runtime은 main thread pre-import
                        embedding warmup + Mongo index 생성은 background 실행
  cli.py                typer CLI — login-chatgpt / backfill-customer-themes /
                        render-atlas-dashboard / crosscheck-weekly-dashboard
  _env.py               dotenv 로드 + 3-tier config 병합 (yaml merge)
  _context.py           프로세스 싱글톤 (지연 초기화)
                        config() / llm_provider() / embedding_provider() / mongo()
                        사용자 tool 경로에서는 네트워크 초기화 작업을 수행하지 않음

  providers/
    llm.py              LLMProvider ABC
                        AnthropicProvider   — anthropic SDK, prompt caching
                        ChatGPTOAuthProvider — httpx, OAuth token refresh
                        make_llm_provider(cfg) factory
    embedding.py        EmbeddingProvider ABC
                        SentenceTransformerProvider — all-MiniLM-L6-v2 lazy load
                        make_embedding_provider(cfg) → None if not installed

  schema/
    meddpicc.py         _DIMS, VALID_STAGES, Contact, StageHistoryEntry
                        compute_meddpicc_latest(meetings, weights, gap_threshold, deal_stage)
                        → stage-aware gap 기준 (proposal/negotiation: identify_pain 임계값 완화)
                        Deal, Meeting Pydantic 모델

  storage/
    mongodb.py          MongoDBClient — pymongo lazy import
                        preload_driver()      — main thread에서 pymongo 선행 import
                        ensure_indexes()      — 5개 일반 인덱스 (idempotent)
                        ensure_vector_index() — Atlas Vector Search index (createSearchIndexes)
                        search_by_embedding() — $vectorSearch aggregation pipeline

  tools/
    create_deal.py      딜 생성, stage_history 초기화 [{stage:"discovery", entered_at:now}]
    add_meeting.py      MEDDPICC 추출 LLM → 요약 LLM → meddpicc_latest 재계산 → 임베딩 저장
    get_customer_themes.py
                        customer_themes를 고유 deal 기준으로 집계
    backfill_customer_themes.py
                        기존 meetings에 customer_themes를 idempotent backfill
    get_deal.py         단순 조회
    update_stage.py     VALID_STAGES 검증 → stage_history append → meddpicc_latest 재계산
    update_deal.py      확인된 deal_size_*·metadata 필드 수정 → history append
    archive_deal.py     confirmed archive → default BI/read path exclusion
    restore_deal.py     confirmed restore → default BI/read path inclusion
    delete_deal.py      dry-run first hard delete → delete_audit_logs snapshot
    create_sample_data.py
                        separate demo database sample creation
    delete_sample_data.py
                        separate demo database sample deletion
    list_deals.py       _days_in_current_stage() → is_stuck → stuck 우선 / health_pct 역순 정렬
    get_metrics.py      pipeline_health MCP metric view
    get_deal_gaps.py    read-only prioritized sales follow-up gaps
    export_report.py    weekly_pipeline CSV·Markdown 파일 export
    get_insights.py     7가지 aggregation: pipeline_overview / win_patterns / loss_patterns /
                        compare_won_lost / gap_frequency / industry_benchmark / stage_velocity
    analyze_deal.py     MEDDPICC 집계 텍스트 → LLM → 갭 분석 + BD 전략
    search_deals.py     query embed → Python cosine 기본 / Atlas 선택 → 점수 반환
```

## MEDDPICC health_pct 계산

```
health_pct = Σ(dim_avg_i × weight_i) / Σ(5 × weight_i) × 100
```

dim_avg: 해당 딜의 모든 미팅에서 해당 차원 점수 평균.
trend: 최근 2개 미팅 점수 비교 → "up" / "down" / "flat".

**가중치 (`config/defaults.yaml`)**:
```yaml
meddpicc:
  weights:
    champion:          2.0
    identify_pain:     1.5
    economic_buyer:    1.5
    metrics:           1.0
    decision_criteria: 1.0
    decision_process:  1.0
    competition:       0.5
  gap_threshold: 2
```

ML 자동 조정: `~/.deal-intel/config.yaml`에 weights 섹션 override → 코드 변경 없이 적용.

Health band와 BI stage population의 공식 계약은 [metrics.md](metrics.md)를 따른다.
Health band 경계값은 고정 상수가 아니라 운영 config다:

```yaml
metrics:
  health_bands:
    healthy_min: 70
    watch_min: 40
```

## Stage-aware 갭 분류

```python
_NO_GAP_STAGES      = {"won"}                        # 종결 딜은 갭 없음
_LATE_ACTIVE_STAGES = {"proposal", "negotiation"}    # 후반 단계
_PAIN_LATE_THRESHOLD = 1                             # identify_pain 임계값 완화
```

proposal / negotiation 에서 identify_pain 이 낮아지는 것 = Pain이 해소되는 긍정 신호.
다른 단계에서는 gap_threshold(기본 2) 미만이면 갭으로 분류.

## 3-tier Config

우선순위 낮음 → 높음:

1. `config/defaults.yaml` — 소스에 포함된 기본값
2. `.env` — ANTHROPIC_API_KEY, MONGODB_URI (gitignored)
3. `~/.deal-intel/config.yaml` — 사용자 override (ML weight 튜닝 등)

## Vector Search 흐름

```
add_meeting 호출
  │
  ├─ LLM: MEDDPICC 추출 (1회)
  ├─ LLM: 미팅 요약 생성 (1회, 실패해도 계속)
  ├─ meeting.summary = 요약 텍스트
  ├─ deal.meetings.append(meeting)
  ├─ meddpicc_latest 재계산
  ├─ _build_deal_text(): 전체 미팅 요약 concatenate (최대 1500자)
  ├─ embedding_provider.embed(deal_text) → 384-dim vector
  └─ deal.summary_embedding = vector → MongoDB upsert

search_deals 호출
  │
  ├─ embedding_provider.embed(query) → 384-dim query vector
  ├─ 기본(M0): 임베딩이 있는 딜을 읽어 Python dot product로 cosine 순위 계산
  └─ 선택(M10+): $vectorSearch index로 ANN 검색
       → 두 경로 모두 cosine similarity 내림차순 결과 반환
```

## LLM Provider 선택 로직

```python
# make_llm_provider(cfg)
provider = cfg["llm"]["provider"]   # "chatgpt_oauth" | "anthropic"
env_override = os.environ.get("DEAL_INTEL_USE_CHATGPT_OAUTH")
```

ChatGPT OAuth 주의사항 (`docs/lesson-learned.md` 참조):
- `max_tokens` / `temperature` 파라미터 포함 금지 (Codex backend가 400 반환)
- OAuth token 만료 시 자동 refresh (refresh_token 사용)
- 모델: gpt-5.5 / gpt-5.4 (config에서 override 가능)

## Stuck 기준 (configurable)

```yaml
pipeline:
  expected_close:
    default_days: 7
    days_by_industry:
      공공: 60
      대기업: 28
  stuck_threshold_days: 14       # 기본값 (stage override 없을 때)
  stuck_threshold_days_by_stage:
    discovery:     7
    qualification: 14
    proposal:      21
    negotiation:   30

metrics:
  overdue:
    grace_days: 0
  win_rate:
    minimum_closed_sample: 10

reporting:
  timezone: Asia/Seoul
```

`list_deals` 결과에서 `is_stuck: true` 딜이 상위 정렬되며 overdue와
attention reason도 함께 반환한다. expected close를 직접 입력하지 않은 새 딜은
기본 7일 또는 업종 override를 적용한다. `list_deals`, `get_metrics`, `get_insights`는
`as_of`, `timezone`, UTC `generated_at`을 반환한다. 명시적 `as_of`는 현재
컬렉션을 해당 날짜 기준으로 계산하며 과거 문서 상태를 복원하지 않는다.
