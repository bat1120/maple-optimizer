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

## 2026-10-04 G10 진행 중 — 배포 준비물
- BUILD: Dockerfile(web 빌드 → python:3.12-slim + uv, amd64·arm64), .dockerignore, docker-compose.yml(api + caddy, .env, 캐시·인증서 볼륨), deploy/Caddyfile(자동 HTTPS), .github/workflows/deploy.yml(테스트 → GHCR 멀티아치 푸시 → DEPLOY_ENABLED일 때 SSH 배포), README 배포·시크릿 표(VM_HOST·VM_USER·VM_SSH_KEY·GHCR_READ_TOKEN·DEPLOY_ENABLED)
- VERIFY: ① compose config exit 0 ③ 워크플로 파싱·시크릿 문서화 통과. ② 이미지 빌드·health: Docker Desktop 데몬이 꺼져 있어 실행 불가(실패로 기록, skip 아님)

## 2026-10-04 G10 VERIFIED
- 사용자가 Docker Desktop 실행 → VERIFY exit 0: ① compose config 0 ② amd64 이미지 빌드 0, 컨테이너 /api/health 200, / 에 root div ③ 워크플로 시크릿 4개(GHCR_READ_TOKEN·VM_HOST·VM_SSH_KEY·VM_USER) README 문서화
- 추가 확인: `docker buildx --platform linux/arm64` 빌드 성공(약 5분, QEMU), arm64 컨테이너에서 server·engine import 정상 — Oracle Ampere 대상 확인

## 2026-10-04 G11 VERIFIED — 관리자 전용 AI 에이전트
- 사용자 요청("AI 에이전트도 있었으면")으로 범위 밖이던 5단계 진행. 같은 날 GitHub 비공개 저장소 생성·푸시(github.com/bat1120/maple-optimizer, H4 완료)
- BUILD: agent/tools.py(엔진 도구 7개: lookup_character·rank_settings·evaluate_listings·starforce_cost·cube_probability·craft_compare·optimize_budget, 서버 스키마로 입력 검증, 오류는 error 결과로), agent/numbers.py(억·만·% 환산 숫자 출처 검사), agent/loop.py(manual tool use 루프, claude-opus-5-5 effort medium, server-side fallback "default", refusal·max_tokens·pause_turn 처리, append-only), server/admin.py(PBKDF2 비밀번호 해시·HMAC 세션 쿠키·KST 일일 토큰 사용량), /api/admin/login·/api/agent/chat(SSE), web AgentPanel(로그인·스트림·검증 안 된 숫자 경고)
- VERIFY exit 0 (goals/results/G11.json): ① 4/4 ② 위조 숫자 검출 ['999억'] ③ 401→로그인→200 ④ 예산 초과 후 Claude 호출 0회 ⑤ ['error', 'done']
- validate 267 passed, vitest 24. 실제 Claude 호출 스모크는 키 필요 → H5

## 2026-10-04 G11 모델 공급자 전환: Anthropic → OpenAI (사용자 결정)
- 공식 문서 확인(developers.openai.com): GPT-6 계열 API ID `gpt-6-astra`($10/$50), `gpt-6.1-sol`($2/$10, 현행 Sol), `gpt-6-luna`($0.10/$0.50) — 모두 함수 호출·Responses API 지원, Responses가 새 프로젝트 권장
- Ruling: 기본 모델 `gpt-6.1-sol` — 에이전트는 계산하지 않고 도구 선택·설명만 하므로 Astra 불필요, 비용·성능 균형. `OPENAI_MODEL`로 변경 가능 — 틀리면 응답 품질/비용만 달라짐
- agent/loop.py를 Responses API manual loop로 재작성: store=False, 매 턴 output(reasoning·function_call) 재투입, function_call_output, reasoning effort medium, max_output_tokens 32000, refusal 콘텐츠·incomplete 상태 처리, 깨진 JSON 인자는 error 결과로 모델에 반환. 도구 정의는 평평한 function 형식(strict False — 선택 필드 보존)
- 의존성 anthropic 제거, openai 3.24.0 추가. 설치된 SDK의 responses.create 시그니처·ResponseFunctionToolCall 필드와 루프 인자 일치 확인
- 판정 테스트 가짜 클라이언트를 OpenAI 응답 형태로 바꿔 RED(3 실패) → 재작성 후 5/5. 단위 테스트(거절·incomplete·깨진 인자) 추가

## 2026-10-04 G12 — 경매장 화면 실시간 분석
- 배경 조사: 경매장 전체 수집은 불가(Open API 없음, 웹 경매장은 로그인·OTP·계정당 하루 검색 100회·과대 검색 거부·세션 1개). 비공개 API 자동화는 운영정책 [4-4]("홈페이지의 정보를 … 열람하는 프로그램", "공식 제공하지 않는 … 프로그램")·약관 제11조 4호에 걸릴 위험 → 하지 않음. iframe 임베드는 X-Frame-Options: SAMEORIGIN으로 불가
- 사용자 결정: 화면이 바뀔 때마다 자동 분석(B). 넥슨 서버 요청 0 — 사용자가 공유한 탭의 픽셀만 읽음
- BUILD: web/src/watch.js(16×16 회색조 해시·평균 절대 차이·2프레임 안정·3초 쿨다운), ScreenWatch.jsx(getDisplayMedia 탭 공유, 1.5초 주기, 지문 중복 제거, 읽은 내용·평가 표시, OpenAI 전송 고지), server/vision.py(Responses API input_image detail high + json_schema strict 구조화 출력, 깨진 JSON → VisionError), service.vision_items(반지·펜던트 슬롯 후보 중 실딜 최대 자리, 목록만 보이면 평가 생략), /api/vision/listings(관리자 쿠키·일일 토큰 한도 429)
- 실제 화면 공유·실제 비전 호출은 H6
- VERIFY exit 0 (goals/results/G12.json): ① screen watch 6개 통과 ② 깨진 JSON → VisionError ③ 1회차 평가 1, 2회차(같은 매물) 0 ④ 반지 슬롯 엔진 반지3 = 수작업 반지3 ⑤ 미인증 401, 한도 초과 429·비전 호출 1회. validate 269, vitest 30

## 2026-10-04 H5 VERIFIED — 에이전트 실호출
- 사용자가 .env에 OPENAI_API_KEY 등록(처음엔 Windows 숨김 입력 Ctrl+V로 제어문자 1자만 저장 → setup_secrets에 형식 검사·클립보드 읽기 추가, 최종은 메모장으로 입력). 키 164자·인증 OK, gpt-6 계열 4종 사용 가능 확인(값 미출력)
- tools/agent_smoke.py로 실제 OpenAI(gpt-6.1-sol) + 실제 넥슨 데이터: "보스 세팅 최선인지·반지 교체 효율" → lookup_character·rank_settings 호출, 답변의 수치(2.4754배, 18성·17성) 전부 도구 결과에서 확인(미검증 0), 오류 0, 6,091토큰. 매물 가격이 없어 반지 효율은 "판단 불가, 툴팁·가격을 달라"고 답함 — 숫자 원칙 준수
- 사용자 요청 "5.6 sol mini": 해당 ID 없음. 사용 가능 5.6 계열 gpt-5.6-sol($4/$20)·gpt-5.6-terra($2/$12)·gpt-5.6-luna($0.20/$1.20) — 사용자 확인 대기
- 모델 결정(사용자): gpt-6-luna. 1차 스모크 통과했으나 rank_settings에 없는 인자(setting="blah")를 지어내 오류 결과 1회(자체 복구), 14,149토큰, 숫자 아닌 설명 1건("반지 4개 모두 이벤트 링") 도구 근거 없음
- 수정: 함수 도구 최상위 parameters에 additionalProperties: false. 재실행: 도구 2회 정확, 오류 0, 미검증 숫자 0, 6,907토큰. DEFAULT_MODEL·비전 기본값 gpt-6-luna
- 남은 한계: 숫자 출처 검사는 숫자만 본다 — 숫자 아닌 사실 주장(아이템 분류 등)은 검사하지 않음

## 2026-10-04 실사용 피드백 반영 (에이전트·화면 분석)
- 사용자 실사용 스크린샷: 같은 매물 2번 표시, 에테르넬 메이지햇 실딜 −4.9%(총 옵션 미독해 추정), "검증되지 않은 숫자: 2만" 오탐, 에이전트가 화면 매물을 못 봄, 가격 미표시, 사냥 세팅 중 "프리셋 바꾸라" 반복
- 수정(모두 RED→GREEN): 지문에서 가격·총옵션 제외(OCR 흔들림), 총 옵션 없으면 평가 보류+이유 표시, "N만의"(조사) 숫자 제외, 음수·문자열 속 숫자 출처 인정, 읽은 총옵션·가격 표시 + 가격 못 읽으면 직접 입력해 억당 계산, 비전 지시에 목록 행 가격 읽기, 화면 매물을 에이전트 질문에 첨부(평가 숫자는 빼고 도구로 재계산), lookup_character에 evaluation_setting(보스 최적)·사냥 세팅 정상 안내, 지시문: 프리셋 전환 권유 금지·setting 생략(보스 기준)·수치 반올림 표기·잠재 합산 금지
- 실호출(gpt-6-luna) 화면 매물 2개 첨부: 보스 세팅 기준 +1.68%/−2.43%, 억당 +0.037%/−0.135%, 환산 +972/−1,405, 표 정리. 잠재 합산 "30%"는 검사기가 정상 검출 → 지시 보강

## G13 매물 검색 추천 — VERIFIED (2026-10-04)
- BASELINE: validate 275 passed / vitest 33. 판정 테스트 RED: ImportError(engine.market.recommend 없음), 웹 카드 없음
- BUILD: Item에 윗잠 원문·윗잠 뺀 기본 블록·에디/소울 원문 저장(nexon/convert.item), with_potentials, recommend_searches(보스 최적 세팅 기준, Δ>0만 내림차순),
  service.recommend + GET /api/character/{name}/recommend, 에이전트 도구 recommend_searches, 웹 RecommendPanel, 화면 공유 기본값 window + 게임 창 안내
- VALIDATE ■ 0 (pytest 276 · vitest 37), VERIFY ■ 0 (5/5)
- 측정: 레테 상위 보조무기 6.612%, 엠블렘 5.423%, 장갑 3.371%, 무기 2.242% · 수작업 교체와 최대 차이 0.0 · 자기 잠재 교체 항등 OK · 제외 슬롯 0건
- Ruling: 목표 잠재는 레전드리 대표 조합(방어구·장신구 주스탯 12/9/9, 장갑 크뎀8/크뎀8/주스탯9, 무기·보조 공12/보공40/공9, 엠블렘 공12/공9/방무35)으로 고정 — 레벨·등급별 최대치를 따지지 않는다 — 틀리면 일부 부위 상승률이 과대/과소(검색 조건의 출발점일 뿐)
- Ruling: 기계 심장은 잠재가 있어도 추천에서 제외(경매장 교체 대상으로 보기 어려움), 잠재가 없는 템(시드링 등)도 제외 — 틀리면 해당 부위 추천 누락

## 실사용 화면 피드백 수정 (2026-10-04)
- 재현 테스트 tests/test_screen_feedback.py 7건 RED→GREEN, 웹 2건 RED→GREEN · validate 283 passed / vitest 39 · verify G11·G12·G13 OK
- 가격 자릿수 오보(327억 9999만→"32억 7999만 9999", 400억→"40억"): 도구 결과에 price_text, 지시문 "글자 그대로 인용". 숫자 검사기는 이 오보를 정확히 잡았다
- 총옵션 없는 매물 -19.5%: evaluate_listings가 held로 보류
- 깃펜을 무기로 분류: 무기 종류표에 없으면 보조무기로 보정 + 판독 지시문
- "에디셔널 잠재능력:" 머리말 제거
- 캐릭터 조회 전 읽은 매물: 조회 시 /api/vision/evaluate로 재평가, 목록만 본 행은 한 줄로 접음
- 관리자 해시 구분자 $→: (docker compose가 env_file의 $를 변수로 치환) · 예전 형식 호환, .env 1줄 변환
- 후속(같은 날): AI가 조회한 캐릭터를 모름(화면 매물 있을 때만 이름을 붙였음) → 항상 "[조회한 캐릭터]" 첨부. 사용자 글의 숫자("200억", 첨부 잠재)를 출처로 인정. 목록 행만 본 매물은 첨부에서 빼고 같은 이름 목록 가격을 list_prices 후보로. validate 284 / vitest 41
- 후속(같은 날) 추천 사다리: 고점 하나 대신 부위별 잠재 단계(공식 확률표·장비 실측 수치)에서 실딜이 처음 오르는 단계를 추천. 쿨감 줄은 유지(kept), 쿨감 1초=주스탯 N%는 사용자가 정하면 반영(cooldown_main_pct), 매물 결과에 cooldown_s_not_valued. Item.level 추가. validate 292 / vitest 42 · G11~G13 OK (validate 첫 실행 1회 웹 단계 실패 — 재실행·3회 반복 모두 통과, 재현 안 됨)
- Ruling: 주스탯 13/10은 착용 레벨 250 이상에만(160제 9/6 실측, 200~249 실측 없음) — 틀리면 200~249제 방어구 목표가 1%p 낮게 잡힘
- 후속(같은 날) 경매장 판매 수수료: 기본 5%, MVP 실버 이상·PC방 3% (출처 mesangi.com·namu.wiki, 2026-10-04 조회). 사는 가격엔 없고 판매 예상가에서만 차감 — 비용 = 가격 − 판매가×(1−수수료). 매물 평가·예산 최적화·도구·웹 선택에 반영(net_resale·net_cost). validate 297 / vitest 43 · G7~G13 OK
- 후속(같은 날) 화면에서 수수료 읽기: 비전 스키마 fee_rate(퍼센트 숫자, 안 보이면 null) → normalize_fee(0 이하·10% 초과 버림) → 웹 수수료 선택에 자동 적용("화면에서 읽음"), 에이전트 질문에 첨부. validate 301 / vitest 45 · G11~G13 OK
- 후속(같은 날) 공식 확률표 기반 로드맵: tools/fetch_cube_tables.py로 블랙·에디셔널 큐브 확률표(에픽·유니크·레전드리 × 16부위 × 200 이하/201 이상) 수집 → engine/data/cube_tables.json. 단계 = 등급×2/3줄, 줄마다 확률 2%↑·이탈 제외 옵션 중 단독 기여 최대. 다음 단계 = 실딜 0.1%↑ 처음 오르는 단계. 에디 추천 추가, 제네시스·데스티니 무기는 route 큐브(검색 카드 제외), GET /roadmap·upgrade_roadmap 도구·웹 로드맵 패널. validate 304 / vitest 47 · G11~G13 OK
- Ruling 정정: 주스탯 +1 구간은 250이 아니라 201레벨부터(공식표 실측: 레전 모자 200=12%, 201=13%) — 앞선 Ruling(250 이상) 폐기
- Ruling: 흔한 조합 기준 확률 2%·최소 상승 0.1% — 틀리면 일부 단계가 이탈 포함/제외로 달라지거나 작은 개선이 빠짐
- 후속(같은 날) 가격 대비: 단계마다 메소 재설정 평균 비용(윗잠=블랙, 에디=화이트 에디셔널 비용표·등급 상승 확률·천장, 나무위키 2026-10-04) + 억당 실딜, value_ranking(부위·종류마다 최고 억당 단계, 억당 내림차순). 도달 확률은 줄별 단독 기여 합 비교 근사(곱연산과 오차 가능 — Ruling). Item에 잠재·에디 등급. validate 312 / vitest 48 · G11~G13 OK
- Ruling: 에디 메소 재설정 확률표 = 에디셔널 큐브(5062500) 확률표로 가정 — 틀리면 에디 도달 확률·비용이 달라짐
- 후속(같은 날) 관측 시세: 비전 스키마에 에디(additional) 분리, 읽은 매물(가격+줄 있는 것)을 PriceStore(SQLite, 30일)에 저장, 로드맵 단계마다 같은 부위·스타포스 이상·줄 덮음(covers) 매물의 중앙값·최저가·억당. GET /api/market/observed(관리자), 도구·웹 표시. 경매장 자동 조회 없음. validate 317 / vitest 49 · G11~G13 OK
- 후속(같은 날) 업그레이드 경로 비교: engine/market/paths.py — 구매(관측 매물 그대로, 세트 재계산·set_change, 다른 월드 +10%)·직작(매물가+매물 등급→단계 메소 재설정 평균)·큐브(지금 템)를 억당 정렬, best_by_slot. GET /paths, upgrade_paths 도구(추천의 기본 근거). 비전에 착용 레벨·잠재/에디 등급 추가. validate 324 · G11~G13 OK
- Ruling: 직작은 매물 스타포스 그대로(스타포스 강화 비용·스탯 미포함), 레벨 모르면 지금 템 레벨로 비용 구간 — 틀리면 직작 비용 과소/구간 차이
- 후속(같은 날) maple-auction-mcp 연결(사용자 결정: 시세까지 분석): server/auction_mcp.py — MCP stdio 클라이언트, 로드맵 다음 단계 줄→검색 필터(합산), 부위·스타포스·착용 레벨·직업군 조건으로 판매 중/판매 완료/직작 베이스 검색, 결과→관측 시세. 읽기 도구만, 갱신당 최대 15회(에이전트 10), POST /api/market/refresh(관리자, AUCTION_MCP_CMD 없으면 503), refresh_market 도구, 웹 경로 비교 패널(갱신 버튼). 가짜 MCP로 검증. validate 330 / vitest 51 · G11~G13 OK
- Ruling: 사용자가 비공식 경로(로그인 브라우저로 웹 경매장 검색)를 위험을 알고 선택 — 로컬 전용·옵트인·읽기 전용·소량으로 제한. 주무기는 무기 종류 분류가 필요해 검색 제외
- 후속(같은 날) 할루시네이션 방지: 골든셋 비교(툴팁 3·가격 화면 3)에서 AI가 옵션 문장을 줄이고 이름을 바꿔 적음 → 에이전트 지시문 맨 앞에 "실측값 원칙"(측정·관측값만, 글자 그대로, 없으면 측정값 없음, 평균·근사 표기), 비전 지시문에 "화면 글자 그대로·없는 값 채우지 않기·별 셀 수 있을 때만 스타포스", 공식 큐브 옵션표(304줄)에 없는 줄은 unverified_lines로 표시(웹 "확인 필요", 에이전트 첨부). validate 334 / vitest 53 · G11~G13 OK
- 측정(참고, 표본 작음): 툴팁 49항목 — OCR+규칙 47/49·1.6초·무료, 이미지→AI 46/49·5.5초(스타포스 못 읽음), OCR텍스트→LLM 38/49·7.9초. 가격 10개 — OCR 7/10(4862만 6250→6250 오독), AI 8/10(큰 가격 전부 정답)
- 후속(같은 날) 화면 공유 유사 프레임 측정(합성 14 + 실제 1): AI 툴팁 읽기 89.9%(찾은 것만), 1920→1600 축소 시 숫자 오독 4건(255→2550, 76→276 등), 비교 툴팁(현재 장착 중인 장비)을 매물로 착각. 수정: 비전 스키마 equipped·breakdown, equipped 매물 제외, 괄호 합 검산 실패 시 평가 보류(unverified_totals), 넥슨 API 착용 템과 이름·윗잠 일치 시 착용 템으로 제외, 캡처 최대 폭 1600→1920, 스타포스 확인 필요 표시. 재측정: 숫자 오독 0건, 툴팁 읽기 90.0%, 실제 화면 17/18·비교 툴팁 제외 성공, 장착 툴팁 표시만으로는 8개 중 4개 놓침(→착용 템 대조로 보완, 골든셋 캐릭터가 달라 재측정 불가). validate 340 / vitest 53
- 후속(같은 날) server/tooltip.py: 툴팁 찾기(남회색 바탕 + 위아래로 길게 이어진 어두운 열 묶기 — 경매장 창 테두리와 붙는 문제 해결), 별 세기(노란 정사각형 덩어리, 반짝이·가는 선 제외), 이름 보정(한두 글자). 로컬 골든 프레임 15장 실측: 툴팁 찾음 15/15, 별 15/15(AI 판독은 9장 중 1장만 맞았음). pillow·numpy 의존성 추가
- 후속(2026-10-05) 화면 분석 통합(analyze_frame): 툴팁 원래 크기 잘라 함께 전송, 스타포스는 별 세기 값으로 교체(AI 값은 starforce_ai로 보관), 이름 보정, 예시 지시문, 툴팁 번호(tooltip) 필드. 로컬 프레임 15장 재측정: 매물 툴팁 118/118, 툴팁 찾음 7/7, 별 15/15, 장착 비교 툴팁 7/8 걸러냄, 숫자 오독 0, 검산 헛경보 1(작은 괄호 값 누락). 주의: 같은 15장으로 지시문을 다듬어 낙관적일 수 있음 — 새 실제 화면으로 확인 필요
- 후속(2026-10-05) 내 데이터 모으기: server/dataset.py(VISION_DATASET_DIR 지정 시만, 프레임·AI 판독·수정 저장, 최대 2000장, .data/ gitignore), POST /api/vision/correct(고친 값을 정답으로 저장하고 다시 평가), GET /api/vision/dataset, 웹 [고치기](이름·스타포스·윗잠·에디·가격)와 "학습 데이터: 프레임 N장 · 고친 것 M건". validate 356 / vitest 55 · G11~G13 OK
- 후속(2026-10-05) 인터넷 자동 수집: 인벤 글 600개 → 코드가 툴팁으로 판단 42장(눈으로 보면 약 26장이 실제 툴팁) → 자동 라벨링(토큰 약 29만) → 코드 검사 통과 19장. 표본 5장 대조: 4장 완전 일치, 1장 이름 오보정(나이트→메이지, 이름 보정 기준을 한 글자 차이로 강화, 라벨 5건 되돌림). 착용 비교 툴팁 판독도 학습 데이터로 보관(equipped_items). 미해결: 별이 잘린 툴팁을 AI가 0성으로 적음
- 후속(2026-10-05) 수집 확대: 글 2500개 추가 → 새 툴팁 132장(전체 174장), 라벨링 토큰 61만(누적 약 91만), 검증 판독 68개(사진 66장). 표본 대조 11개(2회): 이름 오보정 1(수정 완료), 스타포스 잘림 1(확인 필요 표시) 외 전부 일치. 별 세기 보강: 주황 별, 붙은 툴팁(테두리 없음) 가운데 어두움 최저 열에서 분리, 맨 위 "고른 줄"만 셈(주황 글자 제외) — 골든 별 15/15 유지, 미트라(별 없음)·19성 펜던트 정답. 라벨 스타포스 재계산(AI 호출 없음)
- 후속(2026-10-05) (A) 정확도: 별 세기 54건 중 AI 판독과 다른 값 29건(54%) — 코드 별 세기로 교체가 맞음. 검사 탈락 표본 대조: 검산 실패 대부분 AI가 괄호 안 작은 값을 누락·오독(총합은 정답), 옵션표 탈락 다수가 레어·낮은 레벨 옵션(표 공백). 수정: 공식 옵션 문장 304→533(레어·레벨 10~250, engine/data/cube_options.json), 실딜과 무관한 줄은 대조 제외, 검산 실패 줄만 다시 읽기. 결과: 검증 판독 68→81, 다시 읽기 12건 중 5건 맞춤(토큰 7336), 대조한 2건 모두 다시 읽은 값이 정답. (B) OpenAI 공식 문서: 파인튜닝 플랫폼 종료 중, 신규 사용자 접근 불가, 비전 파인튜닝은 gpt-4o-2024-08-06만 — 우리 계정으로는 불가. 대안은 로컬 오픈 모델 학습(GPU 필요)
- 후속(2026-10-05) 자동 프레임 테스트셋 40장(사람 손 없음, 토큰 23만): 툴팁 찾음 36/40, 항목 576/653(찾은 것만 95.8%). 스타포스가 정확히 15 모자람(22→7) — 상자가 첫 별 줄 아래에서 시작. 수정: stars_near(상자 위 40px 띠까지), 위쪽 배경의 들쭉날쭉한 덩어리 줄은 건너뜀. 별 세기(AI 없이 재측정) 7/21→19/21, 골든 15/15 유지. 남은 오류: 이름 변형(에센던트·엠블럼·시프러스), 숫자 일부(131→13), 툴팁 못 찾음 4. 방법 2: 빠른 캡처(0.5초·줄 세우기·32×32), POST /api/vision/score(넥슨 API 착용 템이 정답), 웹 [장비창 채점]
- 후속(2026-10-05) 실제 게임 장비창 훑기 첫 측정: 저장 프레임 46장 중 판독 15개를 넥슨 API 착용 템과 채점 → 착용 템 11개 매칭, 항목 191/191(100%). 문제: 장비창 툴팁이 착용 템으로 분류돼 목록에서 빠짐(→ equipped_items 응답·웹에서 모아 채점), 0.5초 캡처가 IP당 제한에 걸려 23번 중 5번 거절(→ 관리자 화면 분석은 제한 제외, 토큰 한도로만)
- 후속(2026-10-05) 토큰 절약: 하루 한도(20만) 소진 — 장비창 훑기 46장 중 31장(67%)이 툴팁 없는 화면이었고 판독 0. 툴팁 없는 화면은 AI에 안 보냄(기본, "목록 화면도 읽기"로 끔), 같은 툴팁·같은 화면은 이전 판독 재사용(FrameCache), 캐시·건너뛴 화면은 학습 데이터에 중복 저장 안 함
- 후속(2026-10-05) 1개만 채점된 원인: scripts/run-local.ps1이 빌드 결과가 없을 때만 웹을 빌드해, 이후 웹 수정(착용 템 판독 모으기 등)이 화면에 반영되지 않음 → 소스가 빌드보다 새로우면 다시 빌드. 저장 판독으로 다시 채점: 착용 템 14개 매칭, 항목 238/239(99.6%) — 틀린 1개는 도미네이터 펜던트 레벨 미판독
