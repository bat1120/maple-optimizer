"""UI 개편(2026-10-07): 캐릭터 응답에 프로필(아바타·월드·길드)과 장비 상세(아이콘·잠재 등급·줄)를 넣는다.
이미 받은 넥슨 응답에서만 꺼낸다. 픽스처처럼 이미지·아이콘 필드가 없으면 None."""
from helpers import bundle
from nexon.convert import snapshot
from server.service import summary


def test_profile_comes_from_basic_and_missing_image_is_none():
    b = bundle("레테")
    s = summary(snapshot(b))
    p = s["profile"]
    assert p["world"] == b["character/basic"]["world_name"]
    assert p["class_level"] == b["character/basic"]["character_class_level"]
    assert p["image"] is None and "name" in p and "guild" in p


def test_profile_image_and_item_icon_when_present():
    b = bundle("레테")
    b["character/basic"] = {**b["character/basic"], "character_name": "레테", "character_guild_name": "길드",
                            "character_image": "https://open.api.nexon.com/static/maplestory/character/look/x"}
    eq = b["character/item-equipment"]
    for key in ("item_equipment", "item_equipment_preset_1", "item_equipment_preset_2", "item_equipment_preset_3"):
        for x in eq.get(key) or []:
            x["item_icon"] = "https://open.api.nexon.com/static/maplestory/item/icon/y"
    s = summary(snapshot(b))
    assert s["profile"]["image"].endswith("/look/x") and s["profile"]["guild"] == "길드" and s["profile"]["name"] == "레테"
    first = next(iter(s["equipment_presets"].values()))[0]
    assert first["icon"].endswith("/icon/y")


def test_equipment_items_carry_grades_and_lines():
    s = summary(snapshot(bundle("레테")))
    items = [x for xs in s["equipment_presets"].values() for x in xs]
    for key in ("slot", "name", "starforce", "icon", "potential_grade", "additional_grade", "potentials",
                "additional", "level", "special_ring_level"):
        assert all(key in x for x in items), key
    glove = next(x for x in items if x["slot"] == "장갑")
    assert glove["potential_grade"] and glove["potentials"] and glove["icon"] is None
