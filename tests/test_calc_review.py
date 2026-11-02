"""계산식 검토(2026-10-11) 후속: 검토에서 재현된 버그를 고정한다.
- 14성 이하 템 스타포스 기대값이 KeyError로 죽던 것(파괴 확률 0인 성에서도 복구 메소 표를 찾음)
- 큐브로 줄을 바꾼 템이 스타포스·추옵 정보를 잃어 로드맵에서 그 부위 스타포스가 끊기던 것
- 일반 반지 매물을 특수 반지(리스트레인트 등) 칸에 끼우라고 추천하던 것
- 보정에서 HEXA 주력 스탯(%미적용)을 빼먹어 주스탯 잔차%가 부풀던 것
- 샤이닝 스타포스 = 30% 할인 + 21성 이하 파괴 30% 감소(나무위키 '메이플스토리/스타포스 강화'), 나머지는 따로
"""
import pytest

from helpers import bundle
from engine.enhance.starforce import StarforceConditions, expected_totals
from engine.enhance.starforce_stats import eligible
from engine.market.events import Events
from engine.market.paths import upgrade_paths
from engine.market.recommend import SWAP, _Planner
from engine.stats.evaluate import rank_settings
from engine.stats.metrics import BossProfile
from engine.stats.residual import calibrate
from engine.stats.sets import SetCatalog
from nexon.convert import snapshot

CAT, BOSS = SetCatalog.load(), BossProfile("기준", 300.0)


@pytest.mark.parametrize("start", [0, 10, 12, 14])
def test_starforce_totals_from_low_stars(start):
    t = expected_totals(200, start, 17, StarforceConditions())
    from_15 = expected_totals(200, 15, 17, StarforceConditions())
    assert t["meso"] > from_15["meso"] and t["destroys"] == pytest.approx(from_15["destroys"], rel=1e-6)


def test_cube_swap_keeps_starforce_and_flame_fields():
    snap = snapshot(bundle("레테"))
    pl = _Planner(snap, rank_settings(snap, BOSS, CAT)[0][0], BOSS, CAT, None)
    it = next(it for it in pl.raw.values() if eligible(it) and it.potentials and it.core is not None)
    new = SWAP["잠재"](it, it.potentials, snap.level)
    assert eligible(new)
    for f in ("sf_option", "scroll_attack", "amazing", "add_option", "base_attack", "special_ring_level", "icon"):
        assert getattr(new, f) == getattr(it, f), f


RING = {"category": "반지", "part": "반지", "name": "고귀한 이피아의 반지", "starforce": 10, "level": 140, "price": 3e8,
        "total": {"STR": 40, "DEX": 40, "INT": 40, "LUK": 40, "ATK": 10, "MATK": 10},
        "potential_lines": ["LUK +9%", "LUK +6%"], "potential_grade": "유니크"}


def test_plain_ring_listing_never_replaces_special_ring():
    snap = snapshot(bundle("나이트워커"))
    worn = snap.equipment_presets[snap.active_equipment_preset]
    special = {s for s, it in worn.items() if s.startswith("반지") and it.special_ring_level}
    assert special  # 픽스처: 리스트레인트 링
    r = upgrade_paths(snap, rank_settings(snap, BOSS, CAT)[0][0], BOSS, CAT, [RING])
    assert not [p for p in r["all"] if p["path"] == "구매" and p["slot"] in special]


def test_vision_plain_ring_never_lands_on_special_ring_slot():
    from server.service import vision_items
    snap = snapshot(bundle("나이트워커"))
    worn = snap.equipment_presets[snap.active_equipment_preset]
    special = {s for s, it in worn.items() if s.startswith("반지") and it.special_ring_level}
    x = {**RING, "potentials": RING["potential_lines"], "signature": "r1"}
    rows = vision_items(snap, None, 300.0, [x], set())
    assert rows and rows[0].get("slot") not in special


def test_calibration_counts_hexa_main_stat_as_flat_without_pct():
    snap = snapshot(bundle("레테"))
    assert snap.hexa_stat
    cal = calibrate(snap, CAT)
    assert cal.stat_pct["INT"] == pytest.approx(47.07, abs=0.5)  # HEXA 주력 2,500(%미적용)을 빼면 이 값(검토 실측)


def test_shining_is_discount_and_destroy_down_only():
    e = Events.parse("shining")
    assert e.discount30 and e.destroy_down30
    assert not e.guarantee_5_10_15 and not e.restore_discount20


def _page(rows_per_table):
    out = ""
    for name, rows in zip(("첫", "두", "세"), rows_per_table):
        out += f"<th>{name} 번째 옵션</th>" + "".join(f"<td>{o}</td> <td>{v}%</td>" for o, v in rows)
    return out


def test_cube_table_parser_sums_repeated_lines():
    """공식표는 하위 등급 몫과 그 등급 몫을 같은 문장으로 따로 싣는다 — 덮어쓰지 말고 더한다(에픽 무기 방무 +15%)."""
    import sys
    sys.path.insert(0, "tools")
    from fetch_cube_tables import parse
    t = [("공격력 : +9%", "50"), ("몬스터 방어율 무시 : +15%", "20"), ("몬스터 방어율 무시 : +15%", "30")]
    got = parse(_page([t, t, t]))
    assert got[1]["몬스터 방어율 무시 : +15%"] == pytest.approx(50.0)
    with pytest.raises(ValueError):
        parse(_page([[("공격력 : +9%", "50")]] * 3))  # 줄 합이 100%가 아니면 형식이 바뀐 것


def test_saved_cube_tables_lines_sum_to_100():
    """저장된 표의 모든 줄 합이 100%(2026-10-11 다시 받음 — 옛 파서가 덮어쓴 에픽 무기 방무 +15% 0.87% → 2.50%)."""
    import json
    import pathlib
    t = json.loads((pathlib.Path(__file__).resolve().parents[1] / "engine/data/cube_tables.json").read_text(encoding="utf-8"))
    bad = [(k, g, p, b, i) for k, grades in t["tables"].items() for g, parts in grades.items() for p, bands in parts.items()
           for b, lines in bands.items() for i, ln in enumerate(lines) if abs(sum(ln.values()) - 100) > 0.01]
    assert not bad, bad
    assert t["tables"]["잠재"]["에픽"]["무기"]["200"][1]["몬스터 방어율 무시 +15%"] == pytest.approx(2.5023)


# ── 과대평가 6건(2026-10-11 검토 2차) ──
def test_hexa_core_ratio_ignores_normal_monster_damage():
    """마스터리 VI 문장의 '일반 몬스터 공격 시 데미지 N%p'는 보스 실딜과 무관 — 평균에서 뺀다(레테 임프린트 VI)."""
    from engine.market.hexa_core_paths import ratio
    snap = snapshot(bundle("레테"))
    sk = snap.hexa_skills["임프린트 VI"]
    assert ratio(sk["effect"], sk["next"]) == pytest.approx((300 / 295 + 217 / 215) / 2)
    assert ratio("A 10% 확률로 B 100%의 데미지", "A 20% 확률로 B 110%의 데미지") == pytest.approx(1.1)  # 확률 %도 뺀다


def test_origin_ascent_bonus_ied_is_additive_with_skill_ied():
    """나무위키 HEXA 매트릭스: 방무 보너스는 스킬 방무와 합적용(어센트 60→70→80→100). 보뎀은 스킬 보뎀 위에 더한다."""
    from engine.market.hexa_core_paths import bonus_factor
    from engine.stats.model import FinalStats
    final = FinalStats(stats={}, ap={}, atk=0, matk=0, dmg=100.0, boss=300.0, fd=0, cd=0, cr=0, ied=90.0,
                       stat_attack_min=0, stat_attack_max=0, combat_power=0)
    desc = ("[마스터 레벨 : 30]\n10레벨 : 몬스터 방어율 무시 10% 증가, 보스 몬스터 공격 시 데미지 10% 증가\n"
            "20레벨 : 몬스터 방어율 무시 10% 증가, 보스 몬스터 공격 시 데미지 10% 증가\n30레벨 : 몬스터 방어율 무시 20% 증가")
    eff = "몬스터 방어율 60% 추가 무시, 보스 몬스터 공격 시 데미지 40% 증가"
    d, c = 3.0, 0.1
    ied10 = (1 - d * c * (1 - 0.70)) / (1 - d * c * (1 - 0.60))
    assert bonus_factor(desc, 10, final, 300.0, eff) == pytest.approx(ied10 * (540 + 10) / 540)
    ied30 = (1 - d * c * (1 - 1.00)) / (1 - d * c * (1 - 0.80))  # 10·20레벨 보너스까지 이미 80%
    assert bonus_factor(desc, 30, final, 300.0, eff) == pytest.approx(ied30)


def test_hexa_stat_sub_levels_capped_at_10():
    from engine.market.hexa_paths import _spread
    assert _spread((10, 3), 5) == (10, 8)
    assert _spread((4, 6), 4) == (6, 8)
    assert _spread((9, 9), 4) == (10, 10)


def test_setting_comparison_counts_crit_rate_loss():
    import copy
    import dataclasses
    from engine.stats.evaluate import evaluate_setting, swap_item
    from engine.stats.residual import preset_items
    snap = snapshot(bundle("레테"))
    setting = snap.active_setting
    base = evaluate_setting(snap, setting, BOSS, CAT)
    it = preset_items(snap, setting.equipment)["모자"]
    stats = copy.deepcopy(it.stats)
    stats.cr -= 100  # 100% 아래로 떨어질 만큼(여유분 안의 감소는 손해가 아니다 — 2026-10-17)
    worse = dataclasses.replace(it, stats=stats)
    assert swap_item(snap, setting, "모자", worse, BOSS, CAT) < base * 0.99


def test_cube_cost_counts_lines_rolled_at_tier_up():
    """등급이 오를 때 나오는 줄도 목표 등급 표에서 뽑힌다 — 그 한 번도 성공 기회(마지막 항은 (1−p)/p회)."""
    from engine.market.cube_value import expected_cost, reset_cost_for, tier_up_tries
    up = tier_up_tries(0.014, 107).mean * reset_cost_for("잠재", 150, "유니크")
    leg = reset_cost_for("잠재", 150, "레전드리")
    assert expected_cost("잠재", 150, "유니크", "레전드리", 0.02) == pytest.approx(up + leg * (1 / 0.02 - 1))
    assert expected_cost("잠재", 150, "유니크", "유니크", 0.01) == pytest.approx(reset_cost_for("잠재", 150, "유니크") / 0.01)


def test_hexa_reset_expectation_converges_to_namu_table():
    from engine.stats.hexa import reach_cost
    assert reach_cost(10, 0.0)["fragments"] == pytest.approx(145148.2, rel=1e-5)  # 나무위키 기대값표 10레벨 '14만 5148개'


def test_xenon_counts_all_three_main_stats_as_useful():
    """제논은 STR·DEX·LUK 모두 주스탯 — DEX%·LUK% 줄도 큐브 도달 확률에 넣는다(2026-10-17 점검: 상의 레전 2줄 34.55억 → 23.78억)."""
    from engine.market.recommend import _Planner
    snap = snapshot(bundle("제논"))
    setting = rank_settings(snap, BOSS, CAT)[0][0]
    pl = _Planner(snap, setting, BOSS, CAT, None)
    assert pl.is_useful("DEX +9%") and pl.is_useful("LUK +9%") and pl.is_useful("STR +9%")
