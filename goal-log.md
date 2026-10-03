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
