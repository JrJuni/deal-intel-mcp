# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project north star

**deal-intel-mcp** 는 상담 내역·회의록을 MEDDPICC 기준으로 구조화하고 MongoDB Atlas에 저장, Codex/ChatGPT 분석으로 BD 전략과 성공 패턴 BI를 제공하는 MCP 서버다.

시블링 프로젝트: `event-intel-mcp` (전시회 잠재고객 발굴) → **이 프로젝트** (발굴된 고객의 딜 자격 심사 및 클로징 관리).

## Dev environment

`event-intel` conda 환경을 재사용하거나 신규 생성:

```bash
# Option A: event-intel 환경 재사용 (의존성 대부분 겹침)
~/miniconda3/envs/event-intel/python.exe -m pip install -e ".[dev,embedding]"

# Option B: 신규 환경
~/miniconda3/Scripts/conda.exe create -n deal-intel python=3.11 -y
~/miniconda3/envs/deal-intel/python.exe -m pip install -e ".[dev,embedding]"
```

항상 conda env의 Python을 직접 사용 — bare `python` / `py` 금지 (Windows Store stub).

## Common commands

```bash
# 패키지 설치
~/miniconda3/envs/event-intel/python.exe -m pip install -e ".[dev,embedding]"

# ChatGPT OAuth 로그인 (최초 1회, 브라우저 열림)
~/miniconda3/envs/event-intel/python.exe -m deal_intel.cli login-chatgpt

# MCP 서버 (stdio, 보통 Codex Desktop이 spawn)
~/miniconda3/envs/event-intel/python.exe -m deal_intel.mcp_server

# 테스트
~/miniconda3/envs/event-intel/python.exe -m pytest

# 정적 검사
~/miniconda3/envs/event-intel/python.exe -m ruff check .

# 기존 미팅 customer themes backfill (기본 dry-run)
~/miniconda3/envs/event-intel/python.exe -m deal_intel.cli backfill-customer-themes
~/miniconda3/envs/event-intel/python.exe -m deal_intel.cli backfill-customer-themes --apply
```

## Working loop

Juni가 선호하는 작업 루프:

1. 큰 작업 단위의 계획과 다음 서브태스크를 먼저 정한다.
2. 복잡하거나 인간 의사결정이 필요한 태스크는 구현 전에 세부 계획,
   검증 기준, 우려되는 에러/코너케이스, sensemaker 설명을 정리한다.
3. 결정할 내용이 거의 없는 작은 태스크는 바로 구현-검증 루프로 진행한다.
4. 기술 검증 시 우려 포인트를 먼저 테스트 셋으로 고정하고, targeted test,
   관련 regression, full pytest, Ruff, 필요한 smoke test로 닫혔는지 확인한다.
5. 검증하지 못한 항목은 `docs/status.md` 또는 `docs/backlog.md`에 잔여 위험으로
   기록한다.
6. 작업이 닫히면 관련 docs를 업데이트하고, 의도한 범위만 커밋한다. 사용자가
   요청하면 push까지 진행한다.

Repo-local 규칙은 이 `AGENTS.md`에 둔다. 여러 레포에서 반복 적용할 개인 작업법으로
커지면 별도 Codex skill로 승격한다.

## Architecture

```
Codex Desktop (stdio JSON-RPC)
   │
   ▼
deal_intel.mcp_server (FastMCP) — 18 tools
   │
   ├─ create_deal          — 신규 딜 생성 (MongoDB upsert)
   ├─ add_meeting          — 회의록 + MEDDPICC/customer themes 추출 (LLM)
   ├─ update_stage         — stage_history 기록 및 단계 변경
   ├─ update_deal          — 확인된 deal value·metadata 수정
   ├─ archive_deal         — 딜 archive 처리
   ├─ restore_deal         — archived 딜 복구
   ├─ delete_deal          — archived 딜 hard delete (dry-run 기본)
   ├─ create_sample_data   — demo DB에 fictional sample data 생성
   ├─ delete_sample_data   — demo DB sample data 삭제 (dry-run 기본)
   ├─ get_deal             — 딜 전체 조회
   ├─ list_deals           — 딜 목록, health/gaps/stuck 표시
   ├─ get_insights         — 파이프라인 BI 집계
   ├─ get_metrics          — pipeline_health / pipeline_trend metric 반환
   ├─ get_deal_gaps        — 고객 공략 정보 공백 우선순위화
   ├─ export_report        — weekly_pipeline / pipeline_trend CSV·Markdown 파일 생성
   ├─ get_customer_themes  — 고객 고민/선정 기준 빈도 집계
   ├─ search_deals         — 유사 딜 검색 (M0: Python cosine, M10+: Atlas 선택)
   └─ analyze_deal         — MEDDPICC 갭 분석 + BD 전략 생성 (LLM)
   │
   ▼
MongoDB Atlas M0 (MONGODB_URI env)
   └─ deals collection: 딜 + 회의록 + MEDDPICC + 고객 주제 + 임베딩 + BD 전략
```

### 3-tier config (event-intel-mcp와 동일 패턴)

- `.env` → 시크릿 (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `MONGODB_URI`)
- `config/defaults.yaml` → 기본값 (LLM provider, 모델명, DB 이름)
- `~/.deal-intel/config.yaml` → 사용자 override (예: `llm.provider: chatgpt_oauth`)

## LLM Provider

`providers/llm.py`는 event-intel-mcp에서 이식. `_TOKEN_PATH`만 `~/.deal-intel/chatgpt_auth.json`으로 변경.

- **기본**: `chatgpt_oauth` (ChatGPT Plus/Pro 구독, 추가 비용 없음)
- **옵션**: `anthropic` (ANTHROPIC_API_KEY 필요)
- **옵션**: `openai_api` (OPENAI_API_KEY 필요, 공식 OpenAI Responses API)

ChatGPT OAuth 구현 당시 누적된 5가지 함정은 `docs/lesson-learned.md` 참조.

## DO NOT

- **pymongo import는 `storage/mongodb.py` 내부에서만.** 메인 스레드 선행 import가 필요하면
  `storage.mongodb.preload_driver()`를 호출할 것.
- **Tool 핸들러는 `_context.py`의 싱글톤을 통해서만 LLM/MongoDB에 접근.** 직접 인스턴스화 금지.
- **`make_llm_provider(config)`를 쓸 것.** `AnthropicProvider()`,
  `ChatGPTOAuthProvider()`, `OpenAIAPIProvider()`를 직접 호출하지 말 것 —
  config 라우팅을 우회함.
- **MCP tool handler는 동기 블로킹 작업을 tool 호출 안에서 수행할 때 FastMCP worker thread 제약 인지.** 무거운 import는 `mcp_server.py::main()`에서 pre-import.
- **`add_meeting`은 stage를 자동 변경하지 않는다.** `stage_suggestion`을 사용자에게 확인한 뒤
  `update_stage`를 호출할 것.

## Project docs convention

- `docs/status.md` — 지금 진행 중 / 직전 완료
- `docs/backlog.md` — 장기 계획 / 미구현 / defer 항목
- `docs/architecture.md` — 아키텍처 상세
- `docs/baseline.md` — MCP 계약 / 테스트 / 실 DB 검증 기준선
- `docs/metrics.md` — BI/CSV/Charts가 공유하는 metric 의미와 경계값 계약
- `docs/lesson-learned.md` — 실패 로그 (append-only, failures only)
