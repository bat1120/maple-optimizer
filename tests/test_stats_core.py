import pytest

from engine.options import StatLine
from engine.stats.formula import stat_attack_max, stat_value
from engine.stats.jobs import UnsupportedJob, job_profile
from engine.stats.model import FinalStats, StatBlock
from engine.stats.weapons import UnknownWeapon, weapon_constant


def final(**kw):
    base = dict(
        stats={"STR": 0, "DEX": 0, "INT": 0, "LUK": 0, "HP": 0}, ap={}, atk=0, matk=0,
        dmg=0.0, boss=0.0, fd=0.0, cd=0.0, cr=0.0, ied=0.0,
        stat_attack_min=0, stat_attack_max=0, combat_power=0,
    )
    base.update(kw)
    return FinalStats(**base)


def test_statblock_add_and_sum():
    a = StatBlock()
    a.add(StatLine("INT", 12, True))
    a.add(StatLine("INT", 6, False))
    a.add(StatLine("BOSS", 40, True))
    a.add(StatLine("IED", 20, True))
    b = StatBlock()
    b.add(StatLine("INT", 9, True))
    b.add(StatLine("IED", 35, True))
    c = a + b
    assert c.pct["INT"] == 21 and c.flat["INT"] == 6 and c.boss == 40
    assert c.ied == [20, 35]
    assert c.ied_total() == pytest.approx(100 * (1 - 0.8 * 0.65))
    assert a.ied == [20]  # __add__는 원본을 바꾸지 않는다


def test_job_profiles():
    lete = job_profile("레테")
    assert (lete.mains, lete.subs, lete.attack) == (("INT",), ("LUK",), "MATK")
    assert job_profile("렌").mains == ("STR",)
    assert job_profile("섀도어").subs == ("DEX", "STR")
    assert job_profile("제논").mains == ("STR", "DEX", "LUK") and job_profile("제논").subs == ()


def test_unsupported_and_unknown_jobs_raise():  # Review Focus 3
    with pytest.raises(UnsupportedJob):
        job_profile("데몬어벤져")
    with pytest.raises(UnsupportedJob):
        job_profile("처음보는직업")


def test_weapon_constants():
    assert weapon_constant("카르타") == 1.2
    assert weapon_constant("아대") == 1.75
    assert weapon_constant("에너지소드") == 1.3125
    with pytest.raises(UnknownWeapon):  # Review Focus 3
        weapon_constant("처음보는무기")


def test_stat_attack_matches_ingame_screenshots():
    """2026-10-03 인게임 스탯창(레테, 카르타) 두 장."""
    lete = job_profile("레테")
    hunting = final(stats={"STR": 3413, "DEX": 3059, "INT": 51896, "LUK": 5960, "HP": 64856},
                    matk=4852, dmg=84.0, fd=186.70)
    boss = final(stats={"STR": 3540, "DEX": 3397, "INT": 56012, "LUK": 6768, "HP": 66150},
                 matk=5008, dmg=91.0, fd=186.70)
    assert stat_value(hunting, lete) == pytest.approx((51896 * 4 + 5960) / 100)
    assert stat_attack_max(hunting, lete, "카르타") == pytest.approx(65_590_276, rel=1e-4)
    assert stat_attack_max(boss, lete, "카르타") == pytest.approx(75_958_618, rel=1e-4)
