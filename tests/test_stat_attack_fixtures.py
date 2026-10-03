import pytest

from engine.stats.formula import stat_attack_max
from engine.stats.jobs import UnsupportedJob, job_profile
from helpers import classes, load
from nexon.convert import final_stats, num, weapon_part

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


def test_demon_avenger_is_explicitly_unsupported():
    with pytest.raises(UnsupportedJob):
        job_profile(load("데몬어벤져", "character/stat")["character_class"])
