"""G3 판정 — GOALS.md G3 성공 기준."""
import json
import pathlib
import re
import subprocess

from fastapi.testclient import TestClient

from helpers import bundle
from nexon.client import CharacterNotFound, InvalidKey, RateLimited, Unavailable
from server.app import create_app

ROOT = pathlib.Path(__file__).resolve().parents[2]
RESULTS = ROOT / "goals" / "results" / "G3.json"
_m: dict = {}


def _record(k, v):
    _m[k] = v
    RESULTS.write_text(json.dumps(_m, ensure_ascii=False, indent=1), encoding="utf-8")


def test_criterion1_at_least_12_endpoint_tests_pass_without_skip():
    out = subprocess.run(["uv", "run", "pytest", "tests/test_server.py", "-q", "-rs", "-p", "no:cacheprovider"],
                         cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    m = re.search(r"(\d+) passed", out.stdout)
    passed = int(m[1]) if m else 0
    _record("criterion1_server_tests_passed", passed)
    assert out.returncode == 0, out.stdout[-2000:]
    assert "skipped" not in out.stdout
    assert passed >= 12


def test_criterion2_second_lookup_hits_cache(tmp_path):
    calls = []

    def fetcher(name, day):
        calls.append(name)
        return bundle("레테")

    c = TestClient(create_app(fetcher, str(tmp_path / "c.sqlite3")))
    assert c.get("/api/character/내신부레테").status_code == 200
    assert c.get("/api/character/내신부레테").status_code == 200
    _record("criterion2_nexon_calls_for_two_lookups", len(calls))
    assert len(calls) == 1


def test_criterion3_four_nexon_errors_map_to_distinct_statuses(tmp_path):
    seen = {}
    for exc in (CharacterNotFound, RateLimited, Unavailable, InvalidKey):
        def fetcher(name, day, exc=exc):
            raise exc("X", "m", 400)
        r = TestClient(create_app(fetcher, str(tmp_path / f"{exc.__name__}.sqlite3"))).get("/api/character/아무개")
        body = r.json()
        assert re.search(r"[가-힣]", body["message"]), body
        seen[exc.__name__] = r.status_code
    _record("criterion3_status_map", seen)
    assert len(set(seen.values())) == 4


def test_criterion4_ip_rate_limit_returns_429(tmp_path):
    c = TestClient(create_app(lambda n, d: bundle("레테"), str(tmp_path / "r.sqlite3"), rate_limit=3))
    codes = [c.get("/api/health").status_code for _ in range(4)]
    _record("criterion4_codes", codes)
    assert codes[:3] == [200, 200, 200] and codes[3] == 429
