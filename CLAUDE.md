# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project north star

**deal-intel-mcp** 는 상담 내역·회의록을 MEDDPICC 기준으로 구조화하고 MongoDB Atlas에 저장, Claude/ChatGPT 분석으로 BD 전략과 성공 패턴 BI를 제공하는 MCP 서버다.

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

# MCP 서버 (stdio, 보통 Claude Desktop이 spawn)
~/miniconda3/envs/event-intel/python.exe -m deal_intel.mcp_server

# 테스트
~/miniconda3/envs/event-intel/python.exe -m pytest

# 정적 검사
~/miniconda3/envs/event-intel/python.exe -m ruff check .

# 기존 미팅의 customer themes 확인 후 반영
~/miniconda3/envs/event-intel/python.exe -m deal_intel.cli backfill-customer-themes
~/miniconda3/envs/event-intel/python.exe -m deal_intel.cli backfill-customer-themes --apply
```

## Architecture

```
Claude Desktop (stdio JSON-RPC)
   │
   ▼
deal_intel.mcp_server (FastMCP) — 10 tools
   │
   ├─ create_deal          — 신규 딜 생성 (MongoDB upsert)
   ├─ add_meeting          — 회의록 추가 + MEDDPICC 자동 추출 (LLM)
   │                         + customer_themes 추출, stage 전환 신호 시 stage_suggestion 반환
   ├─ update_stage         — 파이프라인 단계 변경 + stage_history 기록 + MEDDPICC 재계산
   ├─ get_deal             — 딜 전체 조회 (회의록 + MEDDPICC 포함)
   ├─ list_deals           — 딜 목록 (stage 필터, health_pct·gaps·stuck 정렬)
   ├─ get_insights         — 7가지 BI aggregation (win/loss 패턴, stage velocity 등)
   ├─ get_metrics          — pipeline_health KPI·stage 집계·warning 반환
   ├─ get_customer_themes  — 고객 고민·선정 기준 빈도 (고유 딜 수 기준 + evidence)
   ├─ search_deals         — 시맨틱 유사 딜 검색 (M0: Python cosine, M10+: Atlas 선택)
   └─ analyze_deal         — MEDDPICC 갭 분석 + BD 전략 생성 (LLM)
   │
   ▼
MongoDB Atlas M0 (MONGODB_URI env)
   └─ deals collection: 딜 + 회의록 + MEDDPICC + customer_themes + BD 전략
                        + summary_embedding (M0에서는 앱에서 cosine 계산)
```

> 도구별 상세 사용법·파라미터·예시 대화는 `README.md`의 "사용 가이드 (10개 도구)" 참조.

### 3-tier config (event-intel-mcp와 동일 패턴)

- `.env` → 시크릿 (`ANTHROPIC_API_KEY`, `MONGODB_URI`)
- `config/defaults.yaml` → 기본값 (LLM provider, 모델명, DB 이름)
- `~/.deal-intel/config.yaml` → 사용자 override (예: `llm.provider: chatgpt_oauth`)

## LLM Provider

`providers/llm.py`는 event-intel-mcp에서 이식. `_TOKEN_PATH`만 `~/.deal-intel/chatgpt_auth.json`으로 변경.

- **기본**: `chatgpt_oauth` (ChatGPT Plus/Pro 구독, 추가 비용 없음)
- **옵션**: `anthropic` (ANTHROPIC_API_KEY 필요)

ChatGPT OAuth 구현 당시 누적된 5가지 함정은 `docs/lesson-learned.md` 참조.

## DO NOT

- **pymongo import는 `storage/mongodb.py` 내부에서만.** 메인 스레드 선행 import는
  `storage.mongodb.preload_driver()`를 사용할 것.
- **Tool 핸들러는 `_context.py`의 싱글톤을 통해서만 LLM/MongoDB에 접근.** 직접 인스턴스화 금지.
- **`make_llm_provider(config)`를 쓸 것.** `AnthropicProvider()`나 `ChatGPTOAuthProvider()`를 직접 호출하지 말 것 — config 라우팅을 우회함.
- **MCP tool handler는 동기 블로킹 작업을 tool 호출 안에서 수행할 때 FastMCP worker thread 제약 인지.** 무거운 import는 `mcp_server.py::main()`에서 pre-import.
- **`add_meeting`은 `deal_stage`를 절대 자동 변경하지 말 것.** 회의록이 "CLOSED WON" 등 클로징을 명시해도 stage 전환은 `stage_suggestion` 필드로 **제안만** 하고, 실제 변경은 사용자 확인 후 `update_stage` 호출로만 한다 (의도된 분리 — 잘못된 자동 클로징 방지).

## Project docs convention

- `docs/status.md` — 지금 진행 중 / 직전 완료
- `docs/backlog.md` — 장기 계획 / 미구현 / defer 항목
- `docs/architecture.md` — 아키텍처 상세
- `docs/baseline.md` — MCP 계약 / 테스트 / 실 DB 검증 기준선
- `docs/metrics.md` — BI/CSV/Charts가 공유하는 metric 의미와 경계값 계약
- `docs/lesson-learned.md` — 실패 로그 (append-only, failures only)
