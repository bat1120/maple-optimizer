"""경매장 판매 수수료: 사는 가격엔 붙지 않고, 지금 템을 팔아 받는 돈(판매 예상가)에서 빠진다. 기본 5%, MVP 실버↑·PC방 3%."""
import pytest

from agent.tools import ToolBox
from engine.market.listing import InvalidPrice, Listing, evaluate_listing, item_from_input, net_resale
from engine.stats.evaluate import rank_settings
from engine.stats.metrics import BossProfile
from engine.stats.sets import SetCatalog
from helpers import bundle
from nexon.convert import snapshot

CAT, BOSS = SetCatalog.load(), BossProfile("기준", 300.0)
RING = {"slot": "반지1", "part": "반지", "name": "센 반지", "total": {"INT": 50}, "potentials": ["INT +12%", "INT +12%", "INT +9%"],
        "starforce": 17}


def test_net_resale_deducts_fee():
    assert net_resale(1_000_000_000, 0.05) == 950_000_000
    assert net_resale(1_000_000_000, 0.03) == 970_000_000
    assert net_resale(0, 0.05) == 0


def test_cost_uses_resale_after_fee():
    snap = snapshot(bundle("레테"))
    setting = rank_settings(snap, BOSS, CAT)[0][0]
    it = item_from_input("반지1", "반지", "센 반지", {"INT": 50}, RING["potentials"], snap.level, 17)
    e = evaluate_listing(snap, setting, Listing("반지1", it, 5_000_000_000, 1_000_000_000), BOSS, CAT)
    assert e.per_100m == pytest.approx(e.delta_pct / ((5e9 - 0.95e9) / 1e8))
    e3 = evaluate_listing(snap, setting, Listing("반지1", it, 5_000_000_000, 1_000_000_000, fee_rate=0.03), BOSS, CAT)
    assert e3.per_100m == pytest.approx(e3.delta_pct / ((5e9 - 0.97e9) / 1e8))


def test_price_equal_to_net_resale_is_invalid():
    snap = snapshot(bundle("레테"))
    setting = rank_settings(snap, BOSS, CAT)[0][0]
    it = item_from_input("반지1", "반지", "센 반지", {"INT": 50}, [], snap.level, 17)
    with pytest.raises(InvalidPrice):
        evaluate_listing(snap, setting, Listing("반지1", it, 950_000_000, 1_000_000_000), BOSS, CAT)


def test_tool_reports_fee_and_net_cost():
    box = ToolBox(lambda name, date=None: snapshot(bundle("레테")))
    r = box.run("evaluate_listings", {"name": "x", "fee_rate": 0.03,
                                      "listings": [{**RING, "price": 5_000_000_000, "resale": 1_000_000_000}]})
    row = r["ranking"][0]
    assert r["fee_rate"] == 0.03 and row["net_resale"] == 970_000_000 and row["net_cost"] == 4_030_000_000
    assert row["net_cost_text"] == "40억 3000만"
    default = box.run("evaluate_listings", {"name": "x", "listings": [{**RING, "price": 5_000_000_000, "resale": 1_000_000_000}]})
    assert default["fee_rate"] == 0.05 and default["ranking"][0]["net_resale"] == 950_000_000


def test_fee_rate_is_bounded():
    box = ToolBox(lambda name, date=None: snapshot(bundle("레테")))
    r = box.run("evaluate_listings", {"name": "x", "fee_rate": 0.5, "listings": [{**RING, "price": 5_000_000_000}]})
    assert "error" in r
