# Status

## Latest Update - 2026-06-09

### BI Reporting Milestone 2.3 완료

- `build_weekly_pipeline_markdown` Markdown 요약 생성기 추가
- 입력은 M2.1 `weekly_pipeline` row report만 허용
- LLM, embedding, MongoDB, 파일 쓰기 없이 deterministic Markdown body 생성
- KPI, 위험 딜, 데이터 품질 warning table 포함
- CSV와 같은 row surface에서 숫자를 계산하도록 고정
- CSV 저장 결과를 다시 읽어 Markdown metrics와 row count, pipeline value, attention deal count가 일치하는 테스트 추가
- Targeted test: `16 passed`
- Full pytest: `123 passed`
- Ruff: `ruff check .` 통과
- Atlas read/write smoke 없음: 2.3은 pure renderer 작업

다음 단계: Milestone 2.4 `export_report(report_type="weekly_pipeline")` MCP 도구

### BI Reporting Milestone 2.2 완료

- `save_report_csv` CSV 저장 모듈 추가
- CSV 저장은 호출자가 명시한 `output_dir`에만 수행
- filename: `{report_type}_YYYYMMDD_HHMMSS.csv`, `generated_at`은 UTC 기준으로 변환
- Excel 한글 호환을 위해 `utf-8-sig` BOM 적용
- CSV formula injection 방어: 첫 non-whitespace 문자가 `=`, `+`, `-`, `@`이면 single quote prefix
- `dict`와 `list` cell은 `ensure_ascii=False` JSON으로 직렬화
- 원본 회의록, 연락처, embedding은 M2.1 row 계약상 CSV 입력 surface에 포함하지 않음
- 파일 쓰기 실패는 `IO_ERROR` / `storage` structured error로 반환
- Targeted test: `12 passed`
- Full pytest: `119 passed`
- Ruff: `ruff check .` 통과
- Atlas write smoke 없음: 2.2는 로컬 CSV 파일 저장만 수행하고 DB를 변경하지 않음

### BI Reporting Milestone 2.1 완료

- `weekly_pipeline` report row generator 추가
- Open deals only: `discovery`, `qualification`, `proposal`, `negotiation`, `stalled`
- Terminal `won`, `lost`는 주간 파이프라인 row에서 제외
- Row fields: company, industry, stage, amount, expected close, days in stage,
  stuck/overdue, health, MEDDPICC gaps, last meeting date, primary pain,
  primary decision criteria, attention reasons, data quality
- Sorting: overdue, stuck, stalled, at risk, earliest expected close, largest amount, company
- Raw notes/contact/vector 미노출 계약을 `docs/reports.md`에 기록
- Targeted test: `7 passed`
- Full pytest: `114 passed`
- Ruff: `ruff check .` 통과
- Atlas read smoke: `2026-06-09` 기준 row `7`, warnings `incomplete_data_quality`, raw notes/contact/vector 미노출 확인
- Atlas write smoke 없음: 2.1은 read-only row 생성 작업

진행 중인 작업과 최근 완료 항목. 장기 계획은 [backlog.md](backlog.md).

## 현재 (2026-06-09)

### BI Reporting Milestone 1.3 완료

- `get_metrics(metric_type="pipeline_health")` MCP 도구 추가
- stage·industry exact-match 필터 지원
- `as_of`, `timezone`, UTC `generated_at` reporting context 반환
- KPI, stage breakdown, health bands, attention reasons, pipeline values, win rate, data quality, warnings 반환
- `get_metrics`는 1.2 공통 계산기와 metric read projection을 그대로 사용
- targeted test: `5 passed`
- targeted regression set: `24 passed`
- full pytest: `107 passed`
- Ruff: `ruff check .` 통과
- FastMCP 등록 smoke: 10 tools
- Atlas read smoke: `2026-06-09` 기준 10건, Open value `453000000`, raw notes/contact/vector 미노출 확인
- Atlas write smoke 없음: 1.3은 read-only metric view

다음 단계: Milestone 2.1 `weekly_pipeline` 보고서 행 생성기

### BI Reporting Milestone 1.2 완료

- `build_pipeline_health_summary` 공통 계산 모듈 추가
- `get_insights("pipeline_overview")`가 Mongo aggregation 대신 공통 계산 모듈 사용
- `total_size_krw` alias를 Open pipeline value 기준으로 교정
- metric read path `MongoDBClient.list_deals_for_metrics()` 추가
- metric projection에서 `_id`, `meetings.raw_notes`, `contacts`, `summary_embedding` 제외
- targeted test: `19 passed`
- full pytest: `102 passed`
- Ruff: `ruff check .` 통과
- FastMCP 등록 smoke: 9 tools 유지
- Atlas read smoke: `2026-06-09` 기준 10건, Open value `453000000`, raw notes/contact/vector 미노출 확인
- Atlas write smoke 없음: 1.2는 read-only BI 계산 작업

## 이전 (2026-06-08)

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

1. Milestone 2.1 `weekly_pipeline` 보고서 행 생성기
2. Milestone 2.2 UTF-8 BOM CSV 저장과 formula injection 방어
3. Milestone 2.3 LLM 없는 Markdown 요약
