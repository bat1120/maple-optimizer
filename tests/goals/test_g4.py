"""G4 판정 (Python 부분): FastAPI가 빌드 결과를 서빙. 빌드·vitest는 scripts/verify.ps1이 따로 판정한다."""
import pathlib

from fastapi.testclient import TestClient

from helpers import bundle
from server.app import create_app

DIST = pathlib.Path(__file__).resolve().parents[2] / "web" / "dist"


def test_criterion3_fastapi_serves_built_web(tmp_path):
    assert (DIST / "index.html").exists(), "web/dist 없음 — npm --prefix web run build 먼저"
    c = TestClient(create_app(lambda n, d: bundle("레테"), str(tmp_path / "c.sqlite3"), static_dir=str(DIST)))
    r = c.get("/")
    assert r.status_code == 200 and '<div id="root">' in r.text
    assert c.get("/api/health").json() == {"status": "ok"}
