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

## 2026-10-03 G5 VERIFIED
- BASELINE: verify G5 → engine.enhance 없음(exit 1)
- 조사: 공식 패치노트 Update/767(2025-03-20 개편), Update/799(2026-03-19 스타캐치 상시·흔적 성 유지), 공식 큐브 확률 페이지(블랙/재설정, 레전드리·무기·200). 비공식(나무위키): 현재 확률표(공식 기본×1.05와 일치), 비용 공식, 재설정 메소 가격 → 데이터에 verified:false
- BUILD: engine/data/{starforce,cube_black}.json, engine/enhance/{stats,starforce,cube}.py. 계획 docs/superpowers/plans/2026-10-03-g5-enhance.md
- VERIFY exit 0 (goals/results/G5.json), 200레벨 0→22성, 파괴 처리비 30억:
  - 기본 정확 178.87억 / MC 178.93억 (0.034%), 30%할인+방지 158.76억 (0.024%), 파괴감소+5·10·15 152.01억 (0.135%), 기본 복구 548.40억 (0.437%, p90 1225.9억)
  - 큐브 보공2줄 2.765% (0.015pp), 마력%합≥21 0.710% (0.028pp), 방무1+보공1 4.429% (0.053pp)

## 2026-10-03 G6 VERIFIED
- BASELINE: verify G6 → engine.market.craft 없음(exit 1)
- 데이터: 넥슨 확률 정보 조회(사용자 계정) history/potential 114건(제네시스 카르타 레전드리 재설정), history/cube 43건 → 익명화 tests/fixtures/history. history/starforce는 조회 3일 0건
- BUILD: engine/market/craft.py(직작 비용 분포·백분위·매물 비교), engine/enhance/history.py(지출·운), nexon.convert.cube_attempts, starforce.simulate_samples. 계획 docs/superpowers/plans/2026-10-03-g6-craft-vs-listing-luck.md
- VERIFY exit 0 (goals/results/G6.json): ① 백분위 반해석↔결합 MC 최대 0.277pp ② 재설정 114회 지출 51.3억 = 수작업, 캐시 큐브 43건 미집계

## 2026-10-03 G7 VERIFIED
- BASELINE: verify G7 → engine.optimize 없음(exit 1)
- BUILD: engine/stats/evaluate.Evaluator(보정 1회 재사용), engine/optimize/budget.py(greedy, brute_force). 계획 docs/superpowers/plans/2026-10-03-g7-optimize.md
- VERIFY 1차 exit 1: 순수 효율 탐욕법 평균 0.954 / 최소 0.543 (싼 후보가 부위를 먼저 차지해 센 후보를 막음)
- 수정: 출발점 다중화(후보별 "먼저 사기" 고정) + 1:1 교체 개선. 재현 테스트 test_greedy_does_not_let_a_cheap_efficient_item_block_a_much_stronger_one RED→GREEN
- VERIFY 2차 exit 0 (goals/results/G7.json): 30개 인스턴스 평균·최소 비율 1.0(상승분 기준), 부위 위반 0, 예산 초과 0

## 2026-10-03 G8 VERIFIED
- BASELINE: verify G8 → E2E 엔드포인트·README 없음(exit 1)
- BUILD: 서버 엔드포인트 추가 POST /api/enhance/starforce, /api/enhance/cube, /api/craft/compare, /api/character/{name}/optimize (+ 단위 테스트 5), scripts/run-local.ps1(-Check), README(로컬 실행·시크릿 소재지·데이터 한계)
- VERIFY exit 0: ① E2E 체인(조회→세팅→매물→스타포스→큐브→직작 비교→최적화) 통과 ② run-local health 200, / 200 ③ README 필수 항목

## 2026-10-03 후속: 무기 상수 4종, 재설정 가격 확인
- 사용자 지시: 해당 무기 사용자를 찾아 상수 실측, 레전드리 200제 재설정 가격 4,500만(인게임 확인)
- 직업 랭킹(블래스터·미하일·팔라딘·데몬슬레이어)에서 무기별 2명씩 8명 수집(API 163회) → 익명화 tests/fixtures/weapons
- 역산 상수: 한손검 1.24000(미하일 ×2), 한손도끼 1.20002/1.20001(데몬슬레이어), 두손둔기 1.33998(팔라딘 ×2), 건틀렛 리볼버 1.69998/1.70002(블래스터)
- 회귀 테스트 8개 RED(UnknownWeapon) → 상수 추가 후 GREEN. validate 254 passed, G5·G6·G8 VERIFY 유지
- cube_black.json `_verified.meso_cost`: 레전드리 200~249 = 45,000,000 확인값으로 표기

## 2026-10-04 G1 재측정: 유니온 프리셋 반영 (PARTIAL 유지)
- 사용자 지적("템·어빌·유니온이 달라서?")으로 두 스냅샷 비교: 장비·하이퍼·어빌·칭호·심볼·AP는 동일, **유니온 프리셋만 2(사냥)→3(보스)**. 엔진이 union_state_stat_preset(유니온 프리셋 효과)을 읽지 않고 잔차로 고정하고 있었음 — 보스 프리셋의 보공 40%·방무 40%·INT 75가 예측에서 빠짐
- 수정: Setting.union, CharacterSnapshot.union_states/active_union_preset, %미적용 블록에 유니온 프리셋 효과 추가, rank_settings에 유니온 차원(레테 81조합). 재현 테스트 test_union_state_presets_are_parsed, test_union_preset_changes_prediction RED→GREEN. validate 256 passed, G2~G8 VERIFY 유지
- 결과: ③ 최적 = (장비2, 하이퍼3, 어빌2, 유니온3) = 실제 보스 세팅 전부 일치. ① 스탯공격력 오차 fixture 짝 4.09%, 같은 버프 짝 0.68% (유니온은 스탯공격력에 INT+75·마력−1만 기여 — 이전 0.59%는 항목 오차 상쇄)
- 같은 버프 짝 항목별: 최종뎀·크뎀 정확, 남는 차 INT −0.6%, 마력 −1.3%, 데미지 +5, 보공 −15, 크확 +10 → 훈장(카오스 벨룸 킬러 보공 5%는 반영됨)·세트 단계는 원인 아님. 두 스냅샷 촬영 시점 사이의 시간 의존 효과로 추정, 데이터로 특정 불가
- 남은 할 일: 같은 상태에서 사냥·보스 세팅 API 스냅샷을 연달아 받아 재판정
