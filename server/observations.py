"""경매장 관측 기록: 화면 분석이 읽은 매물(가격·옵션)을 지우지 않고 쌓는다(2026-10-07).

- 지금 시세(server/market.py, 30일)와 별개. 같은 매물·같은 가격은 하루 한 번, 날짜가 다르면 새 줄 → 시세 흐름
- IP·화면 이미지는 저장하지 않는다. 경매장을 자동 조회하지 않는다 — 사용자가 공유한 화면에서 읽은 것만
- DATABASE_URL(예: Neon 무료 Postgres)이 있으면 Postgres, 없으면 SQLite 파일(로컬·테스트)
- 지금 시세(경로 비교·로드맵)는 이 기록에서 최근 30일을 읽는다(rows, 2026-10-08) — 같은 매물·같은 가격은 한 번
- 일반 유저 화면 분석 하루 한도(vision_quota)도 같은 DB에 둔다(2026-10-08) — 서버가 다시 떠도 0으로 돌아가지 않는다.
  사람은 IP 대신 서버 비밀값으로 만든 해시(who)로만 구분하고, 지난 날짜 줄은 지운다
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
           "potential_lines", "additional", "total", "price", "sold", "other_world", "source", "equip_type", "job_groups")
NEW_COLUMNS = ("equip_type", "job_groups")  # 2026-10-08 추가(보조무기 착용 판정) — 이미 있는 표에는 칸을 더한다
RECENT_SECONDS = 30 * 86400  # 지금 시세로 쓰는 기간


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
            "sold": bool(read.get("sold")), "other_world": bool(read.get("other_world")), "source": read.get("source") or "화면",
            "equip_type": read.get("equip_type"),
            "job_groups": json.dumps(read["job_groups"], ensure_ascii=False) if read.get("job_groups") is not None else None}


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
        for c in NEW_COLUMNS:
            self._add_column(c)
        self._run(lambda cur: cur.execute("CREATE TABLE IF NOT EXISTS vision_quota "
                                          "(day TEXT, who TEXT, n INTEGER, PRIMARY KEY (day, who))"), commit=True)

    def _add_column(self, name: str) -> None:
        if self.backend == "postgres":
            self._run(lambda cur: cur.execute(f"ALTER TABLE observations ADD COLUMN IF NOT EXISTS {name} TEXT"), commit=True)
            return
        def has(cur):
            cur.execute("PRAGMA table_info(observations)")
            return any(r[1] == name for r in cur.fetchall())
        if not self._run(has):
            self._run(lambda cur: cur.execute(f"ALTER TABLE observations ADD COLUMN {name} TEXT"), commit=True)

    def rows(self, seconds: float = RECENT_SECONDS) -> list[dict]:
        """지금 시세: 최근 seconds 안의 관측. 같은 매물·같은 가격(·판매 여부)은 가장 최근 본 한 줄만, 오래된 것부터."""
        def q(cur):
            cur.execute(f"SELECT {', '.join(COLUMNS)} FROM observations WHERE seen_at > {self._ph} ORDER BY seen_at",
                        (self._clock() - seconds,))
            return cur.fetchall()
        latest: dict[str, dict] = {}
        for values in self._run(q):
            r = dict(zip(COLUMNS, values))
            body = {"category": r["category"], "name": r["name"], "part": r["part"], "starforce": r["starforce"] or 0,
                    "level": r["level"], "potential_grade": r["potential_grade"], "additional_grade": r["additional_grade"],
                    "total": json.loads(r["total"] or "{}"), "potential_lines": json.loads(r["potential_lines"] or "[]"),
                    "additional": json.loads(r["additional"] or "[]"), "price": int(r["price"]), "sold": bool(r["sold"]),
                    "other_world": bool(r["other_world"]), "source": r["source"], "equip_type": r["equip_type"],
                    "job_groups": json.loads(r["job_groups"]) if r["job_groups"] else None, "seen_at": r["seen_at"]}
            key = json.dumps([body["category"], body["name"], body["starforce"], sorted(body["potential_lines"]),
                              sorted(body["additional"]), body["price"], body["sold"]], ensure_ascii=False)
            latest.pop(key, None)
            latest[key] = body  # 다시 넣어 '가장 최근 본 순서'를 유지
        return list(latest.values())

    def _today(self) -> str:
        return dt.datetime.fromtimestamp(self._clock(), dt.timezone(dt.timedelta(hours=9))).date().isoformat()  # KST

    def quota_used(self, who: str) -> int:
        """오늘(KST) who가 AI 판독을 쓴 횟수."""
        def q(cur):
            cur.execute(f"SELECT n FROM vision_quota WHERE day = {self._ph} AND who = {self._ph}", (self._today(), who))
            row = cur.fetchone()
            return int(row[0]) if row else 0
        return self._run(q)

    def quota_add(self, who: str) -> int:
        """오늘 횟수 +1 하고 새 값을 돌려준다. 지난 날짜 줄은 이때 지운다."""
        day, ph = self._today(), self._ph
        def q(cur):
            cur.execute(f"DELETE FROM vision_quota WHERE day < {ph}", (day,))
            cur.execute(f"INSERT INTO vision_quota (day, who, n) VALUES ({ph}, {ph}, 1) "
                        "ON CONFLICT (day, who) DO UPDATE SET n = vision_quota.n + 1", (day, who))
            cur.execute(f"SELECT n FROM vision_quota WHERE day = {ph} AND who = {ph}", (day, who))
            return int(cur.fetchone()[0])
        return self._run(q, commit=True)

    def _run(self, fn, commit: bool = False):
        """fn(cursor)를 실행. Neon처럼 쉬다 연결을 끊는 DB면 한 번 다시 연결해 재시도한다."""
        with self._lock:
            for attempt in (0, 1):
                try:
                    cur = self._conn.cursor()
                    out = fn(cur)
                    # 읽기도 트랜잭션을 닫는다 — Postgres에서 'idle in transaction'으로 잠금을 쥐고 있으면 칸 더하기(ALTER)가 멈춘다
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
