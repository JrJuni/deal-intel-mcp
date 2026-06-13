# AGENTS.ko.md

이 파일은 `AGENTS.md`의 한국어 companion 문서다. 최신 source of truth는
항상 `AGENTS.md`이며, 이 파일은 Juni가 한국어 문서 업데이트를 요청했을 때
함께 갱신한다.

## 문서 언어 정책

- 영문 문서가 기본 source of truth다.
- `docs/`, `AGENTS.md`, `CLAUDE.md`, `README.md`, `mcpb/README.md`는 영어와
  ASCII 중심으로 유지한다.
- 한국어로 지속 관리하는 문서는 두 개만 둔다.
  - `README.ko.md`
  - `AGENTS.ko.md`
- 그 외 문서의 한국어 설명이 필요하면 repo에 남기기보다 대화에서 번역을 요청한다.

## 프로젝트 방향

`deal-intel-mcp`는 B2B 딜 인텔리전스 MCP 서버다. 회의록을 MEDDPICC 신호로
구조화하고, 딜 상태와 BI/reporting 도구를 Claude, Codex, ChatGPT, CSV,
Atlas Charts에서 쓸 수 있게 한다.

제품 방향은 한 레포/한 패키지 안에서 세 가지 profile을 제공하는 것이다.

- `sample`: MongoDB 없이 bundled sample data로 바로 써보는 read-only 데모
- `full`: MongoDB Atlas 기반 실제 운영 모드
- `pro`: OpenAI/Anthropic API와 Atlas Vector Search 같은 유료 인프라 경로

## 먼저 읽을 문서

기본 작업에서는 모든 문서를 다 읽지 않는다.

1. `AGENTS.md` 또는 `CLAUDE.md`
2. `docs/README.md`
3. `docs/status.md`
4. `docs/baseline.md`
5. 필요한 영역별 계약 문서

긴 기록 문서인 `docs/lesson-learned.md`, 오래된 `docs/backlog.md` 섹션은
검색해서 필요한 부분만 본다.

## 작업 루프

Juni가 선호하는 루프:

1. 큰 작업 단위와 다음 서브태스크를 먼저 정한다.
2. 복잡하거나 제품 의사결정이 필요한 일은 계획, 리스크, 검증 기준,
   sensemaker 요약을 먼저 정리한다.
3. 작은 일은 바로 구현-검증 루프로 간다.
4. 우려되는 코너케이스를 targeted test로 먼저 고정한다.
5. targeted test, 관련 regression, full pytest, Ruff, 필요한 smoke test로 닫는다.
6. 검증하지 못한 위험은 `docs/status.md` 또는 `docs/backlog.md`에 남긴다.
7. docs를 업데이트하고 의도한 범위만 커밋한다. push는 요청받았을 때 진행한다.

Windows에서 pytest를 돌릴 때는 기본 `%TEMP%`를 쓰지 말고 레포 내부 temp를 쓴다.

```powershell
& "$HOME\miniconda3\envs\event-intel\python.exe" -m pytest -q --basetemp=.tmp\pytest-full
```

Codex/Claude sandbox에서는 `%TEMP%` 아래 `pytest-of-*` 경로가 읽기 불가일 수
있고, 이 경우 테스트 자체가 실패한 게 아니라 fixture setup 단계에서 막힌다.

## 현재 MCP 도구

현재 tool count는 21개다. 정확한 기준은 `src/deal_intel/mcp_server.py`다.

- Write/lifecycle:
  `create_deal`, `add_meeting`, `update_stage`, `update_deal`,
  `archive_deal`, `restore_deal`, `delete_deal`
- Demo data:
  `create_sample_data`, `delete_sample_data`
- Read/review:
  `get_deal`, `list_deals`, `get_deal_gaps`, `get_deal_review`
- BI/reporting:
  `get_insights`, `get_metrics`, `export_report`
- Customer themes:
  `get_customer_themes`, `get_customer_theme_breakdown`,
  `get_customer_theme_evidence`
- Search/analysis:
  `search_deals`, `analyze_deal`

## 중요한 규칙

- storage와 LLM provider는 `_context.py`를 통해 접근한다.
- provider class를 직접 만들지 말고 `make_llm_provider(config)`를 쓴다.
- BI/reporting 경로에서는 LLM과 embedding을 사용하지 않는다.
- metric/report/review 경로는 raw notes, contacts, embedding을 기본적으로 제외한다.
- `add_meeting`은 stage를 자동 변경하지 않는다. `stage_suggestion`만 반환하고,
  실제 변경은 사용자 확인 후 `update_stage`로 한다.
- 삭제/수정 도구는 dry-run, 명시적 확인, reason, audit-safe snapshot을 우선한다.
- 테스트나 문서에 진짜 secret처럼 보이는 placeholder를 쓰지 않는다.
