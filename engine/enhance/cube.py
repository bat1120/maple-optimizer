"""잠재능력 재설정(블랙 큐브) 확률 (공식 확률 페이지, engine/data/cube_black.json).

한 번 돌리면 세 줄이 각자의 줄 확률표에서 독립적으로 뽑힌다(Ruling: G5 계획).
목표 달성 확률 p → 필요한 횟수는 기하분포, 등급 상승은 천장이 있는 기하분포.
"""
import itertools
import json
import math
import pathlib
import random
from collections.abc import Callable
from dataclasses import dataclass

from engine.enhance.stats import Distribution
from engine.options import StatLine, parse_option

_DATA = json.loads((pathlib.Path(__file__).resolve().parent.parent / "data" / "cube_black.json").read_text(encoding="utf-8"))

Option = tuple[StatLine, ...]
Predicate = Callable[[list[Option]], bool]


@dataclass(frozen=True)
class CubeTable:
    name: str
    lines: list[list[tuple[Option, float]]]  # 줄마다 (옵션, 확률) — 확률 합 1로 정규화

    @classmethod
    def load(cls, name: str) -> "CubeTable":
        raw = _DATA["tables"][name]["lines"]
        lines = []
        for line in raw:
            total = sum(line.values())
            lines.append([(tuple(parse_option(text, 200) or ()), pct / total) for text, pct in line.items()])
        return cls(name, lines)


def lines_at_least(key: str, n: int) -> Predicate:
    return lambda options: sum(any(l.key == key for l in opt) for opt in options) >= n


def stat_sum_at_least(key: str, percent: bool, value: float) -> Predicate:
    return lambda options: sum(l.value for opt in options for l in opt if l.key == key and l.percent == percent) >= value


def success_probability(table: CubeTable, predicate: Predicate) -> float:
    """세 줄 조합을 전부 열거한 정확한 1회 성공 확률."""
    total = 0.0
    for combo in itertools.product(*table.lines):
        if predicate([opt for opt, _ in combo]):
            total += math.prod(p for _, p in combo)
    return total


def simulate_success_rate(table: CubeTable, predicate: Predicate, trials: int, seed: int) -> float:
    rng = random.Random(seed)
    opts = [[o for o, _ in line] for line in table.lines]
    weights = [[p for _, p in line] for line in table.lines]
    hits = sum(predicate([rng.choices(opts[i], weights[i])[0] for i in range(len(opts))]) for _ in range(trials))
    return hits / trials


def _quantile_geometric(p: float, q: float) -> int:
    return 1 if p >= 1 else math.ceil(math.log(1 - q) / math.log(1 - p))


def cubes_needed(p: float) -> Distribution:
    if p <= 0:
        raise ValueError("목표 달성 확률이 0입니다")
    return Distribution(1 / p, _quantile_geometric(p, 0.5), _quantile_geometric(p, 0.75), _quantile_geometric(p, 0.9))


def tier_up_tries(p: float, ceiling: int) -> Distribution:
    """천장이 있는 등급 상승 횟수: k < 천장이면 p(1−p)^(k−1), 천장에서 나머지 전부."""
    probs = [p * (1 - p) ** (k - 1) for k in range(1, ceiling)] + [(1 - p) ** (ceiling - 1)]
    mean = sum(k * pk for k, pk in enumerate(probs, start=1))

    def q(x: float) -> int:
        acc = 0.0
        for k, pk in enumerate(probs, start=1):
            acc += pk
            if acc >= x - 1e-12:
                return k
        return ceiling

    return Distribution(mean, q(0.5), q(0.75), q(0.9))


def tier_up(grade: str) -> tuple[float, int]:
    """현재 등급 → (등급 상승 확률, 천장 횟수)."""
    p, ceiling = _DATA["tier_up"][grade]
    return p, ceiling


def reset_cost(level: int, grade: str) -> int:
    bracket = max(int(k) for k in _DATA["meso_cost"] if int(k) <= level)
    return _DATA["meso_cost"][str(bracket)][grade]
