"""목표 배율 로드맵이 보고하는 배율 = 고른 변경을 처음 상태에 다시 적용해서 잰 값(2026-10-17 점검: 큐브 실딜을 처음 상태로
고정해 곱해 '도달'을 거짓으로 보였다 — 레테 34.52→50% 보고 50.24%, 다시 재면 48.19%). 고른 단계는 그 시점에 실딜이 오른다."""
import pytest

from helpers import bundle
from engine.market.events import Events
from engine.market.recommend import _Planner, _valued
from engine.market.symbol_paths import extra_of, step as symbol_step
from engine.market.target_roadmap import target_roadmap
from engine.stats.evaluate import rank_settings
from engine.stats.metrics import BossProfile
from engine.stats.sets import SetCatalog
from nexon.convert import snapshot

CAT, BOSS = SetCatalog.load(), BossProfile("기준", 300.0)


def _replay(snap, setting, out):
    pl = _Planner(snap, setting, BOSS, CAT, None)
    items = {**pl.raw, **out["changed"]}
    stat, force = {}, {}
    for sym in snap.symbol_items:
        to = out["symbols"].get(sym["name"])
        if to:
            st = symbol_step(sym, sym["level"], to, snap.character_class)
            for k, v in st["stat_gain"].items():
                stat[k] = stat.get(k, 0.0) + v
            for k, v in st["force_gain"].items():
                force[k] = force.get(k, 0) + v
    val = lambda its: {s: _valued(it, pl.mains, pl.per_sec) for s, it in its.items()}
    return pl.ev.index(val(items), extra_of(stat, force)) / pl.ev.index(val(pl.raw), extra_of({}, {}))


@pytest.mark.parametrize("target", [50.0, 80.0])
def test_reported_ratio_matches_replay_and_every_step_helps(target):
    snap = snapshot(bundle("레테"))
    setting = rank_settings(snap, BOSS, CAT)[0][0]
    out = target_roadmap(snap, setting, BOSS, CAT, Events(), [], 34.52, target)
    assert out["steps"]
    assert out["final_ratio"] == pytest.approx(34.52 * _replay(snap, setting, out), rel=1e-6)
    assert all(s["delta_pct"] > 0 for s in out["steps"])
    assert out["reached"] == (out["final_ratio"] >= target)
