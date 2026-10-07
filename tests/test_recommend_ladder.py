"""매물 검색 추천·로드맵: 공식 확률표 수치로 등급별 단계를 만들고, 지금보다 한 단계 위를 추천한다.

2026-10-04 실사용 피드백: 고점 한 번에 추천 X, 쿨감 줄 유지, 에디 추천, 제네시스 무기는 경매장 대상 아님, 전체 부위 로드맵.
"""
from engine.market.recommend import (cooldown_seconds, line_tables, recommend_searches, roadmap, with_additional,
                                     with_potentials)
from engine.stats.evaluate import Evaluator, rank_settings
from engine.stats.metrics import BossProfile
from engine.stats.sets import SetCatalog
from helpers import bundle
from nexon.convert import snapshot

CAT, BOSS = SetCatalog.load(), BossProfile("기준", 300.0)


def _setup():
    snap = snapshot(bundle("레테"))
    return snap, rank_settings(snap, BOSS, CAT)[0][0]


def _items():
    snap, setting = _setup()
    return snap, Evaluator(snap, setting, BOSS, CAT).base_items()


def _recs(**kw):
    snap, setting = _setup()
    return {(r.slot, r.kind): r for r in recommend_searches(snap, setting, BOSS, CAT, top=60, **kw)}


def _int_sum(lines):
    return sum(float(t.split("+")[1].rstrip("%")) for t in lines if t.startswith("INT +") and t.endswith("%"))


def test_item_keeps_level_and_additional_lines():
    _, items = _items()
    assert items["장갑"].level == 250 and items["상의"].level == 150
    assert items["상의"].additional == ["INT +4%", "마력 +10"]


def test_official_tables_by_grade_part_and_level_band():
    assert "INT +9%" in line_tables("잠재", "유니크", "상의", 150)[0]
    assert "INT +12%" in line_tables("잠재", "레전드리", "모자", 200)[0]
    assert "INT +13%" in line_tables("잠재", "레전드리", "모자", 201)[0]     # 201레벨부터 +1 (공식표 실측)
    assert "INT +6%" in line_tables("에디", "유니크", "모자", 150)[0]
    assert line_tables("잠재", "유니크", "반지4", 130) == line_tables("잠재", "유니크", "반지", 130)
    assert line_tables("잠재", "에픽", "엠블렘", 250) == line_tables("잠재", "에픽", "엠블렘", 200)  # 201+ 구간 없는 부위


def test_identity_when_replacing_with_own_lines():
    snap, items = _items()
    for slot, it in items.items():
        if it.core is None:
            continue
        for same in (with_potentials(it, it.potentials, snap.level), with_additional(it, it.additional, snap.level)):
            assert same.stats == it.stats, slot


def test_next_step_not_the_top():
    recs = _recs()
    top = recs[("상의", "잠재")]
    assert (top.grade, top.lines_good) == ("유니크", 3) and top.delta_pct > 0     # 유니크 2줄 15% → 유니크 3줄
    assert recs[("반지1", "잠재")].grade == "레전드리"


def test_cooldown_lines_are_kept_on_hat():
    hat = _recs()[("모자", "잠재")]
    assert hat.kept == ["스킬 재사용 대기시간 -2초"] and hat.target[0] == "스킬 재사용 대기시간 -2초"


def test_additional_potential_is_recommended():
    recs = _recs()
    assert any(k == "에디" for _, k in recs)
    r = recs[("상의", "에디")]
    assert r.delta_pct > 0 and r.current == ["INT +4%", "마력 +10"]


def test_genesis_weapon_is_cube_route_not_auction():
    recs = _recs()
    assert ("무기", "잠재") not in recs and ("무기", "에디") not in recs
    snap, setting = _setup()
    weapon = roadmap(snap, setting, BOSS, CAT)["무기"]
    assert weapon["route"] == "큐브" and weapon["잠재"]


def test_roadmap_covers_every_slot_with_tiers():
    snap, setting = _setup()
    rm = roadmap(snap, setting, BOSS, CAT)
    assert len(rm) >= 17 and "훈장" not in rm
    tiers = rm["상의"]["잠재"]
    assert [t["grade"] for t in tiers][:2] == ["에픽", "에픽"] and all(0 < t["probability"] <= 1 for t in tiers)
    assert rm["상의"]["next"]["잠재"] == next(i for i, t in enumerate(tiers) if t["delta_pct"] >= 0.1)


def test_cooldown_value_when_user_gives_equivalence():
    snap, setting = _setup()
    plain = _recs()
    valued = _recs(cooldown_main_pct=8.0)
    assert set(plain) == set(valued)
    assert cooldown_seconds(_items()[1]["모자"]) == 2


def test_listing_rows_report_cooldown_not_valued():
    from agent.tools import ToolBox
    hat = {"slot": "모자", "part": "모자", "name": "도전자의 모자", "starforce": 22, "total": {"INT": 100},
           "potentials": ["스킬 재사용 대기시간 -2초", "INT +9%"], "price": 1_000_000_000}
    r = ToolBox(lambda name, date=None: snapshot(bundle("레테"))).run("evaluate_listings", {"name": "x", "listings": [hat]})
    assert r["ranking"][0]["cooldown_s_not_valued"] == 2


def test_roadmap_route_and_tool():
    from agent.tools import TOOL_DEFS, ToolBox
    assert "upgrade_roadmap" in {t["name"] for t in TOOL_DEFS}
    r = ToolBox(lambda name, date=None: snapshot(bundle("레테"))).run("upgrade_roadmap", {"name": "x"})
    weapon = next(s for s in r["slots"] if s["slot"] == "무기")
    assert weapon["route"] == "큐브" and r["evaluation_setting"]["equipment"] == 2
    cards = ToolBox(lambda name, date=None: snapshot(bundle("레테"))).run("recommend_searches", {"name": "x", "top": 40})
    assert all(c["slot"] != "무기" for c in cards["recommendations"])
    assert {c["kind"] for c in cards["recommendations"]} == {"잠재", "에디"}


def test_astra_secondary_is_cube_route_not_auction():
    """아스트라 보조무기(2026-01 출시)는 교환 불가 — 경매장 검색 추천에서 빼고 로드맵은 '큐브' 경로(2026-10-07 사용자 지적)."""
    import dataclasses
    snap, setting = _setup()
    for slots in snap.equipment_presets.values():
        if "보조무기" in slots:
            slots["보조무기"] = dataclasses.replace(slots["보조무기"], name="아스트라 아케인 실드")
    recs = {(r.slot, r.kind) for r in recommend_searches(snap, setting, BOSS, CAT, top=60)}
    assert ("보조무기", "잠재") not in recs and ("보조무기", "에디") not in recs
    assert roadmap(snap, setting, BOSS, CAT)["보조무기"]["route"] == "큐브"
