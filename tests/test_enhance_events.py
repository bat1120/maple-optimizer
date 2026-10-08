"""강화 이벤트·파괴 비용(2026-10-07)
- 흔적 복구: 파괴 직전 성으로 복구하려면 같은 장비 18성 이하 1개·19~20성 2개·21성 3개·22성 4개(공식 가이드), 23성 이상 파괴는 22성으로
- 복구 메소: 나무위키 표(140·160·200·250제, 억 단위 반올림)가 성마다 '강화 1회 비용 × 일정 배수' — 그 배수로 모든 레벨에 쓴다
- 샤이닝 스타포스: 30% 할인·21성 이하 파괴 30% 감소·5/10/15성 100%·복구 메소 20% 할인 / 미라클 타임: 잠재·에디 등급 상승 확률 2배
"""
import pytest

from engine.enhance.starforce import StarforceConditions, expected_cost, expected_totals, restore_meso, restore_spares
from engine.market.cube_value import expected_cost as cube_cost

NAMU = {140: [1.49, 3.59, 6.06, 13.8, 22.8, 40.2, 50.5, 82.9], 160: [2.22, 5.35, 9.04, 20.6, 34.1, 60, 75.4, 124],
        200: [4.33, 10.5, 17.7, 40.1, 66.5, 118, 148, 242], 250: [8.46, 20.4, 34.5, 78.3, 130, 229, 288, 473]}


@pytest.mark.parametrize("level", NAMU)
def test_restore_meso_reproduces_table(level):
    for i, eok in enumerate(NAMU[level]):
        got = restore_meso(level, 15 + i, StarforceConditions()) / 1e8
        assert got == pytest.approx(eok, rel=0.012), (level, 15 + i)  # 표가 억 단위 3자리 반올림


def test_restore_spares_rule():
    assert [restore_spares(s) for s in (15, 18, 19, 20, 21, 22, 25)] == [1, 1, 2, 2, 3, 4, 4]


def test_shining_restore_discount():
    base = restore_meso(200, 20, StarforceConditions())
    assert restore_meso(200, 20, StarforceConditions(restore_discount20=True)) == pytest.approx(base * 0.8)


def test_totals_meso_includes_restore_and_counts_destroys_and_spares():
    cond = StarforceConditions()
    t = expected_totals(200, 17, 22, cond, spare_price=0.0)
    plain = expected_cost(200, 17, 22, 0.0, cond)
    assert t["destroys"] == pytest.approx(expected_cost(200, 17, 22, 1.0, cond) - plain, rel=1e-6)  # 옛 방식은 큰 수끼리 빼서 오차
    assert t["meso"] > plain                       # 복구 메소가 더해진다
    assert t["spares"] >= t["destroys"] > 0
    priced = expected_totals(200, 17, 22, cond, spare_price=1e9)
    assert priced["cost"] == pytest.approx(t["meso"] + t["spares"] * 1e9, rel=1e-9)


def test_shining_starforce_is_cheaper():
    normal = expected_totals(200, 17, 22, StarforceConditions())
    shining = expected_totals(200, 17, 22, StarforceConditions(discount30=True, destroy_down30=True,
                                                              guarantee_5_10_15=True, restore_discount20=True))
    assert shining["cost"] < normal["cost"] and shining["destroys"] < normal["destroys"]


def test_miracle_time_doubles_tier_up_and_lowers_cube_cost():
    normal = cube_cost("잠재", 200, "유니크", "레전드리", 0.05)
    miracle = cube_cost("잠재", 200, "유니크", "레전드리", 0.05, miracle=True)
    assert miracle < normal
    # 목표 등급이 지금 등급이면(등급 상승 없음) 미라클 타임은 상관없다
    assert cube_cost("잠재", 200, "레전드리", "레전드리", 0.05, miracle=True) == cube_cost("잠재", 200, "레전드리", "레전드리", 0.05)


def test_paths_api_takes_events_and_spare_price(tmp_path):
    from fastapi.testclient import TestClient
    from helpers import bundle
    from server.app import create_app
    c = TestClient(create_app(lambda n, d: bundle("레테"), str(tmp_path / "c.sqlite3")))
    base = c.get("/api/character/x/paths").json()
    ev = c.get("/api/character/x/paths?sf=shining,protect&miracle=true&spare_price=1000000000").json()
    assert ev["events"]["discount30"] and ev["events"]["protect"] and ev["events"]["miracle"] and ev["events"]["spare_price"] == 1e9
    assert "미라클 타임" in ev["events"]["label"] and base["events"]["label"] == "이벤트 없음"
    sf = [p for p in ev["all"] if p["path"] == "스타포스"]
    assert sf and all(p["cost"] == pytest.approx(p["meso"] + p["expected_spares"] * 1e9) for p in sf)
    assert c.get("/api/character/x/paths?sf=nope").status_code == 400


def test_roadmap_api_miracle_lowers_cube_cost(tmp_path):
    from fastapi.testclient import TestClient
    from helpers import bundle
    from server.app import create_app
    c = TestClient(create_app(lambda n, d: bundle("레테"), str(tmp_path / "c.sqlite3")))
    cost = lambda r: sum(t["cube_cost"] or 0 for row in r["slots"] for k in ("잠재", "에디") for t in row[k])  # noqa: E731
    assert cost(c.get("/api/character/x/roadmap?miracle=true").json()) < cost(c.get("/api/character/x/roadmap").json())


def test_spare_price_per_slot_overrides_default(tmp_path):
    """스페어 값은 부위마다 다르다(2026-10-08): spare_slots='벨트:300000000'이면 벨트만 3억, 나머지는 spare_price."""
    from fastapi.testclient import TestClient
    from helpers import bundle
    from server.app import create_app
    from engine.market.events import Events
    c = TestClient(create_app(lambda n, d: bundle("레테"), str(tmp_path / "c.sqlite3")))
    ev = c.get("/api/character/x/paths?spare_price=1000000000&spare_slots=" + "벨트:300000000").json()
    sf = [p for p in ev["all"] if p["path"] == "스타포스"]
    belt = [p for p in sf if p["slot"] == "벨트"]
    rest = [p for p in sf if p["slot"] != "벨트"]
    assert belt and rest
    assert all(p["spare_price"] == 3e8 and p["cost"] == pytest.approx(p["meso"] + p["expected_spares"] * 3e8) for p in belt)
    assert all(p["spare_price"] == 1e9 and p["cost"] == pytest.approx(p["meso"] + p["expected_spares"] * 1e9) for p in rest)
    assert ev["events"]["spare_slots"] == {"벨트": 3e8}
    # 기본값 없이 한 부위만 줘도 된다 / 잘못된 형식은 400
    only = Events.parse(spare_slots="장갑:5e8, 반지4:0")
    assert only.spare_for("장갑") == 5e8 and only.spare_for("반지4") == 0 and only.spare_for("벨트") == 0
    assert c.get("/api/character/x/paths?spare_slots=벨트").status_code == 400
    assert c.get("/api/character/x/paths?spare_slots=벨트:-1").status_code == 400
