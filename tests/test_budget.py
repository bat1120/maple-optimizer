import copy

import pytest

from engine.optimize.budget import Action, brute_force, greedy
from engine.stats.evaluate import Evaluator, evaluate_setting
from engine.stats.metrics import BossProfile
from engine.stats.sets import SetCatalog
from engine.stats.snapshot import Setting
from helpers import bundle
from nexon.convert import snapshot

CAT = SetCatalog.load()
BOSS = BossProfile("기준", 300.0)
SNAP = snapshot(bundle("레테"))
EV = Evaluator(SNAP, Setting(2, 3, 2), BOSS, CAT)


def better(slot, int_pct=10, cost=10 * 10**8, label="x"):
    it = copy.deepcopy(EV.base_items()[slot])
    it.stats.pct["INT"] = it.stats.pct.get("INT", 0) + int_pct
    return Action(slot, it, cost, label)


def test_evaluator_matches_evaluate_setting():
    assert EV.index(EV.base_items()) == pytest.approx(evaluate_setting(SNAP, Setting(2, 3, 2), BOSS, CAT))


def test_greedy_respects_budget_and_slots():
    acts = [better("반지1", 10, 30 * 10**8, "a"), better("반지1", 12, 31 * 10**8, "b"), better("펜던트", 5, 10 * 10**8, "c")]
    plan = greedy(EV, acts, 45 * 10**8)
    assert plan.spent <= 45 * 10**8
    assert len({a.slot for a in plan.actions}) == len(plan.actions)
    assert plan.gain_pct > 0


def test_empty_budget_gives_empty_plan():
    plan = greedy(EV, [better("반지1")], 0)
    assert plan.actions == [] and plan.gain_pct == 0


def test_brute_force_is_optimal_on_tiny_case():
    # 비싼 하나(+12%) vs 싼 둘(+7% ×2, 다른 부위): 예산이 둘 다 살 수 있으면 둘이 낫다
    acts = [better("반지1", 12, 20 * 10**8, "big"), better("반지2", 7, 10 * 10**8, "s1"), better("펜던트", 7, 10 * 10**8, "s2")]
    plan = brute_force(EV, acts, 20 * 10**8)
    assert sorted(a.label for a in plan.actions) == ["s1", "s2"]


def test_negative_actions_are_never_chosen():
    worse = better("반지1", -20, 1 * 10**8, "worse")
    assert greedy(EV, [worse], 10**10).actions == []
    assert brute_force(EV, [worse], 10**10).actions == []


def test_greedy_does_not_let_a_cheap_efficient_item_block_a_much_stronger_one():
    # 같은 부위: 싼 +3%(효율 최고) vs 예산 안의 비싼 +21%. 순수 효율 탐욕법은 싼 것을 먼저 집어 부위를 막는다.
    acts = [better("반지1", 3, 1 * 10**8, "cheap"), better("반지1", 21, 30 * 10**8, "strong")]
    plan = greedy(EV, acts, 30 * 10**8)
    assert [a.label for a in plan.actions] == ["strong"]
