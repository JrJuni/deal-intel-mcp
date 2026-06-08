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
5. 결정 필요: 데이터 누락률, reporting timezone과 `as_of`
6. 이후: `get_insights`와 향후 CSV가 공유할 순수 계산 모듈

현재 계약: [metrics.md](metrics.md)

### #2 `get_metrics` MCP 도구

첫 view는 `pipeline_health`만 지원한다. stage·industry 필터, KPI, stage별 집계,
coverage와 warning을 반환한다.

### #3 Weekly Pipeline 보고서

1. 보고서 row 생성기
2. UTF-8 BOM CSV와 formula injection 방어
3. LLM 없는 Markdown 요약
4. `export_report(report_type="weekly_pipeline")` MCP 도구

### #4 Atlas Charts Pipeline Dashboard

CSV Reporting MVP가 실제 주간 회의에서 검증된 뒤 진행한다. KPI, stage별 건수·금액,
health band, stuck/overdue, MEDDPICC gaps를 표시하고 MCP/CSV 결과와 교차 검증한다.

### #5 데이터 품질

`data_quality` metric, `update_deal`, 누락 정보 보고서, Claude/Codex 보완 흐름을
각각 별도 태스크로 구현한다.

`update_deal`의 금액 변경은 status, 중앙값, 범위, 근거를 사용자에게 먼저 보여주고
명시적 승인 이후에만 저장한다. `add_meeting` 등 LLM 기반 경로는
`deal_value_suggestion`만 반환하며 금액 필드를 자동 변경하지 않는다.

### #6 추세 분석

현재 상태 BI가 안정된 뒤 `analytics_snapshots`, 변경 이벤트 idempotency,
`pipeline_trend`, 추세 CSV와 Atlas 차트를 순서대로 추가한다.

---

## P2

### #7 Customer Themes 확장

Customer Themes CSV, 산업·stage 비교, 전용 Atlas 대시보드와 evidence drill-down.

### #8 Atlas Vector Search 전환 (M10+)

M0 호환 Python cosine 기반 `search_deals`는 완료. 딜 수가 커져 M10+로 올릴 때
`mongodb.vector_search: atlas`와 `deal_summary_vector` 인덱스로 전환하고 성능을 검증.

### #9 in-app ChatGPT 로그인

현재 `login-chatgpt`는 CLI-only이며 브라우저 인증을 수행한다. MCP 도구화 시
blocking 호출을 피하고 인증 상태와 재시도 계약부터 정의한다.

### #10 Notion 연동

Notion에서 작성한 회의록을 Notion API → `add_meeting`으로 자동 싱크.

### #11 deal_stage 추천 확장

현재 명시적 회의록 신호는 `stage_suggestion`으로 제안한다. 향후 MEDDPICC 점수 기반
추천을 추가하더라도 자동 변경하지 않고 사용자 확인 후 `update_stage`를 호출한다.

---

## P3

### #12 event-intel-mcp 연결
event-intel-mcp의 prospect → deal 전환 트리거. `prospect_id` 필드는 이미 스키마에 있음.

### #13 성공 사례 GTM 확산 리포트

현재 semantic search 결과와 won/lost 데이터가 충분히 누적된 뒤 유사 딜 패턴 기반
GTM 전략 리포트를 추가한다.

---

## 의도적 OOS

- **Web UI**: CLI + Claude Desktop으로 충분. 별도 결정 시 새 product.
- **실시간 CRM 동기 (Salesforce/HubSpot)**: v0 scope 밖. CSV export를 우선한다.
