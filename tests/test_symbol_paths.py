"""심볼 경로(2026-10-11): engine/data/symbol_tables.json(나무위키 성장표·공식 공지) — 픽스처 실측으로 표·스탯 공식을 검산하고,
심볼마다 다음 레벨(최대 레벨까지 한 단계씩)의 실딜·강화 메소·필요 심볼 개수를 낸다."""
import json
import math

import pytest

from engine.stats import symbols as S
from engine.stats.evaluate import rank_settings
from engine.stats.metrics import BossProfile
from engine.stats.model import StatBlock
from engine.stats.sets import SetCatalog
from helpers import bundle, classes, load
from nexon.convert import snapshot

CAT, BOSS = SetCatalog.load(), BossProfile("기준", 300.0)
STAT_KEYS = (("symbol_str", "STR"), ("symbol_dex", "DEX"), ("symbol_int", "INT"), ("symbol_luk", "LUK"), ("symbol_hp", "HP"))


def _all_fixture_symbols():
    for cls in classes():
        for s in load(cls, "character/symbol-equipment").get("symbol") or []:
            yield cls, s


def test_table_has_sources_and_checked_date():
    raw = json.loads(S.PATH.read_text(encoding="utf-8"))
    assert raw["_checked"] == "2026-10-11"
    assert any("namu.wiki" in s for s in raw["_source"]) and any("maplestory.nexon.com" in s for s in raw["_source"])
    assert S.max_level("아케인심볼") == 20 and S.max_level("어센틱심볼") == 11 and S.max_level("그랜드 어센틱심볼") == 11


def test_required_growth_matches_every_fixture_symbol():
    # 넥슨 symbol_require_growth_count = 지금 레벨 → 다음 레벨 필요 성장치(최대 레벨에서도 수식값을 준다 — 그건 건너뛴다)
    seen = 0
    for _, s in _all_fixture_symbols():
        kind, _ = S.split_name(s["symbol_name"])
        lv = s["symbol_level"]
        if lv < S.max_level(kind):
            assert S.need(kind, lv) == s["symbol_require_growth_count"], s["symbol_name"]
            seen += 1
    assert seen > 10


def test_stat_formula_matches_every_fixture_symbol_including_xenon_and_demon_avenger():
    checked = set()
    for cls, s in _all_fixture_symbols():
        kind, _ = S.split_name(s["symbol_name"])
        got = S.stats_at(kind, s["symbol_level"], cls)
        want = {key: float(s[k]) for k, key in STAT_KEYS if float(s[k])}
        assert got == want, (cls, s["symbol_name"], s["symbol_level"])
        checked.add((kind, cls in ("제논", "데몬어벤져")))
    assert ("아케인심볼", True) in checked and ("어센틱심볼", True) in checked  # 제논·데몬어벤져 예외까지


def test_meso_table_values_from_namu():
    assert S.meso("어센틱심볼", "세르니움", 1) == 36_500_000
    assert S.meso("어센틱심볼", "세르니움", 9) == 709_000_000
    assert S.meso("어센틱심볼", "카르시온", 10) == 1_782_000_000
    assert S.meso("아케인심볼", "에스페라", 19) == 51_810_000
    assert S.meso("그랜드 어센틱심볼", "탈라하트", 1) == 113_600_000
    # 누적 메소(나무 표 11레벨 칸)와 레벨별 합이 같다
    assert sum(S.meso("어센틱심볼", "오디움", lv) for lv in range(1, 11)) == 5_573_300_000


def test_snapshot_keeps_symbol_list():
    snap = snapshot(bundle("레테"))
    names = [s["name"] for s in snap.symbol_items]
    assert "어센틱심볼 : 세르니움" in names and len(names) == 12
    ser = next(s for s in snap.symbol_items if s["name"] == "어센틱심볼 : 세르니움")
    assert (ser["kind"], ser["region"], ser["level"], ser["growth"], ser["require_growth"]) == ("어센틱심볼", "세르니움", 9, 646, 909)
    assert "선택받은 세렌" in ser["other_effect"]
    assert snap.symbols.flat["INT"] == sum(s["stats"].get("INT", 0) for s in snap.symbol_items)


def _planner():
    from engine.market.recommend import _Planner
    snap = snapshot(bundle("레테"))
    return snap, _Planner(snap, rank_settings(snap, BOSS, CAT)[0][0], BOSS, CAT, None)


def test_symbol_paths_for_lete():
    from engine.market.symbol_paths import symbol_paths
    snap, pl = _planner()
    ps = symbol_paths(pl)
    assert ps and all(p["path"] == "심볼" and p["slot"] == "심볼" for p in ps)
    assert not [p for p in ps if p["kind"] == "아케인심볼"]  # 아케인은 전부 20레벨
    ser = [p for p in ps if p["region"] == "세르니움"]
    assert [(p["from_level"], p["to_level"]) for p in ser] == [(9, 10), (9, 11)]
    one = ser[0]
    assert one["cost"] == one["meso"] == 709_000_000
    assert (one["need_symbols"], one["growth"], one["remaining_symbols"]) == (909, 646, 263)
    assert one["daily"] == 30 and one["days"] == math.ceil(263 / 30)
    assert one["stat_gain"] == {"INT": 200.0}
    want = (pl.ev.index(pl.items, {"nopct": StatBlock(flat={"INT": 200.0})}) / pl.base - 1) * 100
    assert one["delta_pct"] == pytest.approx(want) and one["delta_pct"] > 0
    assert one["per_100m"] == pytest.approx(one["delta_pct"] / 7.09)
    two = ser[1]
    assert two["cost"] == 709_000_000 + 792_000_000 and two["need_symbols"] == 909 + 1100
    assert two["delta_pct"] > one["delta_pct"]
    assert "선택받은 세렌" in two["max_effect"] and one["max_effect"] is None  # 11레벨 효과는 표시만(실딜 미반영)
    # 아르테리아 7레벨: 성장치 583 ≥ 581 → 다음 레벨은 메소만
    art = next(p for p in ps if p["region"] == "아르테리아" and p["to_level"] == 8)
    assert art["remaining_symbols"] == 0 and art["days"] == 0
    # 오디움 7레벨 성장치 728: 8레벨(581)은 다 찼고 9레벨까지는 581+736−728 남는다
    odi = next(p for p in ps if p["region"] == "오디움" and p["to_level"] == 9)
    assert odi["remaining_symbols"] == 581 + 736 - 728


def test_grand_symbols_have_no_damage_path():
    from engine.market.symbol_paths import symbol_paths
    from engine.market.recommend import _Planner
    snap = snapshot(bundle("라라"))  # 그랜드 어센틱 9레벨
    pl = _Planner(snap, rank_settings(snap, BOSS, CAT)[0][0], BOSS, CAT, None)
    assert not [p for p in symbol_paths(pl) if p["kind"] == "그랜드 어센틱심볼"]


def test_xenon_gain_is_each_of_str_dex_luk():
    assert S.stats_at("어센틱심볼", 8, "제논") == {"STR": 66 * 19.0, "DEX": 66 * 19.0, "LUK": 66 * 19.0}
    assert S.gain("어센틱심볼", 7, 8, "제논") == {"STR": 132.0, "DEX": 132.0, "LUK": 132.0}
    assert S.gain("아케인심볼", 3, 5, "레테") == {"INT": 200.0}


def test_upgrade_paths_include_symbols():
    from engine.market.paths import upgrade_paths
    snap = snapshot(bundle("레테"))
    r = upgrade_paths(snap, rank_settings(snap, BOSS, CAT)[0][0], BOSS, CAT, [])
    assert any(p["path"] == "심볼" for p in r["all"])


def test_target_roadmap_levels_symbols_one_at_a_time():
    from engine.market.events import Events
    from engine.market.target_roadmap import target_roadmap
    snap = snapshot(bundle("레테"))
    setting = rank_settings(snap, BOSS, CAT)[0][0]
    r = target_roadmap(snap, setting, BOSS, CAT, Events(), [], 34.52, 80.0)
    sym = [s for s in r["steps"] if s["path"] == "심볼"]
    assert sym
    by = {}
    for s in sym:
        by.setdefault(s["name"], []).append((s["from_level"], s["to_level"]))
    for name, seq in by.items():
        assert all(b == a + 1 for a, b in seq), (name, seq)  # 한 레벨씩
        assert all(seq[i][1] == seq[i + 1][0] for i in range(len(seq) - 1)), (name, seq)  # 이어서
    assert r["symbols"] == {n: seq[-1][1] for n, seq in by.items()}


def test_paths_api_returns_symbol_rows_with_cost_text(tmp_path):
    from fastapi.testclient import TestClient
    from server.app import create_app
    c = TestClient(create_app(lambda n, d: bundle("레테"), str(tmp_path / "c.sqlite3")))
    r = c.get("/api/character/x/paths").json()
    sym = [p for p in r["all"] if p["path"] == "심볼"]
    assert sym and all(p["cost_text"] and p["need_symbols"] > 0 for p in sym)
    assert "심볼" in r["note"]


def test_service_roadmap_puts_symbol_stat_into_scouter_nopct():
    from server.service import target_roadmap as service_target
    out = service_target(snapshot(bundle("레테")), 300.0, [], current_ratio=34.52, target_ratio=80.0)
    sym = [s for s in out["steps"] if s["path"] == "심볼"]
    assert sym and all(s["cost_text"] for s in sym)
    gained = sum(s["stat_gain"].get("INT", 0) for s in sym)
    # 조각 값이 없어 HEXA 스탯 단계가 없다 — '% 미적용' 칸은 심볼 몫 그대로
    assert out["scouter"]["fields"]["INT|% 미적용"] == pytest.approx(gained)
    assert "심볼" in out["note"]
