"""저장소 연결 하나를 FastAPI 작업 스레드들이 같이 쓴다 — 동시에 읽고 써도 깨지지 않는다(2026-10-11: 동시 roadmap 요청에서 500)."""
from concurrent.futures import ThreadPoolExecutor

from server.cache import BundleCache
from server.market import PriceStore


def test_bundle_cache_concurrent_get_put(tmp_path):
    c = BundleCache(str(tmp_path / "c.sqlite3"), clock=lambda: 1000.0)
    c.put("레테", None, {"x": 1})

    def work(i):
        c.put(f"캐릭{i % 5}", None, {"i": i})
        return c.get("레테", None)

    with ThreadPoolExecutor(16) as ex:
        assert all(r == {"x": 1} for r in ex.map(work, range(400)))


def test_price_store_concurrent_record_rows(tmp_path):
    p = PriceStore(str(tmp_path / "p.sqlite3"), clock=lambda: 1000.0)

    def work(i):
        p.record({"price": 100 + i, "category": "엠블렘", "potential_lines": ["마력 +12%"]})
        return len(p.rows())

    with ThreadPoolExecutor(16) as ex:
        list(ex.map(work, range(300)))
    assert len(p.rows()) == 300
