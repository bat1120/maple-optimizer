# G1 (1b단계): 잔차 분해·교체·세트·프리셋 조합 Implementation Plan

> 자동 반복 모드(goal 설정 C). 승인 대기 없이 진행하고 결정은 `Ruling:`으로 남긴다.

**Goal:** 한 스냅샷을 보정(calibrate)한 뒤, 장비·하이퍼·어빌리티 프리셋 조합과 아이템 교체에 대한 최종 스탯·스탯공격력·보스 실딜 지수를 예측한다.

**Spec:** `docs/superpowers/specs/2026-10-03-maple-optimizer-design.md` §5.2, §5.4(1~6), §5.5. 성공 기준: `GOALS.md` G1.

## 사전 실측 (2026-10-03, 스크래치 프로토타입)

- 세트 매핑: fixture 47개 스냅샷의 `set-effect` 개수 제약을 ILP로 풀고 이름 규칙(에테르넬·아케인셰이드·앱솔랩스·도전자 접두어)을 고정했다. 장비형 방어구 세트는 전부 일치. 남는 불일치는 펫·캐시·심볼형 세트(쁘띠, 마스터 ~, 소멸의 여로, 결속의 반지 등)와 에스페라 2·모라스 1·보스 장신구 1건.
- 무기 규칙: 제네시스·데스티니 무기는 직업군 에테르넬 세트에 항상 +1, 루타비스·앱솔랩스·아케인셰이드 직업군 세트에는 그 세트 장비가 3개 이상일 때 +1(럭키).
- %미적용: 하이퍼스탯 고정값, 아케인·어센틱 심볼 스탯, 유니온 공격대원 효과. 이것을 빼면 예측이 1.5% 크게 빗나갔다.
- 사냥→보스 전환 예측 스탯공격력 오차: 같은 버프 상태 짝(스크린샷 ↔ 보스 스냅샷) 0.60%, API fixture 짝 4.0%(입력 스냅샷의 버프 차이: 최종뎀 188.93 vs 186.70).

## Rulings

- Ruling: 주·부스탯 잔차는 "%"로 둔다(보이지 않는 % 출처 = 패시브·버프), 공격력/마력 잔차는 "고정값"으로 둔다(펫·캐시·스킬 고정값이 큼) — 프로토타입에서 반대 조합보다 오차가 작았다(0.60% vs 0.98%) — 틀리면 교체 Δ가 수 % 왜곡.
- Ruling: `예비 특수 반지` 슬롯은 스탯에 넣지 않는다 — 착용 슬롯이 아니라 교체용 보관 슬롯이고, 넣으면 세트 개수가 API와 어긋난다 — 틀리면 해당 반지 스탯만큼 누락.
- Ruling: 판정 ①은 GOALS 문구대로 API fixture 짝으로 판정하고, 같은 버프 상태 짝(인게임 스크린샷 수치) 결과를 함께 기록한다 — 기준을 바꾸지 않기 위해 — 틀리면 G1이 모델 결함이 아닌 입력 버프 차이로 PARTIAL.
- Ruling: 세트 매핑은 생성 데이터(`engine/data/set_items.json`)로 커밋하고, 재생성 도구(`tools/derive_set_data.py`, scipy 필요)는 dev 의존성 그룹 `analysis`로 둔다.

## File Structure

```
engine/data/set_items.json      아이템명 → 세트명 (생성물)
engine/data/set_tiers.json      세트명 → {개수: 옵션 문자열} (생성물)
engine/stats/sets.py            SetCatalog, count_sets, set_block (무기 규칙 포함)
engine/stats/jobs.py            JobProfile.branch 추가 (전사/마법사/궁수/도적/해적)
engine/stats/snapshot.py        titles, symbols, union 필드 추가, Setting
engine/stats/residual.py        Sources, Calibration, sources_for, calibrate, predict
engine/stats/metrics.py         BossProfile, stat_attack, boss_index
engine/stats/evaluate.py        evaluate_setting, rank_settings, swap_item
nexon/convert.py                칭호·심볼·유니온 공격대 파싱, 예비 특수 반지 제외
tools/build_fixtures.py         .raw-pairs → tests/fixtures/pairs 익명화
tools/derive_set_data.py        세트 데이터 재생성 (ILP)
tests/test_sets.py, tests/test_residual.py, tests/goals/test_g1.py
```

## Interfaces

- `Setting(equipment: int, hyper: int, ability: int)` (frozen)
- `SetCatalog.load() -> SetCatalog`; `count_sets(items: list[Item], branch: str) -> Counter[str]`; `set_block(counts, level) -> StatBlock`
- `sources_for(snap, setting, catalog, items=None) -> Sources(pct: StatBlock, nopct: StatBlock)`
- `calibrate(snap, catalog) -> Calibration` (스냅샷의 활성 세팅 기준)
- `predict(cal, sources) -> Predicted(stats: dict[str,float], atk, matk, dmg, boss, fd, cd, ied)` — 활성 세팅을 넣으면 API 최종값을 그대로 재현
- `BossProfile(name: str, defense: float)`; `stat_attack(pred, job, weapon_part) -> float`; `boss_index(pred, job, weapon_part, boss) -> float`
- `evaluate_setting(snap, setting, boss, catalog) -> float`; `rank_settings(snap, boss, catalog) -> list[tuple[Setting, float]]` (27개, 내림차순); `swap_item(snap, setting, slot, new_item, boss, catalog) -> float`

## TDD 순서

1. `tests/goals/test_g1.py` 작성 → 실패 확인 (모듈 없음)
2. fixture 쌍 추가(build_fixtures 확장) → 쌍 존재 테스트
3. sets: 레테 사냥·보스 세트 개수가 API와 정확히 일치, 47개 장비형 세트 일치율 ≥ 0.95
4. snapshot 확장: 칭호·심볼·유니온 파싱 값 단언
5. residual: 활성 세팅 predict == API 최종값(재현), 45명
6. metrics/evaluate: 27조합, 교체
7. `scripts/validate.ps1`, `scripts/verify.ps1 -Goal G1`
