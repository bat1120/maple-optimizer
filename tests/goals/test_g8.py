"""G8 판정 — 녹화 fixture 기반 E2E: 조회 → 세팅 → 매물 → 강화 비용 → 직작 비교 → 예산 최적화 (서버 API 연쇄)."""
import json
import pathlib

from fastapi.testclient import TestClient

from helpers import bundle
from server.app import create_app

ROOT = pathlib.Path(__file__).resolve().parents[2]
RESULTS = ROOT / "goals" / "results" / "G8.json"
RING = {"slot": "반지4", "part": "반지", "name": "더 센 반지",
        "total": {"INT": 80, "LUK": 80, "MATK": 30}, "potentials": ["INT +12%", "INT +12%", "INT +12%", "마력 +12"]}


def test_criterion1_e2e_api_chain(tmp_path):
    c = TestClient(create_app(lambda n, d: bundle("레테"), str(tmp_path / "e2e.sqlite3")))
    out = {}

    s = c.get("/api/character/내신부레테").json()
    assert s["character_class"] == "레테"

    best = c.get("/api/character/내신부레테/settings").json()["ranking"][0]["setting"]
    out["best_setting"] = best

    lst = c.post("/api/character/내신부레테/listings",
                 json={"setting": best, "listings": [{**RING, "price": 3_000_000_000}]}).json()
    out["listing_delta_pct"] = lst["ranking"][0]["delta_pct"]
    assert lst["ranking"][0]["delta_pct"] > 0

    sf = c.post("/api/enhance/starforce", json={"level": 200, "start": 17, "target": 22,
                                                "destroy_cost": 3_000_000_000, "trials": 20000}).json()
    assert sf["exact_mean"] > 0 and sf["distribution"]["median"] <= sf["distribution"]["p90"]
    out["starforce_17_22_mean"] = sf["exact_mean"]

    cube = c.post("/api/enhance/cube", json={"table": "레전드리/무기/200", "level": 200, "grade": "레전드리",
                                             "lines_at_least": {"BOSS": 2}}).json()
    assert 0 < cube["probability"] < 1 and cube["cubes"]["mean"] > 1
    out["cube_boss2_probability"] = cube["probability"]

    cmp_ = c.post("/api/craft/compare", json={"price": 20_000_000_000, "base_price": 2_000_000_000, "level": 200,
                                               "start_star": 0, "target_star": 22, "destroy_cost": 3_000_000_000,
                                               "cube_p": cube["probability"], "cube_cost": cube["cost_per_reset"]}).json()
    assert 0 <= cmp_["prob_craft_costs_more"] <= 1 and cmp_["craft_mean"] > 2_000_000_000
    out["craft_compare"] = cmp_

    opt = c.post("/api/character/내신부레테/optimize", json={
        "setting": best, "budget": 5_000_000_000,
        "candidates": [{**RING, "price": 3_000_000_000}, {**RING, "slot": "반지1", "price": 4_000_000_000}]}).json()
    assert opt["spent"] <= 5_000_000_000 and len({a["slot"] for a in opt["actions"]}) == len(opt["actions"])
    assert opt["gain_pct"] > 0
    out["optimize"] = opt
    RESULTS.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


def test_criterion3_readme_documents_local_run_and_secrets():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    for needle in ("scripts/run-local.ps1", "NEXON_API_KEY", ".env", "uv sync", "npm --prefix web"):
        assert needle in text, needle
