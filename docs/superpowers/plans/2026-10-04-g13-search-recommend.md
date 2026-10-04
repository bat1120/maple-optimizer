# G13 매물 검색 추천 계획

목표: 게임 경매장에서 무엇을 검색할지(부위·잠재·최소 스타포스)를 보스 실딜 상승률 순으로 추천한다.

1. 판정 테스트 tests/goals/test_g13.py (①~⑤) 먼저 작성, RED 확인
2. Item에 potentials/core/after 추가 — 윗잠만 교체 가능하게 (convert.item에서 더하는 순서를 유지해 항등 보장)
3. engine/market/recommend.py: with_potentials, target_potentials, recommend_searches(Evaluator로 보정 1회)
4. server/service.recommend, GET /api/character/{name}/recommend, agent 도구 recommend_searches + 지시문 규칙
5. web RecommendPanel(+test "recommend panel"), ScreenWatch 공유 기본값 window·게임 창 안내
6. validate / verify -Goal G13
