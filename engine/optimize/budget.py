"""예산 안에서 실딜 지수를 가장 많이 올리는 후보 조합.

탐욕법: 남은 후보 중 (적용 후 지수/현재 지수 − 1) ÷ 비용 최대를 적용하고, 적용된 상태에서 다시 평가한다.
같은 부위는 한 번만 바꾼다. 지수를 올리지 못하는 후보는 고르지 않는다.
순수 효율 탐욕법은 싸고 효율 좋은 후보가 부위를 먼저 차지해 훨씬 센 후보를 막는다(G7 1차 측정 최소 0.54).
그래서 (1) 후보마다 "먼저 산다"로 고정한 출발점에서도 돌려 최고를 고르고, (2) 결과에서 한 후보를 다른 후보로
바꿔 나아지면 계속 바꾼다.
전수 탐색: 부위당 최대 1개·예산 이내 모든 조합 (후보 ≤ 10개 검증용).
"""
import itertools
from dataclasses import dataclass, field

from engine.stats.evaluate import Evaluator
from engine.stats.snapshot import Item


@dataclass(frozen=True)
class Action:
    slot: str
    item: Item
    cost: float
    label: str = ""


@dataclass
class Plan:
    actions: list[Action] = field(default_factory=list)
    spent: float = 0.0
    index: float = 0.0
    gain_pct: float = 0.0


def _apply(base: dict[str, Item], actions) -> dict[str, Item]:
    items = dict(base)
    for a in actions:
        items[a.slot] = a.item
    return items


def _greedy_from(ev: Evaluator, base: dict[str, Item], actions: list[Action], budget: float,
                 chosen: list[Action]) -> tuple[list[Action], float, float]:
    chosen = list(chosen)
    spent = sum(a.cost for a in chosen)
    current = ev.index(_apply(base, chosen))
    while True:
        used = {a.slot for a in chosen}
        best, best_score, best_index = None, 0.0, current
        for a in actions:
            if a in chosen or a.slot in used or spent + a.cost > budget:
                continue
            idx = ev.index(_apply(base, chosen + [a]))
            gain = idx / current - 1 if current > 0 else 0.0
            if gain <= 0:
                continue
            score = gain / a.cost if a.cost > 0 else float("inf")
            if score > best_score:
                best, best_score, best_index = a, score, idx
        if best is None:
            return chosen, spent, current
        chosen.append(best)
        spent += best.cost
        current = best_index


def _improve(ev: Evaluator, base: dict[str, Item], actions: list[Action], budget: float,
             chosen: list[Action], current: float) -> tuple[list[Action], float]:
    """고른 후보 하나를 고르지 않은 후보로 바꿔 지수가 오르면 바꾼다. 더 나아지지 않을 때까지."""
    improved = True
    while improved:
        improved = False
        for i, old in enumerate(chosen):
            rest = chosen[:i] + chosen[i + 1:]
            used = {a.slot for a in rest}
            spent = sum(a.cost for a in rest)
            for a in actions:
                if a in chosen or a.slot in used or spent + a.cost > budget:
                    continue
                idx = ev.index(_apply(base, rest + [a]))
                if idx > current * (1 + 1e-12):
                    chosen, current, improved = rest + [a], idx, True
                    break
            if improved:
                break
    return chosen, current


def greedy(ev: Evaluator, actions: list[Action], budget: float) -> Plan:
    base = ev.base_items()
    start = ev.index(base)
    starts = [[]] + [[a] for a in actions if a.cost <= budget and ev.index(_apply(base, [a])) > start]
    best_chosen, best_index = [], start
    for forced in starts:
        chosen, _spent, idx = _greedy_from(ev, base, actions, budget, forced)
        if idx > best_index:
            best_chosen, best_index = chosen, idx
    best_chosen, best_index = _improve(ev, base, actions, budget, best_chosen, best_index)
    spent = sum(a.cost for a in best_chosen)
    return Plan(best_chosen, spent, best_index, (best_index / start - 1) * 100 if start > 0 else 0.0)


def brute_force(ev: Evaluator, actions: list[Action], budget: float) -> Plan:
    base = ev.base_items()
    start = ev.index(base)
    best = Plan([], 0.0, start, 0.0)
    for r in range(1, len(actions) + 1):
        for combo in itertools.combinations(actions, r):
            slots = [a.slot for a in combo]
            cost = sum(a.cost for a in combo)
            if len(set(slots)) != len(slots) or cost > budget:
                continue
            idx = ev.index(_apply(base, combo))
            if idx > best.index:
                best = Plan(list(combo), cost, idx, (idx / start - 1) * 100 if start > 0 else 0.0)
    return best
