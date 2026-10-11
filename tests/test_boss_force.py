"""보스 목록·포스 보정(2026-10-11): engine/data/bosses.json(나무위키 보스 문서·'아케인포스'·'어센틱포스', 공지 791)과
포스 격차별 피해 비율을 보스 실딜 지수에 곱한다. 캐릭터 포스는 넥슨 character/stat의 '아케인포스'·'어센틱포스'."""
import json

import pytest
from fastapi.testclient import TestClient

from engine.stats import force as F
from engine.stats import symbols as S
from engine.stats.evaluate import evaluate_setting, rank_settings
from engine.stats.metrics import BossProfile
from engine.stats.model import StatBlock
from engine.stats.sets import SetCatalog
from helpers import bundle, classes, load
from nexon.convert import snapshot

CAT = SetCatalog.load()


def test_boss_table_has_sources_checked_date_and_unique_ids():
    raw = json.loads(F.PATH.read_text(encoding="utf-8"))
    assert raw["_checked"] == "2026-10-11"
    ids = [b["id"] for b in raw["bosses"]]
    assert len(ids) == len(set(ids)) and len(ids) >= 30
    for b in raw["bosses"]:
        assert b["source"] and all(s.startswith("https://namu.wiki/") or s.startswith("https://maplestory.nexon.com/")
                                   or s.startswith("넥슨 Open API") for s in b["source"]), b["id"]
        assert any("namu.wiki" in s for s in b["source"]), b["id"]
        assert b["defense"] > 0


def test_known_bosses_values():
    bm = F.boss("blackmage-extreme")
    assert (bm.defense, bm.arcane, bm.authentic) == (300.0, 1320, None)
    assert F.boss("lotus-extreme").defense == 380.0  # 기존 기본값 300은 익스트림 스우가 아니다(나무: 300%→380%)
    assert F.boss("lotus-hard").defense == 300.0 and F.boss("lotus-hard").arcane is None
    kl = F.boss("kaling-extreme")
    assert (kl.defense, kl.authentic, kl.symbol_region) == (380.0, 480, "도원경")
    assert F.boss("kalos-normal-1").defense == 330.0 and F.boss("kalos-normal-2").authentic == 300
    names = {b["name"] for b in F.boss_list()}
    for n in ("검은 마법사", "선택받은 세렌", "감시자 칼로스", "최초의 대적자", "카링", "림보", "스우", "진 힐라"):
        assert n in names
    with pytest.raises(KeyError):
        F.boss("없는-보스")


def test_symbol_region_matches_api_symbol_description():
    # 넥슨 심볼 설명 '성장 레벨 11 이상: <보스> 공격 시 데미지 +20%'의 보스가 그 지역 항목과 같다
    desc = {}
    for cls in classes():
        for s in load(cls, "character/symbol-equipment").get("symbol") or []:
            desc[S.split_name(s["symbol_name"])[1]] = s.get("symbol_other_effect_description") or ""
    for b in F.boss_list():
        if b.get("symbol_region"):
            assert b["name"] in desc[b["symbol_region"]], b["id"]


def test_arcane_ratio_table():
    m = F.arcane_mult
    assert m(1320, 1320) == 1.0 and m(1319, 1320) == 0.8 and m(1452, 1320) == 1.1 and m(1451, 1320) == 1.0
    assert m(1716, 1320) == 1.3 and m(1980, 1320) == 1.5 and m(3000, 1320) == 1.5
    assert m(660, 1320) == 0.7 and m(659, 1320) == 0.6 and m(132, 1320) == 0.3 and m(0, 1320) == 0.1


def test_authentic_gap_table():
    m = F.authentic_mult
    assert [m(480 + g, 480) for g in (0, -10, -50, -90, -95, -300)] == [1.0, 0.9, 0.5, 0.1, 0.05, 0.05]
    assert [m(480 + g, 480) for g in (10, 20, 40, 50, 120)] == [1.05, 1.1, 1.2, 1.25, 1.25]
    assert m(465, 480) == 0.8 and m(495, 480) == 1.05  # 표 행 사이는 바로 아래 행


def test_symbol_force_formula_matches_every_fixture_symbol():
    seen = set()
    for cls in classes():
        for s in load(cls, "character/symbol-equipment").get("symbol") or []:
            kind, _ = S.split_name(s["symbol_name"])
            assert S.force_at(kind, s["symbol_level"]) == int(s["symbol_force"]), (cls, s["symbol_name"])
            seen.add(kind)
    assert seen == {"아케인심볼", "어센틱심볼", "그랜드 어센틱심볼"}


def test_snapshot_reads_api_force_and_hyper_arcane():
    snap = snapshot(bundle("레테"))
    assert (snap.arcane_force, snap.authentic_force) == (1385, 450)
    assert snap.hyper_force == {1: 35, 2: 0, 3: 0}  # 사냥 하이퍼(1번)만 아케인포스 35
    # 다른 하이퍼 프리셋으로 바꾸면 그 몫만 바뀐다(1385 = 심볼 1320 + 하이퍼 35 + 길드 30)
    from engine.stats.snapshot import Setting
    assert F.character_force(snap, Setting(1, 2, 1)) == {"아케인": 1350, "어센틱": 450}
    assert F.character_force(snap, Setting(1, 1, 1)) == {"아케인": 1385, "어센틱": 450}


def test_force_multiplies_boss_index():
    snap = snapshot(bundle("레테"))
    kl = F.boss("kaling-extreme")
    plain = BossProfile("같은 방어율", kl.defense)
    s = rank_settings(snap, plain, CAT)[0][0]
    # 레테 어센틱 450, 카링 익스트림 480 → 격차 -30 → 70%
    assert evaluate_setting(snap, s, kl, CAT) / evaluate_setting(snap, s, plain, CAT) == pytest.approx(0.7)
    info = F.force_info(kl, F.character_force(snap, s))
    assert info == {"kind": "어센틱포스", "required": 480, "current": 450, "damage_pct": 70.0}
    assert F.force_info(plain, F.character_force(snap, s)) is None


def test_symbol_path_gain_includes_force_change():
    from engine.market.recommend import _Planner
    from engine.market.symbol_paths import symbol_paths
    snap = snapshot(bundle("레테"))
    kl = F.boss("kaling-extreme")
    plain = BossProfile("같은 방어율", kl.defense)
    s = rank_settings(snap, kl, CAT)[0][0]
    with_force = {(p["region"], p["to_level"]): p for p in symbol_paths(_Planner(snap, s, kl, CAT, None))}
    without = {(p["region"], p["to_level"]): p for p in symbol_paths(_Planner(snap, s, plain, CAT, None))}
    a, b = with_force[("세르니움", 10)], without[("세르니움", 10)]
    assert a["force_gain"] == {"어센틱": 10}
    # 세르니움 9→10: 어센틱 +10 → 격차 -30 → -20, 피해 70% → 80%
    assert 1 + a["delta_pct"] / 100 == pytest.approx((1 + b["delta_pct"] / 100) * 0.8 / 0.7)
    assert a["force_after"] == {"kind": "어센틱포스", "required": 480, "current": 460, "damage_pct": 80.0}


def test_symbol_arcane_force_not_counted_for_authentic_boss():
    from engine.market.symbol_paths import step
    sym = {"kind": "아케인심볼", "region": "에스페라", "level": 3, "growth": 0}
    assert step(sym, 3, 4, "레테")["force_gain"] == {"아케인": 10}


def _client(tmp_path):
    from server.app import create_app
    return TestClient(create_app(lambda n, d: bundle("레테"), str(tmp_path / "c.sqlite3")))


def test_bosses_api_lists_bosses(tmp_path):
    r = _client(tmp_path).get("/api/bosses").json()
    assert any(b["id"] == "kaling-extreme" and b["authentic"] == 480 for b in r["bosses"])
    assert r["checked"] == "2026-10-11"


def test_settings_with_boss_id_reports_force(tmp_path):
    c = _client(tmp_path)
    r = c.get("/api/character/x/settings?boss=kaling-extreme").json()
    assert r["boss"]["defense"] == 380.0 and r["boss"]["id"] == "kaling-extreme"
    assert r["force"] == {"kind": "어센틱포스", "required": 480, "current": 450, "damage_pct": 70.0}
    old = c.get("/api/character/x/settings?boss_defense=300").json()  # 하위 호환
    assert old["boss"]["defense"] == 300.0 and old["force"] is None
    assert c.get("/api/character/x/settings?boss=nope").status_code == 400


def test_force_override_from_user(tmp_path):
    r = _client(tmp_path).get("/api/character/x/settings?boss=kaling-extreme&authentic_force=530").json()
    assert r["force"]["current"] == 530 and r["force"]["damage_pct"] == 125.0


def test_paths_and_target_roadmap_take_boss_id(tmp_path):
    c = _client(tmp_path)
    p = c.get("/api/character/x/paths?boss=kaling-extreme").json()
    assert p["boss"]["id"] == "kaling-extreme" and p["force"]["damage_pct"] == 70.0
    ser = [x for x in p["all"] if x["path"] == "심볼" and x["region"] == "세르니움"]
    assert all(x["force_gain"] == {"어센틱": x["to_level"] * 10 - 90} for x in ser)
    t = c.get("/api/character/x/target-roadmap?boss=kaling-extreme&current_ratio=30&target_ratio=40").json()
    assert t["force"]["required"] == 480
    assert c.get("/api/character/x/target-roadmap?boss_defense=380&current_ratio=30&target_ratio=40").status_code == 200


def test_listings_body_accepts_boss_id(tmp_path):
    ring = {"slot": "반지4", "part": "반지", "name": "어센던트 펄스 링", "total": {"INT": 59, "LUK": 59, "MATK": 16},
            "potentials": ["INT +12%", "LUK +9%", "INT +9%", "마력 +10", "INT +6"], "price": 100_000_000}
    r = _client(tmp_path).post("/api/character/x/listings", json={"boss": "seren-normal-2", "listings": [ring]}).json()
    assert r["boss"]["id"] == "seren-normal-2" and r["boss"]["defense"] == 380.0
