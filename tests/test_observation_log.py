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


def test_reconnects_once_when_connection_dropped(tmp_path):
    """Neon 무료 DB는 쉬면 잠들며 연결을 끊는다(2026-10-07) — 끊긴 연결이면 다시 열고 한 번 더 시도한다."""
    import sqlite3
    path = str(tmp_path / "r.sqlite3")
    opened = []

    class Dropping:
        """첫 연결은 표를 만든 뒤 끊긴 것처럼 동작한다."""
        def __init__(self):
            self.real = sqlite3.connect(path, check_same_thread=False)
            self.dead = False
        def cursor(self):
            if self.dead:
                raise ConnectionError("server closed the connection unexpectedly")
            return self.real.cursor()
        def commit(self):
            self.real.commit()
        def rollback(self):
            pass

    def connect():
        c = Dropping()
        opened.append(c)
        return c

    log = ObservationLog(connect(), "?", "sqlite", lambda: 1_800_000_000.0, "INTEGER PRIMARY KEY AUTOINCREMENT",
                         reconnect=connect, retry_on=(ConnectionError,))
    opened[0].dead = True
    assert log.record(READ) is True and len(opened) == 2
    assert log.count() == 1


def test_rows_are_last_30_days_deduped_like_price_store(tmp_path):
    """지금 시세는 관측 기록(DB)에서 최근 30일만 꺼내 쓴다(2026-10-08 사용자: DB에서 30일로 나눠 보면 된다).
    같은 매물·같은 가격은 여러 날 봤어도 한 번(가장 최근 본 시각), 보조무기 판정용 equip_type·job_groups도 돌려준다."""
    now = [1_800_000_000.0]
    log = _log(tmp_path, now)
    old = {**READ, "name": "오래된 장갑"}
    assert log.record(old)
    now[0] += 31 * 86400                                       # 31일 뒤
    sec = {**READ, "category": "보조무기", "name": "녹스 마법깃펜", "part": "마법깃펜", "equip_type": "마법깃펜",
           "job_groups": ["마법사"]}
    assert log.record(READ) and log.record(sec)
    now[0] += 86400
    assert log.record(READ)                                    # 다음 날 같은 매물·같은 가격 → 기록은 쌓이지만
    rows = log.rows()
    assert log.count() == 4
    assert [r["name"] for r in rows] == ["녹스 마법깃펜", "에테르넬 메이지글러브"]  # 30일 지난 것 빠짐, 같은 매물 한 번
    glove = rows[1]
    assert glove["seen_at"] == now[0] and glove["price"] == 12_300_000_000 and glove["total"] == {"INT": 100}
    assert glove["potential_lines"] == ["크리티컬 데미지 +8%", "INT +9%"] and glove["additional"] == ["마력 +10"]
    assert glove["sold"] is False and glove["starforce"] == 22
    assert rows[0]["equip_type"] == "마법깃펜" and rows[0]["job_groups"] == ["마법사"]


def test_old_table_without_new_columns_is_upgraded(tmp_path):
    """이미 Neon에 있는 표(equip_type·job_groups 칸 없음)에도 칸을 더해 그대로 쓴다."""
    import sqlite3
    path = tmp_path / "old.sqlite3"
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE observations (id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT UNIQUE, seen_at DOUBLE PRECISION, "
                "day TEXT, category TEXT, name TEXT, part TEXT, starforce INTEGER, level INTEGER, potential_grade TEXT, "
                "additional_grade TEXT, potential_lines TEXT, additional TEXT, total TEXT, price BIGINT, sold BOOLEAN, "
                "other_world BOOLEAN, source TEXT)")
    con.commit()
    con.close()
    log = ObservationLog.sqlite(str(path), clock=lambda: 1_800_000_000.0)
    assert log.record({**READ, "equip_type": "장갑"}) and log.rows()[0]["equip_type"] == "장갑"
