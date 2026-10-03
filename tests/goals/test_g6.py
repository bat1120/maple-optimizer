"""G6 판정 — GOALS.md G6 성공 기준."""
import json
import pathlib

from engine.enhance.history import meso_spent
from engine.enhance.starforce import StarforceConditions
from engine.market.craft import CraftPlan, price_percentile, simulate_craft
from nexon.convert import cube_attempts

ROOT = pathlib.Path(__file__).resolve().parents[2]
RESULTS = ROOT / "goals" / "results" / "G6.json"
HIST = ROOT / "tests" / "fixtures" / "history"
_m: dict = {}


def _record(k, v):
    _m[k] = v
    RESULTS.write_text(json.dumps(_m, ensure_ascii=False, indent=1), encoding="utf-8")


def test_criterion1_price_percentile_matches_monte_carlo_within_1pp():
    plan = CraftPlan(base_price=2_000_000_000, level=200, start_star=0, target_star=22, destroy_cost=3_000_000_000,
                     cond=StarforceConditions(), cube_p=0.027650, cube_cost=45_000_000)
    empirical = sorted(simulate_craft(plan, trials=100_000, seed=777))
    out = {}
    for price in (15_000_000_000, 20_000_000_000, 30_000_000_000, 50_000_000_000):
        semi = price_percentile(plan, price, samples=20_000, seed=20261003)
        emp = sum(1 for c in empirical if c <= price) / len(empirical)
        out[str(price)] = {"semi_analytic": semi, "empirical": emp, "abs_diff_pp": abs(semi - emp) * 100}
    _record("criterion1", out)
    for r in out.values():
        assert r["abs_diff_pp"] <= 1.0, r


def test_criterion2_actual_spend_equals_hand_sum():
    pot = json.loads((HIST / "history_potential.json").read_text(encoding="utf-8"))
    cube = json.loads((HIST / "history_cube.json").read_text(encoding="utf-8"))
    attempts = cube_attempts(pot, cube)
    spent = meso_spent(attempts)
    # 수작업: 잠재능력 재설정 기록마다 레벨 구간·등급 가격(200~249 레전드리 4,500만)을 직접 더한다
    price = {("레전드리", 200): 45_000_000, ("유니크", 200): 38_250_000, ("에픽", 200): 18_000_000, ("레어", 200): 4_500_000}
    hand = sum(price[(r["potential_option_grade"], 200 if 200 <= r["item_level"] < 250 else -1)]
               for r in pot if r["potential_type"] == "잠재능력 재설정")
    _record("criterion2", {"engine": spent.meso, "hand": hand, "counted": spent.counted, "uncounted": spent.uncounted})
    assert spent.meso == hand and spent.counted == sum(1 for r in pot if r["potential_type"] == "잠재능력 재설정")
    assert spent.uncounted == len(cube)
