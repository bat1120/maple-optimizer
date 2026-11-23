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


def test_crit_loss_counts_only_below_100_percent():
    """스탯창 크확(직업 스킬 크확이 빠진 값)이 100%를 넘으면 그 여유만큼은 줄어도 손해가 아니다(2026-10-17 점검:
    레테 보스 세팅 예측 크확 103%인데 '크리티컬 확률 +3%' 줄을 빼면 -1.65%로 잡았다). 여유보다 더 줄면 손해."""
    import copy
    import dataclasses
    from engine.market.recommend import _Planner, with_additional
    snap = snapshot(bundle("레테"))
    setting = rank_settings(snap, BOSS, CAT)[0][0]
    pl = _Planner(snap, setting, BOSS, CAT, None)
    em = pl.raw["엠블렘"]
    assert "크리티컬 확률 +3%" in em.additional
    lines = [x for x in em.additional if x != "크리티컬 확률 +3%"]
    no_crit_line = pl.ev.index({**pl.items, "엠블렘": with_additional(em, lines, snap.level)})
    without_line_and_other = with_additional(em, lines, snap.level)
    # 크확이 여유(3%)보다 많이 줄면 손해
    stats = copy.deepcopy(without_line_and_other.stats)
    stats.cr -= 10
    much_less = pl.ev.index({**pl.items, "엠블렘": dataclasses.replace(without_line_and_other, stats=stats)})
    assert much_less < no_crit_line
    # 크확 3% 줄만 빼면(여유 안) 남은 줄 차이만 남는다 — 크확 손해로 줄지 않는다
    stats0 = copy.deepcopy(em.stats)
    stats0.cr -= 3
    same_lines_less_crit = pl.ev.index({**pl.items, "엠블렘": dataclasses.replace(em, stats=stats0)})
    assert same_lines_less_crit == pytest.approx(pl.base)


def test_roadmap_keeps_crit_rate_by_default():
    """MapleScouter는 크확 100% 미만이면 결과를 안 보여 준다 — 기본 로드맵은 크확을 깎는 큐브를 고르지 않는다."""
    from server.service import target_roadmap as service_target
    out = service_target(snapshot(bundle("레테")), 300.0, [], current_ratio=34.52, target_ratio=50.0)
    assert out["scouter"]["fields"]["크리티컬 확률"] >= 0
    snap = snapshot(bundle("레테"))
    setting = rank_settings(snap, BOSS, CAT)[0][0]
    free = target_roadmap(snap, setting, BOSS, CAT, Events(), [], 34.52, 50.0, keep_crit=False)
    assert any(s["slot"] == "엠블렘" and s["path"] == "큐브" for s in free["steps"])  # 끄면 크확을 내주는 교환도 고른다


def test_budget_mode_fills_the_budget_and_skips_what_it_cannot_afford():
    """2026-11-23: 예산 모드 — 남은 돈으로 못 사는 단계는 건너뛰고 그다음 효율 단계로 채운다. 예산을 넘지 않는다."""
    snap = snapshot(bundle("레테"))
    setting = rank_settings(snap, BOSS, CAT)[0][0]
    budget = 5_000_000_000
    r = target_roadmap(snap, setting, BOSS, CAT, Events(), [], 100.0, 1e9, budget=budget, flames=True)
    assert r["steps"] and r["total_cost"] <= budget
    skipped = r["skipped_first"]
    assert skipped and skipped["cost"] > budget - r["steps"][-1]["total_cost"]
    # 건너뛴 뒤에도 더 싼 단계를 이어서 쌓았다(앞에서 자르기만 하면 34억대에서 멈춘다)
    assert any(s["per_100m"] < skipped["per_100m"] for s in r["steps"])
    mults = [s["multiplier"] for s in r["steps"]]
    assert mults == sorted(mults) and mults[0] > 1


def test_flames_join_only_when_asked_and_target_mode_is_unchanged():
    snap = snapshot(bundle("레테"))
    setting = rank_settings(snap, BOSS, CAT)[0][0]
    plain = target_roadmap(snap, setting, BOSS, CAT, Events(), [], 34.52, 36.0)
    assert "추옵" not in {s["path"] for s in plain["steps"]} and plain["skipped_first"] is None
    with_flames = target_roadmap(snap, setting, BOSS, CAT, Events(), [], 100.0, 1e9, budget=5_000_000_000, flames=True)
    flame_slots = [s["slot"] for s in with_flames["steps"] if s["path"] == "추옵"]
    assert flame_slots and len(flame_slots) == len(set(flame_slots))  # 부위마다 한 번


def test_budget_roadmap_route_answers_how_far_the_budget_goes(tmp_path):
    """화면의 '내 예산' 칸이 부르는 API(2026-11-23) — AI 도구와 같은 계산."""
    from fastapi.testclient import TestClient
    from server.app import create_app
    c = TestClient(create_app(lambda n, d: bundle("레테"), str(tmp_path / "c.sqlite3")))
    r = c.get("/api/character/레테/budget-roadmap", params={"budget": 5_000_000_000})
    assert r.status_code == 200
    body = r.json()
    assert body["budget_text"] == "50억" and body["steps"] and body["gain_pct"] > 0
    assert body["spent_text"] == body["steps"][-1]["total_cost_text"]
    assert c.get("/api/character/레테/budget-roadmap", params={"budget": 50}).status_code == 400


def test_plan_without_budget_lists_the_first_steps_and_marks_buyable_cube_steps(tmp_path):
    """2026-11-23 사용자: 계획 하나로 합친다 — 메소를 안 넣어도 효율 순서 앞 단계가 나오고, 큐브 단계는 경매장에서 살 수 있는지 알려 준다."""
    from fastapi.testclient import TestClient
    from server import service
    from server.app import create_app
    c = TestClient(create_app(lambda n, d: bundle("레테"), str(tmp_path / "c.sqlite3")))
    body = c.get("/api/character/레테/budget-roadmap").json()
    assert body["budget"] is None and body["budget_text"] is None and body["left_text"] is None
    assert len(body["steps"]) == service.PLAN_STEPS
    eff = [s["per_100m"] for s in body["steps"]]
    assert eff[0] == max(eff)
    cube = [s for s in body["steps"] if s["path"] == "큐브"]
    assert cube and all(s["route"] in ("경매장", "큐브") and s["target"] and s["lines_good"] for s in cube)
    assert len(c.get("/api/character/레테/budget-roadmap", params={"steps": 1}).json()["steps"]) == 1
    assert c.get("/api/character/레테/budget-roadmap", params={"steps": 0}).status_code == 400
