"""스타포스 강화 비용 (2025-03 개편 + 2026-03 스타캐치 상시 적용 기준, engine/data/starforce.json).

- 실패하면 단계 유지, 15성 이상은 일정 확률로 파괴
- 파괴 시 흔적: 완전 복구면 파괴 직전 성(23성 이상에서 파괴되면 22성), 기본 복구면 12성
- 파괴 처리 비용(스페어 시세 + 복구 메소)은 사용자가 넣는다
"""
import json
import pathlib
import random
from dataclasses import dataclass

from engine.enhance.stats import Distribution

_DATA = json.loads((pathlib.Path(__file__).resolve().parent.parent / "data" / "starforce.json").read_text(encoding="utf-8"))
_PROBS = [tuple(p) for p in _DATA["probabilities"]]
_DIV = {int(k): v for k, v in _DATA["cost_divisor_from_10"].items() if k.isdigit()}
_DIV_DEFAULT = _DATA["cost_divisor_from_10"]["22+"]


@dataclass(frozen=True)
class StarforceConditions:
    discount30: bool = False          # 30% 할인 이벤트 (파괴 방지 추가금 제외)
    destroy_down30: bool = False      # 21성 이하 파괴 확률 30% 감소 이벤트
    guarantee_5_10_15: bool = False   # 5·10·15성 100% 성공 이벤트
    protect: bool = False             # 파괴 방지 (15~17성 시도)
    restore: str = "full"             # "full"(같은 성으로) | "basic"(12성)


def max_star(level: int) -> int:
    for upto, star in _DATA["max_star_by_level"]:
        if level <= upto:
            return star
    raise ValueError(level)


def base_cost(level: int, star: int) -> int:
    if star < 10:
        raw = 1000 + level ** 3 * (star + 1) / 36
    else:
        raw = 1000 + level ** 3 * (star + 1) ** 2.7 / _DIV.get(star, _DIV_DEFAULT)
    return round(raw / 100) * 100


def _raw_transition(star: int, cond: StarforceConditions) -> tuple[float, float, float]:
    s, k, d = _PROBS[star]
    if cond.guarantee_5_10_15 and star in _DATA["guarantee_stars"]:
        return 1.0, 0.0, 0.0
    if cond.destroy_down30 and star <= _DATA["destroy_down30_max_star"] and d > 0:
        k, d = k + d * 0.3, d * 0.7  # Ruling: 줄어든 파괴 확률은 유지로 (G5 계획)
    return s, k, d


def _protected(star: int, cond: StarforceConditions) -> bool:
    return cond.protect and star in _DATA["protect_stars"] and _raw_transition(star, cond)[2] > 0


def transition(star: int, cond: StarforceConditions) -> tuple[float, float, float]:
    s, k, d = _raw_transition(star, cond)
    if _protected(star, cond):
        k, d = k + d, 0.0
    return s, k, d


def attempt_cost(level: int, star: int, cond: StarforceConditions) -> float:
    b = base_cost(level, star)
    c = b * 0.7 if cond.discount30 else b
    if _protected(star, cond):
        c += b * _DATA["protect_surcharge"]
    return c


def destroy_return(star: int, cond: StarforceConditions) -> int:
    if cond.restore == "basic":
        return _DATA["basic_restore_star"]
    return _DATA["trace_cap_star"] if star >= _DATA["trace_cap_from"] else star


def _check(level: int, start: int, target: int) -> None:
    if not 0 <= start < target:
        raise ValueError(f"시작 {start}성 < 목표 {target}성 이어야 합니다")
    if target > max_star(level):
        raise ValueError(f"{level}레벨 장비는 {max_star(level)}성까지입니다")


def expected_cost(level: int, start: int, target: int, destroy_cost: float, cond: StarforceConditions) -> float:
    """정확한 기대 비용: E[s] = c + p·E[s+1] + k·E[s] + d·(D + E[r(s)]), E[target] = 0 을 푼다."""
    _check(level, start, target)
    lo = min([start] + [destroy_return(s, cond) for s in range(start, target) if transition(s, cond)[2] > 0])
    states = list(range(lo, target))
    n = len(states)
    a = [[0.0] * (n + 1) for _ in range(n)]
    for i, st in enumerate(states):
        p, k, d = transition(st, cond)
        a[i][i] += 1 - k
        if st + 1 < target:
            a[i][i + 1] -= p
        if d > 0:
            a[i][destroy_return(st, cond) - lo] -= d
        a[i][n] = attempt_cost(level, st, cond) + d * destroy_cost
    for col in range(n):  # 가우스 소거 (부분 피벗)
        piv = max(range(col, n), key=lambda r: abs(a[r][col]))
        a[col], a[piv] = a[piv], a[col]
        for r in range(n):
            if r != col and a[r][col]:
                f = a[r][col] / a[col][col]
                for c in range(col, n + 1):
                    a[r][c] -= f * a[col][c]
    return a[start - lo][n] / a[start - lo][start - lo]


def simulate(level: int, start: int, target: int, destroy_cost: float, cond: StarforceConditions,
             trials: int, seed: int) -> Distribution:
    return Distribution.from_samples(simulate_samples(level, start, target, destroy_cost, cond, trials, seed))


def simulate_samples(level: int, start: int, target: int, destroy_cost: float, cond: StarforceConditions,
                     trials: int, seed: int) -> list[float]:
    _check(level, start, target)
    rng = random.Random(seed)
    trans = {s: transition(s, cond) for s in range(target)}
    costs = {s: attempt_cost(level, s, cond) for s in range(target)}
    back = {s: destroy_return(s, cond) for s in range(target)}
    out = []
    for _ in range(trials):
        star, total = start, 0.0
        while star < target:
            p, k, _d = trans[star]
            total += costs[star]
            u = rng.random()
            if u < p:
                star += 1
            elif u >= p + k:
                total += destroy_cost
                star = back[star]
        out.append(total)
    return out
