"""넥슨 응답 번들 캐시 (SQLite). 현재 데이터는 15분, 과거 날짜는 30일(넥슨 약관 30일 갱신 의무) 보관."""
import datetime as dt
import json
import pathlib
import sqlite3
import threading
from collections.abc import Callable

CURRENT_TTL = 15 * 60
PAST_TTL = 30 * 86400


class BundleCache:
    def __init__(self, path: str, clock: Callable[[], float]):
        pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.execute("CREATE TABLE IF NOT EXISTS bundles (key TEXT PRIMARY KEY, fetched REAL, body TEXT)")
        self._clock = clock
        # 연결 하나를 FastAPI 작업 스레드들이 같이 쓴다 — 동시 요청(예: 요약 1순위 띠 + 업그레이드 순위)에서
        # 'bad parameter or other API misuse'로 500이 났다(2026-10-11). 한 번에 하나만.
        self._lock = threading.Lock()

    @staticmethod
    def _key(name: str, day: dt.date | None) -> str:
        return f"{name.casefold()}|{day.isoformat() if day else 'current'}"

    def get(self, name: str, day: dt.date | None) -> dict | None:
        key = self._key(name, day)
        with self._lock:
            row = self._db.execute("SELECT fetched, body FROM bundles WHERE key = ?", (key,)).fetchone()
            if row is None:
                return None
            ttl = CURRENT_TTL if day is None else PAST_TTL
            if self._clock() - row[0] >= ttl:
                self._db.execute("DELETE FROM bundles WHERE key = ?", (key,))
                self._db.commit()
                return None
        return json.loads(row[1])

    def put(self, name: str, day: dt.date | None, body: dict) -> None:
        now = self._clock()
        with self._lock:
            self._db.execute("DELETE FROM bundles WHERE fetched <= ?", (now - PAST_TTL,))
            self._db.execute("INSERT OR REPLACE INTO bundles VALUES (?, ?, ?)",
                             (self._key(name, day), now, json.dumps(body, ensure_ascii=False)))
            self._db.commit()
