"""매물 가격 vs 직작 비용 분포 (스펙 §7 "직작 기댓값 대비").

직작 비용 = 베이스 템 가격 + 스타포스 비용 + 잠재 재설정 비용(목표 확률 p × 1회 가격의 기하분포).
추옵(환불)은 확률표가 없어 포함하지 않는다 (Ruling, G6 계획).
"""
import math
import random
from dataclasses import dataclass

from engine.enhance.starforce import StarforceConditions, expected_cost, simulate_samples
from engine.enhance.stats import Distribution


@dataclass(frozen=True)
class CraftPlan:
    base_price: float
    level: int
    start_star: int
    target_star: int
    destroy_cost: float
    cond: StarforceConditions
    cube_p: float      # 1회 재설정으로 목표 잠재가 뜰 확률 (0이면 큐브 단계 없음 — cube_cost도 0)
    cube_cost: float   # 1회 재설정 메소


@dataclass(frozen=True)
class CraftComparison:
    price: float
    craft_mean: float
    distribution: Distribution
    ratio_to_mean: float          # 매물 가격 ÷ 직작 평균
    prob_craft_costs_more: float  # 직작하면 이 가격보다 더 들 확률


def _starforce(plan: CraftPlan, n: int, seed: int) -> list[float]:
    if plan.target_star <= plan.start_star:
        return [0.0] * n
    return simulate_samples(plan.level, plan.start_star, plan.target_star, plan.destroy_cost, plan.cond, n, seed)


def _cube_cdf(plan: CraftPlan, budget: float) -> float:
    """큐브에 budget 메소 이하를 쓰고 목표를 달성할 확률."""
    if plan.cube_p <= 0 or plan.cube_cost <= 0:
        return 1.0 if budget >= 0 else 0.0
    m = math.floor(budget / plan.cube_cost + 1e-9)
    return 0.0 if m < 1 else 1 - (1 - plan.cube_p) ** m


def price_percentile(plan: CraftPlan, price: float, samples: int = 20_000, seed: int = 20261003) -> float:
    """P[직작 비용 ≤ price]. 스타포스는 몬테카를로 표본, 큐브는 정확한 기하분포 CDF."""
    sf = _starforce(plan, samples, seed)
    return sum(_cube_cdf(plan, price - plan.base_price - x) for x in sf) / samples


def simulate_craft(plan: CraftPlan, trials: int, seed: int) -> list[float]:
    """직작 전체를 결합 몬테카를로로 뽑은 비용 표본."""
    sf = _starforce(plan, trials, seed)
    rng = random.Random(seed + 1)
    out = []
    for x in sf:
        cubes = 0
        if plan.cube_p > 0 and plan.cube_cost > 0:
            cubes = math.ceil(math.log(1 - rng.random()) / math.log(1 - plan.cube_p)) if plan.cube_p < 1 else 1
        out.append(plan.base_price + x + cubes * plan.cube_cost)
    return out


def craft_mean(plan: CraftPlan) -> float:
    sf = 0.0 if plan.target_star <= plan.start_star else expected_cost(
        plan.level, plan.start_star, plan.target_star, plan.destroy_cost, plan.cond)
    cube = plan.cube_cost / plan.cube_p if plan.cube_p > 0 else 0.0
    return plan.base_price + sf + cube


def compare_listing(plan: CraftPlan, price: float, samples: int = 20_000, seed: int = 20261003) -> CraftComparison:
    mean = craft_mean(plan)
    dist = Distribution.from_samples(simulate_craft(plan, samples, seed))
    return CraftComparison(price, mean, dist, price / mean, 1 - price_percentile(plan, price, samples, seed))
