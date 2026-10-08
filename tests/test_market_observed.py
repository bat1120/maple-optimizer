"""관측 시세: 사용자가 본 경매장 화면에서 읽은 매물 가격을 쌓아, 로드맵 단계 조건에 맞는 매물의 시세를 보여준다.

경매장을 자동으로 긁지 않는다(약관) — 화면 분석이 읽은 것만 저장한다.
"""
import json
from types import SimpleNamespace as NS

from fastapi.testclient import TestClient

from engine.market.recommend import covers, roadmap
from engine.stats.evaluate import rank_settings
from engine.stats.metrics import BossProfile
from engine.stats.sets import SetCatalog
from helpers import bundle
from nexon.convert import snapshot
from server.admin import make_password_hash
from server.app import create_app
from server.market import PriceStore
from server.vision import normalize_listing

CAT, BOSS = SetCatalog.load(), BossProfile("기준", 300.0)


def _row(price, pots=("INT +9%", "INT +6%", "INT +6%"), add=(), sf=22, cat="상의", ts=0.0):
    return {"category": cat, "name": "도전자의 상의", "starforce": sf, "potential_lines": list(pots),
            "additional": list(add), "price": price, "seen_at": ts}


def test_vision_listing_keeps_main_and_additional_apart_and_combined_for_evaluation():
    x = normalize_listing({"name": "모자", "category": "모자", "part": "모자",
                           "potentials": ["INT +12%", "INT +9%"], "additional": ["마력 +10", "INT +4%"]})
    assert x["potential_lines"] == ["INT +12%", "INT +9%"] and x["additional"] == ["마력 +10", "INT +4%"]
    assert x["potentials"] == ["INT +12%", "INT +9%", "마력 +10", "INT +4%"]


def test_covers_compares_lines_by_stat_and_value():
    assert covers(["INT +12%", "INT +9%", "INT +6%"], ["INT +9%", "INT +6%", "INT +6%"], 287)
    assert not covers(["INT +12%", "INT +9%", "LUK +9%"], ["INT +9%", "INT +6%", "INT +6%"], 287)
    assert covers(["올스탯 +9%", "INT +9%"], ["INT +9%", "INT +6%"], 287)        # 올스탯은 주스탯 줄을 덮는다
    assert covers(["스킬 재사용 대기시간 -2초", "INT +9%", "INT +9%"], ["스킬 재사용 대기시간 -2초", "INT +9%"], 287)
    assert not covers(["INT +9%", "INT +9%"], ["스킬 재사용 대기시간 -2초", "INT +9%"], 287)


def test_price_store_records_dedupes_and_lists(tmp_path):
    clock = iter([100.0, 200.0, 300.0, 400.0])
    store = PriceStore(str(tmp_path / "m.sqlite3"), lambda: next(clock))
    read = {"name": "도전자의 상의", "category": "상의", "starforce": 22, "potential_lines": ["INT +9%"],
            "additional": [], "price": 3_000_000_000}
    assert store.record(read) is True
    assert store.record(dict(read)) is False                          # 같은 매물·같은 가격은 한 번만
    assert store.record({**read, "price": 2_900_000_000}) is True
    assert store.record({**read, "price": None}) is False             # 가격 모르면 저장 안 함
    rows = store.rows()
    assert [r["price"] for r in rows] == [3_000_000_000, 2_900_000_000] and rows[0]["seen_at"] == 100.0


def test_roadmap_attaches_observed_market_price_to_matching_tier():
    snap = snapshot(bundle("레테"))
    setting = rank_settings(snap, BOSS, CAT)[0][0]
    observed = [_row(3_000_000_000), _row(5_000_000_000), _row(4_000_000_000),
                _row(1_000_000_000, sf=17),                      # 지금 템(22성)보다 스타포스가 낮으면 제외
                _row(9_000_000_000, pots=("INT +9%", "LUK +6%")),  # 조건 미달
                _row(2_000_000_000, cat="하의")]
    rm = roadmap(snap, setting, BOSS, CAT, observed=observed)
    tier = next(t for t in rm["상의"]["잠재"] if t["grade"] == "유니크" and t["lines_good"] == 3)
    m = tier["market"]
    assert (m["count"], m["median"], m["min"]) == (3, 4_000_000_000, 3_000_000_000)
    assert m["per_100m"] == tier["delta_pct"] / 40


def test_vision_endpoint_stores_prices_and_market_route_lists_them(tmp_path):
    payload = {"tooltip_visible": True, "fee_rate": None, "listings": [
        {"name": "도전자의 상의", "category": "상의", "part": "상의", "starforce": 22, "total": {"INT": 100},
         "potentials": ["INT +9%", "INT +6%", "INT +6%"], "additional": ["INT +4%"], "price": 3_000_000_000}]}
    fake = NS(responses=NS(create=lambda **kw: NS(output=[], output_text=json.dumps(payload), status="completed",
                                                   usage=NS(input_tokens=1, output_tokens=1))))
    c = TestClient(create_app(lambda n, d: bundle("레테"), str(tmp_path / "c.sqlite3"), agent_client=fake,
                              admin_password_hash=make_password_hash("pw", 1000), session_secret="s" * 32))
    c.post("/api/admin/login", json={"password": "pw"})
    c.post("/api/vision/listings", json={"image": "data:image/jpeg;base64,AAA", "name": "내신부레테"})
    obs = c.get("/api/market/observed").json()
    assert obs["count"] == 1 and obs["rows"][0]["additional"] == ["INT +4%"]
    rm = c.get("/api/character/내신부레테/roadmap").json()
    top = next(s for s in rm["slots"] if s["slot"] == "상의")
    assert any(t.get("market", {}).get("count") == 1 for t in top["잠재"])



def test_current_prices_come_from_observation_db(tmp_path):
    """지금 시세는 관측 기록 DB(Neon)에서 최근 30일을 읽는다(2026-10-08) — 서버 안 SQLite가 재시작 때 비워져도 남는다.
    관측 기록에만 있는 매물이 경로 비교·관리자 목록에 보이면 DB에서 읽는 것."""
    from fastapi.testclient import TestClient
    from helpers import bundle
    from server.admin import make_password_hash
    from server.app import create_app
    from server.observations import ObservationLog

    path = str(tmp_path / "c.sqlite3")
    c = TestClient(create_app(lambda n, d: bundle("레테"), path, admin_password_hash=make_password_hash("pw", 1000),
                              session_secret="s" * 32))
    read = {"category": "장갑", "name": "에테르넬 메이지글러브", "part": "장갑", "starforce": 22, "level": 250,
            "potential_grade": "레전드리", "potential_lines": ["INT +12%", "INT +9%", "INT +9%"], "additional": [],
            "total": {"INT": 300, "LUK": 100, "MATK": 50}, "price": 1_000_000_000}
    import time
    ObservationLog.sqlite(path, clock=time.time).record(read)   # 관측 기록에만 넣는다(다른 서버 인스턴스가 쓴 것처럼)
    c.post("/api/admin/login", json={"password": "pw"})
    assert [r["name"] for r in c.get("/api/market/observed").json()["rows"]] == ["에테르넬 메이지글러브"]
    assert c.get("/api/character/x/paths").json()["observed_count"] == 1
