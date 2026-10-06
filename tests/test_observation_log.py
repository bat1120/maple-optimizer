"""경매장 관측 기록(2026-10-07 사용자: 툴팁으로 읽은 가격·정보를 DB에 계속 쌓고 싶다).
- 지우지 않는다(지금 시세 30일 저장소와 별개). 같은 매물·같은 가격은 하루 한 번, 날짜가 다르면 새 줄
- IP·이미지는 저장하지 않는다. DATABASE_URL이 있으면 Postgres(Neon), 없으면 SQLite 파일"""
import csv
import io

from server.observations import ObservationLog, open_log

READ = {"category": "장갑", "name": "에테르넬 메이지글러브", "part": "장갑", "starforce": 22, "level": 250,
        "potential_grade": "레전드리", "additional_grade": "에픽", "total": {"INT": 100},
        "potential_lines": ["크리티컬 데미지 +8%", "INT +9%"], "additional": ["마력 +10"], "price": 12_300_000_000}


def _log(tmp_path, now):
    return ObservationLog.sqlite(str(tmp_path / "o.sqlite3"), clock=lambda: now[0])


def test_same_listing_same_price_once_per_day_new_row_next_day(tmp_path):
    now = [1_800_000_000.0]
    log = _log(tmp_path, now)
    assert log.record(READ) is True
    assert log.record(READ) is False
    assert log.record({**READ, "price": 11_000_000_000}) is True       # 가격이 바뀌면 새 관측
    now[0] += 86400
    assert log.record(READ) is True                                    # 다음 날 같은 매물도 기록(시세 흐름)
    assert log.count() == 3


def test_needs_price_and_lines_and_category(tmp_path):
    log = _log(tmp_path, [1.0])
    assert log.record({**READ, "price": None}) is False
    assert log.record({**READ, "potential_lines": [], "additional": []}) is False
    assert log.record({**READ, "category": None}) is False


def test_never_deleted_even_after_30_days(tmp_path):
    now = [1_800_000_000.0]
    log = _log(tmp_path, now)
    log.record(READ)
    now[0] += 400 * 86400
    log.record({**READ, "price": 1})
    assert log.count() == 2


def test_stats_by_category_and_csv_export(tmp_path):
    log = _log(tmp_path, [1_800_000_000.0])
    log.record(READ)
    log.record({**READ, "category": "반지", "name": "어센던트 펄스 링"})
    s = log.stats()
    assert s["total"] == 2 and s["by_category"] == {"반지": 1, "장갑": 1}
    rows = list(csv.DictReader(io.StringIO(log.export_csv())))
    assert rows[0]["name"] and rows[0]["price"] and "ip" not in rows[0]


def test_open_log_without_database_url_uses_sqlite(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    log = open_log(str(tmp_path / "x.sqlite3"), clock=lambda: 1.0)
    assert log.backend == "sqlite"


def test_screen_reads_are_logged_and_stats_public_export_admin(tmp_path, monkeypatch):
    import json as _json
    from types import SimpleNamespace as NS
    from fastapi.testclient import TestClient
    from helpers import bundle
    from server.admin import make_password_hash
    from server.app import create_app
    monkeypatch.delenv("DATABASE_URL", raising=False)
    listing = {"name": "에테르넬 메이지글러브", "category": "장갑", "part": "장갑", "starforce": 22, "level": 250,
               "potential_grade": "레전드리", "additional_grade": "에픽", "total": {"INT": 100}, "breakdown": {},
               "potentials": ["크리티컬 데미지 +8%"], "additional": ["마력 +10"], "price": 12_300_000_000,
               "equipped": False, "tooltip": None, "special_ring_level": None}
    out = {"tooltip_visible": True, "fee_rate": None, "listings": [listing]}
    fake = NS(responses=NS(create=lambda **kw: NS(output=[], output_text=_json.dumps(out, ensure_ascii=False),
                                                   status="completed", usage=NS(input_tokens=1, output_tokens=1))))
    c = TestClient(create_app(lambda n, d: bundle("레테"), str(tmp_path / "c.sqlite3"), agent_client=fake,
                              admin_password_hash=make_password_hash("pw", 1000), session_secret="s" * 32))
    assert c.post("/api/vision/listings", json={"image": "data:image/jpeg;base64,AAAA"}).status_code == 200
    s = c.get("/api/market/stats").json()
    assert s["total"] == 1 and s["by_category"] == {"장갑": 1}
    assert c.get("/api/market/export.csv").status_code == 401
    c.post("/api/admin/login", json={"password": "pw"})
    r = c.get("/api/market/export.csv")
    assert r.status_code == 200 and "text/csv" in r.headers["content-type"] and "에테르넬 메이지글러브" in r.text
