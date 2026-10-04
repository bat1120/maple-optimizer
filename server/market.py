"""관측 시세 저장소: 화면 분석이 읽은 경매장 매물(부위·잠재·에디·스타포스·가격)을 쌓는다.

경매장을 자동으로 조회하지 않는다 — 사용자가 공유한 화면에서 읽은 것만 저장한다(넥슨 약관).
"""
import json
import pathlib
import sqlite3
from collections.abc import Callable

KEEP_SECONDS = 30 * 86400  # 시세는 금방 바뀐다 — 30일 지난 관측은 지운다


class PriceStore:
    def __init__(self, path: str, clock: Callable[[], float]):
        pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.execute("CREATE TABLE IF NOT EXISTS observed (key TEXT PRIMARY KEY, seen_at REAL, body TEXT)")
        self._clock = clock

    def record(self, read: dict) -> bool:
        """가격과 잠재·에디 줄이 있는 매물만 저장한다. 같은 매물·같은 가격은 한 번만. 저장했으면 True."""
        price = read.get("price")
        lines = list(read.get("potential_lines") or []), list(read.get("additional") or [])
        if not price or not (lines[0] or lines[1]) or not read.get("category"):
            return False
        body = {"category": read["category"], "name": read.get("name"), "part": read.get("part"),
                "starforce": read.get("starforce") or 0, "level": read.get("level"),
                "potential_grade": read.get("potential_grade"), "additional_grade": read.get("additional_grade"),
                "total": read.get("total") or {}, "potential_lines": lines[0], "additional": lines[1],
                "price": int(price), "sold": bool(read.get("sold")), "other_world": bool(read.get("other_world")),
                "source": read.get("source") or "화면"}
        key = json.dumps([body["category"], body["name"], body["starforce"], sorted(lines[0]), sorted(lines[1]),
                          body["price"], body["sold"]], ensure_ascii=False)
        now = self._clock()
        self._db.execute("DELETE FROM observed WHERE seen_at <= ?", (now - KEEP_SECONDS,))
        cur = self._db.execute("INSERT OR IGNORE INTO observed VALUES (?, ?, ?)",
                               (key, now, json.dumps(body, ensure_ascii=False)))
        self._db.commit()
        return cur.rowcount == 1

    def rows(self) -> list[dict]:
        return [{**json.loads(body), "seen_at": seen}
                for seen, body in self._db.execute("SELECT seen_at, body FROM observed ORDER BY seen_at")]
