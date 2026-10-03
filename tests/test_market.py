import pytest

from engine.market.listing import Listing, item_from_input, rank_listings
from engine.stats.metrics import BossProfile
from engine.stats.sets import SetCatalog
from engine.stats.snapshot import Setting
from helpers import bundle
from nexon.convert import snapshot

CAT = SetCatalog.load()
BOSS = BossProfile("기준", 300.0)


def test_item_from_input_builds_statblock():
    it = item_from_input("반지4", "반지", "어센던트 펄스 링",
                         {"INT": 59, "LUK": 59, "MATK": 16, "ALL%": 0},
                         ["INT +12%", "LUK +9%", "INT +9%", "마력 +10", "INT +6"], level=287, starforce=17)
    assert it.stats.flat["INT"] == 65 and it.stats.flat["MATK"] == 26
    assert it.stats.pct["INT"] == 21 and it.starforce == 17 and it.excluded == []


def test_item_from_input_reports_unknown_option():
    it = item_from_input("반지4", "반지", "x", {}, ["처음보는 옵션 +5%"], level=287)
    assert it.excluded == ["처음보는 옵션 +5%"]


def test_item_from_input_rejects_unknown_total_key():
    with pytest.raises(ValueError):
        item_from_input("반지4", "반지", "x", {"STRR": 1}, [], level=287)


def test_rank_listings_orders_by_efficiency():
    snap = snapshot(bundle("레테"))
    ring = snap.equipment_presets[2]["반지4"]
    cheap = Listing("반지4", ring, price=1_000_000_000)
    pricey = Listing("반지4", ring, price=5_000_000_000)
    ranked = rank_listings(snap, Setting(1, 1, 1), [pricey, cheap], BOSS, CAT)
    assert [e.listing.price for e in ranked] == [1_000_000_000, 5_000_000_000]
    assert ranked[0].per_100m == pytest.approx(ranked[1].per_100m * 5)


def test_zero_damage_baseline_is_explicit_error():
    """방어율 300%에서 방무가 66.7% 미만이면 데미지 0 → 비율을 정의할 수 없다."""
    from engine.market.listing import NoDamage, evaluate_listing
    snap = snapshot(bundle("나이트로드"))
    assert snap.final.ied < 66.67
    it = snap.equipment_presets[snap.active_equipment_preset]["반지1"]
    with pytest.raises(NoDamage):
        evaluate_listing(snap, snap.active_setting, Listing("반지1", it, price=10**9), BOSS, CAT)


def test_listing_reports_equivalent_main_stat():
    from engine.market.listing import evaluate_listing
    snap = snapshot(bundle("레테"))
    ring = snap.equipment_presets[2]["반지4"]
    ev = evaluate_listing(snap, Setting(1, 1, 1), Listing("반지4", ring, price=3_000_000_000), BOSS, CAT)
    assert ev.main_stat_gain > 0
    assert ev.main_stat_gain_per_100m == pytest.approx(ev.main_stat_gain / 30)
