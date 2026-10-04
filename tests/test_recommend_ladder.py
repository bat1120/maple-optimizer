"""매물 검색 추천: 한 번에 고점이 아니라 '지금보다 한 단계 위'를, 쿨감 줄은 버리지 않는다 (2026-10-04 실사용 피드백)."""
from engine.market.recommend import cooldown_seconds, ladder, recommend_searches, with_potentials
from engine.stats.evaluate import Evaluator, rank_settings
from engine.stats.metrics import BossProfile
from engine.stats.sets import SetCatalog
from helpers import bundle
from nexon.convert import snapshot

CAT, BOSS = SetCatalog.load(), BossProfile("기준", 300.0)


def _setup():
    snap = snapshot(bundle("레테"))
    return snap, rank_settings(snap, BOSS, CAT)[0][0]


def _by_slot(**kw):
    snap, setting = _setup()
    return {r.slot: r for r in recommend_searches(snap, setting, BOSS, CAT, top=30, **kw)}


def _int_sum(lines):
    return sum(float(t.split("+")[1].rstrip("%")) for t in lines if t.startswith("INT +"))


def test_item_level_is_kept_from_api():
    snap, setting = _setup()
    items = Evaluator(snap, setting, BOSS, CAT).base_items()
    assert items["장갑"].level == 250 and items["상의"].level == 150


def test_ladder_uses_official_line_values_by_item_level():
    assert ladder("상의", "INT", "MATK", 150)[0] == [["INT +9%", "INT +6%"]]
    assert ["INT +13%", "INT +10%", "INT +10%"] in ladder("모자", "INT", "MATK", 250)[2]
    assert ladder("무기", "INT", "MATK", 200)[0] == [["마력 +12%", "마력 +9%"]]


def test_recommends_next_step_not_the_top():
    recs = _by_slot()
    assert _int_sum(recs["상의"].target_potentials) == 21          # 지금 9+6=15 → 유니크 3줄 21, 레전 30으로 건너뛰지 않음
    assert recs["상의"].step == 2
    assert _int_sum(recs["반지1"].target_potentials) == 30         # 지금 12+9=21 → 레전 3줄 30


def test_cooldown_lines_are_kept_on_hat():
    recs = _by_slot()
    hat = recs["모자"]
    assert "스킬 재사용 대기시간 -2초" in hat.target_potentials and len(hat.target_potentials) == 3
    assert hat.kept == ["스킬 재사용 대기시간 -2초"]


def test_cooldown_seconds_reads_lines():
    snap, setting = _setup()
    hat = Evaluator(snap, setting, BOSS, CAT).base_items()["모자"]
    assert cooldown_seconds(hat) == 2
    assert cooldown_seconds(with_potentials(hat, ["INT +9%"], snap.level)) == 0


def test_cooldown_value_when_user_gives_equivalence():
    """쿨감 1초 = 주스탯 N%를 사용자가 정하면 쿨감도 실딜에 넣는다. 쿨감을 버리는 교체는 그만큼 손해로 계산된다."""
    snap, setting = _setup()
    ev = Evaluator(snap, setting, BOSS, CAT)
    items = ev.base_items()
    hat = items["모자"]
    plain = recommend_searches(snap, setting, BOSS, CAT, top=30)
    valued = recommend_searches(snap, setting, BOSS, CAT, top=30, cooldown_main_pct=8.0)
    assert {r.slot for r in plain} == {r.slot for r in valued}            # 쿨감 줄을 유지하므로 추천 부위는 같다
    # 수작업: 모자에 INT +16%(2초×8%)를 더한 세트를 기준·후보 양쪽에 똑같이 준다
    from engine.options import StatLine
    def cd(it):
        it = with_potentials(it, it.potentials, snap.level)
        it.stats.add(StatLine("INT", cooldown_seconds(it) * 8.0, True))
        return it
    r = next(x for x in valued if x.slot == "모자")
    base = dict(items); base["모자"] = cd(hat)
    trial = dict(items); trial["모자"] = cd(with_potentials(hat, r.target_potentials, snap.level))
    assert abs((ev.index(trial) / ev.index(base) - 1) * 100 - r.delta_pct) < 1e-9


def test_listing_rows_report_cooldown_not_valued():
    from agent.tools import ToolBox
    hat = {"slot": "모자", "part": "모자", "name": "도전자의 모자", "starforce": 22, "total": {"INT": 100},
           "potentials": ["스킬 재사용 대기시간 -2초", "INT +9%"], "price": 1_000_000_000}
    r = ToolBox(lambda name, date=None: snapshot(bundle("레테"))).run("evaluate_listings", {"name": "x", "listings": [hat]})
    assert r["ranking"][0]["cooldown_s_not_valued"] == 2


def test_recommend_tool_passes_cooldown_equivalence():
    from agent.tools import ToolBox
    box = ToolBox(lambda name, date=None: snapshot(bundle("레테")))
    r = box.run("recommend_searches", {"name": "x", "top": 30, "cooldown_main_pct": 8})
    hat = next(c for c in r["recommendations"] if c["slot"] == "모자")
    assert r["cooldown_main_pct"] == 8 and hat["kept"] == ["스킬 재사용 대기시간 -2초"] and hat["step"] >= 1
    assert "쿨감 1초를 주스탯 8%로 환산" in r["note"]
