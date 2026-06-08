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

## 다음 스텝

1. BI Reporting Milestone 1.1 metric 계약 정의
2. metric 경계값·누락값·종료 딜 fixture 테스트
3. 공통 metric 계산 모듈 구현 전 계약 gate 검증
