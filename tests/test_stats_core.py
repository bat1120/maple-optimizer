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
    assert job_profile("데몬어벤져").mains == ("HP",) and job_profile("데몬어벤져").subs == ("STR",)   # 2026-11-25 지원
    with pytest.raises(UnsupportedJob):
        job_profile("처음보는직업")


def test_weapon_constants():
    assert weapon_constant("카르타") == 1.2
    assert weapon_constant("아대") == 1.75
    assert weapon_constant("에너지소드") == 1.3125
    # 히어로의 두손검은 1.44(2026-11-24 실측) — 다른 직업의 두손검은 그대로 1.34
    assert weapon_constant("두손검", "히어로") == 1.44 and weapon_constant("두손검", "카이저") == 1.34 == weapon_constant("두손검")
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


def test_statblock_add_copies_without_sharing():
    """2026-11-25: 더하기를 deepcopy 대신 얕은 복사로 바꿨다(속도). 결과가 같고, 더한 결과를 고쳐도 원래 것이 안 바뀌어야 한다."""
    import copy

    from engine.options import StatLine
    from engine.stats.model import StatBlock
    a = StatBlock(flat={"STR": 10.0, "ATK": 5.0}, pct={"STR": 9.0}, dmg=3.0, boss=30.0, cd=8.0, cr=5.0, fd=1.5, ied=[30.0, 20.0])
    b = StatBlock(flat={"STR": 1.5, "HP": 100.0}, pct={"ALL": 6.0}, boss=10.0, ied=[15.0])
    a0, b0 = copy.deepcopy(a), copy.deepcopy(b)
    out = a + b
    assert out == StatBlock(flat={"STR": 11.5, "ATK": 5.0, "HP": 100.0}, pct={"STR": 9.0, "ALL": 6.0}, dmg=3.0, boss=40.0, cd=8.0, cr=5.0,
                            fd=1.5, ied=[30.0, 20.0, 15.0])
    out.add(StatLine("STR", 7.0, False))
    out.add(StatLine("IED", 40.0, True))
    out.pct["STR"] += 1
    assert a == a0 and b == b0


def test_parse_option_cache_returns_fresh_lists():
    """2026-11-25: 옵션 줄 풀이를 기억해 두고 다시 쓴다(속도). 받은 목록을 고쳐도 다음 결과가 안 바뀌고, 레벨이 다르면 따로 푼다."""
    from engine.options import StatLine, parse_option
    first = parse_option("올스탯 +9%", 200)
    assert first == [StatLine(k, 9.0, True) for k in ("STR", "DEX", "INT", "LUK")]
    first.clear()
    assert len(parse_option("올스탯 +9%", 200)) == 4
    assert parse_option("캐릭터 기준 9레벨 당 STR +2", 200) == [StatLine("STR", 44, False)]
    assert parse_option("캐릭터 기준 9레벨 당 STR +2", 250) == [StatLine("STR", 54, False)]
    assert parse_option("처음 보는 옵션 줄", 200) is None and parse_option("메소 획득량 +20%", 200) == []
