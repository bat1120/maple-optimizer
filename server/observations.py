"""경매장 관측 기록: 화면 분석이 읽은 매물(가격·옵션)을 지우지 않고 쌓는다(2026-10-07).

- 지금 시세(server/market.py, 30일)와 별개. 같은 매물·같은 가격은 하루 한 번, 날짜가 다르면 새 줄 → 시세 흐름
- IP·화면 이미지는 저장하지 않는다. 경매장을 자동 조회하지 않는다 — 사용자가 공유한 화면에서 읽은 것만
- DATABASE_URL(예: Neon 무료 Postgres)이 있으면 Postgres, 없으면 SQLite 파일(로컬·테스트)
"""
import csv
import datetime as dt
import io
import json
import os
import pathlib
import sqlite3
import threading
from collections.abc import Callable

COLUMNS = ("seen_at", "day", "category", "name", "part", "starforce", "level", "potential_grade", "additional_grade",
           "potential_lines", "additional", "total", "price", "sold", "other_world", "source")


def _row(read: dict, now: float) -> dict | None:
    price = read.get("price")
    lines = list(read.get("potential_lines") or []), list(read.get("additional") or [])
    if not price or not (lines[0] or lines[1]) or not read.get("category"):
        return None
    day = dt.datetime.fromtimestamp(now, dt.timezone(dt.timedelta(hours=9))).date().isoformat()  # KST 날짜
    return {"seen_at": now, "day": day, "category": read["category"], "name": read.get("name"),
            "part": read.get("part"), "starforce": int(read.get("starforce") or 0), "level": read.get("level"),
            "potential_grade": read.get("potential_grade"), "additional_grade": read.get("additional_grade"),
            "potential_lines": json.dumps(lines[0], ensure_ascii=False), "additional": json.dumps(lines[1], ensure_ascii=False),
            "total": json.dumps(read.get("total") or {}, ensure_ascii=False), "price": int(price),
            "sold": bool(read.get("sold")), "other_world": bool(read.get("other_world")), "source": read.get("source") or "화면"}


class ObservationLog:
    def __init__(self, conn, placeholder: str, backend: str, clock: Callable[[], float], serial: str,
                 reconnect: Callable | None = None, retry_on: tuple = ()):
        self._conn, self._ph, self.backend, self._clock = conn, placeholder, backend, clock
        self._reconnect, self._retry_on = reconnect, retry_on
        self._lock = threading.Lock()
        cols = ", ".join(f"{c} {'DOUBLE PRECISION' if c == 'seen_at' else 'BIGINT' if c == 'price' else 'INTEGER' if c in ('starforce', 'level') else 'TEXT'}"
                         if c not in ("sold", "other_world") else f"{c} BOOLEAN" for c in COLUMNS)
        self._run(lambda cur: cur.execute(f"CREATE TABLE IF NOT EXISTS observations (id {serial}, key TEXT UNIQUE, {cols})"),
                  commit=True)

    def _run(self, fn, commit: bool = False):
        """fn(cursor)를 실행. Neon처럼 쉬다 연결을 끊는 DB면 한 번 다시 연결해 재시도한다."""
        with self._lock:
            for attempt in (0, 1):
                try:
                    cur = self._conn.cursor()
                    out = fn(cur)
                    if commit:
                        self._conn.commit()
                    return out
                except self._retry_on:
                    if attempt or self._reconnect is None:
                        raise
                    self._conn = self._reconnect()
                except Exception:
                    try:
                        self._conn.rollback()
                    except Exception:
                        pass
                    raise

    @classmethod
    def sqlite(cls, path: str, clock: Callable[[], float]):
        pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
        return cls(sqlite3.connect(path, check_same_thread=False), "?", "sqlite", clock, "INTEGER PRIMARY KEY AUTOINCREMENT")

    @classmethod
    def postgres(cls, url: str, clock: Callable[[], float]):
        import psycopg  # Docker 이미지에서만 설치(Dockerfile) — DATABASE_URL이 있을 때만 필요
        return cls(psycopg.connect(url, autocommit=False), "%s", "postgres", clock, "BIGSERIAL PRIMARY KEY",
                   reconnect=lambda: psycopg.connect(url, autocommit=False),
                   retry_on=(psycopg.OperationalError, psycopg.InterfaceError))

    def record(self, read: dict) -> bool:
        """저장했으면 True. 가격·잠재/에디 줄·부위가 있어야 하고, 같은 날 같은 매물·가격은 한 번만."""
        row = _row(read, self._clock())
        if row is None:
            return False
        key = json.dumps([row["day"], row["category"], row["name"], row["starforce"], row["potential_lines"],
                          row["additional"], row["price"], row["sold"]], ensure_ascii=False)
        names = ("key",) + COLUMNS
        sql = (f"INSERT INTO observations ({', '.join(names)}) VALUES ({', '.join([self._ph] * len(names))}) "
               "ON CONFLICT (key) DO NOTHING")
        def ins(cur):
            cur.execute(sql, (key, *(row[c] for c in COLUMNS)))
            return cur.rowcount == 1
        return self._run(ins, commit=True)

    def count(self) -> int:
        def q(cur):
            cur.execute("SELECT COUNT(*) FROM observations")
            return int(cur.fetchone()[0])
        return self._run(q)

    def stats(self) -> dict:
        def q(cur):
            cur.execute("SELECT category, COUNT(*) FROM observations GROUP BY category ORDER BY category")
            by = {c: int(n) for c, n in cur.fetchall()}
            cur.execute("SELECT MIN(day), MAX(day) FROM observations")
            return by, cur.fetchone()
        by, (first, last) = self._run(q)
        return {"total": sum(by.values()), "by_category": by, "first_day": first, "last_day": last, "backend": self.backend}

    def export_csv(self) -> str:
        def q(cur):
            cur.execute(f"SELECT {', '.join(COLUMNS)} FROM observations ORDER BY seen_at")
            return cur.fetchall()
        rows = self._run(q)
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(COLUMNS)
        w.writerows(rows)
        return buf.getvalue()


def open_log(sqlite_path: str, clock: Callable[[], float]) -> ObservationLog:
    url = os.environ.get("DATABASE_URL")
    return ObservationLog.postgres(url, clock) if url else ObservationLog.sqlite(sqlite_path, clock)
