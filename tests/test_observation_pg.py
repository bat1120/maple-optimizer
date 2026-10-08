"""관측 기록을 진짜 Postgres로(Neon과 같은 SQL). TEST_DATABASE_URL이 있을 때만 — 없으면 건너뛴다(로컬 Docker로 확인).
  docker run -d --name pgtest -e POSTGRES_PASSWORD=test -p 55432:5432 postgres:16-alpine
  TEST_DATABASE_URL=postgresql://postgres:test@127.0.0.1:55432/postgres uv run pytest tests/test_observation_pg.py"""
import csv
import io
import os

import pytest

from server.observations import ObservationLog

URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="TEST_DATABASE_URL 없음")

READ = {"category": "장갑", "name": "에테르넬 메이지글러브", "starforce": 22, "level": 250, "potential_grade": "레전드리",
        "potential_lines": ["크리티컬 데미지 +8%"], "additional": ["마력 +10"], "total": {"INT": 100}, "price": 12_300_000_000}


def test_postgres_record_dedupe_stats_export():
    import psycopg
    with psycopg.connect(URL) as c:
        c.execute("DROP TABLE IF EXISTS observations")
    now = [1_800_000_000.0]
    log = ObservationLog.postgres(URL, clock=lambda: now[0])
    assert log.record(READ) is True and log.record(READ) is False
    now[0] += 86400
    assert log.record(READ) is True
    assert log.record({**READ, "category": "반지", "name": "어센던트 펄스 링", "sold": True}) is True
    s = log.stats()
    assert s["total"] == 3 and s["by_category"] == {"반지": 1, "장갑": 2} and s["backend"] == "postgres"
    rows = list(csv.DictReader(io.StringIO(log.export_csv())))
    assert len(rows) == 3 and rows[0]["name"] == "에테르넬 메이지글러브"


def test_postgres_reconnects_after_server_drops_connection():
    log = ObservationLog.postgres(URL, clock=lambda: 1_900_000_000.0)
    log._conn.close()                       # 쉬는 동안 끊긴 것처럼
    assert log.count() >= 0                 # 다시 연결해서 된다


def test_postgres_vision_quota_counts_per_day():
    import psycopg
    with psycopg.connect(URL) as c:
        c.execute("DROP TABLE IF EXISTS vision_quota")
    now = [1_800_000_000.0]
    log = ObservationLog.postgres(URL, clock=lambda: now[0])
    assert log.quota_used("a") == 0
    assert log.quota_add("a") == 1 and log.quota_add("a") == 2 and log.quota_add("b") == 1
    now[0] += 86400
    assert log.quota_used("a") == 0 and log.quota_add("a") == 1


def test_postgres_rows_last_30_days_and_adds_new_columns_to_old_table():
    import psycopg
    with psycopg.connect(URL) as c:
        c.execute("DROP TABLE IF EXISTS observations")
        c.execute("CREATE TABLE observations (id BIGSERIAL PRIMARY KEY, key TEXT UNIQUE, seen_at DOUBLE PRECISION, day TEXT, "
                  "category TEXT, name TEXT, part TEXT, starforce INTEGER, level INTEGER, potential_grade TEXT, "
                  "additional_grade TEXT, potential_lines TEXT, additional TEXT, total TEXT, price BIGINT, sold BOOLEAN, "
                  "other_world BOOLEAN, source TEXT)")  # 2026-10-07 표(새 칸 없음)
    now = [1_800_000_000.0]
    log = ObservationLog.postgres(URL, clock=lambda: now[0])
    assert log.record({**READ, "name": "오래된"})
    now[0] += 31 * 86400
    assert log.record({**READ, "equip_type": "장갑", "job_groups": ["마법사"]})
    now[0] += 86400
    assert log.record(READ)
    rows = log.rows()
    assert [r["name"] for r in rows] == ["에테르넬 메이지글러브"] and rows[0]["seen_at"] == now[0]
    assert ObservationLog.postgres(URL, clock=lambda: now[0]).count() == 3  # 다시 열어도(칸 더하기 반복) 된다
