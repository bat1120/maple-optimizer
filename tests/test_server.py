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
    assert {k: weapon[k] for k in ("slot", "name", "starforce")} == {"slot": "무기", "name": "제네시스 카르타", "starforce": 22}
    assert {"icon", "potential_grade", "potentials", "additional"} <= set(weapon)  # UI 개편(2026-10-07): 장비창 상세


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
    import copy
    body = copy.deepcopy(bundle("레테"))
    body["character/basic"]["character_class"] = "처음보는직업"
    r = make(tmp_path, clock, source=lambda _: body).get("/api/character/x")
    assert r.status_code == 422 and r.json()["code"] == "UNSUPPORTED" and "처음보는직업" in r.json()["message"]


def test_demon_avenger_is_supported(tmp_path, clock):
    """2026-11-25: 스탯창 HP는 표시 상한(500,000)이지만 스탯공격력에서 되짚어 계산한다."""
    c = make(tmp_path, clock, source=lambda _: bundle("데몬어벤져"))
    r = c.get("/api/character/x")
    assert r.status_code == 200 and r.json()["character_class"] == "데몬어벤져"
    plan = c.get("/api/character/x/budget-roadmap")
    assert plan.status_code == 200 and plan.json()["steps"]


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
    assert first["search"].startswith(f"{first['category']} · ") and first["delta_pct"] > 0
    both = [c for c in r["recommendations"] if len(c["parts"]) == 2]  # 윗잠·에디를 한 카드로(2026-10-11)
    assert all(" · 잠재 " in c["search"] and " · 에디 " in c["search"] for c in both)
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


def test_optional_endpoints_may_be_empty(tmp_path, clock):
    """2026-10-08 회귀: 연무장 기록·HEXA 같은 선택 데이터가 비어 있어도(None) 조회는 된다 — 필수 데이터만 '없음' 판정."""
    def src(_):
        b = bundle("레테")
        b.update({"battle-practice/result": None, "character/hexamatrix": None, "character/hexamatrix-stat": None,
                  "character/skill_6": None})
        return b
    r = make(tmp_path, clock, source=src).get("/api/character/x")
    assert r.status_code == 200 and r.json()["character_class"] == "레테"


def test_required_endpoint_missing_is_no_data(tmp_path, clock):
    def src(_):
        b = bundle("레테")
        b["character/stat"] = None
        return b
    r = make(tmp_path, clock, source=src).get("/api/character/x")
    assert r.status_code == 404 and r.json()["code"] == "NO_DATA"


def test_concurrent_cold_lookups_call_nexon_once(tmp_path, clock):
    """2026-11-25 운영: 화면이 요약·세팅·계획을 한꺼번에 불러, 캐시가 빈 첫 조회에서 넥슨을 겹쳐 불렀다(초당 한도 초과 + 호출량 3배)."""
    import threading
    import time
    calls, body = [], bundle("레테")

    def slow(name, day):
        calls.append(name)
        time.sleep(0.3)                                    # 넥슨을 부르는 동안 다른 요청이 들어온다
        return body
    c = TestClient(create_app(slow, str(tmp_path / "c.sqlite3"), clock=clock))
    out = []
    paths = ["/api/character/x", "/api/character/x/settings", "/api/character/x/budget-roadmap", "/api/character/X"]
    ts = [threading.Thread(target=lambda p=p: out.append(c.get(p).status_code)) for p in paths]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert out == [200] * 4 and len(calls) == 1


def test_serves_saved_data_when_nexon_is_blocked(tmp_path, clock):
    """넥슨 호출 한도·점검 때: 전에 받아 둔 값이 있으면 그걸로 답하고 얼마나 된 데이터인지 알린다. 없으면 전처럼 503."""
    from nexon.client import RateLimited
    calls, state = [], {"blocked": False}

    def fetcher(name, day):
        calls.append(name)
        if state["blocked"]:
            raise RateLimited("OPENAPI00007", "limit", 429)
        return bundle("레테")
    c = TestClient(create_app(fetcher, str(tmp_path / "c.sqlite3"), clock=clock))
    assert c.get("/api/character/a").json()["stale_minutes"] is None
    state["blocked"] = True
    clock.t += 40 * 60                                         # 캐시 기한(15분)이 지났고 넥슨은 막혔다
    r = c.get("/api/character/a")
    assert r.status_code == 200 and r.json()["stale_minutes"] == 40
    assert c.get("/api/character/a/budget-roadmap").status_code == 200
    assert len(calls) == 2                                     # 막힌 동안에는 요청마다 다시 두드리지 않는다
    r = c.get("/api/character/처음보는캐릭터")
    assert r.status_code == 503 and r.json()["code"] == "NEXON_RATE_LIMIT"
    state["blocked"] = False
    clock.t += 6 * 60                                          # 잠시 뒤에는 다시 불러 새 값으로 바꾼다
    assert c.get("/api/character/a").json()["stale_minutes"] is None and len(calls) == 4


def test_same_plan_request_is_computed_once(tmp_path, clock, monkeypatch):
    """2026-11-25 운영: 계획 23초 — 화면이 같은 계획을 두 번 부르고 탭을 오갈 때마다 다시 계산했다.
    같은 캐릭터 데이터·같은 조건이면 잠깐(MEMO_TTL) 한 번 계산한 답을 쓰고, 동시에 온 요청은 먼저 온 계산을 기다린다."""
    import threading
    import time

    from server import app as app_module
    from server import service
    real, runs = service.budget_roadmap, []

    def counted(*a, **kw):
        runs.append(a[3:])
        time.sleep(0.2)
        return real(*a, **kw)
    monkeypatch.setattr(service, "budget_roadmap", counted)
    c = make(tmp_path, clock)
    assert c.get("/api/character/x").status_code == 200
    out = []
    ts = [threading.Thread(target=lambda: out.append(c.get("/api/character/x/budget-roadmap").json())) for _ in range(3)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert len(runs) == 1 and out[0] == out[1] == out[2] and out[0]["steps"]
    c.get("/api/character/X/budget-roadmap")                       # 대소문자만 다른 이름도 같은 캐릭터
    assert len(runs) == 1
    c.get("/api/character/x/budget-roadmap?boss_defense=100")      # 조건이 다르면 따로 계산
    c.get("/api/character/x/budget-roadmap?budget=5000000000")
    assert len(runs) == 3
    clock.t += app_module.MEMO_TTL + 1                              # 시간이 지나면 새로 계산(시세가 바뀌었을 수 있다)
    c.get("/api/character/x/budget-roadmap")
    assert len(runs) == 4
    clock.t += 16 * 60                                              # 캐릭터 데이터를 새로 받으면 새로 계산
    c.get("/api/character/x/budget-roadmap")
    assert len(runs) == 5


def test_settings_ranking_is_also_relative_to_the_boss_setting(tmp_path, clock):
    """2026-11-26 사용자: 전부 보스 기준 — 지금 착용(사냥용일 수 있다)이 아니라 1위 조합과 비교한 값을 준다."""
    rows = make(tmp_path, clock).get("/api/character/x/settings").json()["ranking"]
    assert rows[0]["relative_to_best"] == 1 and rows[0]["main_stat_vs_best"] == 0
    assert all(r["relative_to_best"] <= 1 and r["main_stat_vs_best"] <= 0 for r in rows)
    assert rows[1]["relative_to_best"] == rows[1]["index"] / rows[0]["index"] and rows[-1]["main_stat_vs_best"] < 0


def test_listing_evaluation_says_which_set_effect_breaks():
    """2026-11-26 실사용: 에스텔라 이어링(여명 세트)을 다른 귀고리로 바꾸면 여명 세트 단계가 깨져 실딜이 낮게 나오는데,
    화면에는 숫자만 있어 계산이 맞는지 알 수 없었다. 개수가 달라지는 세트와 사라지는 효과를 같이 준다."""
    from nexon.convert import snapshot
    from server import service
    read = {"name": "처음 보는 귀고리", "category": "귀고리", "part": "귀고리", "starforce": 18, "level": 130,
            "total": {"INT": 136, "LUK": 67, "MATK": 49}, "potentials": ["INT +12%"], "price": None}
    row = service.vision_items(snapshot(bundle("레테")), None, 300.0, [read], set())[0]
    assert row["evaluated"] is True and row["slot"] == "귀고리"
    assert row["set_change"] == [{"set": "여명의 보스 세트", "before": 4, "after": 3, "gained": [],
                                  "lost": ["올스탯 +10, 최대 HP +250, 공격력 +10, 마력 +10, 방어력 +100, 몬스터 방어율 무시 +10%"]}]


def test_consult_gives_whole_builds_per_star(tmp_path, clock):
    """2026-11-26 사용자: 템 세팅은 한 단계씩이 아니라 메소를 모아 한 번에 갈아타는 것 — 세팅 전체를 한 번에 잰 목표 세팅을 준다."""
    r = make(tmp_path, clock).get("/api/character/x/consult")
    assert r.status_code == 200
    every = r.json()["builds"]
    # 2026-11-26: 성 × 잠재 목표(지금 그대로·레전드리 2줄·3줄). 아래는 '지금 그대로' 줄
    assert [(b["starforce"], b["potential"]) for b in every] == [(s, k) for s in (17, 18, 21, 22) for k in ("same", "legend2", "legend3")]
    assert {b["potential_label"] for b in every} == {"지금 그대로", "레전드리 2줄", "레전드리 3줄"}
    for b in every:
        assert b["cube_cost"] == sum(c["cost"] or 0 for c in b["cube"]) and all(c["cost_text"] for c in b["cube"] if c["cost"])
        assert all(len(x["target"]) in (2, 3) for x in b["buy"] if x["target"]) and (b["potential"] != "same" or not b["cube"])
    best = [b for b in every if b["potential"] == "legend3"][-1]
    goals = [x["goal"] for x in best["buy"] if x["target"]]
    assert goals and all(g["gain_pct"] > 0 and g["cost_text"] and g["per_100m"] > 0 for g in goals)
    assert all(c["gain_pct"] > 0 for c in best["cube"]) and all(x["goal"] is None for x in every[0]["buy"])
    assert best["delta_pct"] > every[-3]["delta_pct"] and best["match_cost"] > every[-3]["match_cost"]
    builds = [b for b in every if b["potential"] == "same"]
    assert [b["starforce"] for b in builds] == [17, 18, 21, 22]
    assert [b["delta_pct"] for b in builds] == sorted(b["delta_pct"] for b in builds) and builds[-1]["delta_pct"] > 0   # 성이 높을수록 높다
    top = builds[-1]
    assert top["buy"] and all(x["starforce"] <= 22 and x["name"] and x["slot"] for x in top["buy"])
    names = [p["name"] for p in top["pieces"]]
    assert len(names) == len(set(names))                                    # 같은 템을 두 번 끼지 않는다
    assert all(x["starforce"] > x["from_star"] and x["cost"] > 0 and x["cost_text"] for x in top["raise"])
    assert top["raise_cost"] == sum(x["cost"] for x in top["raise"])
    assert all({"set", "before", "after", "lost", "gained"} <= set(c) and c["before"] != c["after"] for c in top["set_change"])
    assert not {"무기", "보조무기", "엠블렘"} & {p["slot"] for p in top["pieces"]}   # 무기류는 그대로 둔다
