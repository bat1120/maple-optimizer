"""경매장 관측 기록(2026-10-07 사용자: 툴팁으로 읽은 가격·정보를 DB에 계속 쌓고 싶다).
- 지우지 않는다(지금 시세 30일 저장소와 별개). 같은 매물·같은 가격은 하루 한 번, 날짜가 다르면 새 줄
- IP·이미지는 저장하지 않는다. DATABASE_URL이 있으면 Postgres(Neon), 없으면 SQLite 파일"""
import csv
import io

from server.observations import PUBLIC_SOURCE, ObservationLog, open_log

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


def test_rows_skip_public_reads_but_they_stay_in_the_log(tmp_path):
    """공개 사용자 판독은 지금 시세(rows)에 넣지 않는다 — 조작한 툴팁으로 모두의 추천을 오염시키지 않게. 기록에는 남는다."""
    log = _log(tmp_path, [1_800_000_000.0])
    assert log.record({**READ, "source": PUBLIC_SOURCE, "price": 1}) is True
    assert log.rows() == []
    assert log.count() == 1


def test_public_read_does_not_block_same_day_trusted_read(tmp_path):
    """공개 판독이 먼저 들어와도 같은 매물의 관리자 판독은 지금 시세에 들어간다(먼저 넣어 막기 방지)."""
    log = _log(tmp_path, [1_800_000_000.0])
    assert log.record({**READ, "source": PUBLIC_SOURCE}) is True
    assert log.record({**READ, "source": PUBLIC_SOURCE}) is False       # 공개 판독끼리는 여전히 하루 한 번
    assert log.record(READ) is True
    assert [r["source"] for r in log.rows()] == ["화면"]


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


def test_reads_close_their_transaction(tmp_path):
    """읽기도 트랜잭션을 닫는다(2026-10-13) — Postgres(Neon)에서 읽기 뒤 'idle in transaction'이 잠금을 쥐면
    다음 칸 추가(ALTER)·다른 연결의 쓰기가 멈춘다(로컬 Postgres 16에서 재현)."""
    import sqlite3

    class Conn:
        def __init__(self, inner):
            self.inner, self.commits = inner, 0

        def cursor(self):
            return self.inner.cursor()

        def commit(self):
            self.commits += 1
            self.inner.commit()

        def rollback(self):
            self.inner.rollback()

    conn = Conn(sqlite3.connect(tmp_path / "x.sqlite3"))
    log = ObservationLog(conn, "?", "sqlite", lambda: 1_800_000_000.0, "INTEGER PRIMARY KEY AUTOINCREMENT")
    for read in (log.count, log.stats, log.rows, log.export_csv, lambda: log.quota_used("a")):
        before = conn.commits
        read()
        assert conn.commits == before + 1, read


def test_rows_keep_main_and_other_world_copies_apart(tmp_path):
    """같은 템·같은 가격이라도 다른 월드 매물은 따로 — 나중에 본 다른 월드 줄이 본월드 매물을 지우면 안 된다(2026-11-10 리뷰)."""
    now = [1_800_000_000.0]
    log = _log(tmp_path, now)
    log.record(READ)
    now[0] += 60
    log.record({**READ, "other_world": True})
    rows = log.rows()
    assert sorted(r["other_world"] for r in rows) == [False, True]


def test_rows_cached_briefly_but_new_record_shows_at_once(tmp_path):
    """지금 시세는 요청마다 DB를 다시 읽지 않는다(짧게 재사용). 새 관측을 기록하면 바로 보인다."""
    now = [1_800_000_000.0]
    log = _log(tmp_path, now)
    log.record(READ)
    first = log.rows()
    first[0]["price"] = 1                                               # 돌려준 값을 고쳐도 캐시는 그대로
    assert log.rows()[0]["price"] == READ["price"]
    log.record({**READ, "price": 11_000_000_000})
    assert len(log.rows()) == 2


def test_rows_cache_expires(tmp_path):
    now = [1_800_000_000.0]
    log = _log(tmp_path, now)
    log.record(READ)
    assert len(log.rows()) == 1
    now[0] += 31 * 86400                                                # 30일이 지나면 캐시를 넘어서도 빠진다
    assert log.rows() == []


def test_seen_at_index_exists(tmp_path):
    log = _log(tmp_path, [1.0])
    names = log._run(lambda cur: [r[1] for r in cur.execute("PRAGMA index_list(observations)").fetchall()])
    assert "observations_seen_at" in names


def test_rows_read_before_concurrent_record_is_not_cached(tmp_path):
    """시세를 읽은 직후·캐시에 넣기 전에 다른 요청이 기록해도, 옛 결과가 캐시로 남지 않는다(2026-11-10 crash-out)."""
    now = [1_800_000_000.0]
    log = _log(tmp_path, now)
    log.record(READ)
    orig, done = log._run, []
    def run(fn):
        out = orig(fn)
        if fn.__name__ == "q" and not done:
            done.append(1)
            log.record({**READ, "price": 11_000_000_000})
        return out
    log._run = run
    log.rows()
    log._run = orig
    assert len(log.rows()) == 2


def test_rows_nested_lists_are_not_shared_with_cache(tmp_path):
    log = _log(tmp_path, [1_800_000_000.0])
    log.record(READ)
    log.rows()[0]["potential_lines"].append("조작")
    assert log.rows()[0]["potential_lines"] == READ["potential_lines"]


def test_no_retry_errors_are_not_retried_on_a_new_connection(tmp_path):
    """잠금 대기 초과처럼 연결 오류의 하위 종류라도 no_retry면 다시 연결해 또 기다리지 않는다."""
    import sqlite3

    class Locked(ConnectionError):
        pass

    opened = []
    def connect():
        opened.append(1)
        return sqlite3.connect(str(tmp_path / "n.sqlite3"), check_same_thread=False)
    log = ObservationLog(connect(), "?", "sqlite", lambda: 1.0, "INTEGER PRIMARY KEY AUTOINCREMENT",
                         reconnect=connect, retry_on=(ConnectionError,), no_retry=(Locked,))
    calls = []
    def fn(cur):
        calls.append(1)
        raise Locked("lock timeout")
    import pytest
    with pytest.raises(Locked):
        log._run(fn)
    assert len(calls) == 1 and len(opened) == 1


def test_reconnects_when_server_killed_connection_with_non_retry_error(tmp_path):
    """DB가 놀던 연결을 끊으면 오류 종류가 재연결 대상(OperationalError)이 아닐 수 있다(예: 25P03 InternalError).
    2026-11-10 운영에서 첫 요청이 0.16초 만에 500, 다음 요청은 재연결해 200 — 연결이 깨졌으면 종류와 상관없이 다시 붙는다."""
    import sqlite3
    path = str(tmp_path / "k.sqlite3")
    opened = []

    class Killed(Exception):
        pass

    class Conn:
        def __init__(self):
            self.real = sqlite3.connect(path, check_same_thread=False)
            self.kill, self.broken = False, False
        def cursor(self):
            if self.kill:
                self.broken = True
                raise Killed("terminating connection due to idle-in-transaction timeout")
            return self.real.cursor()
        def commit(self):
            self.real.commit()
        def rollback(self):
            pass

    def connect():
        c = Conn()
        opened.append(c)
        return c

    log = ObservationLog(connect(), "?", "sqlite", lambda: 1_800_000_000.0, "INTEGER PRIMARY KEY AUTOINCREMENT",
                         reconnect=connect, retry_on=(ConnectionError,))
    opened[0].kill = True
    assert log.stats()["total"] == 0 and len(opened) == 2


def test_non_retry_error_on_live_connection_is_not_retried(tmp_path):
    """연결이 멀쩡한 오류(예: SQL 오류)는 다시 연결하지 않고 그대로 올린다."""
    import sqlite3

    import pytest
    opened = []
    def connect():
        opened.append(1)
        return sqlite3.connect(str(tmp_path / "l.sqlite3"), check_same_thread=False)
    log = ObservationLog(connect(), "?", "sqlite", lambda: 1.0, "INTEGER PRIMARY KEY AUTOINCREMENT",
                         reconnect=connect, retry_on=(ConnectionError,))
    with pytest.raises(sqlite3.OperationalError):
        log._run(lambda cur: cur.execute("SELECT * FROM no_such_table"))
    assert len(opened) == 1
