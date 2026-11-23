"""약한 캐릭터·무기 없는 캐릭터(2026-11-24 직업별 측정에서 찾음): 서버 오류(500) 대신 무엇을 하면 되는지 알려 준다."""
import copy

import pytest
from fastapi.testclient import TestClient

from engine.market.listing import NoDamage
from helpers import bundle
from nexon.convert import snapshot
from server import service
from server.app import create_app


def test_plan_says_why_when_no_damage_goes_in():
    snap = snapshot(bundle("레테"))
    with pytest.raises(NoDamage) as e:
        service.budget_roadmap(snap, 100000.0, None)                        # 어떤 세팅으로도 피해가 0인 방어율
    assert f"방어율 무시가 {snap.final.ied:.1f}%" in str(e.value) and "낮추면" in str(e.value)
    assert service.no_damage_text(snap, 300.0) is None                      # 피해가 들어가는 캐릭터는 그대로
    assert service.budget_roadmap(snap, 300.0, None)["steps"]


def test_api_answers_422_not_500(tmp_path):
    c = TestClient(create_app(lambda name, day: bundle("레테"), str(tmp_path / "a.sqlite3")), raise_server_exceptions=False)
    for path in ("budget-roadmap", "roadmap", "recommend", "paths"):
        r = c.get(f"/api/character/레테/{path}?boss_defense=100000")
        assert r.status_code == 422 and r.json()["code"] == "NO_DAMAGE", (path, r.status_code)
        assert "보스 방어율을 낮추면" in r.json()["message"]


def test_character_saved_without_a_weapon_gets_a_clear_message(tmp_path):
    body = copy.deepcopy(bundle("레테"))
    eq = body["character/item-equipment"]
    for key, value in eq.items():
        if isinstance(value, list):
            eq[key] = [it for it in value if it.get("item_equipment_slot") != "무기"]
    c = TestClient(create_app(lambda name, day: body, str(tmp_path / "b.sqlite3")), raise_server_exceptions=False)
    r = c.get("/api/character/레테")
    assert r.status_code == 422 and r.json()["code"] == "NO_WEAPON" and "무기를 끼고" in r.json()["message"]
