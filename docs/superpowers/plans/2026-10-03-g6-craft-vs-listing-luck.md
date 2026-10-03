# G6 (3단계): 매물의 직작 기댓값 대비, 내 운 분석

> 자동 반복 모드(goal 설정 C). 성공 기준: `GOALS.md` G6. 스펙 §7(직작 기댓값 대비), §6(내 운).

## Rulings
- Ruling: 직작 비용 = 베이스 템 가격 + 스타포스 비용 + 잠재 재설정 비용(목표 확률 p, 1회 메소 가격). 추옵(환불)은 확률표가 없어 1차에서 뺀다 — 숫자를 지어내지 않기 위해 — 비싼 추옵 매물은 직작 대비가 낙관적으로 나온다(화면에 "추옵 미포함" 표기).
- Ruling: 백분위 계산은 반해석적: 스타포스 몬테카를로 표본마다 큐브 횟수의 정확한 기하분포 CDF를 적용. 판정은 서로 다른 시드의 결합 몬테카를로 경험분포와 비교한다.
- Ruling: 내 운 지출은 `잠재능력 재설정` 기록만 메소 가격표로 합산한다. 캐시 큐브(`history/cube`) 기록은 가격을 알 수 없어 횟수만 센다.
- Ruling: 확률 정보 API 응답의 JSON 형태는 nexon/convert.py에서 `CubeAttempt`로 바꾼다.

## Interfaces
- `engine/enhance/starforce.py`: `simulate_samples(...) -> list[float]` (기존 `simulate`가 사용)
- `engine/market/craft.py`: `CraftPlan(base_price, level, start_star, target_star, destroy_cost, cond, cube_p, cube_cost)`, `price_percentile(plan, price, samples=20000, seed=...) -> float` (P[직작 비용 ≤ 가격]), `simulate_craft(plan, trials, seed) -> list[float]`, `compare_listing(plan, price) -> CraftComparison`
- `engine/enhance/history.py`: `CubeAttempt(kind, item, part, level, grade, after: list[str], date)`, `meso_spent(attempts) -> Spent(meso, counted, uncounted)`, `luck(attempts, item, predicate, p) -> Luck(tries, achieved, percentile)`
- `nexon/convert.py`: `cube_attempts(potential_json_rows, cube_json_rows) -> list[CubeAttempt]`
