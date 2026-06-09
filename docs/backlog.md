# Backlog

장기 계획, 미구현 항목. 진행 중/직전 완료는 [status.md](status.md).

---

## P1 — BI Reporting MVP

각 항목은 독립 서브 태스크로 구현하고 targeted test와 전체 회귀 gate를 통과한 뒤
다음 항목으로 이동한다.

### #1 Metric 계약과 공통 계산

1. 완료: Active/Open/Stalled 범위와 health assessment 정의
2. 완료: config 기반 health band와 경계값 fixture 테스트
3. 완료: pipeline value, 추정 범위, 전략적 0원, 금액 coverage 정의
4. 완료: stuck/overdue, win rate, expected close 기본값 정의
5. 완료: 데이터 품질 coverage, reporting timezone, 재현 가능한 `as_of`
6. 완료: `get_insights`와 향후 CSV가 공유할 순수 계산 모듈

현재 계약: [metrics.md](metrics.md)

Milestone 1.2 상태:

- 완료: `build_pipeline_health_summary`를 BI/CSV/Atlas 공통 계산기로 추가
- 완료: `get_insights("pipeline_overview")`가 공통 계산기를 사용하도록 전환
- 완료: `get_metrics(pipeline_health)` MCP 도구 구현
- 완료: Weekly Pipeline 보고서 행 생성기
- 완료: UTF-8 BOM CSV 저장과 formula injection 방어
- 완료: LLM 없는 Markdown 요약
- 완료: `export_report(report_type="weekly_pipeline")` MCP 도구
- 완료: Atlas Charts Pipeline Dashboard와 교차 검증

### #2 `get_metrics` MCP 도구

완료. `pipeline_health`와 `pipeline_trend`를 지원한다. stage·industry 필터,
KPI, stage별 집계, coverage, warning, snapshot 기반 추세를 반환한다.
LLM과 embedding은 사용하지 않는다.

### #3 Weekly Pipeline 보고서

1. 완료: 보고서 row 생성기
2. 완료: UTF-8 BOM CSV와 formula injection 방어
3. 완료: LLM 없는 Markdown 요약
4. 완료: `export_report(report_type="weekly_pipeline")` MCP 도구

CSV Reporting MVP Gate 통과. 다음 단계는 실제 주간 회의에서 CSV/Markdown
보고서를 사용해 본 뒤 Atlas Charts 대시보드와 교차 검증을 진행한다.

### #4 Atlas Charts Pipeline Dashboard

1. 완료: `Weekly Pipeline Review` aggregation JSON 버전 관리
2. 완료: KPI, stage별 건수·금액, health band, stuck/overdue, MEDDPICC gap
   pipeline을 실제 Atlas read smoke로 검증
3. 완료: Atlas UI dashboard 구성 runbook과 `render-atlas-dashboard` CLI 추가
4. 완료: MongoDB Atlas UI에서 `Weekly Pipeline Review` dashboard 구성 및
   6개 chart 화면 확인
5. 완료: `get_metrics`, CSV/Markdown, Atlas Charts aggregation 주요 KPI 교차 검증

Atlas Charts MVP 완료. 다음 BI 작업은 실제 주간 리뷰에서 사용해 본 뒤 데이터 품질
또는 추세 분석으로 이동한다.

### #5 데이터 품질

완료: M4.3 deal lifecycle safety layer. `archive_deal`, `restore_deal`,
`delete_deal`을 추가했다. 기본 BI/read path는 archived deal을
`{"archived": {"$ne": true}}`로 제외하며, legacy document는 계속 보인다.
hard delete는 `dry_run=true`가 기본이고, 실제 삭제는 archived deal에 대해
사용자 확인, exact company match, 삭제 사유, safe audit snapshot 저장 후에만
수행한다.

완료: M4.4 onboarding/demo sample data. 샘플 데이터는 운영 DB의
`is_sample` 필터가 아니라 `mongodb.demo_database` 기반 별도 demo database
context에서 `create_sample_data`와 `delete_sample_data`로만 관리한다.
두 도구 모두 `dry_run=true`가 기본이며 실제 write/delete는
`confirmed_by_user=true`가 필요하다.

`data_quality` metric, 누락 정보 보고서, Claude/Codex 보완 흐름을 각각 별도
태스크로 구현한다.

완료: `get_deal_gaps` read-only customer-attack gap view. table completeness가
아니라 다음 영업 액션, forecast trust, postmortem에 필요한 미확인 정보를
우선순위화한다. MongoDB write, LLM, embedding은 사용하지 않는다.

완료: `update_deal` value-only MVP. 기존 딜의 `deal_size_*` 필드는
`confirmed_by_user=true`와 `deal_size_note` 근거가 있을 때만 수정하고,
`deal_value_history`를 남긴다.

완료: `update_deal` metadata 확장. `company`, `industry`,
`expected_close_date`, `actual_close_date`, `close_reason`은
`confirmed_by_user=true`와 사용자 승인 근거(`update_note`)가 있을 때만
수정한다. stage 변경은 계속 `update_stage`로만 처리한다.

남은 범위: `add_meeting` 등 LLM 기반 경로는 향후
`deal_value_suggestion`만 반환하고 금액 필드를 자동 변경하지 않는다.

### #6 추세 분석

완료: M5.1-M5.5 trend foundation. `analytics_snapshots` 저장 계약을 추가하고
`create_deal`, `add_meeting`, `update_stage`에 non-blocking snapshot 기록을
연결했다. Snapshot은 `event_id` 기준 idempotent upsert이며, 실패해도 원래
딜 작업은 중단하지 않고 응답에 warning만 반환한다.

완료: M5.6 `pipeline_trend` metric. `get_metrics`에서
`metric_type="pipeline_trend"`를 지원하며, 기본 7일 lookback으로
`analytics_snapshots`의 시작/종료 latest snapshot을 비교한다.

완료: M5.7 trend CSV. `export_report(report_type="pipeline_trend")`가
analytics snapshot 기반 trend summary를 CSV와 Markdown으로 저장한다.

남은 범위: Atlas 추세 차트.

---

## P2

### #7 OpenAI API provider support

완료. `llm.provider: openai_api`가 공식 OpenAI Responses API를 사용하도록
추가했다. `OPENAI_API_KEY`, `llm.openai_api_model`,
`llm.openai_api_reasoning_effort`로 설정하며 기존 MCP tool surface는 그대로
유지한다. 현재 환경에는 OpenAI API credit/key가 없어 live smoke는 mock HTTP
테스트로 대체했다.

추후 검증 필요: disposable `OPENAI_API_KEY`와 API credit이 준비되면
`llm.provider: openai_api`로 최소 live smoke를 수행한다. 검증 범위는
provider ping, 작은 `chat_once` 1회, 그리고 가능하면 `add_meeting`의 LLM
경로 1회다. 비용이 발생하므로 명시적으로 opt-in할 때만 수행한다.

### #8 Customer Themes 확장

Customer Themes CSV, 산업·stage 비교, 전용 Atlas 대시보드와 evidence drill-down.

### #9 Atlas Vector Search 전환 (M10+)

M0 호환 Python cosine 기반 `search_deals`는 완료. 딜 수가 커져 M10+로 올릴 때
`mongodb.vector_search: atlas`와 `deal_summary_vector` 인덱스로 전환하고 성능을 검증.

### #10 in-app ChatGPT 로그인

현재 `login-chatgpt`는 CLI-only이며 브라우저 인증을 수행한다. MCP 도구화 시
blocking 호출을 피하고 인증 상태와 재시도 계약부터 정의한다.

### #11 Notion 연동

Notion에서 작성한 회의록을 Notion API → `add_meeting`으로 자동 싱크.

### #12 deal_stage 추천 확장

현재 명시적 회의록 신호는 `stage_suggestion`으로 제안한다. 향후 MEDDPICC 점수 기반
추천을 추가하더라도 자동 변경하지 않고 사용자 확인 후 `update_stage`를 호출한다.

### #13 확인 정책 config / Autopilot 모드

현재 `create_deal`은 금액 입력 시 `deal_size_status` 확인을 강제하고,
`add_meeting`은 stage 변경을 `stage_suggestion`으로만 제안한다. 이는 데이터 품질에는
좋지만, 일부 사용자는 "AI가 보수적으로 추정해서 먼저 결과물을 만들고 나중에
고치기"를 선호할 수 있다.

M3 이후 별도 태스크로 다음 운영 모드를 config화한다.

- `strict`: 현재 동작. 금액 분류, 0원 딜, stage 변경은 사용자 확인 필요.
- `assistant_default`: AI/assistant가 보수적 기본값을 넣고 warning을 반환.
  예: 양수 금액 + status 누락 시 `rough_estimate`.
- `autopilot`: 가능한 한 진행하고 data quality/report에서 추정값과 warning을 노출.

초기 config 후보:

```yaml
workflow:
  confirmation_mode: strict  # strict | assistant_default | autopilot
  require_confirmation_for:
    deal_value_classification: true
    stage_change_from_meeting: true
    terminal_stage_change: true
```

구현 시 기존 metric의 `estimated` / `confirmed` coverage와 연결해서, autopilot이
편하더라도 BI에서 추정값과 확인값은 계속 분리한다.

---

## P3

### #14 event-intel-mcp 연결
event-intel-mcp의 prospect → deal 전환 트리거. `prospect_id` 필드는 이미 스키마에 있음.

### #15 성공 사례 GTM 확산 리포트

현재 semantic search 결과와 won/lost 데이터가 충분히 누적된 뒤 유사 딜 패턴 기반
GTM 전략 리포트를 추가한다.

---

## 의도적 OOS

- **Web UI**: CLI + Claude Desktop으로 충분. 별도 결정 시 새 product.
- **실시간 CRM 동기 (Salesforce/HubSpot)**: v0 scope 밖. CSV export를 우선한다.
