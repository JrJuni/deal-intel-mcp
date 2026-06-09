# Status

## Latest Update - 2026-06-09

### BI Reporting Milestone 3.3 Atlas/get_metrics/CSV 교차 검증 완료

- `deal_intel.reports.dashboard_crosscheck` 추가
- `deal-intel crosscheck-weekly-dashboard` CLI 추가
- 같은 `as_of` 기준으로 세 BI surface를 비교:
  `get_metrics(pipeline_health)`, `export_report(weekly_pipeline)`,
  Atlas Charts aggregation
- 실제 Atlas UI dashboard `Weekly Pipeline Review` 수동 구성 확인
- Dashboard cards/charts:
  Active Deal Count, Open Pipeline Value, Attention Deal Count,
  Attention Deals, Stage Pipeline Value, Health Bands,
  MEDDPICC Gap Distribution
- Live Atlas cross-check: `ok=true`, mismatches 없음
- `2026-06-09` 기준 주요 일치값:
  - deal count `22`
  - active/open/stalled/terminal `12 / 13 / 1 / 9`
  - active pipeline value `977,500,000`
  - open pipeline value `1,035,500,000`
  - avg health `85.5`, health coverage `100.0`
  - health assessed count `12`
  - stuck/overdue/attention `0 / 3 / 4`
  - stage value: discovery `453,000,000`, negotiation `372,500,000`,
    proposal `152,000,000`, stalled `58,000,000`
  - health bands: healthy `19`, watch `2`, at_risk `0`, unassessed `1`
- Generated artifacts:
  `outputs/m3_3_crosscheck/weekly_pipeline_20260609_035638.csv`,
  `outputs/m3_3_crosscheck/weekly_pipeline_20260609_035638.md`
- MongoDB writes 없음, LLM/embedding 없음

### BI Reporting Milestone 3.2 Atlas Charts dashboard setup 준비

- `deal-intel render-atlas-dashboard` CLI 추가
- 전체 dashboard spec 또는 chart id별 aggregation pipeline을 config/as_of 기준으로
  렌더링
- 렌더 결과는 Atlas Charts Query bar에 바로 붙여넣을 수 있는 JSON array 또는
  full dashboard JSON
- [`docs/atlas-charts.md`](atlas-charts.md)에 Atlas UI 구성 runbook 추가
- Dashboard target: `Weekly Pipeline Review`
- Chart IDs:
  `pipeline_kpis`, `stage_breakdown`, `health_bands`, `attention_deals`,
  `meddpicc_gap_distribution`
- LLM/embedding/MongoDB write 없음
- Targeted test: `tests/test_cli_atlas_charts.py tests/test_atlas_charts.py`
  `7 passed`
- Regression subset: `tests/test_export_report.py tests/test_get_metrics.py`
  `10 passed`
- Full pytest: `152 passed`
- Ruff: `ruff check .` 통과
- CLI render smoke:
  `outputs/atlas_charts/weekly_pipeline_review_20260609.json` 생성 확인
- 실제 Atlas UI 5개 chart 생성과 화면 확인은 계정 세션에서 수행 후 M3.3
  교차 검증으로 확정

### Data Quality Prep - update_deal value-only MVP 완료

- `update_deal` MCP 도구 추가, FastMCP 등록 smoke 기준 현재 12 tools
- 첫 버전은 기존 딜의 deal value 필드만 수정:
  `deal_size_krw`, `deal_size_low_krw`, `deal_size_high_krw`,
  `deal_size_status`, `deal_size_note`
- `confirmed_by_user=true`와 비어 있지 않은 `deal_size_note`를 요구하여
  기존 딜 mutation이 사용자 확인과 근거 없이 실행되지 않도록 제한
- 기존 positive amount + missing status 딜은 amount를 보존한 채 status만
  업데이트 가능
- `unknown`으로 업데이트하면 amount/range를 `null`로 정리
- 모든 수정은 `deal_value_history`에 audit entry를 남김
- 기존 DB 읽기 확인: 현재 22 deals 중 value invalid는 0건,
  positive amount + missing status unclassified legacy는 10건,
  회사명 기준 중복은 `아르카나게임즈` 1건 확인
- Targeted test: `10 passed`
- Full pytest: `149 passed`
- Ruff: `ruff check .` 통과
- FastMCP registration smoke: 12 tools, `update_deal` required params 확인
- Atlas write smoke 없음: 기존 딜 mutation을 동반하므로 mock storage로 검증

### BI Reporting Milestone 3.1 Atlas Charts aggregation JSON 완료

- `atlas/charts/weekly_pipeline_review.v1.json` 추가
- `Weekly Pipeline Review` dashboard용 chart pipeline 5종을 버전 관리:
  KPI, stage breakdown, health bands, attention deals, MEDDPICC gap distribution
- `deal_intel.reports.atlas_charts` 렌더러 추가:
  reporting `as_of`, health band threshold, stuck/overdue config placeholder 치환
- Atlas aggregation에서 raw notes, contacts, embedding 필드 미사용
- 기존 legacy positive `deal_size_krw` + missing `deal_size_status`도 Part B
  backward-compat 계약대로 pipeline value에 포함
- Targeted test: `tests/test_atlas_charts.py` `4 passed`
- Full pytest: `141 passed`
- Ruff: `ruff check src/deal_intel/reports/atlas_charts.py tests/test_atlas_charts.py` 통과
- Atlas read smoke: chart pipeline 5종 실제 DB 실행 성공
- Atlas/get_metrics 교차 검증: `2026-06-09` 기준 주요 KPI 모두 일치
  - deal count `21`
  - active/open/stalled/terminal `12 / 13 / 1 / 8`
  - active pipeline value `977,500,000`
  - open pipeline value `1,035,500,000`
  - avg health `85.5`, health coverage `100.0`
  - stuck/overdue/attention `0 / 3 / 4`
- Atlas write smoke 없음: M3.1은 versioned aggregation JSON과 read-only 검증

### M3 Prep - create_deal 초기 금액 분류 입력 확장

- `create_deal`이 `deal_size_status`, `deal_size_low_krw`,
  `deal_size_high_krw`, `deal_size_note`를 입력받도록 확장
- `deal_size_krw=0`이 MCP wrapper에서 `None`으로 사라지던 문제 수정
- Part B 금액 계약을 저장 전 검증에 적용:
  `unknown`, `rough_estimate`, `customer_budget`, `quoted`, `strategic_zero`
- `deal_size_krw=0`만 들어오면 storage 접근 전 clarification error를 반환하여
  사용자에게 전략적 0원 딜인지 금액 미정인지 확인하게 함
- `deal_size_status=unknown`과 0 금액 필드가 함께 들어오면 금액 미정으로 보고
  `deal_size_krw`, low/high를 `null`로 정규화
- 의도적 0원 딜은 `deal_size_status=strategic_zero`일 때만 실제 0으로 저장
- 양수 금액도 `deal_size_status` 없이 신규 저장하지 않고, `rough_estimate`,
  `customer_budget`, `quoted` 중 하나를 확인하게 함
- 기존 `get_metrics`, CSV/Markdown report, data-quality 계산은 같은
  `assess_deal_value` 계약을 사용하므로 downstream metric surface 변경 없음
- FastMCP 등록 smoke: 당시 11 tools, `create_deal` nullable 금액/범위 schema 확인
- Targeted create_deal confirmation tests: `6 passed`
- Full pytest: `141 passed`
- Ruff: `ruff check .` 통과
- Atlas write smoke 없음: 실제 새 딜 생성을 동반하므로 mock storage로 검증

### BI Reporting Milestone 2.4 완료

- `export_report(report_type="weekly_pipeline")` MCP 도구 추가
- CSV와 Markdown을 같은 `weekly_pipeline` row surface에서 생성
- 기본 저장 경로: `reporting.output_dir` 또는 `outputs/reports`
- `output_dir`, `stage`, `industry`, `as_of` optional parameter 지원
- 결과에 `csv_path`, `markdown_path`, `artifacts`, `metrics`, `warnings`, `row_count` 반환
- LLM과 embedding 미사용, MongoDB write 없음
- FastMCP 등록 smoke: 11 tools
- Targeted test: `26 passed`
- Full pytest: `128 passed`
- Ruff: `ruff check .` 통과
- Atlas read/file-write smoke: `2026-06-09` 기준 row `7`, warnings `incomplete_data_quality`, CSV/Markdown 생성 및 raw notes/contact/vector 미노출 확인

CSV Reporting MVP Gate 통과. 다음 단계: Milestone 3 Atlas Charts Pipeline Dashboard

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

1. Milestone 3.1 Atlas Charts용 Pipeline dashboard aggregation JSON
2. Milestone 3.2 MongoDB Atlas `Weekly Pipeline Review` dashboard 구성
3. Milestone 3.3 `get_metrics`, CSV/Markdown, Atlas Charts KPI 교차 검증
