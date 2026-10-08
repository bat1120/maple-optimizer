"""추옵(환생의 불꽃·메소 재설정) 경로(2026-10-08): 확률표 engine/data/flame.json + 넥슨 API 실측 검산."""
import glob
import json
import math
import pathlib

import pytest

from engine.market.flame import (DATA, POOL, TIERS, amounts, current_lines, explains, reach_table, single_const,
                                 double_const)

FIX = pathlib.Path(__file__).parent / "fixtures" / "characters"
API_KEYS = {"str", "dex", "int", "luk", "attack_power", "magic_power", "all_stat", "max_hp", "max_mp", "armor", "speed",
            "jump", "equipment_level_decrease"}


def _fixture_items():
    for f in sorted(glob.glob(str(FIX / "*" / "character_item-equipment.json"))):
        for it in json.loads(pathlib.Path(f).read_text(encoding="utf-8")).get("item_equipment") or []:
            add = {k: v for k, v in (it.get("item_add_option") or {}).items() if str(v) not in ("0", "")}
            if add and it["item_equipment_slot"] != "무기" and it["item_equipment_part"] not in ("대검", "태도"):
                yield it, add


def test_tier_tables_sum_to_one_and_match_source():
    for name, t in TIERS.items():
        assert sum(t.values()) == pytest.approx(1.0), name
    assert TIERS["메소 재설정"] == {4: 0.29, 5: 0.45, 6: 0.25, 7: 0.01}
    assert DATA["boss_lines"] == 4 and len(POOL) == 19


def test_constants():
    assert (single_const(140), double_const(140)) == (8, 4)
    assert (single_const(160), double_const(160)) == (9, 5)
    assert (single_const(200), double_const(200)) == (11, 6)
    assert (single_const(250), double_const(250)) == (12, 7)  # 250레벨 단일 상수는 13이 아니라 12(실측)
    assert amounts("INT+LUK", 5, 200) == {"INT": 30, "LUK": 30}
    assert amounts("마력", 6, 200) == {"MATK": 6} and amounts("올스탯%", 7, 200) == {"ALL%": 7}
    assert amounts("이동속도", 7, 200) == {}


def test_value_formulas_explain_every_measured_item():
    """넥슨 API 실측: 무기를 뺀 추옵 있는 장비 전부가 '4줄 이하 · 서로 다른 옵션 · 1~7단계'로 정확히 나뉜다."""
    n = 0
    for it, add in _fixture_items():
        level = int(it["item_base_option"]["base_equipment_level"])
        assert explains(add, level), (it["item_name"], level, add)
        n += 1
    assert n >= 500


def test_pool_contains_every_measured_option():
    seen = {k for _, add in _fixture_items() for k in add}
    assert seen <= API_KEYS  # API 키 13종 = 풀 19종(이중 스탯 6종을 단일 키로 나눠 보여 준다)


def test_current_lines_reads_add_option():
    lines = current_lines({"int": "44", "luk": "20", "armor": "40", "all_stat": "5"}, 150)
    assert lines == {"INT": 44.0, "LUK": 20.0, "ALL%": 5.0}


def test_reach_probability_exact_for_one_option():
    """INT 단일 한 줄만 쓸모 있을 때: 그 줄이 4줄 안에 들 확률 4/19 × 7단계 1%."""
    level = 200
    w = {"INT": 1.0}
    table = reach_table(w, level, "메소 재설정")
    top = max(s for s, _ in table)
    assert top == pytest.approx(single_const(level) * 7 + double_const(level) * 7 * 3)  # 단일 + INT 들어간 이중 3종
    only_single_7 = [p for s, p in table if s >= single_const(level) * 7 - 1e-9]
    assert only_single_7[-1] > 0
    # 전체 확률 합 = 1
    assert sum(p for _, p in _pmf(table)) == pytest.approx(1.0)
    # 점수 0(쓸모 있는 줄 없음) 확률 = C(15,4)/C(19,4)
    assert dict(_pmf(table))[0.0] == pytest.approx(math.comb(15, 4) / math.comb(19, 4))


def _pmf(table):
    """reach_table(점수 내림차순, P(점수 ≥ s)) → (점수, 확률) 목록."""
    out, prev = [], 0.0
    for s, p in table:
        out.append((s, p - prev))
        prev = p
    return out


def test_paths_api_includes_flame_with_reset_price(tmp_path):
    from fastapi.testclient import TestClient
    from helpers import bundle
    from server.app import create_app
    c = TestClient(create_app(lambda n, d: bundle("레테"), str(tmp_path / "c.sqlite3")))
    none = c.get("/api/character/x/paths").json()
    assert not [p for p in none["all"] if p["path"] == "추옵"]  # 재설정 1회 값이 없으면 만들지 않는다
    r = c.get("/api/character/x/paths?flame_price=5000000").json()
    fl = [p for p in r["all"] if p["path"] == "추옵"]
    assert fl, "추옵 경로가 있어야 한다"
    assert r["events"]["flame_price"] == 5e6
    for p in fl:
        assert p["slot"] != "무기" and not p["name"].startswith("도전자의")
        assert 0 < p["reach_probability"] <= 1
        assert p["cost"] == pytest.approx(p["expected_tries"] * 5e6) and p["expected_tries"] == pytest.approx(1 / p["reach_probability"])
        assert p["delta_pct"] > 0 and p["unverified"]
