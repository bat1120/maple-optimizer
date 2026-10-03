"""G7 판정 — GOALS.md G7 성공 기준."""
import copy
import json
import pathlib
import random
import statistics

from engine.optimize.budget import Action, brute_force, greedy
from engine.stats.evaluate import Evaluator
from engine.stats.metrics import BossProfile
from engine.stats.sets import SetCatalog
from engine.stats.snapshot import Setting
from helpers import bundle
from nexon.convert import snapshot

RESULTS = pathlib.Path(__file__).resolve().parents[2] / "goals" / "results" / "G7.json"
SLOTS = ["반지1", "반지2", "펜던트", "귀고리", "벨트", "모자"]


def instance(ev, rng):
    """현재 템을 조금씩 강하게 바꾼 후보 ≤ 10개, 무작위 비용. 부위가 겹치는 후보가 섞인다."""
    base = ev.base_items()
    actions = []
    for i in range(rng.randint(6, 10)):
        slot = rng.choice(SLOTS)
        it = copy.deepcopy(base[slot])
        it.stats.pct["INT"] = it.stats.pct.get("INT", 0) + rng.choice([3, 6, 9, 12, 21])
        it.stats.boss += rng.choice([0, 0, 10, 20])
        it.stats.flat["MATK"] = it.stats.flat.get("MATK", 0) + rng.choice([0, 5, 10])
        actions.append(Action(slot, it, rng.randint(5, 60) * 100_000_000, f"후보{i}"))
    budget = rng.randint(30, 150) * 100_000_000
    return actions, budget


def test_g7_greedy_vs_brute_force_on_30_seeded_instances():
    snap = snapshot(bundle("레테"))
    ev = Evaluator(snap, Setting(2, 3, 2), BossProfile("기준", 300.0), SetCatalog.load())
    base_index = ev.index(ev.base_items())
    ratios, slot_violations, over_budget = [], 0, 0
    for seed in range(30):
        actions, budget = instance(ev, random.Random(seed))
        g, b = greedy(ev, actions, budget), brute_force(ev, actions, budget)
        for plan in (g, b):
            slots = [a.slot for a in plan.actions]
            slot_violations += len(slots) - len(set(slots))
            over_budget += plan.spent > budget
        gain_g, gain_b = g.index - base_index, b.index - base_index
        ratios.append(1.0 if gain_b <= 0 else gain_g / gain_b)
    out = {"mean_ratio": statistics.mean(ratios), "min_ratio": min(ratios), "slot_violations": slot_violations,
           "over_budget": over_budget, "ratios": ratios}
    RESULTS.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    assert out["mean_ratio"] >= 0.95 and out["min_ratio"] >= 0.85
    assert slot_violations == 0 and over_budget == 0
