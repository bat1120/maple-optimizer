# goal-log — 목표 실행 기록 (append only)

형식: `## <날짜> <ID> <결과>` 아래에 BASELINE, BUILD 요약, 게이트 결과(종료코드), after 측정값, 커밋.

## 2026-10-03 G0 (1a) VERIFIED
- 1a 계획(`docs/superpowers/plans/2026-10-03-stage1a-parsing-and-stat-attack.md`) 완료, main 머지 cc17d83
- 스위트 135 passed. 45개 직업 스탯공격력 상대 오차 < 1e-4. 실캐릭터 스모크 오차 0.00104%

## 2026-10-03 G1 PARTIAL
- BASELINE: validate 135 passed, verify G1 → 판정 모듈 없음(exit 1)
- BUILD: 세트 매핑 ILP 데이터(engine/data, 아이템 156·세트 60), 무기 규칙(제네시스·데스티니), 칭호·심볼·유니온 파싱, 잔차 보정(주·부스탯 %, 공마 고정값, 합/곱 잔차), 보스 실딜 지수, 27조합 평가, 아이템 교체. 계획 docs/superpowers/plans/2026-10-03-g1-residual-swap-sets-presets.md
- VALIDATE: 192 passed (exit 0). 게이트 수정: 회귀 스위트에서 tests/goals 분리 (판정 미달 목표가 이후 모든 VALIDATE를 막는 게이트 결함)
- VERIFY: exit 1 — ① 실패, ② ③ 통과
- after (goals/results/G1.json):
  - ① fixture 짝 오차 3.99% (기준 ≤ 1% 미달). 같은 버프 상태 짝(인게임 스크린샷 수치) 참고값 0.59%
  - ② 45개 직업 자기 교체 최대 |Δ| = 0
  - ③ 27조합 최적 = (장비2, 하이퍼3, 어빌2) = 실제 보스 세팅, 비율 1.0
- 판단: ①의 미달은 모델이 아니라 입력 스냅샷의 버프 차이(사냥 fixture 최종뎀 188.93 vs 보스 186.70, 마력 4973 vs 4852). 롤백하지 않음(skill 규칙: 측정 미달은 PARTIAL로 기록). 재판정에는 보스 스냅샷과 같은 버프 상태(가능하면 버프 전부 끔)의 사냥 세팅 API 스냅샷이 필요 → 사람 할 일

## 2026-10-03 G2 VERIFIED
- BASELINE: validate 192 passed, verify G2 → engine.market 없음(exit 1)
- BUILD: engine/market/listing.py (Listing, item_from_input, evaluate_listing, rank_listings, InvalidPrice, NoDamage). 계획 docs/superpowers/plans/2026-10-03-g2-market-engine.md
- VERIFY 1차 exit 1: 방어율 300% 보스에서 방무 66.7% 미만 캐릭터의 실딜 지수 0 → ZeroDivisionError. 제품 수정: NoDamage 명시 오류(test_zero_damage_baseline_is_explicit_error RED→GREEN). Ruling: ①은 기준에 보스 지정이 없어 45명 전원이 데미지를 넣는 방어율 100% 보스로 측정
- VERIFY 2차 exit 0. after (goals/results/G2.json): ① 최대 |Δ| 0 ② 레테 보스 반지4 매물 Δ +1.0486% = 교체 계산 ③ 억당 0.04194%/억 = 수작업

## 2026-10-03 G3 VERIFIED
- BASELINE: validate OK, verify G3 → server 모듈 없음(exit 1)
- BUILD: server/{app,cache,ratelimit,schemas,service}.py, FastAPI·uvicorn 의존성. 계획 docs/superpowers/plans/2026-10-03-g3-server.md
- 엔드포인트: /api/health, /api/character/{name}, /settings(27조합), POST /listings(기본 세팅 = 최적 조합)
- 중간 실패 1건: test_no_damage_is_422 — 테스트가 기본(최적) 세팅을 써서 방무가 충분했음. 테스트를 활성 세팅 명시로 수정(제품 코드 변경 없음)
- VERIFY exit 0. after (goals/results/G3.json): ① 서버 테스트 18 passed, skip 0 ② 2회 조회 넥슨 호출 1회 ③ 404/503/502/500 ④ 200,200,200,429

## 2026-10-03 G4 VERIFIED
- BASELINE: verify G4 → web/dist 없음(exit 1)
- BUILD: web/ (React 18 + Vite 6 + vitest 2, JSX): 조회·보스 세팅 순위·매물 폼(총 옵션+잠재 텍스트, "45억 3000만" 가격)·억당 효율 표, localStorage 매물 보관. server.create_app(static_dir) 정적 서빙. 계획 docs/superpowers/plans/2026-10-03-g4-web.md
- 게이트 수정: verify.ps1 vitest 결과 파싱이 ANSI 색 코드에 막힘 → NO_COLOR/FORCE_COLOR=0
- VERIFY exit 0: ① build exit 0 ② vitest 12 passed ③ GET / 200 + root div
