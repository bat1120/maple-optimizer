"""스타포스 성별 스탯(2026-10-07): engine/data/starforce_stats.json(나무위키 표)을 넥슨 API 실측 item_starforce_option으로 검산하고,
업그레이드 경로에 '스타포스'(지금 성 → 목표 성) 경로를 넣는다."""
import json
import pathlib

import pytest

from engine.enhance.starforce_stats import cumulative, eligible, gain
from engine.market.paths import upgrade_paths
from engine.stats.evaluate import rank_settings
from engine.stats.metrics import BossProfile
from engine.stats.sets import SetCatalog
from helpers import bundle
from nexon.convert import item as convert_item
from nexon.convert import snapshot

CAT, BOSS = SetCatalog.load(), BossProfile("기준", 300.0)
FIX = pathlib.Path(__file__).parent / "fixtures"


def _fixture_items():
    for f in FIX.rglob("character_item-equipment.json"):
        j = json.loads(f.read_text(encoding="utf-8"))
        for key in ("item_equipment", "item_equipment_preset_1", "item_equipment_preset_2", "item_equipment_preset_3"):
            for raw in j.get(key) or []:
                yield raw


def test_table_matches_every_measured_item():
    """픽스처의 모든 스타포스 템: 0성부터 지금 성까지 쌓은 값이 API 실측 스타포스 옵션과 같다(표에 없는 구간은 None)."""
    checked = 0
    for raw in _fixture_items():
        it = convert_item(raw, 200)
        if not eligible(it):
            continue
        c = cumulative(it, it.starforce)
        if c is None:
            continue
        assert max(it.sf_option.get(k, 0) for k in ("STR", "DEX", "INT", "LUK")) == c["STAT"], (it.name, it.starforce, it.sf_option, c)
        for k in ("ATK", "MATK"):
            if k in c:
                assert it.sf_option.get(k, 0) == c[k], (it.name, it.starforce, k, it.sf_option, c)
        checked += 1
    assert checked > 1000


def test_gain_is_difference_of_cumulative():
    snap = snapshot(bundle("레테"))
    belt = snap.equipment_presets[snap.active_equipment_preset]["벨트"]  # 분노한 자쿰의 벨트 17성, 150레벨
    g = gain(belt, 22)
    assert g["INT"] == 117 - 62 and g["ATK"] == 85 - 19 and g["MATK"] == 85 - 19


def test_not_eligible_special_or_zero_star():
    snap = snapshot(bundle("레테"))
    eq = snap.equipment_presets[snap.active_equipment_preset]
    assert not eligible(eq["무기"])      # 제네시스: 22성 고정
    assert not eligible(eq["반지1"])     # 0성: 어떤 스탯에 붙는지 모른다
    assert not eligible(eq["보조무기"])  # 보조무기는 16성 이상 공격력이 표와 다르다


def test_upgrade_paths_include_starforce_routes():
    snap = snapshot(bundle("레테"))
    setting = rank_settings(snap, BOSS, CAT)[0][0]
    sf = [p for p in upgrade_paths(snap, setting, BOSS, CAT)["all"] if p["path"] == "스타포스"]
    belt = [p for p in sf if p["slot"] == "벨트"]
    assert belt and all(p["from_star"] == 17 and p["to_star"] > 17 and p["cost"] > 0 and p["delta_pct"] > 0 for p in belt)
    assert not [p for p in sf if p["slot"] == "무기"]
    assert all(p["to_star"] <= 30 and all(v > 0 for v in p["gain"].values()) for p in sf)
    assert all(p["expected_destroys"] >= 0 for p in sf)
    assert max(p["expected_destroys"] for p in sf if p["to_star"] >= 22) > 0  # 22성 이상은 파괴가 생긴다
