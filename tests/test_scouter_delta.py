"""환산 계산기(MapleScouter) 입력용 변화량(2026-10-07 사용자: 최소 클릭으로 복붙).
템을 바꿨을 때 '출처 합'(장비·세트·…)의 차이 — MapleScouter 칸 이름 그대로: INT 기본/%, 마력 기본/%, 보스 데미지 등.
방무는 곱연산이라 더해진/빠진 줄을 따로 준다."""
import copy

from helpers import bundle
from nexon.convert import snapshot
from engine.stats.snapshot import Setting
from server.service import CATALOG, scouter_delta


def _snap_and_glove():
    snap = snapshot(bundle("레테"))
    setting = Setting(1, 1, 1)
    glove = snap.equipment_presets[1]["장갑"]
    return snap, setting, glove


def test_same_item_gives_zero_delta():
    snap, setting, glove = _snap_and_glove()
    d = scouter_delta(snap, setting, "장갑", glove)
    assert all(v == 0 for v in d["fields"].values()) and d["ied_add"] == [] and d["ied_remove"] == []


def test_stronger_glove_delta_by_field():
    snap, setting, glove = _snap_and_glove()
    better = copy.deepcopy(glove)
    better.stats.flat["INT"] = better.stats.flat.get("INT", 0) + 30
    better.stats.pct["INT"] = better.stats.pct.get("INT", 0) + 9
    better.stats.flat["MATK"] = better.stats.flat.get("MATK", 0) + 12
    better.stats.cd += 8
    better.stats.boss += 30
    better.stats.ied.append(40)
    d = scouter_delta(snap, setting, "장갑", better)
    f = d["fields"]
    assert f["INT|기본"] == 30 and f["INT|%"] == 9 and f["마력|기본"] == 12
    assert f["크리 데미지"] == 8 and f["보스 데미지"] == 30 and d["ied_add"] == [40]
    assert d["rows"] == {"main": ["INT"], "sub": ["LUK"], "attack": "마력"}


def test_set_effect_change_is_included():
    """세트 아이템을 스탯이 똑같은 세트 밖 템으로 바꾸면, 변화량은 세트 효과가 빠진 만큼만 생긴다(출처 합 기준이라 포함)."""
    snap, setting, glove = _snap_and_glove()
    plain = copy.deepcopy(glove)
    plain.name = "세트 아닌 장갑"
    d = scouter_delta(snap, setting, "장갑", plain)
    assert any(v != 0 for v in d["fields"].values()) or d["ied_remove"], glove.name


def test_vision_rows_carry_scouter_delta_for_the_chosen_slot():
    from server.service import vision_items
    snap = snapshot(bundle("레테"))
    listing = {"name": "에테르넬 메이지글러브", "category": "장갑", "part": "장갑", "starforce": 22, "level": 250,
               "total": {"INT": 100, "MATK": 40}, "potentials": ["INT +12%"], "potential_lines": ["INT +12%"],
               "additional": [], "price": 10_000_000_000, "breakdown": {}}
    row = vision_items(snap, None, 300, [listing], set())[0]
    assert row["evaluated"] and row["scouter"]["slot"] == row["slot"] and row["scouter"]["to"] == "에테르넬 메이지글러브"
    assert "INT|%" in row["scouter"]["fields"]


def test_delta_carries_character_for_safety_check():
    """북마크가 MapleScouter에 불러와진 캐릭터와 비교한다 — 직업·레벨·이름을 같이 담는다."""
    snap, setting, glove = _snap_and_glove()
    d = scouter_delta(snap, setting, "장갑", glove)
    assert d["job"] == snap.character_class and d["level"] == snap.level and "name" in d
