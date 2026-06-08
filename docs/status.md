# Status

진행 중인 작업과 최근 완료 항목. 장기 계획은 [backlog.md](backlog.md).

## 현재 (2026-06-08)

### BI Reporting Milestone 0.1 완료

- 9개 MCP 도구의 runtime 입력 계약과 응답 surface 기록
- 전체 테스트 `17 passed`
- 기존 Ruff 28건 정리, `ruff check .` 통과
- wheel build와 CLI entry point 검증
- 실제 MongoDB Atlas 읽기 smoke 통과 (10개 딜)
- 상세 기준선: [baseline.md](baseline.md)

### Customer Themes / Semantic Search MVP 완료

- 9개 MCP 도구 등록, `get_customer_themes` 추가
- `add_meeting`에서 MEDDPICC와 함께 고객 고민 주제를 통제 taxonomy로 추출
- 고유 딜 기준 주제 빈도, coverage, 대표 회사·evidence 집계
- 기존 데이터용 `backfill-customer-themes` CLI 추가
- 기존 10개 딜의 customer themes backfill 완료
- Atlas Charts용 aggregation pipeline 추가
- M0 호환 Python cosine 기반 `search_deals`와 startup warmup guard 추가

### 문서 정합성 완료

- `CLAUDE.md`, `AGENTS.md`, README, architecture, backlog, MCPB 안내를 현재 코드 기준으로 동기화
- M0 검색 경로를 Python cosine으로 명확히 하고 M10+ Atlas 전환과 구분
- 로컬 전용 설정과 build artifact는 gitignore 유지

### BI Reporting Milestone 1.1 Part A 완료

- Active, Stalled, Open, Terminal stage population 계약 고정
- 미평가 딜을 `unassessed`로 분리하고 평균 health에서 제외
- Health band 기본값 `70/40`을 `metrics.health_bands` config로 이동
- 잘못된 threshold는 명시적 오류로 차단
- 계약 및 미결정 항목: [metrics.md](metrics.md)

### BI Reporting Milestone 1.1 Part B 완료

- 금액 상태를 `unknown`, `rough_estimate`, `customer_budget`, `quoted`,
  `strategic_zero`로 구분
- 중앙 추정치와 low/high 범위의 유효성 계약 및 순수 계산 함수 추가
- 누락 금액, 전략적 0원, 기존 무분류 금액, 잘못된 금액을 별도 집계
- Pipeline value, known range, validated value, amount coverage 계약 고정
- LLM 추론 금액은 자동 저장하지 않고 사용자 승인 후 별도 update를 수행하도록 계약
- Won/Lost 실제 종료일을 예상일 및 시스템 stage 변경시각과 분리
- `update_stage` actual close 입력과 MCP forwarding test 추가
- 전체 테스트 `58 passed`, Ruff 통과
- 기존 합성 Won 3건의 actual close date backfill은 범위에서 제외

### BI Reporting Milestone 1.1 Part C 완료

- Stuck을 Active stage 체류일 `>=` config 기준으로 고정
- Stalled, unassessed stage history, terminal 상태를 stuck과 분리
- Open 딜의 expected close 기반 overdue와 config grace period 추가
- Win rate 분모를 `won + lost`로 수정하고 최소 표본 warning 계약 추가
- 복수 `attention_reasons`와 중복 없는 향후 KPI 계약 정의
- expected close 기본 7일 및 업종별 config override 추가
- 자동 날짜와 사용자 입력 날짜를 source로 구분
- targeted test `25 passed`, 전체 테스트 `83 passed`, Ruff 통과
- 실제 Atlas read smoke: 10개 중 overdue 3개, 산업별 closed-only 승률 확인
- create write smoke는 운영 Atlas 데이터 오염을 피하기 위해 생략

### BI Reporting Milestone 1.1 Part D 완료

- 필드 품질을 `valid`, `estimated`, `missing`, `invalid`,
  `not_applicable`로 분리
- 딜별 및 전체 usable coverage와 confirmed coverage 추가
- `reporting.timezone` 기본값을 `Asia/Seoul`로 설정
- `list_deals`, `get_insights`에 재현 가능한 `as_of`, `timezone`,
  UTC `generated_at` 메타데이터 추가
- 예상 종료일과 실제 종료일의 자동 기본값은 업무 시간대를 사용하고 감사
  timestamp는 UTC 유지

## 다음 스텝

1. Milestone 1.1 전체 계약 회귀 검토
2. Milestone 1.2 공통 metric 계산 모듈 구현
3. `get_metrics(pipeline_health)` MCP 도구 구현
