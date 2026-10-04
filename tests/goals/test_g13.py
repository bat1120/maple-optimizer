"""G13 판정 — 매물 검색 추천."""
import json
import pathlib
import subprocess

import pytest

from agent.tools import TOOL_DEFS, ToolBox
from engine.market.recommend import SKIP_SLOTS, SWAP, recommend_searches, with_potentials
from engine.stats.evaluate import evaluate_setting, rank_settings, swap_item
from engine.stats.metrics import BossProfile
from engine.stats.residual import preset_items
from engine.stats.sets import SetCatalog
from helpers import bundle
from nexon.convert import snapshot

ROOT = pathlib.Path(__file__).resolve().parents[2]
RESULTS = ROOT / "goals" / "results" / "G13.json"
REPORT = ROOT / "goals" / "results" / "G13-vitest.json"
CAT, BOSS = SetCatalog.load(), BossProfile("기준", 300.0)
_m: dict = {}


def _record(k, v):
    _m[k] = v
    RESULTS.write_text(json.dumps(_m, ensure_ascii=False, indent=1), encoding="utf-8")


def _setup():
    snap = snapshot(bundle("레테"))
    return snap, rank_settings(snap, BOSS, CAT)[0][0]


def test_criterion1_recommendations_positive_sorted_and_match_hand_swap():
    snap, setting = _setup()
    recs = recommend_searches(snap, setting, BOSS, CAT, top=8)
    base = evaluate_setting(snap, setting, BOSS, CAT)
    items = preset_items(snap, setting.equipment)
    worst = 0.0
    for r in recs:
        target = SWAP[r.kind](items[r.slot], r.target, snap.level)
        hand = (swap_item(snap, setting, r.slot, target, BOSS, CAT) / base - 1) * 100
        worst = max(worst, abs(hand - r.delta_pct))
    deltas = [r.delta_pct for r in recs]
    _record("criterion1", {"slots": [r.slot for r in recs], "deltas": deltas, "worst_abs_diff": worst})
    assert recs and all(d > 0 for d in deltas) and deltas == sorted(deltas, reverse=True)
    assert worst < 1e-9


def test_criterion2_replacing_with_own_potentials_is_identity():
    snap, setting = _setup()
    for slot, it in preset_items(snap, setting.equipment).items():
        same = with_potentials(it, it.potentials, snap.level)
        assert same.stats.flat == pytest.approx(it.stats.flat) and same.stats.pct == pytest.approx(it.stats.pct), slot
        assert (same.stats.boss, same.stats.dmg, same.stats.cd, sorted(same.stats.ied)) == \
               (it.stats.boss, it.stats.dmg, it.stats.cd, sorted(it.stats.ied)), slot
    _record("criterion2", "identity ok")


def test_criterion3_slots_without_potential_are_skipped():
    snap, setting = _setup()
    recs = recommend_searches(snap, setting, BOSS, CAT, top=30)
    _record("criterion3", sorted({r.slot for r in recs} & set(SKIP_SLOTS)))
    assert not ({r.slot for r in recs} & set(SKIP_SLOTS))


def test_criterion4_agent_tool_returns_cards():
    assert "recommend_searches" in {t["name"] for t in TOOL_DEFS}
    out = ToolBox(lambda name, date=None: snapshot(bundle("레테"))).run("recommend_searches", {"name": "x", "top": 3})
    _record("criterion4", out["recommendations"][:1])
    assert len(out["recommendations"]) == 3
    card = out["recommendations"][0]
    assert {"slot", "category", "search", "delta_pct", "current"} <= set(card)
    assert out["evaluation_setting"]["equipment"] == 2


def test_criterion5_web_recommend_panel():
    subprocess.run(["npm", "--prefix", "web", "test", "--", "--reporter=json", f"--outputFile={REPORT}"],
                   cwd=ROOT, capture_output=True, shell=True)
    data = json.loads(REPORT.read_text(encoding="utf-8"))
    results = [a for f in data["testResults"] for a in f["assertionResults"] if "recommend panel" in a["fullName"]]
    _record("criterion5", {r["title"]: r["status"] for r in results})
    assert results and all(r["status"] == "passed" for r in results)
