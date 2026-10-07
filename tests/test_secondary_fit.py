"""보조무기 착용 가능 판정(2026-10-07): 매물 툴팁의 장비분류가 지금 낀 보조무기 종류(넥슨 API item_equipment_part)와 같아야 한다.
여러 직업군이 같이 쓰는 '방패'는 툴팁의 착용 가능 직업군까지 맞아야 한다. 못 읽었으면 None(모름)."""
from engine.market.secondary import secondary_fits
from engine.market.paths import upgrade_paths
from engine.stats.evaluate import rank_settings
from engine.stats.metrics import BossProfile
from engine.stats.sets import SetCatalog
from helpers import bundle
from nexon.convert import snapshot

CAT, BOSS = SetCatalog.load(), BossProfile("기준", 300.0)
MAGE = ("마법사",)


def test_same_type_fits_other_type_does_not():
    assert secondary_fits("마법깃펜", MAGE, "마법깃펜", None) is True
    assert secondary_fits("마법깃펜", MAGE, "포스실드", ["전사"]) is False
    assert secondary_fits("마법깃펜", MAGE, None, None) is None


def test_shield_needs_job_group():
    assert secondary_fits("방패", MAGE, "방패", ["마법사"]) is True
    assert secondary_fits("방패", MAGE, "방패", ["전사"]) is False
    assert secondary_fits("방패", MAGE, "방패", None) is None


SUB = {"category": "보조무기", "part": "보조무기", "name": "x", "starforce": 0, "level": 200,
       "potential_grade": "레전드리", "additional_grade": None, "total": {"INT": 150, "LUK": 150, "MATK": 250},
       "potential_lines": ["보스 몬스터 데미지 +40%", "마력 +12%", "마력 +12%"], "additional": ["마력 +12%"], "price": 1_000_000_000, "seen_at": 1.0}


def _buy_slots(observed):
    snap = snapshot(bundle("레테"))  # 레테 보조무기 = 마법깃펜
    setting = rank_settings(snap, BOSS, CAT)[0][0]
    return [p["slot"] for p in upgrade_paths(snap, setting, BOSS, CAT, observed=observed)["all"] if p["path"] != "큐브"]


def test_paths_buy_secondary_only_when_type_matches():
    assert "보조무기" in _buy_slots([{**SUB, "equip_type": "마법깃펜", "job_groups": ["마법사"]}])
    assert "보조무기" not in _buy_slots([{**SUB, "name": "y", "equip_type": "포스실드", "job_groups": ["전사"]}])
    assert "보조무기" not in _buy_slots([{**SUB, "name": "z"}])  # 종류를 못 읽은 옛 관측은 구매 경로로 세우지 않는다


def test_screen_eval_skips_other_job_secondary_and_flags_unknown():
    from server.service import vision_items
    from server.vision import _SCHEMA
    props = _SCHEMA["properties"]["listings"]["items"]
    assert {"equip_type", "job_groups"} <= set(props["required"])  # 툴팁의 장비분류·착용 가능 직업군을 읽게 한다
    snap = snapshot(bundle("레테"))
    read = {"name": "아케인셰이드 포스실드", "category": "보조무기", "part": "보조무기", "starforce": 0, "level": 200,
            "total": {"STR": 100, "ATK": 100}, "potentials": ["공격력 +12%"], "price": 1_000_000_000,
            "equip_type": "포스실드", "job_groups": ["전사"]}
    row = vision_items(snap, None, 300.0, [read], set())[0]
    assert row["evaluated"] is False and "포스실드" in row["reason"] and "마법깃펜" in row["reason"]
    unknown = vision_items(snap, None, 300.0, [{**read, "name": "녹스 마법깃펜", "equip_type": None, "job_groups": None,
                                                "total": {"INT": 100, "MATK": 100}, "potentials": ["마력 +12%"]}], set())[0]
    assert unknown["evaluated"] is True and "확인" in unknown["secondary_note"]
