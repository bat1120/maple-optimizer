import datetime as dt

import pytest
from fastapi.testclient import TestClient

from helpers import bundle, pair_bundle
from nexon.client import CharacterNotFound
from server.app import create_app

RING = {"slot": "반지4", "part": "반지", "name": "어센던트 펄스 링",
        "total": {"INT": 59, "LUK": 59, "MATK": 16}, "potentials": ["INT +12%", "LUK +9%", "INT +9%", "마력 +10", "INT +6"]}


class Clock:
    def __init__(self):
        self.t = 1_000_000.0

    def __call__(self):
        return self.t


@pytest.fixture
def clock():
    return Clock()


def make(tmp_path, clock, source=None, calls=None, **kw):
    def fetcher(name, day):
        if calls is not None:
            calls.append((name, day))
        if isinstance(source, Exception):
            raise source
        return bundle("레테") if source is None else source(name)
    return TestClient(create_app(fetcher, str(tmp_path / "c.sqlite3"), clock=clock, **kw))


def test_health(tmp_path, clock):
    assert make(tmp_path, clock).get("/api/health").json() == {"status": "ok"}


def test_character_summary(tmp_path, clock):
    r = make(tmp_path, clock).get("/api/character/내신부레테").json()
    assert r["character_class"] == "레테" and r["level"] == 287
    assert r["active_setting"] == {"equipment": 1, "hyper": 1, "ability": 1, "union": 2, "link": 1}
    assert r["stat_attack"]["engine"] == pytest.approx(r["stat_attack"]["api"], rel=1e-4)
    assert r["combat_power_reference"] == 72267618


def test_character_summary_lists_presets(tmp_path, clock):
    r = make(tmp_path, clock).get("/api/character/내신부레테").json()
    assert set(r["equipment_presets"]) == {"1", "2", "3"}
    weapon = next(i for i in r["equipment_presets"]["1"] if i["slot"] == "무기")
    assert weapon == {"slot": "무기", "name": "제네시스 카르타", "starforce": 22}


def test_settings_ranking(tmp_path, clock):
    r = make(tmp_path, clock).get("/api/character/내신부레테/settings?boss_defense=300").json()
    assert len(r["ranking"]) == 162
    assert r["ranking"][0]["setting"] == {"equipment": 2, "hyper": 3, "ability": 2, "union": 3, "link": 2}
    assert r["ranking"][0]["relative_to_active"] > 1


def test_settings_boss_defense_changes_index(tmp_path, clock):
    c = make(tmp_path, clock)
    a = c.get("/api/character/내신부레테/settings?boss_defense=100").json()["ranking"][0]["index"]
    b = c.get("/api/character/내신부레테/settings?boss_defense=300").json()["ranking"][0]["index"]
    assert a > b


def test_listings_ranked_by_efficiency(tmp_path, clock):
    body = {"setting": {"equipment": 1, "hyper": 1, "ability": 1}, "boss_defense": 300,
            "listings": [{**RING, "price": 5_000_000_000}, {**RING, "price": 1_000_000_000}]}
    r = make(tmp_path, clock).post("/api/character/내신부레테/listings", json=body).json()
    assert [x["price"] for x in r["ranking"]] == [1_000_000_000, 5_000_000_000]
    assert r["ranking"][0]["delta_pct"] > 0 and r["ranking"][0]["excluded"] == []


def test_listing_invalid_price_is_400_korean(tmp_path, clock):
    body = {"listings": [{**RING, "price": 95, "resale": 100}]}  # 수수료 5% 뺀 판매 대금 95 = 가격
    r = make(tmp_path, clock).post("/api/character/내신부레테/listings", json=body)
    assert r.status_code == 400 and r.json()["code"] == "INVALID_PRICE" and "가격" in r.json()["message"]


def test_listing_unknown_total_key_is_422(tmp_path, clock):
    body = {"listings": [{**RING, "total": {"STRR": 1}, "price": 10**9}]}
    assert make(tmp_path, clock).post("/api/character/내신부레테/listings", json=body).status_code == 422


def test_listing_defaults_to_best_boss_setting(tmp_path, clock):
    body = {"listings": [{**RING, "price": 10**9}]}
    r = make(tmp_path, clock).post("/api/character/내신부레테/listings", json=body).json()
    assert r["setting"] == {"equipment": 2, "hyper": 3, "ability": 2, "union": 3, "link": 2}


def test_unsupported_job_is_422(tmp_path, clock):
    r = make(tmp_path, clock, source=lambda _: bundle("데몬어벤져")).get("/api/character/x")
    assert r.status_code == 422 and r.json()["code"] == "UNSUPPORTED" and "데몬어벤져" in r.json()["message"]


def test_no_damage_is_422(tmp_path, clock):
    c = make(tmp_path, clock, source=lambda _: bundle("나이트로드"))
    active = c.get("/api/character/x").json()["active_setting"]  # 현재 착용 세팅은 방무 66.7% 미만
    body = {"setting": active, "boss_defense": 300, "listings": [{**RING, "slot": "반지1", "price": 10**9}]}
    r = c.post("/api/character/x/listings", json=body)
    assert r.status_code == 422 and r.json()["code"] == "NO_DAMAGE"


def test_bad_date_is_400(tmp_path, clock):
    r = make(tmp_path, clock).get("/api/character/내신부레테?date=2026-13-40")
    assert r.status_code == 400 and r.json()["code"] == "BAD_DATE"


def test_date_is_passed_to_fetcher(tmp_path, clock):
    calls = []
    make(tmp_path, clock, calls=calls).get("/api/character/내신부레테?date=2026-10-01")
    assert calls == [("내신부레테", dt.date(2026, 10, 1))]


def test_current_cache_expires_after_15_minutes(tmp_path, clock):
    calls = []
    c = make(tmp_path, clock, calls=calls)
    c.get("/api/character/내신부레테")
    clock.t += 14 * 60
    c.get("/api/character/내신부레테")
    clock.t += 2 * 60
    c.get("/api/character/내신부레테")
    assert len(calls) == 2


def test_past_date_cache_kept_but_purged_after_30_days(tmp_path, clock):
    calls = []
    c = make(tmp_path, clock, calls=calls)
    c.get("/api/character/내신부레테?date=2026-10-01")
    clock.t += 29 * 86400
    c.get("/api/character/내신부레테?date=2026-10-01")
    clock.t += 2 * 86400
    c.get("/api/character/내신부레테?date=2026-10-01")
    assert len(calls) == 2


def test_name_is_case_insensitive_for_cache(tmp_path, clock):
    calls = []
    c = make(tmp_path, clock, calls=calls)
    c.get("/api/character/BrutalThief")
    c.get("/api/character/brutalthief")
    assert len(calls) == 1


def test_character_not_found_is_404(tmp_path, clock):
    r = make(tmp_path, clock, source=CharacterNotFound("OPENAPI00004", "x", 400)).get("/api/character/없음")
    assert r.status_code == 404 and r.json()["code"] == "NOT_FOUND"


def test_pair_snapshot_summary_is_boss_setting(tmp_path, clock):
    r = make(tmp_path, clock, source=lambda _: pair_bundle("레테_boss")).get("/api/character/x").json()
    assert r["active_setting"] == {"equipment": 2, "hyper": 3, "ability": 2, "union": 3, "link": 2}


def test_starforce_endpoint_exact_and_distribution(tmp_path, clock):
    r = make(tmp_path, clock).post("/api/enhance/starforce", json={
        "level": 200, "start": 20, "target": 21, "destroy_cost": 0, "trials": 2000, "conditions": {"discount30": True}})
    body = r.json()
    assert r.status_code == 200 and body["exact_mean"] > 0 and body["conditions"]["discount30"] is True


def test_starforce_target_above_cap_is_422(tmp_path, clock):
    r = make(tmp_path, clock).post("/api/enhance/starforce", json={"level": 130, "start": 0, "target": 22, "destroy_cost": 0})
    assert r.status_code == 422 and r.json()["code"] == "INVALID_INPUT"


def test_cube_unknown_table_is_404(tmp_path, clock):
    r = make(tmp_path, clock).post("/api/enhance/cube", json={"table": "없는표", "level": 200, "grade": "레전드리",
                                                               "lines_at_least": {"BOSS": 1}})
    assert r.status_code == 404 and r.json()["code"] == "NO_TABLE"


def test_cube_without_target_is_422(tmp_path, clock):
    r = make(tmp_path, clock).post("/api/enhance/cube", json={"table": "레전드리/무기/200", "level": 200, "grade": "레전드리"})
    assert r.status_code == 422


def test_optimize_respects_budget(tmp_path, clock):
    body = {"budget": 2_000_000_000, "candidates": [{**RING, "price": 3_000_000_000}]}
    r = make(tmp_path, clock).post("/api/character/내신부레테/optimize", json=body).json()
    assert r["actions"] == [] and r["spent"] == 0


def test_listing_and_settings_report_equivalent_main_stat(tmp_path, clock):
    c = make(tmp_path, clock)
    stronger = {**RING, "total": {"INT": 90, "LUK": 59, "MATK": 30}}  # 현재 보스 반지보다 센 매물
    lst = c.post("/api/character/내신부레테/listings", json={"listings": [{**stronger, "price": 3_000_000_000}]}).json()
    assert lst["ranking"][0]["main_stat_gain"] > 0 and "main_stat_gain_per_100m" in lst["ranking"][0]
    st = c.get("/api/character/내신부레테/settings").json()["ranking"][0]
    assert st["main_stat_vs_active"] > 0


def test_recommend_route_returns_search_cards_on_boss_setting(tmp_path, clock):
    r = make(tmp_path, clock).get("/api/character/내신부레테/recommend?boss_defense=300&top=3").json()
    assert r["evaluation_setting"]["equipment"] == 2 and len(r["recommendations"]) == 3
    first = r["recommendations"][0]
    assert first["search"].startswith(f"{first['category']} · 잠재 ") and first["delta_pct"] > 0
    ring = make(tmp_path, clock).get("/api/character/내신부레테/recommend?top=20").json()["recommendations"]
    assert all(c["category"] == "반지" for c in ring if c["slot"].startswith("반지"))


def test_index_page_is_not_cached_but_hashed_assets_are(tmp_path, clock):
    """새로 빌드해도 브라우저가 옛 화면을 계속 쓰던 문제(2026-10-05) — index.html은 매번 새로 확인하게 한다."""
    web = tmp_path / "dist"
    (web / "assets").mkdir(parents=True)
    (web / "index.html").write_text("<html>new</html>", encoding="utf-8")
    (web / "assets" / "index-abc.js").write_text("x", encoding="utf-8")
    c = make(tmp_path, clock, static_dir=str(web))
    assert c.get("/").headers.get("cache-control") == "no-cache"
    assert "no-cache" not in (c.get("/assets/index-abc.js").headers.get("cache-control") or "")
