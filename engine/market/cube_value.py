"""메소 재설정(큐브) 기대 비용: 지금 등급에서 목표 등급까지 올리고(천장 포함), 목표 등급에서 원하는 줄이 나올 때까지.

- 윗잠: engine/data/cube_black.json (메소 재설정 = 블랙 큐브, 등급 상승 확률·천장)
- 에디: engine/data/cube_additional_cost.json (메소 재설정 = 화이트 에디셔널 큐브)
- 등급이 오를 때는 줄이 새로 굴려지므로, 목표 등급 도달 후의 재설정 횟수만 성공 확률로 나눈다.
"""
import functools
import json
import pathlib

from engine.enhance.cube import tier_up_tries

GRADE_ORDER = ("레어", "에픽", "유니크", "레전드리")
_DATA = pathlib.Path(__file__).resolve().parents[1] / "data"
_FILES = {"잠재": "cube_black.json", "에디": "cube_additional_cost.json"}


@functools.lru_cache(maxsize=2)
def _data(kind: str) -> dict:
    return json.loads((_DATA / _FILES[kind]).read_text(encoding="utf-8"))


def reset_cost_for(kind: str, level: int, grade: str) -> int:
    costs = _data(kind)["meso_cost"]
    bracket = max(int(k) for k in costs if int(k) <= level)
    return costs[str(bracket)][grade]


def expected_cost(kind: str, level: int, current_grade: str | None, target_grade: str, p_success: float) -> float | None:
    """평균 메소. 목표 등급이 지금보다 낮거나 잠재가 없으면(None) 큐브로는 갈 수 없다."""
    if current_grade not in GRADE_ORDER or p_success <= 0:
        return None
    cur, tgt = GRADE_ORDER.index(current_grade), GRADE_ORDER.index(target_grade)
    if tgt < cur:
        return None
    cost = 0.0
    for g in GRADE_ORDER[cur:tgt]:
        p, ceiling = _data(kind)["tier_up"][g]
        cost += tier_up_tries(p, ceiling).mean * reset_cost_for(kind, level, g)
    return cost + reset_cost_for(kind, level, target_grade) / p_success
