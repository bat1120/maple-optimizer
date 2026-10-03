"""G5 판정 — GOALS.md G5 성공 기준."""
import json
import pathlib

from engine.enhance.cube import CubeTable, lines_at_least, simulate_success_rate, success_probability, \
    stat_sum_at_least
from engine.enhance.starforce import StarforceConditions, expected_cost, simulate

ROOT = pathlib.Path(__file__).resolve().parents[2]
RESULTS = ROOT / "goals" / "results" / "G5.json"
_m: dict = {}
CONDITIONS = {
    "기본(완전 복구)": StarforceConditions(),
    "30%할인+파괴방지": StarforceConditions(discount30=True, protect=True),
    "파괴30%감소+5·10·15성100%": StarforceConditions(destroy_down30=True, guarantee_5_10_15=True),
    "기본 복구(12성)": StarforceConditions(restore="basic"),
}


def _record(k, v):
    _m[k] = v
    RESULTS.write_text(json.dumps(_m, ensure_ascii=False, indent=1), encoding="utf-8")


def test_criterion1_starforce_exact_vs_monte_carlo_within_1pct():
    out = {}
    for name, cond in CONDITIONS.items():
        exact = expected_cost(200, 0, 22, destroy_cost=3_000_000_000, cond=cond)
        mc = simulate(200, 0, 22, destroy_cost=3_000_000_000, cond=cond, trials=100_000, seed=20261003)
        out[name] = {"exact_mean": exact, "mc_mean": mc.mean, "mc_median": mc.median, "mc_p75": mc.p75,
                     "mc_p90": mc.p90, "rel_diff": abs(mc.mean / exact - 1)}
    _record("criterion1", out)
    assert len(out) >= 3
    for name, r in out.items():
        assert r["rel_diff"] <= 0.01, (name, r)


def test_criterion2_cube_exact_vs_monte_carlo_within_1pp():
    t = CubeTable.load("레전드리/무기/200")
    targets = {
        "보공 2줄 이상": lines_at_least("BOSS", 2),
        "마력% 합 ≥ 21": stat_sum_at_least("MATK", True, 21),
        "방무 1줄 이상 + 보공 1줄 이상": lambda lines: lines_at_least("IED", 1)(lines) and lines_at_least("BOSS", 1)(lines),
    }
    out = {}
    for name, pred in targets.items():
        exact = success_probability(t, pred)
        mc = simulate_success_rate(t, pred, trials=100_000, seed=20261003)
        out[name] = {"exact": exact, "mc": mc, "abs_diff_pp": abs(mc - exact) * 100}
    _record("criterion2", out)
    for name, r in out.items():
        assert r["abs_diff_pp"] <= 1.0, (name, r)


def test_criterion3_tables_have_source_and_date():
    for f in ("starforce.json", "cube_black.json", "set_items.json", "set_tiers.json"):
        d = json.loads((ROOT / "engine" / "data" / f).read_text(encoding="utf-8"))
        src = d.get("_source")
        assert src and (isinstance(src, str) or all(isinstance(s, str) for s in src)), f
        assert d.get("_as_of") or d.get("_collected"), f
        if f in ("starforce.json", "cube_black.json"):
            assert any("http" in s for s in (src if isinstance(src, list) else [src])), f
