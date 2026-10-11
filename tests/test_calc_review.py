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
    """저장된 표의 줄 합. 에픽 무기·보조무기·엠블렘 2·3번째 줄은 옛 파서가 중복 문장을 덮어써 98%대 — 다시 받기 전까지 알려진 예외."""
    import json
    import pathlib
    t = json.loads((pathlib.Path(__file__).resolve().parents[1] / "engine/data/cube_tables.json").read_text(encoding="utf-8"))
    bad = []
    for kind, grades in t["tables"].items():
        for grade, parts in grades.items():
            for part, bands in parts.items():
                for band, lines in bands.items():
                    for i, ln in enumerate(lines):
                        if abs(sum(ln.values()) - 100) > 0.01:
                            bad.append((kind, grade, part, band, i))
    known = {("잠재", "에픽", p, b, i) for p in ("무기", "보조무기", "엠블렘") for b in ("200", "250") for i in (1, 2)}
    assert set(bad) <= known, sorted(set(bad) - known)
