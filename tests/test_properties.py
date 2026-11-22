"""속성 기반 테스트: 예시 몇 개가 아니라 '어떤 입력이 와도 지켜져야 하는 조건'을 무작위 입력으로 확인한다.

기본은 고정 시드라 CI에서 결과가 매번 같다. 더 넓게 찾을 때는 `HYPOTHESIS_PROFILE=explore uv run pytest tests/test_properties.py`.
"""
import copy
import os

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from engine.enhance.cube import CubeTable, cubes_needed, lines_at_least, stat_sum_at_least, success_probability, \
    tier_up_tries
from engine.enhance.starforce import StarforceConditions, attempt_cost, expected_cost, max_star, transition
from engine.optimize.budget import Action, brute_force, greedy
from engine.stats.evaluate import Evaluator
from engine.stats.metrics import BossProfile
from engine.stats.sets import SetCatalog
from engine.stats.snapshot import Setting
from helpers import bundle
from nexon.convert import snapshot

settings.register_profile("fixed", derandomize=True, database=None, deadline=None)
settings.register_profile("explore", max_examples=500, database=None, deadline=None)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "fixed"))

EV = Evaluator(snapshot(bundle("레테")), Setting(2, 3, 2), BossProfile("기준", 300.0), SetCatalog.load())
BASE_ITEMS = EV.base_items()
START_INDEX = EV.index(BASE_ITEMS)
SLOTS = ["반지1", "반지2", "펜던트", "벨트"]
EOK = 10**8

CUBE = CubeTable.load("레전드리/무기/200")
CUBE_KEYS = sorted({line.key for row in CUBE.lines for option, _ in row for line in option})

LEVELS = [140, 150, 160, 200, 250]

conditions = st.builds(
    StarforceConditions,
    discount30=st.booleans(), destroy_down30=st.booleans(), guarantee_5_10_15=st.booleans(),
    protect=st.booleans(), restore=st.sampled_from(["full", "basic"]), restore_discount20=st.booleans(),
)


@st.composite
def star_ranges(draw):
    level = draw(st.sampled_from(LEVELS))
    target = draw(st.integers(1, max_star(level)))
    start = draw(st.integers(0, target - 1))
    return level, start, target


@st.composite
def action_lists(draw):
    count = draw(st.integers(0, 5))
    actions = []
    for i in range(count):
        slot = draw(st.sampled_from(SLOTS))
        item = copy.deepcopy(BASE_ITEMS[slot])
        item.stats.pct["INT"] = item.stats.pct.get("INT", 0) + draw(st.integers(-5, 15))
        actions.append(Action(slot, item, draw(st.integers(1, 50)) * EOK, f"후보{i}"))
    return actions


@given(star=st.integers(0, max_star(250) - 1), cond=conditions)
def test_starforce_transition_is_a_probability_distribution(star, cond):
    success, keep, destroy = transition(star, cond)
    assert min(success, keep, destroy) >= 0
    assert success + keep + destroy == pytest.approx(1)


@given(level=st.sampled_from(LEVELS), star=st.integers(0, 29), cond=conditions)
def test_starforce_discount_never_raises_attempt_cost(level, star, cond):
    assume(star < max_star(level))
    full_price = StarforceConditions(**{**cond.__dict__, "discount30": False})
    discounted = StarforceConditions(**{**cond.__dict__, "discount30": True})
    assert 0 < attempt_cost(level, star, discounted) <= attempt_cost(level, star, full_price)


@given(span=star_ranges(), cond=conditions, cheap=st.integers(0, 100), extra=st.integers(0, 100))
def test_starforce_expected_cost_grows_with_destroy_cost(span, cond, cheap, extra):
    level, start, target = span
    low = expected_cost(level, start, target, cheap * EOK, cond)
    high = expected_cost(level, start, target, (cheap + extra) * EOK, cond)
    assert 0 < low <= high * (1 + 1e-9)


@given(span=star_ranges(), cond=conditions, destroy=st.integers(0, 100))
def test_starforce_higher_target_never_costs_less(span, cond, destroy):
    level, start, target = span
    assume(target < max_star(level))
    near = expected_cost(level, start, target, destroy * EOK, cond)
    far = expected_cost(level, start, target + 1, destroy * EOK, cond)
    assert near <= far * (1 + 1e-9)


@settings(max_examples=20)
@given(key=st.sampled_from(CUBE_KEYS), count=st.integers(0, 3))
def test_cube_more_matching_lines_is_never_more_likely(key, count):
    easier = success_probability(CUBE, lines_at_least(key, count))
    harder = success_probability(CUBE, lines_at_least(key, count + 1))
    assert 0 <= harder <= easier <= 1 + 1e-9


@settings(max_examples=20)
@given(key=st.sampled_from(CUBE_KEYS), percent=st.booleans(), low=st.integers(0, 40), step=st.integers(0, 40))
def test_cube_higher_stat_target_is_never_more_likely(key, percent, low, step):
    easier = success_probability(CUBE, stat_sum_at_least(key, percent, low))
    harder = success_probability(CUBE, stat_sum_at_least(key, percent, low + step))
    assert 0 <= harder <= easier <= 1 + 1e-9


@given(p=st.floats(1e-6, 1))
def test_cubes_needed_quantiles_are_ordered(p):
    dist = cubes_needed(p)
    assert dist.mean == pytest.approx(1 / p)
    assert 1 <= dist.median <= dist.p75 <= dist.p90


@given(p=st.floats(1e-4, 1), ceiling=st.integers(1, 200))
def test_tier_up_never_exceeds_ceiling(p, ceiling):
    dist = tier_up_tries(p, ceiling)
    assert 1 <= dist.median <= dist.p75 <= dist.p90 <= ceiling
    assert 1 - 1e-9 <= dist.mean <= min(ceiling, 1 / p) + 1e-9


@settings(max_examples=30)
@given(actions=action_lists(), budget=st.integers(0, 80))
def test_budget_plan_respects_budget_slots_and_optimum(actions, budget):
    plan = greedy(EV, actions, budget * EOK)
    best = brute_force(EV, actions, budget * EOK)
    slots = [a.slot for a in plan.actions]

    assert plan.spent == sum(a.cost for a in plan.actions) <= budget * EOK
    assert len(set(slots)) == len(slots)
    assert all(a in actions for a in plan.actions)
    assert START_INDEX <= plan.index <= best.index * (1 + 1e-9)
    assert plan.gain_pct == pytest.approx((plan.index / START_INDEX - 1) * 100)
