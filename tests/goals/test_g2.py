"""G2 판정 — GOALS.md G2 성공 기준."""
import json
import pathlib

import pytest

from engine.market.listing import InvalidPrice, Listing, evaluate_listing
from engine.stats.evaluate import evaluate_setting, swap_item
from engine.stats.metrics import BossProfile
from engine.stats.sets import SetCatalog
from engine.stats.snapshot import Setting
from helpers import bundle, classes
from nexon.convert import snapshot

RESULTS = pathlib.Path(__file__).resolve().parents[2] / "goals" / "results" / "G2.json"
BOSS = BossProfile("기준 보스(방어율 300%)", 300.0)
# ①은 45명 전원이 데미지를 넣을 수 있는 보스로 잰다 (방어율 300%에서는 방무 66.7% 미만 캐릭터가 데미지 0 → NoDamage).
ALL_HIT = BossProfile("일반 보스(방어율 100%)", 100.0)
CAT = SetCatalog.load()
_m: dict = {}


def _record(k, v):
    _m[k] = v
    RESULTS.write_text(json.dumps(_m, ensure_ascii=False, indent=1), encoding="utf-8")


def test_criterion1_same_item_listing_has_zero_delta_45_classes():
    worst = 0.0
    for c in classes():
        if c == "데몬어벤져":
            continue
        snap = snapshot(bundle(c))
        for slot, it in snap.equipment_presets[snap.active_equipment_preset].items():
            ev = evaluate_listing(snap, snap.active_setting, Listing(slot, it, price=1_000_000_000), ALL_HIT, CAT)
            worst = max(worst, abs(ev.delta_pct))
            assert abs(ev.delta_pct) < 1e-9, (c, slot, ev.delta_pct)
    _record("criterion1_worst_abs_delta_pct", worst)


def test_criterion2_listing_delta_equals_swap_calculation():
    snap = snapshot(bundle("레테"))
    hunt = Setting(1, 1, 1)
    ring = snap.equipment_presets[2]["반지4"]
    ev = evaluate_listing(snap, hunt, Listing("반지4", ring, price=3_000_000_000), BOSS, CAT)
    base = evaluate_setting(snap, hunt, BOSS, CAT)
    expected = (swap_item(snap, hunt, "반지4", ring, BOSS, CAT) / base - 1) * 100
    _record("criterion2_delta_pct", ev.delta_pct)
    assert abs(ev.delta_pct - expected) < 1e-9


def test_criterion3_per_100m_matches_hand_calculation_and_rejects_bad_price():
    snap = snapshot(bundle("레테"))
    hunt = Setting(1, 1, 1)
    ring = snap.equipment_presets[2]["반지4"]
    ev = evaluate_listing(snap, hunt, Listing("반지4", ring, price=3_000_000_000, resale=500_000_000), BOSS, CAT)
    hand = ev.delta_pct / ((3_000_000_000 - 500_000_000) / 100_000_000)
    _record("criterion3_per_100m", ev.per_100m)
    assert abs(ev.per_100m - hand) < 1e-9
    with pytest.raises(InvalidPrice):
        evaluate_listing(snap, hunt, Listing("반지4", ring, price=100, resale=100), BOSS, CAT)
