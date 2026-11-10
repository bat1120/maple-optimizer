"""경매장 관측 기록: 화면 분석이 읽은 매물(가격·옵션)을 지우지 않고 쌓는다(2026-10-07).

- 같은 매물·같은 가격은 하루 한 번, 날짜가 다르면 새 줄 → 시세 흐름
- 지금 시세(경로 비교·로드맵)도 이 기록에서 최근 30일을 읽는다(rows, 2026-10-13) — 서버가 다시 떠도 남는다
- IP·화면 이미지는 저장하지 않는다(화면 분석 하루 한도는 날짜별 HMAC 해시로만 센다). 경매장을 자동 조회하지 않는다 — 사용자가 공유한 화면에서 읽은 것만
- DATABASE_URL(예: Neon 무료 Postgres)이 있으면 Postgres, 없으면 SQLite 파일(로컬·테스트)
"""
import copy
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
NEW_COLUMNS = ("equip_type", "job_groups")  # 2026-10-13 추가(보조무기 착용 판정) — 이미 있는 표에는 칸을 더한다
RECENT_SECONDS = 30 * 86400  # 지금 시세로 쓰는 기간
ROWS_CACHE_SECONDS = 10  # 지금 시세 결과 재사용 시간(새 관측을 기록하면 바로 비운다)
DDL_LOCK_TIMEOUT = "5s"  # 시작할 때 칸·색인을 더하며 표 잠금을 기다리는 상한
PUBLIC_SOURCE = "공개화면"  # 공개 사용자 판독 — 기록에는 남기지만 지금 시세에는 넣지 않는다(조작한 툴팁 방지, 2026-10-17)


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
                 reconnect: Callable | None = None, retry_on: tuple = (), no_retry: tuple = ()):
        self._conn, self._ph, self.backend, self._clock = conn, placeholder, backend, clock
        self._reconnect, self._retry_on, self._no_retry = reconnect, retry_on, no_retry
        self._lock = threading.Lock()
        self._gen = 0  # 새 관측을 기록할 때마다 +1 — 캐시는 만든 때의 번호가 지금과 같을 때만 쓴다
        self._rows_cache: tuple[float, float, int, list[dict]] | None = None  # (만든 시각, seconds, 번호, 결과)
        cols = ", ".join(f"{c} {'DOUBLE PRECISION' if c == 'seen_at' else 'BIGINT' if c == 'price' else 'INTEGER' if c in ('starforce', 'level') else 'TEXT'}"
                         if c not in ("sold", "other_world") else f"{c} BOOLEAN" for c in COLUMNS)
        self._run(lambda cur: cur.execute(f"CREATE TABLE IF NOT EXISTS observations (id {serial}, key TEXT UNIQUE, {cols})"))
        for c in NEW_COLUMNS:
            self._add_column(c)
        self._add_index("observations_seen_at", "seen_at")  # 지금 시세(rows)가 seen_at 범위로 읽는다 — 기록은 지우지 않아 계속 커진다
        # 화면 분석 하루 한도(2026-10-11 사용자: 해시만 DB에). who = 날짜별 HMAC(IP) — IP 원문은 남기지 않는다
        self._run(lambda cur: cur.execute("CREATE TABLE IF NOT EXISTS vision_quota (day TEXT, who TEXT, n INTEGER, "
                                          "PRIMARY KEY (day, who))"))

    def _run(self, fn):
        """fn(cursor)를 실행. Neon처럼 쉬다 연결을 끊는 DB면 한 번 다시 연결해 재시도한다."""
        with self._lock:
            for attempt in (0, 1):
                try:
                    cur = self._conn.cursor()
                    out = fn(cur)
                    # 읽기도 트랜잭션을 닫는다 — Postgres에서 'idle in transaction'으로 잠금을 쥐면 칸 더하기(ALTER)·쓰기가 멈춘다
                    self._conn.commit()
                    return out
                except self._no_retry:  # 연결 오류의 하위 종류라도 다시 연결해 또 기다리지 않는다(예: 잠금 대기 초과)
                    try:
                        self._conn.rollback()
                    except Exception:
                        pass
                    raise
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
                   retry_on=(psycopg.OperationalError, psycopg.InterfaceError),
                   no_retry=(psycopg.errors.LockNotAvailable,))

    def record(self, read: dict) -> bool:
        """저장했으면 True. 가격·잠재/에디 줄·부위가 있어야 하고, 같은 날 같은 매물·가격은 한 번만."""
        row = _row(read, self._clock())
        if row is None:
            return False
        parts = [row["day"], row["category"], row["name"], row["starforce"], row["potential_lines"],
                 row["additional"], row["price"], row["sold"]]
        if row["other_world"]:  # 다른 월드 매물이 같은 날 본월드 매물 기록을 막지 않게(본월드 키는 예전 그대로)
            parts.append("other_world")
        if row["source"] == PUBLIC_SOURCE:  # 공개 판독이 같은 매물의 믿을 수 있는 판독을 먼저 막지 못하게 따로 센다
            parts.append(PUBLIC_SOURCE)
        key = json.dumps(parts, ensure_ascii=False)
        names = ("key",) + COLUMNS
        sql = (f"INSERT INTO observations ({', '.join(names)}) VALUES ({', '.join([self._ph] * len(names))}) "
               "ON CONFLICT (key) DO NOTHING")
        def ins(cur):
            cur.execute(sql, (key, *(row[c] for c in COLUMNS)))
            if cur.rowcount == 1:
                self._gen += 1  # 잠금 안에서 올린다 — 이 기록 전에 읽은 시세 결과는 캐시로 쓰이지 않는다
                return True
            return False
        return self._run(ins)

    def _add_column(self, name: str) -> None:
        if self.backend == "postgres":
            # ADD COLUMN IF NOT EXISTS도 칸이 있든 없든 표 전체 잠금(ACCESS EXCLUSIVE)을 기다린다 — 배포 중 옛 서버가
            # 잠금을 쥐고 있으면 새 서버가 영영 못 뜬다. 카탈로그로 먼저 보고, 없을 때만 잠금 대기 상한을 걸고 더한다
            def has_pg(cur):
                cur.execute("SELECT 1 FROM information_schema.columns WHERE table_name = 'observations' "
                            "AND column_name = %s AND table_schema = current_schema()", (name,))
                return cur.fetchone() is not None
            if not self._run(has_pg):
                def alter(cur):
                    cur.execute(f"SET LOCAL lock_timeout = '{DDL_LOCK_TIMEOUT}'")
                    cur.execute(f"ALTER TABLE observations ADD COLUMN IF NOT EXISTS {name} TEXT")
                self._run(alter)
            return
        def has(cur):
            cur.execute("PRAGMA table_info(observations)")
            return any(r[1] == name for r in cur.fetchall())
        if not self._run(has):
            self._run(lambda cur: cur.execute(f"ALTER TABLE observations ADD COLUMN {name} TEXT"))

    def _add_index(self, index: str, column: str) -> None:
        if self.backend == "postgres":
            def has_pg(cur):
                cur.execute("SELECT 1 FROM pg_indexes WHERE indexname = %s AND schemaname = current_schema()", (index,))
                return cur.fetchone() is not None
            if self._run(has_pg):
                return
            def create(cur):
                cur.execute(f"SET LOCAL lock_timeout = '{DDL_LOCK_TIMEOUT}'")
                cur.execute(f"CREATE INDEX IF NOT EXISTS {index} ON observations ({column})")
            try:
                self._run(create)
            except Exception as e:  # noqa: BLE001 — 색인은 속도용: 잠금에 막혀도 서버는 뜨고 다음 시작 때 다시 만든다
                import logging
                logging.getLogger("uvicorn.error").warning("관측 기록 색인을 못 만들었어요(다음 시작 때 다시): %s", type(e).__name__)
            return
        self._run(lambda cur: cur.execute(f"CREATE INDEX IF NOT EXISTS {index} ON observations ({column})"))

    def rows(self, seconds: float = RECENT_SECONDS) -> list[dict]:
        """지금 시세: 최근 seconds 안의 관측(공개 판독 제외). 같은 매물·같은 가격(·판매 여부·다른 월드 여부)은
        가장 최근 본 한 줄만, 오래된 것부터. 요청마다 DB를 다시 읽지 않게 ROWS_CACHE_SECONDS 동안 결과를 재사용한다
        (이 서버가 새로 기록하면 바로 무효. 같은 DB를 쓰는 다른 서버의 기록은 최대 ROWS_CACHE_SECONDS 늦게 보인다)."""
        now = self._clock()
        cached = self._rows_cache
        if cached and cached[1] == seconds and cached[2] == self._gen and 0 <= now - cached[0] < ROWS_CACHE_SECONDS:
            return copy.deepcopy(cached[3])
        gen = self._gen  # 읽기 전 번호 — 읽는 사이 누가 기록하면 번호가 달라져 이 결과는 캐시로 쓰이지 않는다
        def q(cur):
            cur.execute(f"SELECT {', '.join(COLUMNS)} FROM observations "
                        f"WHERE seen_at > {self._ph} AND COALESCE(source, '') <> {self._ph} ORDER BY seen_at",
                        (now - seconds, PUBLIC_SOURCE))
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
                              sorted(body["additional"]), body["price"], body["sold"], body["other_world"]],
                             ensure_ascii=False)
            latest.pop(key, None)
            latest[key] = body  # 다시 넣어 '가장 최근 본 순서'를 유지
        out = list(latest.values())
        self._rows_cache = (now, seconds, gen, out)
        return copy.deepcopy(out)  # 호출자가 고쳐도(안쪽 목록까지) 캐시는 그대로

    def _today(self) -> str:
        return dt.datetime.fromtimestamp(self._clock(), dt.timezone(dt.timedelta(hours=9))).date().isoformat()

    def quota_used(self, who: str) -> int:
        """오늘(KST) who가 쓴 AI 판독 횟수."""
        def q(cur):
            cur.execute(f"SELECT n FROM vision_quota WHERE day = {self._ph} AND who = {self._ph}", (self._today(), who))
            row = cur.fetchone()
            return int(row[0]) if row else 0
        return self._run(q)

    def quota_add(self, who: str) -> None:
        """한 번 더 세고, 지난 날짜 줄은 지운다(오늘 것만 남긴다)."""
        day, ph = self._today(), self._ph
        def ins(cur):
            cur.execute(f"DELETE FROM vision_quota WHERE day <> {ph}", (day,))
            cur.execute(f"INSERT INTO vision_quota (day, who, n) VALUES ({ph}, {ph}, 1) "
                        "ON CONFLICT (day, who) DO UPDATE SET n = vision_quota.n + 1", (day, who))
        self._run(ins)

    def quota_take(self, who: str) -> int:
        """한 번 차감하고 차감 뒤 오늘 횟수를 돌려준다(확인과 기록 사이 틈이 없게, 2026-10-17). 지난 날짜 줄은 지운다."""
        day, ph = self._today(), self._ph
        def take(cur):
            cur.execute(f"DELETE FROM vision_quota WHERE day <> {ph}", (day,))
            cur.execute(f"INSERT INTO vision_quota (day, who, n) VALUES ({ph}, {ph}, 1) "
                        "ON CONFLICT (day, who) DO UPDATE SET n = vision_quota.n + 1 RETURNING n", (day, who))
            return int(cur.fetchone()[0])
        return self._run(take)

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
    if url:
        try:
            return ObservationLog.postgres(url, clock)
        except Exception as e:  # noqa: BLE001 — 관측 DB에 못 붙어도 사이트는 뜬다(2026-10-17 배포 장애: 시작하다 죽어 502)
            if type(e).__name__ == "LockNotAvailable":  # psycopg.errors — psycopg가 없는 환경에서도 import 없이 판별
                # 붙기는 했는데 칸 더하기가 표 잠금에 막힘 — SQLite로 넘어가면 기록이 두 곳으로 갈라진다. 시작을 실패시켜
                # 컨테이너 재시작(restart: unless-stopped)으로 잠금이 풀린 뒤 다시 붙는다
                raise
            import logging
            logging.getLogger("uvicorn.error").warning("관측 DB(Postgres) 연결 실패 — 로컬 SQLite로 돈다: %s", type(e).__name__)
    return ObservationLog.sqlite(sqlite_path, clock)
