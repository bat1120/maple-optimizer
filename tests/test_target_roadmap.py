"""목표 배율 로드맵(2026-10-09): 지금 보스 배율(예: MapleScouter 익스트림 스우 34.52%)에서 목표(50%)까지,
억당 효율 순으로 업그레이드를 쌓는다. 스타포스는 같은 부위를 한 성씩 이어서 올린다."""
import pytest

from engine.market.events import Events
from engine.market.target_roadmap import target_roadmap
from engine.stats.evaluate import rank_settings
from engine.stats.metrics import BossProfile
from engine.stats.sets import SetCatalog
from helpers import bundle
from nexon.convert import snapshot

CAT, BOSS = SetCatalog.load(), BossProfile("기준", 300.0)


def _run(current=34.52, target=50.0, **kw):
    snap = snapshot(bundle("레테"))
    setting = rank_settings(snap, BOSS, CAT)[0][0]
    return snap, target_roadmap(snap, setting, BOSS, CAT, Events(**kw), [], current, target)


def test_steps_are_ordered_and_cumulative_ratio_grows():
    _, r = _run(target=40.0)
    steps = r["steps"]
    assert steps and r["needed_multiplier"] == pytest.approx(40.0 / 34.52)
    ratios = [s["ratio_after"] for s in steps]
    assert ratios == sorted(ratios) and ratios[0] > 34.52
    costs = [s["total_cost"] for s in steps]
    assert costs == sorted(costs)
    assert r["reached"] == (ratios[-1] >= 40.0)


def test_starforce_chains_one_star_at_a_time_on_same_slot():
    _, r = _run(target=80.0)
    sf = [s for s in r["steps"] if s["path"] == "스타포스"]
    by_slot = {}
    for s in sf:
        by_slot.setdefault(s["slot"], []).append((s["from_star"], s["to_star"]))
    for slot, seq in by_slot.items():
        assert all(b == a + 1 for a, b in seq), (slot, seq)          # 한 성씩
        assert all(seq[i][1] == seq[i + 1][0] for i in range(len(seq) - 1)), (slot, seq)  # 이어서


def test_each_cube_slot_kind_used_at_most_once():
    _, r = _run(target=80.0)
    keys = [(s["slot"], s.get("kind")) for s in r["steps"] if s["path"] == "큐브"]
    assert len(keys) == len(set(keys))


def test_already_reached_returns_no_steps():
    _, r = _run(current=60.0, target=50.0)
    assert r["steps"] == [] and r["reached"] is True


def test_scouter_payload_combines_equipment_changes():
    from server.service import target_roadmap as service_target
    snap = snapshot(bundle("레테"))
    out = service_target(snap, 300.0, [], current_ratio=34.52, target_ratio=40.0)
    p = out["scouter"]
    assert p and "name" in p and p["job"] == "레테" and p["fields"]  # 픽스처는 이름을 지운 데이터
    assert p["slot"] == "로드맵" and any(v for v in p["fields"].values())
    assert out["equipment_steps"] >= 1


def test_api_and_agent_tool(tmp_path):
    from fastapi.testclient import TestClient
    from agent.tools import TOOL_DEFS, ToolBox
    from server.app import create_app
    c = TestClient(create_app(lambda n, d: bundle("레테"), str(tmp_path / "c.sqlite3")))
    r = c.get("/api/character/x/target-roadmap?current_ratio=34.52&target_ratio=40").json()
    assert r["steps"] and r["steps"][0]["cost_text"] and r["scouter"]["fields"]
    assert c.get("/api/character/x/target-roadmap?current_ratio=0").status_code == 400
    assert "target_roadmap" in {t["name"] for t in TOOL_DEFS}
    box = ToolBox(lambda name, date=None: snapshot(bundle("레테")))
    out = box.run("target_roadmap", {"name": "x", "current_ratio": 34.52, "target_ratio": 40})
    assert out["steps"] and "scouter" not in out


def test_crit_rate_below_100_lowers_index():
    """2026-10-09 실사이트: 로드맵이 크확 줄을 빼 크확 94%가 됐는데(MapleScouter '크확 100%미만!!') 엔진은 크확 100% 고정이었다."""
    from types import SimpleNamespace
    from engine.stats import metrics
    job = SimpleNamespace(mains=("STR",), subs=("DEX",), attack="ATK")
    orig = metrics.stat_attack
    metrics.stat_attack = lambda pred, job, part: 1.0
    try:
        mk = lambda cr: SimpleNamespace(dmg=0.0, boss=0.0, cd=50.0, cr=cr, ied=0.0)  # noqa: E731
        full, over, low = (metrics.boss_index(mk(0.0), job, "x", BossProfile("b", 0.0), crit_rate=c) for c in (100.0, 120.0, 94.0))
        default = metrics.boss_index(mk(69.0), job, "x", BossProfile("b", 0.0))  # 스탯창 크확(렌 69%)은 쓰지 않는다
    finally:
        metrics.stat_attack = orig
    assert full == pytest.approx(1.85) and over == full and default == full  # 100% 이상·기본값은 같다
    assert low == pytest.approx(1 + 0.94 * 0.85) and low < full    # 100% 밑은 치명타가 덜 터진다


def test_removing_crit_rate_line_now_costs_damage():
    """엠블렘 에디 '크리티컬 확률 +3%' 줄만 빼면 실딜이 줄어야 한다(예전엔 크확 100% 고정이라 0)."""
    from engine.market.recommend import _Planner, with_additional
    snap = snapshot(bundle("레테"))
    setting = rank_settings(snap, BOSS, CAT)[0][0]
    pl = _Planner(snap, setting, BOSS, CAT, None)
    em = pl.raw["엠블렘"]
    assert "크리티컬 확률 +3%" in em.additional
    lines = [x for x in em.additional if x != "크리티컬 확률 +3%"]
    assert pl.ev.index({**pl.items, "엠블렘": with_additional(em, lines, snap.level)}) < pl.base


def test_roadmap_keeps_crit_rate_by_default():
    """MapleScouter는 크확 100% 미만이면 결과를 안 보여 준다 — 기본 로드맵은 크확을 깎는 큐브를 고르지 않는다."""
    from server.service import target_roadmap as service_target
    out = service_target(snapshot(bundle("레테")), 300.0, [], current_ratio=34.52, target_ratio=50.0)
    assert out["scouter"]["fields"]["크리티컬 확률"] >= 0
    snap = snapshot(bundle("레테"))
    setting = rank_settings(snap, BOSS, CAT)[0][0]
    free = target_roadmap(snap, setting, BOSS, CAT, Events(), [], 34.52, 50.0, keep_crit=False)
    assert any(s["slot"] == "엠블렘" and s["path"] == "큐브" for s in free["steps"])  # 끄면 크확을 내주는 교환도 고른다
