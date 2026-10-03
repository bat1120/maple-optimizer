import re

import pytest

from engine.options import StatLine, parse_option
from helpers import classes, load

L = 287


@pytest.mark.parametrize("text,expected", [
    # 신 표기 잠재
    ("STR +12%", [StatLine("STR", 12, True)]),
    ("INT +6", [StatLine("INT", 6, False)]),
    ("올스탯 +9%", [StatLine(k, 9, True) for k in ("STR", "DEX", "INT", "LUK")]),
    ("공격력 +12%", [StatLine("ATK", 12, True)]),
    ("마력 +14", [StatLine("MATK", 14, False)]),
    ("데미지 +12%", [StatLine("DMG", 12, True)]),
    ("보스 몬스터 데미지 +40%", [StatLine("BOSS", 40, True)]),
    ("몬스터 방어율 무시 +35%", [StatLine("IED", 35, True)]),
    ("크리티컬 데미지 +8%", [StatLine("CD", 8, True)]),
    ("크리티컬 확률 +9%", [StatLine("CR", 9, True)]),
    ("최대 HP +12%", [StatLine("HP", 12, True)]),
    ("최대 HP +300", [StatLine("HP", 300, False)]),
    ("캐릭터 기준 9레벨 당 INT +2", [StatLine("INT", 62, False)]),  # 287 // 9 = 31, ×2
    # 구 표기 잠재 (Review Focus 1)
    ("STR : +12%", [StatLine("STR", 12, True)]),
    ("보스 몬스터 공격 시 데미지 : +40%", [StatLine("BOSS", 40, True)]),
    ("몬스터 방어율 무시 : +15%", [StatLine("IED", 15, True)]),
    ("캐릭터 기준 10레벨 당 STR : +2", [StatLine("STR", 56, False)]),  # 287 // 10 = 28, ×2
    # 하이퍼스탯
    ("지력 180 증가", [StatLine("INT", 180, False)]),
    ("공격력과 마력 18 증가", [StatLine("ATK", 18, False), StatLine("MATK", 18, False)]),
    ("보스 몬스터 공격 시 데미지 47% 증가", [StatLine("BOSS", 47, True)]),
    ("방어율 무시 36% 증가", [StatLine("IED", 36, True)]),
    # 어빌리티
    ("모든 능력치 15 증가", [StatLine(k, 15, False) for k in ("STR", "DEX", "INT", "LUK")]),
    ("INT 30 증가, STR 15 증가", [StatLine("INT", 30, False), StatLine("STR", 15, False)]),
    # 세트 효과 (이중 공백)
    ("공격력  +30, 마력  +30, 보스 몬스터 데미지 +10%",
     [StatLine("ATK", 30, False), StatLine("MATK", 30, False), StatLine("BOSS", 10, True)]),
    # 세트 효과에 딜 무관 항목이 섞인 경우
    ("공격력  +4, 마력  +4, 파티퀘스트 경험치 3% 추가", [StatLine("ATK", 4, False), StatLine("MATK", 4, False)]),
    ("공격력  +7, 마력  +7, [수호령 라이딩] 스킬 사용 가능", [StatLine("ATK", 7, False), StatLine("MATK", 7, False)]),
])
def test_relevant_options(text, expected):
    assert parse_option(text, L) == expected


@pytest.mark.parametrize("text", [
    "아이템 드롭률 +20%",
    "메소 획득량 +20%",
    "스킬 재사용 대기시간 -2초",
    "HP 회복 아이템 및 회복 스킬 효율 +30%",
    "<쓸만한 샤프 아이즈> 스킬 사용 가능",
    "[피의 갈망 Lv.1] 스킬 사용 가능",
    "공격 시 15% 확률로 95의 HP 회복",
    "피격 시 5% 확률로 데미지의 40% 무시",
    "스킬 사용 시 19% 확률로 재사용 대기시간이 미적용",
    "상태 이상에 걸린 대상 공격 시 데미지 8% 증가",
    "일반 몬스터 공격 시 데미지 14% 증가",
    "최대 MP +195",
    "방어력 +125",
    "모든 스킬의 재사용 대기시간 : -2초(10초 이하는 10%감소, 5초 미만으로 감소 불가)",
    "파티퀘스트 경험치 10% 추가",
])
def test_irrelevant_options_are_empty(text):
    assert parse_option(text, L) == []


@pytest.mark.parametrize("text", [
    "AP를 직접 투자한 LUK의 15% 만큼 DEX 증가",
    "패시브 스킬 레벨이 1 증가 (액티브 혼합형, 5차, 6차 스킬 적용안됨)",
    "완전히 새로운 옵션 +10%",
])
def test_unknown_options_are_none(text):
    assert parse_option(text, L) is None


# fixture 46명에서 나온 모든 옵션 문자열 중 None이 허용되는 것은 이 두 종류뿐이다.
ALLOWED_UNKNOWN = (re.compile(r"^AP를 직접 투자한 "), re.compile(r"^패시브 스킬 레벨이 "))


def _all_option_strings():
    for c in classes():
        eq = load(c, "character/item-equipment")
        for key in ("item_equipment", "item_equipment_preset_1", "item_equipment_preset_2", "item_equipment_preset_3"):
            for item in eq.get(key) or []:
                for n in (1, 2, 3):
                    for prefix in ("potential_option_", "additional_potential_option_"):
                        if item.get(f"{prefix}{n}"):
                            yield item[f"{prefix}{n}"]
        hy = load(c, "character/hyper-stat")
        for n in (1, 2, 3):
            for s in hy.get(f"hyper_stat_preset_{n}") or []:
                if s.get("stat_increase"):
                    yield s["stat_increase"]
        ab = load(c, "character/ability")
        for n in (1, 2, 3):
            for a in (ab.get(f"ability_preset_{n}") or {}).get("ability_info", []):
                yield a["ability_value"]
        for se in load(c, "character/set-effect").get("set_effect") or []:
            for tier in se.get("set_option_full") or []:
                yield tier["set_option"]


def test_every_fixture_option_is_recognized():
    unknown = sorted({t for t in _all_option_strings()
                      if parse_option(t, L) is None and not any(p.match(t) for p in ALLOWED_UNKNOWN)})
    assert unknown == []
