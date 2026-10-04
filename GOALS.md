# GOALS — maple-optimizer 백로그

`/goal` 파이프라인(설정 C)이 읽는 백로그. 위에서부터 순서대로 진행한다.
스펙: `docs/superpowers/specs/2026-10-03-maple-optimizer-design.md`

- 상태: `TODO` → `DOING` → `VERIFIED` | `PARTIAL`(기준 미달, 사실대로 기록) | `BLOCKED`(같은 게이트 3회 연속 실패 또는 사람 몫)
- AUTO: `자동` = 에이전트가 끝낼 수 있음 / `사람` = 사람이 해야 함(선행 작업 후 할 일만 정리)
- 판정: `scripts/verify.ps1 -Goal <ID>` 종료코드 0. skip은 통과가 아니다.
- 목표별 판정 테스트는 `tests/goals/test_<id>.py`. 측정값은 `goals/results/<ID>.json`에 기록한다.
- 성공 기준을 실행 도중에 느슨하게 고치지 않는다.

| ID | 단계 | 목표 | 성공 기준 (숫자) | AUTO | 상태 |
|---|---|---|---|---|---|
| G1 | 1b | 잔차 분해, 아이템 교체, 세트 효과, 프리셋 27조합 평가, 보스 실딜 지수 | ① 레테 사냥 세팅 스냅샷(fixture)에서 보스 세팅(장비2·하이퍼3·어빌2) 전환을 예측한 최대 스탯공격력과 실제 보스 스냅샷(`.raw-pairs/레테_boss` → 익명화 fixture) 값의 상대 오차 ≤ 1% ② 45개 직업 전원에서 "자기 자신으로 교체" Δ실딜 = 0 (절대 오차 < 1e-9) ③ 프리셋 조합(장비·하이퍼·어빌리티, 2026-10-04부터 유니온·링크 포함 — 레테 162개) 최적 조합의 실딜 지수 ≥ 실제 보스 세팅 조합의 실딜 지수 | 자동 | VERIFIED (① 같은 상태 짝 0.76%, 2026-10-04) |
| G2 | 2 | 매물 평가 엔진 (`engine/market`) | ① 매물 = 현재 착용 템과 같은 옵션이면 Δ실딜 = 0 (< 1e-9), 45명 ② 레테 보스 프리셋 반지4를 사냥 세팅 반지4 자리에 매물로 넣은 Δ가 G1 교체 계산과 1e-9 이내로 같음 ③ 억당 효율 = Δ실딜% ÷ ((가격 − 판매가)/1억) 수작업 계산값과 1e-9 이내, 판매가 ≥ 가격이면 명시적 오류 | 자동 | VERIFIED |
| G3 | 2 | FastAPI 서버 (`server/`): 공개 계산 API, SQLite 캐시, IP 호출 제한 | ① 엔드포인트 테스트 ≥ 12개 통과, skip 0 ② 같은 캐릭터 2회 조회 시 2회차 넥슨 호출 0회 ③ 넥슨 오류 4종(캐릭터 없음·한도·점검·키)이 서로 다른 HTTP 상태와 한국어 메시지로 매핑 ④ IP 제한 초과 시 429 | 자동 | VERIFIED |
| G4 | 2 | React+Vite 웹 (`web/`): 캐릭터 조회, 보스 세팅 표시, 매물 입력, 효율 표 | ① `npm --prefix web run build` 종료코드 0 ② `npm --prefix web test` vitest ≥ 8개 통과 ③ FastAPI가 빌드 결과를 서빙: TestClient `GET /`가 200 + `<div id="root">` | 자동 | VERIFIED |
| G5 | 3 | 강화 기댓값 (`engine/enhance`): 스타포스·큐브·추옵 비용 분포 | ① 스타포스 정확 계산 평균과 몬테카를로(10만 회, 고정 시드) 평균 차 ≤ 1% (0→22성, 파괴 복구비 포함, 3개 이상 조건) ② 큐브 목표 확률 정확 열거와 몬테카를로(10만 회) 차 ≤ 1%p ③ 확률 테이블 파일마다 출처 URL·기준일 기록 | 자동 | VERIFIED |
| G6 | 3 | 매물의 직작 기댓값 대비, 내 운 분석 | ① 매물 가격의 직작 비용 분포 백분위 계산이 몬테카를로 경험 분포와 1%p 이내 ② `확률 정보 조회` 응답(fixture, 익명화)에서 실제 지출 합산이 수작업 합계와 일치 | 자동 | VERIFIED |
| G7 | 4 | 예산 최적화 (`engine/optimize`) | ① 고정 시드 30개 소규모 인스턴스(후보 ≤ 10)에서 재평가 탐욕법/전수 탐색 최적값 비율 평균 ≥ 0.95, 최소 ≥ 0.85 (측정값 기록) ② 부위 배타성 위반 0건 ③ 예산 초과 0건 | 자동 | VERIFIED |
| G8 | 2~4 | 로컬 통합: 서버+웹으로 조회→매물→강화 비용→최적화 흐름 | ① 녹화 fixture 기반 E2E 테스트(서버 API 연쇄 호출) 통과 ② `scripts/run-local.ps1`로 서버 기동 후 `/api/health` 200 ③ README에 로컬 실행·시크릿 소재지 문서화 | 자동 | VERIFIED |
| G9 | 2~4 | 웹 화면 확장: 스타포스 비용·큐브 확률·직작 vs 매물·예산 최적화 패널 | ① 패널 4개 각각 "입력 → 서버 호출 → 결과 표시" vitest 통과(테스트 이름 고정: starforce panel, cube panel, craft panel, optimize panel) ② vitest 전체 ≥ 20 통과 ③ `npm --prefix web run build` 종료코드 0 | 자동 | VERIFIED |
| G10 | 배포 | 배포 준비물: Dockerfile(arm64 가능), docker-compose(api+caddy), Caddyfile, GitHub Actions 워크플로 | ① `docker compose config` 종료코드 0 ② `docker build` 성공 후 컨테이너에서 `/api/health` 200 ③ 워크플로 YAML 파싱 + 시크릿 이름이 README 표와 일치 | 자동 | VERIFIED |
| H1 | 배포 | Oracle Always Free VM 생성, 도메인, Docker Compose 배포 | VM에서 `https://<도메인>/api/health` 200 | 사람 | TODO |
| H2 | 배포 | 넥슨 서비스 단계 키 신청 | 서비스 단계 키 발급 | 사람 | TODO |
| H3 | 배포 | GitHub Actions Secrets·Variables 등록 (README 시크릿 표) | 배포 job 성공 | 사람 | TODO |
| G11 | 5 | 관리자 전용 AI 에이전트 (OpenAI Responses API 함수 호출, 엔진 도구 7개, SSE — 2026-10-04 Claude에서 전환) | ① 고정 시나리오 4개(가짜 모델 응답)에서 도구 호출 이름·인자·순서 4/4 일치 ② 숫자 출처 검사: 정상 시나리오 답변 숫자 100% 도구 결과에 존재, 위조 숫자 시나리오 검출 1/1 ③ 미인증 401, 로그인 후 200, 틀린 비밀번호 401 ④ 일일 토큰 예산 초과 시 모델 호출 0회 + 한국어 안내 ⑤ 도구 예외 시 SSE `error` 이벤트 후 `done`(조용히 끊기지 않음) | 자동 | VERIFIED |
| G12 | 5 | 경매장 화면 실시간 분석: 공유 탭 화면 변화 감지 → GPT 비전 매물 추출 → 엔진 평가 | ① 변화 감지(웹, 테스트 이름 "screen watch"): 같은 화면 반복 0회, 툴팁 바뀜 → 2프레임 안정 후 1회, 3초 쿨다운 안 재호출 0회 ② 비전 추출: 가짜 모델 JSON → 매물 변환, 깨진 JSON → 명시 오류 ③ 같은 매물 2회 감지 → 평가 1회(중복 제거) ④ 반지 매물 → 반지1~4 중 실딜 최대 슬롯 자동 선택(수작업 비교 일치) ⑤ 미인증 401, 일일 토큰 한도 적용 | 자동 | VERIFIED |
| H6 | 5 | 실제 경매장 탭 공유 + 실제 비전 호출 확인 (OPENAI_API_KEY 필요) | 툴팁 1개를 읽어 평가까지 표시 | 사람 | TODO |
| H4 | 배포 | GitHub 저장소 생성·원격 연결 | 2026-10-04 완료: github.com/bat1120/maple-optimizer (private) | 사람 | VERIFIED |
| H5 | 5 | OpenAI API 키를 VM·로컬 `.env`에 넣고 에이전트 실호출 스모크 | 실제 질문 1개에 도구 호출 ≥ 1 + 숫자 검증 통과 | 사람 | TODO |
