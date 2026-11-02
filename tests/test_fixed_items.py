"""스타포스·잠재를 재설정할 수 없는 템(2026-10-17 사용자): 크리티컬 확률이 달린 도미네이터 펜던트는 PC방 도미네이터 —
스타포스 강화·잠재(큐브) 재설정이 안 된다. 픽스처: 레테·렌·히어로 펜던트2(15성 고정, 유니크 주스탯 9/6% + 크확 6%, 에디 없음).
다른 펜던트를 사서 바꾸는 경로(구매)와 검색 추천은 그대로."""
import pytest

from helpers import bundle
from engine.enhance.starforce_stats import eligible
from engine.market.events import Events
from engine.market.paths import upgrade_paths
from engine.market.recommend import _Planner, fixed_reason, roadmap
from engine.market.target_roadmap import target_roadmap
from engine.stats.evaluate import rank_settings
from engine.stats.metrics import BossProfile
from engine.stats.sets import SetCatalog
from nexon.convert import snapshot

CAT, BOSS = SetCatalog.load(), BossProfile("기준", 300.0)


def _lete():
    snap = snapshot(bundle("레테"))
    return snap, rank_settings(snap, BOSS, CAT)[0][0]


def test_pcbang_dominator_is_detected_by_crit_potential():
    snap, setting = _lete()
    pl = _Planner(snap, setting, BOSS, CAT, None)
    pend = pl.raw["펜던트2"]
    assert pend.name == "도미네이터 펜던트" and any("크리티컬 확률" in p for p in pend.potentials)
    assert fixed_reason(pend)
    assert not eligible(pend)
    other = snapshot(bundle("바이퍼")).equipment_presets[1]["펜던트"]  # 일반 도미네이터(22성, 크확 없음)
    assert other.name == "도미네이터 펜던트" and fixed_reason(other) is None


def test_no_starforce_or_cube_paths_on_pcbang_dominator():
    snap, setting = _lete()
    rm = roadmap(snap, setting, BOSS, CAT)
    assert all(t["cube_cost"] is None for k in ("잠재", "에디") for t in rm.get("펜던트2", {}).get(k, []))
    r = upgrade_paths(snap, setting, BOSS, CAT, [], None, Events())
    assert not [p for p in r["all"] if p["slot"] == "펜던트2" and p["path"] in ("스타포스", "큐브")]


def test_target_roadmap_skips_pcbang_dominator_enhance():
    snap, setting = _lete()
    r = target_roadmap(snap, setting, BOSS, CAT, Events(), [], 34.52, 40.0)
    assert not [s for s in r["steps"] if s["slot"] == "펜던트2" and s["path"] in ("스타포스", "큐브")]


def test_pcbang_item_cannot_be_sold_so_resale_is_zero():
    """PC방 템은 팔 수 없다(2026-10-17 사용자) — 지금 그 부위가 PC방 도미네이터면 넣은 판매 예상가를 0으로 본다."""
    from types import SimpleNamespace as NS
    from server import service
    snap, setting = _lete()
    x = NS(slot="펜던트2", part="펜던트", name="도미네이터 펜던트", total={"INT": 120, "MATK": 10}, potentials=["INT +12%"],
           starforce=22, price=3_000_000_000, resale=1_000_000_000)
    r = service.listings(snap, setting, 300.0, [x])
    row = r["ranking"][0]
    assert row["resale"] == 0 and row["net_cost"] == 3_000_000_000
    assert "팔 수 없" in row["resale_note"]
    plan = service.optimize(snap, setting, 300.0, 10_000_000_000, [x])
    assert all(a["cost"] == 3_000_000_000 for a in plan["actions"])
