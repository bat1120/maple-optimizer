"""가격 대비 스펙업: 단계마다 메소 재설정(큐브) 기대 비용과 억당 실딜 상승률."""
import pytest

from engine.enhance.cube import tier_up_tries
from engine.market.cube_value import expected_cost, reset_cost_for
from engine.market.recommend import MIN_GAIN, roadmap
from engine.stats.evaluate import Evaluator, rank_settings
from engine.stats.metrics import BossProfile
from engine.stats.sets import SetCatalog
from helpers import bundle
from nexon.convert import snapshot

CAT, BOSS = SetCatalog.load(), BossProfile("기준", 300.0)


def _rm():
    snap = snapshot(bundle("레테"))
    setting = rank_settings(snap, BOSS, CAT)[0][0]
    return snap, setting, roadmap(snap, setting, BOSS, CAT)


def test_reset_costs_by_kind_level_grade():
    assert reset_cost_for("잠재", 200, "레전드리") == 45_000_000
    assert reset_cost_for("에디", 150, "유니크") == 66_300_000
    assert reset_cost_for("에디", 250, "레전드리") == 98_000_000
    assert reset_cost_for("에디", 160, "에픽") == 29_050_000


def test_expected_cost_same_grade_is_geometric():
    assert expected_cost("잠재", 150, "유니크", "유니크", 0.01) == pytest.approx(34_000_000 / 0.01)


def test_expected_cost_with_grade_up_adds_tier_up_tries():
    up = tier_up_tries(0.014, 107).mean * 34_000_000
    assert expected_cost("잠재", 150, "유니크", "레전드리", 0.02) == pytest.approx(up + 40_000_000 / 0.02)
    up2 = tier_up_tries(0.009804, 152).mean * 27_300_000 + tier_up_tries(0.007, 214).mean * 66_300_000
    assert expected_cost("에디", 150, "에픽", "레전드리", 0.05) == pytest.approx(up2 + 78_000_000 / 0.05)


def test_lower_grade_or_missing_grade_has_no_cube_cost():
    assert expected_cost("잠재", 150, "레전드리", "유니크", 0.5) is None
    assert expected_cost("에디", 150, None, "에픽", 0.5) is None


def test_items_know_current_grades():
    snap = snapshot(bundle("레테"))
    setting = rank_settings(snap, BOSS, CAT)[0][0]
    items = Evaluator(snap, setting, BOSS, CAT).base_items()
    assert (items["상의"].potential_grade, items["상의"].additional_grade) == ("유니크", "에픽")
    assert items["펜던트2"].additional_grade is None


def test_roadmap_tiers_have_reach_probability_cost_and_value():
    _, _, rm = _rm()
    for t in rm["상의"]["잠재"]:
        assert t["probability"] <= t["reach_probability"] <= 1
        if t["cube_cost"] is not None:
            assert t["per_100m"] == pytest.approx(t["delta_pct"] / (t["cube_cost"] / 1e8))
    assert [t["cube_cost"] for t in rm["상의"]["잠재"] if t["grade"] == "에픽"] == [None, None]  # 지금 유니크 → 에픽은 큐브로 못 감


def test_value_ranking_is_sorted_unique_and_meaningful():
    snap, setting, rm = _rm()
    from engine.market.recommend import value_ranking
    vr = value_ranking(rm)
    assert vr == sorted(vr, key=lambda x: x["per_100m"], reverse=True)
    assert len({(x["slot"], x["kind"]) for x in vr}) == len(vr)
    assert all(x["delta_pct"] >= MIN_GAIN and x["cube_cost"] > 0 for x in vr)
    assert any(x["slot"] == "무기" for x in vr)   # 제네시스 무기도 큐브는 돌릴 수 있다


def test_roadmap_tool_returns_value_ranking_with_cost_text():
    from agent.tools import ToolBox
    r = ToolBox(lambda name, date=None: snapshot(bundle("레테"))).run("upgrade_roadmap", {"name": "x"})
    top = r["value_ranking"][0]
    assert top["cube_cost_text"].endswith("만") and top["per_100m"] > 0 and "메소 재설정" in r["value_note"]
