import json
import pathlib

import pytest

from engine.enhance.cube import CubeTable, lines_at_least, stat_sum_at_least, success_probability
from engine.enhance.history import luck, meso_spent
from engine.enhance.starforce import StarforceConditions, expected_cost
from engine.market.craft import CraftPlan, compare_listing, price_percentile
from nexon.convert import cube_attempts

HIST = pathlib.Path(__file__).parent / "fixtures" / "history"
POT = json.loads((HIST / "history_potential.json").read_text(encoding="utf-8"))
CUBE = json.loads((HIST / "history_cube.json").read_text(encoding="utf-8"))
PLAN = CraftPlan(base_price=2_000_000_000, level=200, start_star=0, target_star=22, destroy_cost=3_000_000_000,
                 cond=StarforceConditions(), cube_p=0.02765, cube_cost=45_000_000)


def test_percentile_is_monotone_in_price_and_bounded():
    a = price_percentile(PLAN, 10_000_000_000, samples=5000, seed=1)
    b = price_percentile(PLAN, 40_000_000_000, samples=5000, seed=1)
    assert 0 <= a < b <= 1
    assert price_percentile(PLAN, 1, samples=1000, seed=1) == 0.0


def test_compare_listing_reports_ratio_and_chance_craft_costs_more():
    c = compare_listing(PLAN, 15_000_000_000, samples=5000, seed=1)
    exact_mean = 2_000_000_000 + expected_cost(200, 0, 22, 3_000_000_000, StarforceConditions()) + 45_000_000 / 0.02765
    assert c.craft_mean == pytest.approx(exact_mean)
    assert c.ratio_to_mean == pytest.approx(15_000_000_000 / exact_mean)
    assert c.prob_craft_costs_more == pytest.approx(1 - price_percentile(PLAN, 15_000_000_000, samples=5000, seed=1))
    assert c.distribution.median <= c.distribution.p90


def test_cube_attempts_conversion():
    att = cube_attempts(POT, CUBE)
    assert len(att) == len(POT) + len(CUBE)
    resets = [a for a in att if a.kind == "잠재능력 재설정"]
    assert resets[0].item == "제네시스 카르타" and resets[0].level == 200 and resets[0].grade == "레전드리"
    assert len(resets[0].after) == 3 and all(isinstance(x, str) for x in resets[0].after)
    assert [a.date for a in resets] == sorted(a.date for a in resets)  # 시간순


def test_meso_spent_counts_only_meso_resets():
    s = meso_spent(cube_attempts(POT, CUBE))
    assert s.counted == 114 and s.meso == 114 * 45_000_000 and s.uncounted == len(CUBE)


def test_luck_when_goal_not_reached_reports_failure_chance():
    att = cube_attempts(POT, CUBE)
    t = CubeTable.load("레전드리/무기/200")
    pred = lines_at_least("BOSS", 3)
    p = success_probability(t, pred)
    r = luck(att, "제네시스 카르타", pred, p)
    if not r.achieved:
        assert r.percentile == pytest.approx((1 - p) ** r.tries)  # n번 연속 실패할 확률
    assert r.tries >= 1


def test_luck_when_goal_reached_reports_cdf_at_success():
    att = cube_attempts(POT, CUBE)
    pred = stat_sum_at_least("MATK", True, 0)  # 항상 성공 → 첫 시도에 달성
    r = luck(att, "제네시스 카르타", pred, 1.0)
    assert r.achieved and r.tries == 1 and r.percentile == pytest.approx(1.0)
