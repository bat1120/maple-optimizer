"""업그레이드 경로 비교: 구매(관측 매물) · 직작(관측 매물 + 큐브) · 지금 템 큐브를 억당 실딜로 한 줄에 세운다.
세트 효과는 교체한 템 이름으로 세트 개수를 다시 세서 실딜에 들어가고, 바뀐 세트는 따로 보여 준다."""
import pytest

from engine.market.cube_value import expected_cost
from engine.market.listing import item_from_input
from engine.market.paths import upgrade_paths
from engine.market.recommend import MIN_GAIN, roadmap
from engine.stats.evaluate import Evaluator, rank_settings
from engine.stats.metrics import BossProfile
from engine.stats.sets import SetCatalog
from helpers import bundle
from nexon.convert import snapshot
from server.market import PriceStore
from server.vision import _SCHEMA

CAT, BOSS = SetCatalog.load(), BossProfile("기준", 300.0)

ROBE = {"category": "상의", "part": "상의", "name": "에테르넬 메이지로브", "starforce": 22, "level": 250,
        "potential_grade": "유니크", "additional_grade": "레어",
        "total": {"INT": 520, "LUK": 330, "MATK": 220}, "potential_lines": ["INT +13%", "INT +10%", "INT +10%"],
        "additional": ["마력 +12"], "price": 20_000_000_000, "seen_at": 1.0}
BASE = {**ROBE, "potential_lines": ["최대 HP +7%"], "additional": [], "potential_grade": "유니크",
        "additional_grade": None, "price": 12_000_000_000}


def _setup():
    snap = snapshot(bundle("레테"))
    return snap, rank_settings(snap, BOSS, CAT)[0][0]


def _paths(observed):
    snap, setting = _setup()
    return snap, setting, upgrade_paths(snap, setting, BOSS, CAT, observed)


def test_vision_reads_level_and_grades_and_store_keeps_full_listing(tmp_path):
    props = _SCHEMA["properties"]["listings"]["items"]["properties"]
    assert {"level", "potential_grade", "additional_grade"} <= set(props)
    store = PriceStore(str(tmp_path / "m.sqlite3"), lambda: 5.0)
    assert store.record(dict(ROBE))
    row = store.rows()[0]
    assert (row["total"], row["part"], row["level"], row["potential_grade"]) == (ROBE["total"], "상의", 250, "유니크")


def test_buy_path_matches_hand_swap_and_reports_set_change():
    snap, setting, paths = _paths([ROBE])
    buy = next(p for p in paths["all"] if p["path"] == "구매" and p["slot"] == "상의")
    ev = Evaluator(snap, setting, BOSS, CAT)
    items = ev.base_items()
    trial = dict(items)
    trial["상의"] = item_from_input("상의", "상의", ROBE["name"], ROBE["total"],
                                   ROBE["potential_lines"] + ROBE["additional"], snap.level, 22)
    hand = (ev.index(trial) / ev.index(items) - 1) * 100
    assert buy["delta_pct"] == pytest.approx(hand, abs=1e-9)
    assert buy["cost"] == ROBE["price"] and buy["per_100m"] == pytest.approx(hand / 200)
    changes = {c["set"]: (c["before"], c["after"]) for c in buy["set_change"]}
    before = changes["도전자의 장비 세트(마법사)"][0]
    assert changes["도전자의 장비 세트(마법사)"] == (before, before - 1)
    assert changes["에테르넬 세트(마법사)"][1] == changes["에테르넬 세트(마법사)"][0] + 1


def test_craft_path_is_listing_price_plus_cube_expected_cost():
    snap, setting, paths = _paths([BASE])
    crafts = [p for p in paths["all"] if p["path"] == "직작" and p["slot"] == "상의" and p["kind"] == "잠재"]
    assert crafts
    c = crafts[0]
    cube = expected_cost("잠재", 250, "유니크", c["grade"], c["reach_probability"])
    assert c["cost"] == pytest.approx(BASE["price"] + cube)
    assert c["base_price"] == BASE["price"] and c["cube_cost"] == pytest.approx(cube)


def test_all_paths_are_meaningful_and_sorted_by_value_and_include_cube_on_current_item():
    _, _, paths = _paths([ROBE, BASE])
    allp = paths["all"]
    assert allp == sorted(allp, key=lambda p: p["per_100m"], reverse=True)
    assert all(p["delta_pct"] >= MIN_GAIN and p["cost"] > 0 for p in allp)
    assert {p["path"] for p in allp} >= {"큐브", "구매"}
    best = paths["best_by_slot"]
    assert len({b["slot"] for b in best}) == len(best)


def test_paths_without_observations_still_rank_cube_routes():
    _, _, paths = _paths([])
    # 관측 매물이 없으면 지금 템을 올리는 경로(큐브·스타포스 — 2026-10-07 스타포스 추가)만
    assert paths["all"] and all(p["path"] in ("큐브", "스타포스") for p in paths["all"])
    assert any(p["path"] == "큐브" for p in paths["all"])


def test_agent_tool_returns_paths_with_cost_text():
    from agent.tools import TOOL_DEFS, ToolBox
    assert "upgrade_paths" in {t["name"] for t in TOOL_DEFS}
    box = ToolBox(lambda name, date=None: snapshot(bundle("레테")), market=lambda: [ROBE])
    r = box.run("upgrade_paths", {"name": "x"})
    buy = next(p for p in r["all"] if p["path"] == "구매")
    assert buy["cost_text"] == "200억" and "세트" in r["note"]


def test_weak_listing_that_breaks_a_set_is_not_recommended():
    """도전자 세트를 깨는 약한 매물: 세트 효과가 빠져 실딜이 떨어지므로 구매 경로에 오르지 않는다."""
    weak = {**ROBE, "total": {"INT": 180, "LUK": 160, "MATK": 120}, "potential_lines": ["INT +10%", "INT +7%"]}
    snap, setting = _setup()
    from engine.market.paths import _Paths, listing_item
    from engine.market.recommend import _Planner
    pl = _Planner(snap, setting, BOSS, CAT, None)
    d, change = _Paths(pl, CAT).delta("상의", listing_item("상의", weak, snap.level))
    assert d < 0 and any(c["set"].startswith("도전자") and c["after"] < c["before"] for c in change)
    _, _, paths = _paths([weak])
    assert not [p for p in paths["all"] if p["path"] == "구매"]


def test_untradeable_secondary_job_gets_no_buy_path_for_secondary():
    """카이저는 보조무기를 경매장에서 살 수 없다(2025-12 기준) — 관측된 보조무기 매물을 구매 경로로 세우지 않는다."""
    snap = snapshot(bundle("카이저"))
    setting = rank_settings(snap, BOSS, CAT)[0][0]
    sub = {"category": "보조무기", "part": "보조무기", "name": "노바의 정수", "starforce": 22, "level": 200,
           "potential_grade": "레전드리", "additional_grade": "레전드리", "total": {"STR": 300, "DEX": 300, "ATK": 300},
           "potential_lines": ["보스 몬스터 데미지 +40%", "공격력 +12%", "공격력 +12%"], "additional": ["공격력 +12%"],
           "price": 1_000_000_000, "seen_at": 1.0}
    r = upgrade_paths(snap, setting, BOSS, CAT, observed=[sub])
    assert not [p for p in r["all"] if p["slot"] == "보조무기" and p["path"] != "큐브"]


def test_paths_list_keeps_every_path_kind_when_starforce_is_plentiful():
    """스타포스 경로가 많아도 구매·큐브 경로가 목록에서 밀려나지 않는다(경로 종류별 상위 묶음)."""
    from server.service import paths as service_paths
    r = service_paths(snapshot(bundle("레테")), 300.0, [ROBE])
    kinds = {p["path"] for p in r["all"]}
    assert {"구매", "큐브", "스타포스"} <= kinds
    per = [p["per_100m"] for p in r["all"]]
    assert per == sorted(per, reverse=True)
