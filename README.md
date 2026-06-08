# deal-intel-mcp

회의록을 붙여넣으면 MEDDPICC 점수가 나오고, 어떤 딜이 막혔는지·어디서 지고 있는지를 MongoDB에 쌓아 분석해주는 B2B 영업 지원 MCP 서버.

Claude Desktop이나 MCP를 연결한 Codex에서 말로 하면 된다. 별도 CRM 앱은 없다.

---

## 이게 뭔가요?

**MEDDPICC**란 B2B 영업에서 쓰는 딜 자격 심사 프레임워크다. 7가지 항목으로 "이 고객이 실제로 살 가능성이 있는가"를 점수화한다.

| 항목 | 뭘 보는가 |
|---|---|
| **M**etrics | 고객이 기대하는 수치적 효과 (ROI, 비용 절감 %) |
| **E**conomic Buyer | 실제 예산 집행 권한자가 누구인가 |
| **D**ecision Criteria | 벤더 선정 기준이 뭔가 |
| **D**ecision Process | 내부 승인 절차가 어떻게 돌아가나 |
| **I**dentify Pain | 고객이 겪는 핵심 문제와 긴급도 |
| **C**hampion | 내부에서 우리 편인 사람이 있는가 |
| **C**ompetition | 경쟁사·현 상태 유지(Status Quo)와 어떻게 싸우나 |

이 서버는 회의록을 넣으면 LLM이 이 7가지를 자동으로 추출하고, MongoDB Atlas에 쌓아서 패턴 분석까지 해준다.

---

## 설치 (5분)

### 사전 조건

- Claude Desktop (Windows / Mac)
- Python 3.11 이상 + conda 환경에 `pip install -e .` 완료
- MongoDB Atlas 계정 (M0 무료 클러스터면 충분)
- ChatGPT Plus/Pro 구독 **또는** Anthropic API key

### 설치 순서

**1단계 — 패키지 설치**

```bash
# event-intel conda 환경 재사용
~/miniconda3/envs/event-intel/python.exe -m pip install -e ".[embedding]"
```

`[embedding]` 을 붙이면 `sentence-transformers`(유사 딜 검색용)도 같이 설치된다.

**2단계 — .env 파일 설정**

프로젝트 루트의 `.env.example`을 `.env`로 복사한 뒤 채운다.

```
MONGODB_URI=mongodb+srv://<user>:<password>@<cluster>.mongodb.net/?retryWrites=true&w=majority
ANTHROPIC_API_KEY=sk-ant-...   # ChatGPT OAuth 쓸 거면 비워도 됨
```

**3단계 — mcpb 설치**

`mcpb/manifest.json` 기준으로 만든 `deal-intel-mcp-0.1.5.mcpb`를 더블클릭하거나
Claude Desktop → Settings → Extensions → 파일로 설치한다.
번들 빌드 방법은 [`mcpb/README.md`](mcpb/README.md)를 참고한다.

나타나는 입력 폼:
- **MongoDB Atlas URI** — 위에서 설정한 URI 붙여넣기
- **Use ChatGPT Plus/Pro** — 기본 체크, ChatGPT OAuth 쓸 거면 그대로
- **Anthropic API key** — Anthropic 쓸 거면 입력, ChatGPT OAuth면 비워도 됨

**4단계 — ChatGPT OAuth 로그인** (ChatGPT 구독자만)

```bash
~/miniconda3/envs/event-intel/python.exe -m deal_intel.cli login-chatgpt
```

브라우저가 열리면 ChatGPT 계정으로 로그인. 한 번만 하면 된다.

**5단계 — Claude Desktop 재시작**

도구 목록에 아래 9개가 보이면 완료.

```
create_deal / add_meeting / get_deal / update_stage
list_deals / get_insights / get_customer_themes / analyze_deal / search_deals
```

---

## 사용 가이드 (9개 도구)

> **팁**: Claude Desktop에서 아래 예시 문장을 그대로 입력하거나 비슷하게 말하면 된다.
> deal_id는 `create_deal` 또는 `list_deals`로 확인할 수 있다.

---

### 1. `create_deal` — 새 딜 만들기

**언제 쓰나**: 새 고객사와 상담을 시작했을 때 제일 먼저 실행.

**예시 대화**:
```
현대정밀 새 딜 만들어줘. 제조업종이고 딜 규모는 2억원.
```

**실제 파라미터**:
| 파라미터 | 필수 | 설명 |
|---|---|---|
| `company` | 필수 | 고객사 이름 |
| `industry` | 선택 | 업종 (예: "제조", "IT SaaS") |
| `deal_size_krw` | 선택 | 예상 계약 규모 (원 단위, 예: 200000000) |
| `expected_close_date` | 선택 | 예상 클로징 날짜. 생략 시 config 기본값 적용 |

**결과 예시**:
```json
{
  "ok": true,
  "deal_id": "a3f9...",
  "company": "현대정밀",
  "expected_close_date": "2026-06-15",
  "expected_close_date_source": "config_default"
}
```

이 `deal_id`를 기억해두거나 `list_deals`로 나중에 다시 확인할 수 있다.

예상 종료일을 생략하면 생성일로부터 기본 7일 뒤가 자동 입력된다. 이 날짜는
확정 일정이 아니라 운영 기본값이다. 사용자가 직접 입력한 날짜는 항상 config보다
우선한다.

```yaml
pipeline:
  expected_close:
    default_days: 7
    days_by_industry:
      공공: 60
      대기업: 28
```

업종 override는 자유 형식 `industry` 값과 대소문자를 무시하고 정확히 일치할
때 적용된다.

---

### 2. `add_meeting` — 회의록 추가

**언제 쓰나**: 고객사와 미팅이 끝난 직후. 노트를 그대로 붙여넣으면 LLM이 MEDDPICC를 자동으로 추출한다.

**예시 대화**:
```
현대정밀 deal_id: a3f9... 에 오늘(2026-06-08) 회의록 추가해줘.

회의 내용:
김 이사(구매 결정권자)를 만남. 현재 생산라인 불량률 3.2%로 연간 15억 손실 발생 중.
우리 솔루션으로 1.5% 이하 목표. 박 부장이 사내 도입 찬성 입장.
경쟁사는 A사 검토 중이나 가격 2배 문제 있음. 내부 승인은 6월 말 예정.
```

**실제 파라미터**:
| 파라미터 | 필수 | 설명 |
|---|---|---|
| `deal_id` | 필수 | 대상 딜 ID |
| `date` | 필수 | 미팅 날짜 (YYYY-MM-DD) |
| `raw_notes` | 필수 | 회의록 원문 (한국어/영어 모두 가능) |

**결과에 포함되는 것**:
- `meddpicc` — 이번 미팅에서 추출된 점수 + 근거
- `meddpicc_latest` — 딜 전체 누적 health_pct + 차원별 트렌드
- `summary` — LLM이 생성한 2~3문장 요약
- `customer_themes` — 이번 미팅에서 추출된 고객 고민·선정 기준
- `stage_suggestion` — 회의록이 단계 전환(예: 계약 체결 → won, 실주 → lost)을 명시할 때만 채워짐. 그 외엔 `null`
- `embedding_stored` — 유사 딜 검색용 임베딩 저장 여부

> **stage는 자동으로 안 바뀐다.** 회의록에 "계약 완료"라고 적혀 있어도 `add_meeting`은 단계를 직접 바꾸지 않고 `stage_suggestion`으로 **제안만** 한다. Claude가 "이 딜 won으로 바꿀까요?"라고 물어보면, 확인 후 `update_stage`가 실제로 단계를 변경한다. 잘못된 자동 클로징을 막기 위한 의도된 분리다.

---

### 3. `get_deal` — 딜 상세 조회

**언제 쓰나**: 특정 딜의 전체 히스토리, MEDDPICC 점수, 미팅 기록을 확인할 때.

**예시 대화**:
```
현대정밀 딜 전체 내용 보여줘. deal_id는 a3f9...
```

회의록 원본, 각 미팅별 MEDDPICC 추출 결과, 누적 health_pct가 모두 나온다.

---

### 4. `update_stage` — 파이프라인 단계 변경

**언제 쓰나**: 딜이 다음 단계로 넘어가거나 결과가 확정됐을 때.

```text
update_stage(deal_id, new_stage, actual_close_date="")
```

**예시 대화**:
```
현대정밀 딜 proposal 단계로 올려줘.
```

`won` 또는 `lost`로 변경할 때 실제 종료일을 `YYYY-MM-DD`로 지정할 수 있다.
생략하면 처리 당일이 저장된다. `expected_close_date`는 예상일로 유지되며,
`stage_history.entered_at`은 시스템에서 변경한 감사 시각이므로 실제 종료일과
구분한다. 종료 딜을 다시 열린 stage로 옮기면 `actual_close_date`는 제거된다.

**사용 가능한 단계** (순서대로):
```
discovery → qualification → proposal → negotiation → won / lost / stalled
```

**결과에 포함되는 것**:
- `actual_close_date` — Won/Lost의 실제 종료일
- `days_in_previous_stage` — 이전 단계에 얼마나 있었는지
- `stuck_threshold_days` — 새 Active 단계의 stuck 기준 일수; 그 외 `null`
- MEDDPICC 갭이 단계에 따라 자동 재계산됨 (예: proposal 단계에서 Identify Pain 하락은 갭이 아님 — 고객의 Pain이 해소되고 있다는 긍정 신호)

---

### 5. `list_deals` — 전체 딜 현황 보기

**언제 쓰나**: 파이프라인 전체를 한눈에 보고 싶을 때. 주 1회 리뷰에 활용.

**예시 대화**:
```
전체 딜 목록 보여줘. 막혀있는 딜 먼저.
```

또는 특정 단계만:
```
현재 proposal 단계 딜들만 보여줘.
```

**결과**:
- `health_pct` — MEDDPICC 종합 점수 (0~100)
- `gaps` — 점수가 낮은 취약 차원 목록
- `is_stuck` — Active stage 체류일이 단계별 기준 이상인지
- `is_overdue` / `overdue_days` — Open 딜이 예상 종료일을 넘겼는지
- `attention_reasons` — `stalled`, `overdue`, `stuck`, `at_risk` 복수 사유
- `days_in_stage` — 현재 단계에서 머문 일수

stuck 딜이 상위에 정렬되어 나온다.

---

### 6. `analyze_deal` — MEDDPICC 갭 분석 + BD 전략

**언제 쓰나**: 특정 딜이 막혀있거나 다음 미팅 전략을 세울 때. LLM이 갭을 분석하고 구체적인 액션을 제안한다.

**예시 대화**:
```
현대정밀 딜 분석해줘. 어디가 약한지, 다음 미팅에서 뭘 해야 하는지.
```

결과에 포함되는 것:
- 현재 MEDDPICC 건강도 요약
- 취약 차원별 구체적 대응 방안
- 다음 미팅 권고 아젠다

---

### 7. `get_insights` — 파이프라인 BI 분석

**언제 쓰나**: 전체 딜 데이터를 집계해서 패턴을 파악할 때. 월간 리뷰, 성공/실패 패턴 학습에 활용.

**7가지 분석 유형**:

| query_type | 무엇을 알려주나 |
|---|---|
| `pipeline_overview` | 단계별 딜 수·평균 health·총 규모 |
| `win_patterns` | Won 딜들의 MEDDPICC 평균 점수 |
| `loss_patterns` | Lost 딜들의 MEDDPICC 평균 점수 |
| `compare_won_lost` | Won vs Lost 차원별 점수 차이 |
| `gap_frequency` | 활성 딜에서 가장 자주 빠지는 항목 |
| `industry_benchmark` | 업종별 평균 health·승률·딜 규모 |
| `stage_velocity` | 단계별 평균 체류 일수 |

**예시 대화**:
```
우리 파이프라인 전체 현황 보여줘.
```
```
이기는 딜이랑 지는 딜의 MEDDPICC 패턴 차이가 뭐야?
```
```
어떤 항목이 제일 자주 빠져 있어?
```

---

### 8. `search_deals` — 유사 딜 시맨틱 검색

**언제 쓰나**: 과거에 비슷한 상황의 딜이 어떻게 흘러갔는지 참고하고 싶을 때. 자연어로 검색한다.

**예시 대화**:
```
비용 절감 문제를 가진 고객사 딜 찾아줘.
```
```
champion이 강하고 의사결정 구조가 명확했던 딜 보여줘.
```
```
현대정밀이랑 패턴이 비슷한 딜 있어?
```

**어떻게 동작하나**:
1. 검색어를 384차원 벡터로 변환
2. 모든 딜의 미팅 요약 벡터와 cosine similarity 계산
3. 유사도 높은 순으로 정렬해 반환

**결과에 포함되는 것**:
- `score` — 유사도 (0~1, 높을수록 비슷함)
- `deal_stage`, `health_pct`, `gaps` — 해당 딜 현재 상태

> 서버 시작 시 로컬 embedding 모델을 background warmup한다. 준비 중이면
> `warming_up: true`가 반환되므로 5초 뒤 다시 요청한다. 30초 이상이면 stalled 오류로 전환된다.

---

### 9. `get_customer_themes` — 고객 고민·선정 기준 빈도

**언제 쓰나**: 여러 딜의 미팅 근거를 묶어 고객이 가장 자주 고민한 주제를 확인할 때.
미팅 수가 아니라 고유 딜 수 기준으로 집계하며 대표 회사와 evidence를 함께 반환한다.

**예시 대화**:
```
활성 딜에서 고객들이 가장 많이 고민한 부분 Top 5 보여줘.
```
```
Decision Criteria에서 가장 자주 나온 주제와 근거를 알려줘.
```

**필터**:
- `dimension`: `all`, `identify_pain`, `decision_criteria`, `metrics`
- `stage`: `active`, `all` 또는 개별 딜 stage
- `industry`: 정확한 업종명
- `top_k`: 최대 20

기존 데이터에 주제를 채우려면 먼저 실행한다:

```bash
~/miniconda3/envs/event-intel/python.exe -m deal_intel.cli backfill-customer-themes --apply
```

Atlas Charts용 aggregation은 `scripts/atlas_charts_customer_themes.json`에 있다.

---

## 권장 사용 흐름

```
1. 미팅 직후       → add_meeting (회의록 붙여넣기)
2. 단계 진행 시    → update_stage
3. 미팅 전 준비    → analyze_deal (다음 아젠다 파악)
4. 주간 리뷰       → list_deals (막힌 딜 확인)
5. 월간 회고       → get_insights compare_won_lost / stage_velocity
6. 유사 사례 참고  → search_deals
7. 고객 고민 분석  → get_customer_themes
```

---

## 아키텍처

```
[Claude Desktop / Codex — 자연어 입력]
         │ stdio JSON-RPC
         ▼
[deal-intel-mcp  FastMCP 서버  9 tools]
         │
         ├── LLM Provider
         │     ├── ChatGPT OAuth (기본, Plus/Pro 구독)
         │     └── Anthropic API (선택)
         │
         ├── Embedding Provider
         │     └── sentence-transformers all-MiniLM-L6-v2
         │          → 로컬 실행 / API key 불필요 / 384 dims
         │
         └── MongoDB Atlas M0
               deals collection
               └── Regular Indexes  : deal_id, stage+updated, health_pct, customer themes

search_deals
  ├── M0 기본   : summary_embedding을 읽어 Python cosine 계산
  └── M10+ 선택 : Atlas Vector Search index 사용
```

### 딜 도큐먼트 스키마 (주요 필드)

```json
{
  "deal_id": "uuid",
  "company": "현대정밀",
  "industry": "제조",
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
      "raw_notes": "김 이사 미팅. 불량률 3.2% → 1.5% 목표...",
      "summary": "LLM이 생성한 2~3문장 요약",
      "meddpicc": {
        "metrics":      {"score": 4, "evidence": "연간 15억 손실"},
        "identify_pain": {"score": 5, "evidence": "불량률 3.2%, 생산라인 긴급"},
        "champion":     {"score": 3, "evidence": "박 부장 찬성 입장"}
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

### 모듈 구조

```
src/deal_intel/
  mcp_server.py         FastMCP 진입점, 9개 tool 등록
  cli.py                typer CLI (login-chatgpt, backfill-customer-themes)
  _env.py               dotenv + 3-tier config 병합
  _context.py           LLM / MongoDB / Embedding 프로세스 싱글톤
  providers/
    llm.py              LLMProvider ABC + Anthropic + ChatGPTOAuth + factory
    embedding.py        EmbeddingProvider + SentenceTransformerProvider + factory
  schema/
    meddpicc.py         compute_meddpicc_latest, Deal/Meeting Pydantic 모델
    customer_themes.py  고객 주제 taxonomy, parser, stage signal 검증
  storage/
    mongodb.py          MongoDBClient — CRUD + aggregation + semantic search storage
  tools/
    create_deal.py
    add_meeting.py      MEDDPICC 추출 + summary 생성 + 임베딩 저장
    get_deal.py
    update_stage.py     stage_history 기록 + MEDDPICC 재계산
    list_deals.py       health_pct / gaps / stuck flag 집계
    get_insights.py     7가지 MongoDB aggregation BI 쿼리
    get_customer_themes.py
                        고객 고민을 고유 딜 수 기준으로 집계
    analyze_deal.py     MEDDPICC 갭 분석 + BD 전략 LLM 생성
    search_deals.py     Python cosine 기본 / Atlas 선택 시맨틱 검색
```

### MEDDPICC health_pct 계산 방식

```
health_pct = sum(dim_avg × weight) / sum(5 × weight) × 100
```

가중치 (`config/defaults.yaml`에서 조정 가능):

| 차원 | 가중치 | 이유 |
|---|---|---|
| champion | 2.0 | 내부 동력 없으면 딜 성사 불가 |
| identify_pain / economic_buyer | 1.5 | 문제 확인·예산권자 접근 핵심 |
| metrics / decision_criteria / decision_process | 1.0 | 표준 |
| competition | 0.5 | 경쟁 파악은 후반에 나타나는 게 정상 |

**단계별 갭 기준 조정** (`update_stage` 시 자동 적용):
- `proposal` / `negotiation` 단계에서 Identify Pain 점수 하락 → 갭 아님 (고객 Pain이 해소되고 있다는 신호)
- `won` 딜 → 갭 없음

**Health band 운영 설정**:

기본값은 Healthy 70 이상, Watch 40 이상, At Risk 40 미만이다. 이 값은
수주 확률이 아니라 MEDDPICC 검증 수준의 분류 기준이며, 운영 데이터가 쌓이면
`~/.deal-intel/config.yaml`에서 변경할 수 있다.

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

Active/Open/Stalled와 미평가 처리의 공식 정의는
[`docs/metrics.md`](docs/metrics.md)에 있다.

---

## FAQ

**Q. 회의록을 꼭 완벽하게 써야 하나요?**
아니다. 핵심만 메모한 수준이어도 된다. LLM이 없는 항목은 그냥 건너뛴다.

**Q. 한국어 회의록도 되나요?**
된다. 영어·한국어 혼합도 된다.

**Q. MongoDB Atlas 유료 플랜이 필요한가요?**
현재 기본 기능은 M0 무료 플랜으로 동작한다. `search_deals`도 M0에서는 Python
cosine으로 계산한다. 딜 수가 커지면 M10+에서 Atlas Vector Search로 전환할 수 있다.

**Q. search_deals 결과가 비어있어요.**
서버 최초 실행 직후라면 로컬 모델이 준비 중일 수 있으므로 5초 뒤 다시 요청한다.
또한 `add_meeting`을 실행해 `summary_embedding`이 저장된 딜이 최소 1건 있어야 한다.

**Q. ChatGPT OAuth와 Anthropic 중 뭘 써야 하나요?**
ChatGPT Plus/Pro 구독이 있으면 ChatGPT OAuth가 추가 비용 없이 쓸 수 있어 유리하다.
Anthropic API는 prompt caching 지원으로 반복 분석이 많으면 비용 측면에서 유리할 수 있다.
