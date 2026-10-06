"""G12 판정 — 경매장 화면 실시간 분석. 비전 모델 응답은 가짜 클라이언트로 고정한다(실호출은 H6)."""
import json
import pathlib
import subprocess
from types import SimpleNamespace as NS

from fastapi.testclient import TestClient

from engine.stats.evaluate import swap_item
from engine.stats.metrics import BossProfile
from engine.stats.sets import SetCatalog
from helpers import bundle
from nexon.convert import snapshot
from server.admin import make_password_hash
from server.app import create_app
from server.vision import VisionError, extract_listings

ROOT = pathlib.Path(__file__).resolve().parents[2]
RESULTS = ROOT / "goals" / "results" / "G12.json"
REPORT = ROOT / "goals" / "results" / "G12-vitest.json"
IMG = "data:image/png;base64,iVBORw0KGgo="
RING = {"name": "센 반지", "category": "반지", "part": "반지", "starforce": 17,
        "total": {"STR": None, "DEX": None, "INT": 90, "LUK": 59, "HP": None, "ATK": None, "MATK": 30,
                  "ALL%": None, "BOSS": None, "IED": None, "DMG": None},
        "potentials": ["INT +12%", "LUK +9%", "INT +9%"], "price": 3_000_000_000}
_m: dict = {}


def _record(k, v):
    _m[k] = v
    RESULTS.write_text(json.dumps(_m, ensure_ascii=False, indent=1), encoding="utf-8")


class FakeVision:
    def __init__(self, *payloads):
        self.payloads, self.calls = list(payloads), []
        self.responses = NS(create=self._create)

    def _create(self, **kw):
        self.calls.append(kw)
        text = self.payloads.pop(0)
        return NS(output=[], output_text=text, status="completed", usage=NS(input_tokens=800, output_tokens=200))


def test_criterion1_screen_watch_change_detection_in_web():
    subprocess.run(["npm", "--prefix", "web", "test", "--", "--reporter=json", f"--outputFile={REPORT}"],
                   cwd=ROOT, capture_output=True, shell=True)
    data = json.loads(REPORT.read_text(encoding="utf-8"))
    results = [a for f in data["testResults"] for a in f["assertionResults"] if "screen watch" in a["fullName"]]
    _record("criterion1_screen_watch_tests", {r["title"]: r["status"] for r in results})
    assert len(results) >= 3 and all(r["status"] == "passed" for r in results)


def test_criterion2_extraction_and_bad_json():
    fake = FakeVision(json.dumps({"tooltip_visible": True, "listings": [RING]}, ensure_ascii=False), "{not json")
    out = extract_listings(fake, IMG)
    assert out["tooltip_visible"] and out["listings"][0]["total"] == {"INT": 90, "LUK": 59, "MATK": 30}
    kw = fake.calls[0]
    assert kw["text"]["format"]["type"] == "json_schema" and kw["text"]["format"]["strict"] is True
    assert kw["input"][0]["content"][1] == {"type": "input_image", "image_url": IMG, "detail": "high"}
    try:
        extract_listings(fake, IMG)
        raised = False
    except VisionError:
        raised = True
    _record("criterion2_bad_json_raises", raised)
    assert raised


def _app(tmp_path, fake, budget=1_000_000):
    return TestClient(create_app(lambda n, d: bundle("레테"), str(tmp_path / "c.sqlite3"), agent_client=fake,
                                 admin_password_hash=make_password_hash("pw", iterations=1000), session_secret="s" * 32,
                                 agent_daily_token_budget=budget))


def test_criterion3_and_4_dedupe_and_best_ring_slot(tmp_path):
    payload = json.dumps({"tooltip_visible": True, "listings": [RING]}, ensure_ascii=False)
    fake = FakeVision(payload, payload)
    c = _app(tmp_path, fake)
    c.post("/api/admin/login", json={"password": "pw"})
    body = {"image": IMG, "name": "내신부레테", "boss_defense": 300}
    first = c.post("/api/vision/listings", json=body).json()
    second = c.post("/api/vision/listings", json={**body, "seen": [first["items"][0]["signature"]]}).json()
    _record("criterion3", {"first_evaluated": len([i for i in first["items"] if i["evaluated"]]),
                           "second_evaluated": len([i for i in second["items"] if i["evaluated"]])})
    assert first["items"][0]["evaluated"] and not second["items"][0]["evaluated"]
    # ④ 수작업: 반지1~4 각각에 끼워 본 실딜 지수 최대 슬롯
    from engine.market.listing import item_from_input
    from engine.stats.evaluate import rank_settings
    snap = snapshot(bundle("레테"))
    cat, boss = SetCatalog.load(), BossProfile("x", 300.0)
    setting = rank_settings(snap, boss, cat)[0][0]
    it = item_from_input("반지?", "반지", "센 반지", {"INT": 90, "LUK": 59, "MATK": 30}, RING["potentials"], snap.level, 17)
    best = max(("반지1", "반지2", "반지3", "반지4"), key=lambda s: swap_item(snap, setting, s, it, boss, cat))
    _record("criterion4", {"engine_slot": first["items"][0]["slot"], "hand_slot": best})
    assert first["items"][0]["slot"] == best


def test_criterion5_auth_and_budget(tmp_path):
    payload = json.dumps({"tooltip_visible": False, "listings": []})
    fake = FakeVision(payload, payload)
    c = _app(tmp_path, fake, budget=500)
    # 2026-10-07 사용자 결정(공개 + 한도): 로그인 없이도 판독된다 — 하루 토큰 한도는 누구에게나 그대로 걸린다
    assert c.post("/api/vision/listings", json={"image": IMG}).status_code == 200   # 1000 토큰 사용(일반 유저)
    c.post("/api/admin/login", json={"password": "pw"})
    r = c.post("/api/vision/listings", json={"image": IMG})
    _record("criterion5", {"after_budget_status": r.status_code, "calls": len(fake.calls)})
    assert r.status_code == 429 and "토큰" in r.json()["message"] and len(fake.calls) == 1
