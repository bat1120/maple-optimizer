# 인수인계 (2026-10-08) — 클라우드 세션에서 이어서 작업할 때 먼저 읽기

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

## 다음 할 일 후보 (사용자와 정해서 진행)
- 경로 비교: 30% 할인·파괴 감소 등 썬데이 이벤트를 하나씩 고르기(API는 `sf=discount30,destroy_down30,…` 지원, 화면은 샤이닝 묶음만)
- 스페어 값을 부위마다 다르게 넣기(지금은 모든 부위에 같은 값)
- HEXA: 3rd 스킬 코어를 오리진과 구분(지금은 둘 다 비싼 '스킬' 비용표), 여러 스킬에 걸치는 강화 코어(체인 커맨드 강화) 반영
- 추옵(환생의 불꽃) 재설정 경로 — 불꽃 등급별 확률표(공식 자료)가 먼저 필요
- 업그레이드 탭의 임시 '테스트 템' 줄 정리(사용자 확인 뒤)

## 클라우드에서 못 하는 것 (이 PC에서 해야 함)
- 넥슨 API가 필요한 일: 실제 캐릭터 조회, `tools/collect_skill_shares.py`(직업별 딜 지분 수집 — 지금은 레테만 있음),
  픽스처 갱신. `.env`가 없고 키를 클라우드에 넣지 않는다
- 브라우저 확인(MapleScouter 실사이트, 경매장 화면 공유), 크롬 확장 설치 시험
- 코드 수정과 테스트(`uv run pytest -q --ignore=tests/goals`, `npm --prefix web test`)는 클라우드에서 된다

## 주의
- 숫자는 측정·출처값만. 표를 옮기면 실측(픽스처의 넥슨 API 값)으로 검산하는 테스트를 같이 쓴다
- 템플릿 문자열 안의 JS 코드(`web/src/scouter.js`의 PREP/FILL/RUN_SOURCE)에서는 정규식 역슬래시가 사라진다 — 정규식 대신 indexOf
- `extension/generated/run.js`는 `npm --prefix web run ext`로 만든다(테스트가 최신인지 확인)
