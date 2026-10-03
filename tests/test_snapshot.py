from helpers import bundle, classes
from nexon.convert import snapshot


def test_lete_presets_and_active_flags():
    s = snapshot(bundle("레테"))
    assert (s.character_class, s.level) == ("레테", 287)
    assert (s.active_equipment_preset, s.active_hyper_preset, s.active_ability_preset) == (1, 1, 1)
    assert set(s.equipment_presets) == {1, 2, 3}
    assert s.final.stat_attack_max == 67838474


def test_lete_weapon_item_stats():
    w = snapshot(bundle("레테")).equipment_presets[1]["무기"]
    assert (w.name, w.part, w.starforce) == ("제네시스 카르타", "카르타", 22)
    st = w.stats
    assert st.flat["MATK"] == 992 and st.flat["INT"] == 387 and st.flat["LUK"] == 295
    assert st.pct["MATK"] == 24          # 잠재 마력 +9% + 에디 마력 +12% + 소울 마력 +3%
    assert st.boss == 100                 # 기본 30 + 잠재 40 + 30
    assert st.ied == [20]
    assert st.dmg == 12
    assert st.pct["INT"] == 4             # 추옵 올스탯 4%
    assert st.pct["STR"] == 13            # 에디 STR +9% + 추옵 올스탯 4%
    assert w.excluded == []


def test_lete_boss_preset_ring():
    r = snapshot(bundle("레테")).equipment_presets[2]["반지4"]
    assert r.name == "어센던트 펄스 링"
    assert r.stats.flat["INT"] == 65      # 기본 59 + 에디 6
    assert r.stats.flat["MATK"] == 26     # 기본 16 + 에디 10
    assert r.stats.pct["INT"] == 21 and r.stats.pct["LUK"] == 9


def test_lete_hyper_and_ability_presets():
    s = snapshot(bundle("레테"))
    h2 = s.hyper_presets[2]
    assert h2.flat["INT"] == 180 and h2.flat["LUK"] == 120 and h2.flat["MATK"] == 18
    assert h2.boss == 47 and h2.dmg == 33 and h2.cd == 10 and h2.ied == [36]
    assert s.ability_presets[2].boss == 7
    assert s.ability_presets[1].flat.get("ATK") == 9


def test_all_fixtures_convert_and_unknowns_are_reported():
    for c in classes():
        s = snapshot(bundle(c))
        assert s.equipment_presets[s.active_equipment_preset], c
        for text in s.excluded:
            assert text.startswith(("AP를 직접 투자한 ", "패시브 스킬 레벨이 ")), (c, text)


def test_exceptional_option_is_counted():
    """item_total_option에는 익셉셔널 강화가 들어 있지 않다 (리뷰 Important 1)."""
    s = snapshot(bundle("데몬슬레이어"))
    mark = s.equipment_presets[s.active_equipment_preset]["얼굴장식"]
    assert mark.name == "루즈 컨트롤 머신 마크"
    assert mark.stats.flat["STR"] == 215 + 15
    assert mark.stats.flat["ATK"] == 157 + 10


def test_soul_option_and_soul_potential_are_counted():
    """무기 소울 옵션과 소울 잠재 (리뷰 Important 2)."""
    s = snapshot(bundle("데몬슬레이어"))
    w = s.equipment_presets[s.active_equipment_preset]["무기"]
    assert w.stats.pct["ATK"] == 46 + 3 + 4 + 3   # 잠재·에디 46 + 소울 3 + 소울 잠재 4·3
    assert w.stats.flat["LUK"] == 100 + 16


def test_lete_titles_per_preset():
    s = snapshot(bundle("레테"))
    t1, t2 = s.titles[1], s.titles[2]
    assert t1.flat["INT"] == 10 and t1.flat["MATK"] == 5      # 쑥쑥 새싹: 올스탯 10, 공마 5
    assert t2.flat["INT"] == 20 and t2.flat["MATK"] == 10 and t2.boss == 10   # 마스테리아의 소환사
    assert s.titles[3].flat == {}


def test_lete_symbols_are_flat_int():
    s = snapshot(bundle("레테"))
    assert s.symbols.flat["INT"] == 24000 and s.symbols.flat.get("LUK", 0) == 0


def test_lete_union_raider_stats():
    b = bundle("레테")
    raw = b["user/union-raider"]["union_raider_stat"]
    s = snapshot(b)
    # 독립 계산: "X 80 증가"류 + "STR, DEX, LUK 40 증가" + "ALLSTAT 50"
    def flat(stat):
        total = 0
        for t in raw:
            if t.startswith("ALLSTAT "):
                total += int(t.split()[1].rstrip(","))
            elif t == f"{stat} 80 증가":
                total += 80
            elif t == f"{stat} 100 증가":
                total += 100
            elif t.endswith(" 40 증가") and stat in t.split(" 40")[0].split(", "):
                total += 40
        return total
    for stat in ("STR", "DEX", "INT", "LUK"):
        assert s.union.flat.get(stat, 0) == flat(stat), stat
    assert s.union.boss == 6 and s.union.cd == 5 and s.union.ied == [5]
    assert s.union.flat["MATK"] == 20
    assert not [t for t in s.excluded if "이동속도" in t or "재사용" in t]
