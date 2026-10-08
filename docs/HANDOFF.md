# 인수인계 (2026-10-08, 오후 갱신) — 클라우드 세션에서 이어서 작업할 때 먼저 읽기

## 지금 상태
- 데모: https://maple-optimizer.onrender.com (Render 무료, `main` 푸시마다 자동 배포, 15분 쉬면 잠든다)
- 자동 목표 G1~G13은 모두 판정 완료. 남은 GOALS.md 항목은 사람 몫(H1·H2·H3·H5·H6)
- 마지막 전체 검증: pytest 467 passed · 2 skipped, 웹 테스트 전부 통과

## 최근에 만든 것 (2026-10-07)
| 영역 | 내용 | 주요 파일 |
|---|---|---|
| UI | 디자인 토큰·아이콘·패널 사용 방법·첫 방문 안내·뼈대/빈/오류 상태 | `web/src/styles.css`, `web/src/ui/` |
| 환산 연동 | MapleScouter 북마크(`#/scouter`)와 크롬 확장(내 캐릭터로 교체 후 칸 채우기) | `web/src/scouter.js`, `extension/` |
| 구매 불가 템 | 제네시스·데스티니, 아스트라 보조, 미트라 엠블렘, 엔버·카이저·제논 보조무기 | `engine/market/recommend.py` |
| 보조무기 종류 | 툴팁 장비분류 ↔ 지금 보조무기 종류(API) 맞춰 보기 | `engine/market/secondary.py` |
| 스타포스 경로 | 성별 스탯 표(실측 검산), 기대 비용·흔적 복구·평균 파괴·스페어 | `engine/enhance/starforce_stats.py`, `engine/enhance/starforce.py` |
| 강화 이벤트 | 샤이닝 스타포스·파괴 방지·미라클 타임 | `engine/market/events.py` |
| HEXA | HEXA 스탯(초기화 기대값)·HEXA 코어(다음 1레벨, 연무장 딜 지분) | `engine/stats/hexa.py`, `engine/market/hexa_paths.py`, `engine/market/hexa_core_paths.py` |
| 경로 비교 | 구매·직작·큐브·스타포스·HEXA를 억당으로, 종류별 상위 묶음 | `engine/market/paths.py`, `web/src/PathsPanel.jsx` |
| 부위별 스페어 값 | `spare_slots=벨트:300000000,…`, 화면은 계산 뒤 스타포스 경로가 있는 부위마다 칸 | `engine/market/events.py`, `web/src/PathsPanel.jsx` |
| 화면 분석 하루 한도 DB | `vision_quota` 표(관측 기록과 같은 DB — Neon이면 Postgres), KST 날짜, IP는 HMAC 해시로만 | `server/observations.py`, `server/app.py` |
| 강화 코어 줄별 대상 | 체인 커맨드 강화: '오버로드 스킬의' → 오버로드 스킬 모두, '… 중' 버프 줄은 미반영으로 표시 | `engine/market/hexa_core_paths.py` |
| 테스트 템 정리 | 업그레이드 탭 임시 줄 삭제(견본은 `#/scouter` 설치 화면에만 남김) | `web/src/ScreenWatch.jsx` |
| 추옵 재설정 경로 | 단계 확률(공식표 요약)·수치 공식(실측 564개 검산, 250레벨 단일 상수 12)·정확한 도달 확률 계산, `flame_price` 입력 | `engine/market/flame.py`, `engine/data/flame.json` |
| 썬데이 이벤트 개별 선택 | 30% 할인·21성 이하 파괴 감소·5/10/15성 100%·복구 메소 할인을 하나씩(넷 다 = 샤이닝 묶음) | `web/src/PathsPanel.jsx`, `web/src/api.js` |

## 다음 할 일 후보 (사용자와 정해서 진행)
- HEXA: 3rd 스킬 코어를 오리진·어센트와 구분 — **막힘**. API는 셋 다 '스킬 코어'이고 문장에 구분 표시가 없다.
  인벤(2025-07)은 어센트 = 오리진 비용('스킬' 열). '3rd 스킬' 열을 쓰는 스킬이 무엇인지(직업별 이름) 공식·위키 출처가 있어야 한다
  (클라우드에서는 namu.wiki·maplestory.nexon.com·inven 접속이 막힘). 그 전까지 모든 스킬 코어는 '스킬' 열(비싼 쪽)
- 추옵 경로 확인(이 PC에서): 공식 확률 페이지(maplestory.nexon.com/Guide/OtherProbability/game/gameAddOption)의
  ① 옵션별 등장 확률(지금은 방어구 19종 중 4개 균등 가정 — `engine/data/flame.json`의 armor_pool), ② 단계 확률(4~7단계 29/45/25/1%),
  ③ 지금 메소 재설정 1회 값을 대조. ①이 맞으면 `paths.py`의 unverified를 끄고, 무기 공·마 공식도 실측 검산해 무기를 넣는다

## 클라우드에서 못 하는 것 (이 PC에서 해야 함)
- 넥슨 API가 필요한 일: 실제 캐릭터 조회, `tools/collect_skill_shares.py`(직업별 딜 지분 수집 — 지금은 레테만 있음),
  픽스처 갱신. `.env`가 없고 키를 클라우드에 넣지 않는다
- 브라우저 확인(MapleScouter 실사이트, 경매장 화면 공유), 크롬 확장 설치 시험
- 코드 수정과 테스트(`uv run pytest -q --ignore=tests/goals`, `npm --prefix web test`)는 클라우드에서 된다

## 주의
- 숫자는 측정·출처값만. 표를 옮기면 실측(픽스처의 넥슨 API 값)으로 검산하는 테스트를 같이 쓴다
- 템플릿 문자열 안의 JS 코드(`web/src/scouter.js`의 PREP/FILL/RUN_SOURCE)에서는 정규식 역슬래시가 사라진다 — 정규식 대신 indexOf
- `extension/generated/run.js`는 `npm --prefix web run ext`로 만든다(테스트가 최신인지 확인)
