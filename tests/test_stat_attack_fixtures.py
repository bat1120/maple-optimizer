import copy

import pytest

from engine.stats.formula import stat_attack_max
from engine.stats.jobs import UnsupportedJob, job_profile
from helpers import classes, load, weapon_bundle, weapon_samples
from nexon.convert import final_stats, num, weapon_part

# 데몬어벤져는 스탯창 HP가 표시 상한(500,000)이라 final_stats만으로는 안 맞는다 — 아래에서 따로 본다(snapshot이 HP를 되짚는다)
SUPPORTED = [c for c in classes() if c != "데몬어벤져"]


@pytest.mark.parametrize("v,expected", [
    ("129", 129.0), (129, 129.0), ("116.00", 116.0), ("-633", -633.0), (None, 0.0), ("", 0.0),
])
def test_num_is_tolerant(v, expected):  # Review Focus 4
    assert num(v) == expected


def test_final_stats_parses_lete():
    f = final_stats(load("레테", "character/stat"))
    assert f.stats["INT"] == 51968 and f.stats["LUK"] == 5960
    assert f.matk == 4973 and f.dmg == 84.0 and f.boss == 294.0 and f.fd == 188.93
    assert f.ied == 84.04 and f.stat_attack_max == 67838474 and f.combat_power == 72267618
    assert f.ap["INT"] == 1453


def test_weapon_part_lete():
    eq = load("레테", "character/item-equipment")
    assert weapon_part(eq) == "카르타"
    assert weapon_part(eq, preset=2) == "카르타"


@pytest.mark.parametrize("cls", SUPPORTED)
def test_engine_stat_attack_equals_api(cls):
    f = final_stats(load(cls, "character/stat"))
    got = stat_attack_max(f, job_profile(cls), weapon_part(load(cls, "character/item-equipment")))
    assert got == pytest.approx(f.stat_attack_max, rel=1e-4), cls


def test_unknown_job_is_unsupported():
    with pytest.raises(UnsupportedJob):
        job_profile("처음보는직업")


@pytest.mark.parametrize("level,hp,ap_hp,strength,atk,dmg,fd,expected", [
    (250, 27937, 10785, 1080, 281, 25.0, 0.0, 37968),      # 2026-11-25 실측: HP가 표시 상한 아래인 두 캐릭터의 스탯창
    (260, 294486, 19710, 935, 392, 66.0, 15.0, 677225),
])
def test_demon_avenger_formula_matches_uncapped_stat_windows(level, hp, ap_hp, strength, atk, dmg, fd, expected):
    import math

    from engine.stats.formula import demon_avenger_hp, demon_avenger_pure_hp
    from engine.stats.model import FinalStats
    pure = demon_avenger_pure_hp(ap_hp, level)
    f = FinalStats(stats={"STR": strength, "DEX": 0, "INT": 0, "LUK": 0, "HP": hp}, ap={"HP": pure}, atk=atk, matk=0, dmg=dmg, boss=0, fd=fd,
                   cd=0, cr=0, ied=0, stat_attack_min=0, stat_attack_max=expected, combat_power=0)
    assert math.floor(stat_attack_max(f, job_profile("데몬어벤져"), "데스페라도")) == expected       # 1 단위까지
    # 스탯공격력에서 HP를 되짚으면 ±3.5 안(⌊추가 HP ÷ 3.5⌋까지만 알 수 있다)
    assert abs(demon_avenger_hp(expected, pure, strength, atk, dmg, fd, "데스페라도") - hp) <= 3.5


def test_demon_avenger_capped_hp_is_recovered_from_stat_attack():
    from helpers import bundle
    from nexon.convert import snapshot
    snap = snapshot(bundle("데몬어벤져"))
    f = snap.final
    assert load("데몬어벤져", "character/stat") and f.stats["HP"] > 500_000          # 스탯창은 500,000(표시 상한)
    assert f.ap["HP"] == 22701 + 15 * 300 + 344                                     # 순수 HP = AP 배분 + 레벨 기본
    got = stat_attack_max(f, job_profile("데몬어벤져"), snap.equipment_presets[snap.active_equipment_preset]["무기"].part)
    assert got == pytest.approx(f.stat_attack_max, rel=1e-6)


@pytest.mark.parametrize("missing", ["최종 데미지", "데미지", "마력", "INT", "최대 스탯공격력"])
def test_final_stats_missing_required_stat_raises(missing):
    """필수 스탯이 빠지면 0으로 메우지 않고 멈춘다 (리뷰 Important 3)."""
    data = copy.deepcopy(load("레테", "character/stat"))
    data["final_stat"] = [x for x in data["final_stat"] if x["stat_name"] != missing]
    with pytest.raises(ValueError, match=missing):
        final_stats(data)


def test_weapon_samples_cover_four_more_weapons():
    parts = {name.rsplit("_", 1)[0] for name in weapon_samples()}
    assert {"한손검", "한손도끼", "두손둔기", "건틀렛 리볼버"} <= parts


@pytest.mark.parametrize("name", weapon_samples())
def test_weapon_sample_stat_attack_equals_api(name):
    b = weapon_bundle(name)
    f = final_stats(b["character/stat"])
    got = stat_attack_max(f, job_profile(b["character/stat"]["character_class"]), weapon_part(b["character/item-equipment"]))
    assert got == pytest.approx(f.stat_attack_max, rel=1e-4), name


def test_demon_avenger_conversion_star_force_stacks_by_tier():
    """컨버전 스타포스: 구간별로 쌓인다(1~10성 35, 11~35성 60, 36~60성 80, 61~90성 100 …, 최대 550성)."""
    from engine.stats.formula import demon_avenger_conversion_hp as conv
    assert conv(0) == 0 and conv(10) == 350 and conv(55) == 350 + 25 * 60 + 20 * 80 and conv(63) == 350 + 1500 + 2000 + 3 * 100
    assert conv(550) == conv(9999) and conv(436) - conv(435) == 170


@pytest.mark.parametrize("stars,pure,item_flat,union_flat,pct,symbols,hp", [
    (55, 14879, 2670, 4000, 8.0, 0, 27937),          # 2026-11-25 실측: HP가 표시 상한 아래인 두 캐릭터(250·260레벨)
    (63, 23954, 28380, 0, 121.0, 168000, 294486),
])
def test_demon_avenger_hp_is_explained_by_visible_sources(stars, pure, item_flat, union_flat, pct, symbols, hp):
    """순수 HP + 장비 + 컨버전 스타포스 + 이너 스트렝스에 HP%를 곱하고 심볼을 더하면 스탯창 HP와 3% 안으로 맞는다(나머지는 잔차)."""
    from engine.stats.formula import DA_SKILL_HP, demon_avenger_conversion_hp
    base = pure + item_flat + demon_avenger_conversion_hp(stars) + DA_SKILL_HP
    assert (base * (1 + pct / 100) + symbols + union_flat) == pytest.approx(hp, rel=0.03)

