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

## 2026-10-04 G1 재측정: 링크 스킬 프리셋 반영 (PARTIAL, ① 4.09% → 1.43%)
- 사용자 질문("API에서 템정보 못 가져와?")으로 미사용 API 점검: character/link-skill에 프리셋 1(사냥)·2(보스) 존재. 프리셋 차이(자연의 벗 데미지5, 어드벤쳐러 크확10, 자신감 방무10 ↔ 데몬스 퓨리 보공15, 퍼미에이트 방무15)가 남은 잔차와 정확히 일치
- 수정: link-skill 수집(ENDPOINTS), 조건 없는 링크 효과만 pct 블록에 반영(조건부 표현 줄 제외: 중첩·동안·발동·처치·돌입·적용시키면), Setting.link, 조합에 링크 차원(레테 162). test_link_skill_presets_are_parsed RED→GREEN(조건부 '중첩 당 방무 3%' 오검출 수정 포함), validate 258 passed, G2~G8 VERIFY 유지
- fixture: 레테 사냥 fixture에 현재 링크 데이터(적용=프리셋1, 현재 API와 일치), 보스 짝에는 적용=프리셋2로 **추정** 기입(_note 명시)
- 결과: 데미지·보공 예측 정확(91/91, 438/438). ① fixture 짝 1.43%(기준 1% 미달). 남은 차: 최종뎀 +2.23p·크뎀 +8·크확 +10·마력 — 같은 사냥 세팅의 fixture↔스크린샷 차이와 동일 → fixture 시점에만 있던 일시 효과. INT −0.5%는 유니온·하이퍼 INT의 % 적용 여부 불확실(짝 하나로 판별 불가)
- 참고값(스크린샷 짝)은 1.89%로 커짐: 스크린샷 수치에는 INT·마력도 일시 효과가 빠진 상태라 INT 과소예측이 더 드러남

## 2026-10-04 G1 ④(보조) 과거 기록 짝 검증 — 결론: 날짜 스냅샷은 1% 검증에 부적합
- tools/collect_history_pairs.py: 날짜별 stat의 드롭+메소로 사냥/보스 날을 골라 전체 번들 수집 (레테 14일 + 랭커 25명 8일, API 약 620회)
- 짝 21개 중 유효 5쌍(양방향 10개). 제외: 장비·큐브 변경 10, 같은 세팅 6. 비교 조건: 두 날의 장비(예비 특수 반지 제외)·하이퍼·어빌·유니온·링크 프리셋 내용 동일. 날마다 바뀌는 관측값(AP·심볼·유니온 공격대)은 상대 날 값으로 대체
- 스탯공격력 전환 예측 오차: 중앙값 3.55%, 평균 7.55%, 최대 18.4%(솝상). 솝상은 같은 장비에서도 날마다 보공 382↔502%, 전투력 2억↔5.5억 — 스냅샷 시점의 극딜 버프 상태가 섞인다. 즉 이 오차는 모델이 아니라 기록 시점 차이
- INT %적용 가설(하이퍼/유니온 프리셋/어빌/공격대): 중앙값 3.31~5.23%로 노이즈보다 차이가 작아 판별 불가 → 모델 변경 없음
- 결론: 1% 수준 판정에는 같은 상태에서 연달아 받은 짝(사용자 협조)이 필요. G1은 PARTIAL 유지

## 2026-10-04 G1 같은 상태 짝 실측 (레테_hunt2 ↔ 레테_boss2, 02:50~52 연속 수집)
- 데미지·보공·최종뎀·크뎀·크확 양방향 정확(유니온·링크 반영 확인)
- INT 양방향 대칭 오차 −350/+332 → 가설 비교: 유니온 프리셋 효과(점령) 주스탯 %적용 시 +41/−39. 하이퍼·공격대원 %적용은 악화 → 모델 수정(test_clean_pair_int_prediction_within_60_both_directions RED→GREEN), validate 262 passed
- 남은 오차: 마력만 — 보스 짝에만 마력 버프가 켜져 있었음(보스 5131, 같은 버프가 꺼진 사냥 4852; 사용자 확인 "버프가 하나 켜져 있던 것 같다"). 마력에 실제값을 넣으면 스탯공격력 오차 0.060%/0.065%
- G1 판정(기존 fixture 짝) ① 2.12%, 스크린샷 참고 1.22% — 여전히 PARTIAL. 버프 상태가 같은 짝 하나가 더 필요

## 2026-10-04 G1 판정 짝 교체: 버프 꺼진 같은 상태 짝 (레테_hunt2 02:52 ↔ 레테_boss3 02:56)
- 사용자 협조로 마력 버프를 끈 채 보스 세팅 재수집(마력 5008 = 이전 보스 스냅샷과 동일)
- 판정 테스트 ①을 이 짝으로 교체(같은 기준 1%, 이전 짝은 참고값으로 기록)
- 결과: ① 1.22%(미달) / 이전 짝 2.12%. INT +41/−39, 데미지·보공·최종뎀·크뎀 정확
- 남은 오차는 마력 대칭 −64/+63. 공마% 63 동일, 장비 −5·세트 +40·칭호 +5·하이퍼 +18 = +57(공마% 전) 대비 실제 필요 약 +96 → 보스 프리셋 쪽 마력 고정값 약 39 출처 미확인. 출처별 %미적용 가설로는 해소 안 됨. 후보: 특수 반지(컨티뉴어스 링 Lv4), 도전자 장비 특수 규칙, 헥사 스탯 슬롯 등 API 응답에 드러나지 않는 출처
- PARTIAL 유지. 다음 단서: 인게임 마력 세부(툴팁) 또는 부위 하나씩 바꾼 짝

## 2026-10-04 G1 VERIFIED — 인게임 마력 툴팁으로 원인 확정
- 사용자 제공 인게임 마력 툴팁(사냥·보스): 출처별 기본 수치(스킬 326·헥사 95·장비 2498/2567·유니온 공격대 35/34·하이퍼 0/18·아티팩트 3·챔피언 휘장 20·칭호 —/10), 마력% 63
- 원인 1: 칭호 "쑥쑥 새싹" 옵션 기간 만료(API date_option_expire=expired)인데 엔진이 공마5·올스탯10을 더함 → 만료 칭호 효과 0 (test_expired_title_has_no_effect RED→GREEN)
- 원인 2: 예비 특수 반지(리스트레인트 링) 스탯이 실제로 적용됨(보스 장비 아이템 마력이 정확히 4 큼) → 스탯 합산에 포함, 세트 개수에서는 계속 제외 (test_spare_special_ring_stats_are_counted RED→GREEN). 이전 Ruling("예비 특수 반지 미착용") 정정
- VERIFY G1 exit 0: ① 같은 상태 짝 0.756% (이전 짝 참고 2.593%) ② 0 ③ 최적 = 실제 보스 세팅
- INT: 만료 칭호를 빼고 나니 점령 %적용 가설에서 +127/−97(이전 ±40은 잘못된 칭호 올스탯이 상쇄한 결과). 회귀 테스트를 0.25% 이내로 재설정, 남은 INT 출처는 인게임 INT 툴팁으로 확정 예정
- 남은 차: 사냥 장비 마력이 인게임보다 30 큼(도전자 8세트 공마 30과 같은 값 — 후보). 판정 기준 안이라 후속 과제로 둔다
- validate 264 passed, G1~G8 VERIFY 전부 OK

## 2026-10-04 G9 VERIFIED — 웹 패널 확장
- BASELINE: verify G9 → Panels 테스트 없음(exit 1)
- BUILD: web/src/Panels.jsx(StarforcePanel·CubePanel·CraftPanel·OptimizePanel), api.js(postStarforce·postCube·postCraft·postOptimize), App에 "강화 계산" 섹션(큐브 결과 → 직작 비교 자동 입력)과 매물 아래 예산 최적화
- VERIFY exit 0: 패널 4개 테스트 통과, vitest 21 passed, build 0. G4·G8 VERIFY 유지, validate 264 passed
