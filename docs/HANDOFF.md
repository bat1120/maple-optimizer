# 인수인계 (2026-10-17 갱신) — 클라우드 세션에서 이어서 작업할 때 먼저 읽기

## 지금 상태
- 운영: https://52-79-34-11.sslip.io (AWS Lightsail 서울, docker compose api+caddy). 자동 배포는 `DEPLOY_ENABLED=false`(사용자 결정 대기)
- 옛 데모 https://maple-optimizer.onrender.com 은 아직 켜져 있다(끌지 사용자 결정)
- AI 상담은 모두에게 공개(일반 IP당 하루 5번), 화면 분석도 공개(하루 20회). 추적은 Langfuse
- 2026-10-17 점검 후속: 1차(보안·비용 상한)·2차(목표 로드맵 재측정·크확 기준·기준 고지)·3차(롤백·감시·백업)·4차(사용성·문서)
- 마지막 전체 검증: pytest 590개 안팎 통과 · 2 skipped(Postgres 시험은 TEST_DATABASE_URL 없을 때 건너뜀), 웹 테스트 통과

## 최근에 만든 것 (2026-10-07)
| 영역 | 내용 | 주요 파일 |
|---|---|---|
| UI | 디자인 토큰·아이콘·패널 사용 방법·첫 방문 안내·뼈대/빈/오류 상태 | `web/src/styles.css`, `web/src/ui/` |
| 환산 연동 | MapleScouter 북마크(`#/scouter`)와 크롬 확장(내 캐릭터로 교체 후 칸 채우기) | `web/src/scouter.js`, `extension/` |
| 구매 불가 템 | 제네시스·데스티니, 아스트라 보조, 미트라 엠블렘, 엔버·카이저·제논 보조무기 | `engine/market/recommend.py` |
| 보조무기 종류 | 툴팁 장비분류 ↔ 지금 보조무기 종류(API) 맞춰 보기 | `engine/market/secondary.py` |
| 스타포스 경로 | 성별 스탯 표(실측 검산), 기대 비용·흔적 복구·평균 파괴·스페어 | `engine/enhance/starforce_stats.py`, `engine/enhance/starforce.py` |
| 강화 이벤트 | 썬데이 스타포스(개별)·파괴 방지·미라클 타임·부위별 스페어·불꽃 값 | `engine/market/events.py` |
| HEXA | HEXA 스탯(초기화 기대값)·HEXA 코어(다음 1레벨, 연무장 딜 지분) | `engine/stats/hexa.py`, `engine/market/hexa_paths.py`, `engine/market/hexa_core_paths.py` |
| 경로 비교 | 구매·직작·큐브·스타포스·추옵·HEXA·심볼을 억당으로, 종류별 상위 묶음 | `engine/market/paths.py`, `web/src/PathsPanel.jsx` |

## 다음 할 일 후보 (사용자와 정해서 진행)
- (2026-10-11 끝남: 썬데이 이벤트 개별 선택, 부위별 스페어, 화면 분석 한도 DB, 테스트 템 제거, HEXA 3rd·강화 코어, 추옵 경로)
- HEXA 강화 코어: 최종 데미지가 아닌 줄(예: 맹약 실체화 중 데미지)은 `unvalued`로만 남음 — 화면 표시 없음, 버프 유지율 출처 필요.
  6차 오버로드가 체인 커맨드 강화를 받는지 미확인. 3rd 스킬 목록 `engine/data/hexa_core_kind.json`은 공지 바뀌면 손으로 갱신
- 추옵: 보스 장비로 출처 확인된 템만(에테르넬·도전자·일반·데스티니 무기 빠짐), 제네시스 2차 해방 전 재설정 불가 미반영,
  불꽃 가격은 사용자 입력
- 보스 목록·포스 보정(2026-10-11, `engine/data/bosses.json`·`engine/stats/force.py`): 보스 id(`boss=`)로 방어율·요구 포스, 포스는 넥슨 stat '아케인포스'·'어센틱포스'.
  남은 것: 11레벨 지역 보스 데미지 +20%(최종뎀/데미지% 출처 없음 — 미반영), 발드릭스(나무 방어율 칸 비어 있음 — 목록에 없음),
  칭호 포스의 장비 프리셋별 차이(미반영), 어센틱 격차표 행 사이 값(바로 아래 행으로 봄)
- AI 상담: 캐릭터 화면 맨 위에 모두에게(2026-10-17 공개). 일반 사용자는 IP당 하루 AGENT_PUBLIC_DAILY(기본 5)번,
  refresh_market 없음. 하루 토큰 한도(AGENT_DAILY_TOKEN_BUDGET, 기본 20만)는 관리자와 같이 쓴다 — 일반 사용자가 다 쓰면 관리자도 막힌다.
  AI가 request_auction_screen을 부르면 채팅 안 [화면 연결] → [매물 N개 AI에게 보내기]
- AI 추적(2026-10-17, `agent/tracing.py`): LANGFUSE_PUBLIC_KEY·LANGFUSE_SECRET_KEY(·LANGFUSE_BASE_URL)가 있으면 Langfuse로
  대화(agent)·모델 호출(generation)·도구(tool)를 보낸다. user_id는 'admin' 또는 날짜별 해시. 키가 없으면 아무것도 안 한다
- MapleScouter 자동 채우기(확장·북마클릿) 유지 여부 — 약관 제15조 위험, 사용자 결정 대기

## 클라우드에서 못 하는 것 (이 PC에서 해야 함)
- 넥슨 API가 필요한 일: 실제 캐릭터 조회, `tools/collect_skill_shares.py`(직업별 딜 지분 수집 — 지금은 레테만 있음),
  픽스처 갱신. `.env`가 없고 키를 클라우드에 넣지 않는다
- 브라우저 확인(MapleScouter 실사이트, 경매장 화면 공유), 크롬 확장 설치 시험
- 코드 수정과 테스트(`uv run pytest -q --ignore=tests/goals`, `npm --prefix web test`)는 클라우드에서 된다

## 주의
- 숫자는 측정·출처값만. 표를 옮기면 실측(픽스처의 넥슨 API 값)으로 검산하는 테스트를 같이 쓴다
- 템플릿 문자열 안의 JS 코드(`web/src/scouter.js`의 PREP/FILL/RUN_SOURCE)에서는 정규식 역슬래시가 사라진다 — 정규식 대신 indexOf
- `extension/generated/run.js`는 `npm --prefix web run ext`로 만든다(테스트가 최신인지 확인)
