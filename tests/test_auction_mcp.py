"""maple-auction-mcp 연결: 로드맵 단계 조건으로 웹 경매장을 검색(판매 중·판매 완료)해 관측 시세에 넣는다.
검색은 일일 한도가 있어 갱신 한 번에 쓰는 횟수를 제한한다. 가짜 MCP 서버로 검증한다(브라우저 확장 불필요)."""
import json
import sys

import pytest

from helpers import bundle
from nexon.convert import snapshot
from server.auction_mcp import McpStdioClient, McpUnavailable, filters_for, refresh_market, to_observed
from server.market import PriceStore

FAKE = [sys.executable, "tests/fake_auction_mcp.py"]


def test_target_lines_become_summed_option_filters():
    assert filters_for(["INT +9%", "INT +6%", "INT +6%"]) == [{"option": "intPercent", "minValue": 21}]
    assert filters_for(["스킬 재사용 대기시간 -2초", "INT +9%"]) == [
        {"option": "skillCooldownReduction", "minValue": 2}, {"option": "intPercent", "minValue": 9}]
    assert filters_for(["마력 +12%", "마력 +11", "캐릭터 기준 9레벨 당 INT +1", "보스 몬스터 데미지 +30%"]) == [
        {"option": "magicAttackPercent", "minValue": 12}, {"option": "magicAttack", "minValue": 11},
        {"option": "intPerLevel", "minValue": 1}, {"option": "bossDamagePercent", "minValue": 30}]


def test_mcp_item_summary_becomes_observed_row():
    item = {"name": "에테르넬 메이지로브", "price": 2e10, "starforce": 22, "stat": "INT+520 LUK+330 마력+220 보공%+30 올스탯%+6",
            "potential": "레전드리: INT +13% / INT +10%", "additional": "레어: 마력 +12", "status": "SOLD", "isMyWorld": False}
    row = to_observed(item, "상의", "상의")
    assert row["total"] == {"INT": 520, "LUK": 330, "MATK": 220, "BOSS": 30, "ALL%": 6}
    assert (row["potential_grade"], row["potential_lines"]) == ("레전드리", ["INT +13%", "INT +10%"])
    assert (row["additional_grade"], row["additional"]) == ("레어", ["마력 +12"])
    assert row["sold"] is True and row["other_world"] is True and row["source"] == "경매장 검색"


def test_stdio_client_calls_tool():
    with McpStdioClient(FAKE) as c:
        r = c.call("search_armor", {"subCategory": "ARMOR_ARMOR_COAT"})
    assert r["items"][0]["name"] == "에테르넬 메이지로브" and r["searchRemaining"] == 87


def test_refresh_searches_roadmap_conditions_records_and_respects_budget(tmp_path, monkeypatch):
    log = tmp_path / "calls.jsonl"
    monkeypatch.setenv("FAKE_MCP_LOG", str(log))
    store = PriceStore(str(tmp_path / "m.sqlite3"), lambda: 1.0)
    snap = snapshot(bundle("레테"))
    r = refresh_market(snap, FAKE, store, slots=["상의"], max_searches=3)
    calls = [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines()]
    assert len(calls) == 3 and r["searched"] == 3 and r["search_remaining"] == 87
    args = calls[0]["arguments"]
    assert calls[0]["name"] == "search_armor" and args["subCategory"] == "ARMOR_ARMOR_COAT"
    assert args["starforceMin"] == 22 and args["levelMin"] == 150 and args["jobClass"] == "MAGE"
    assert {c["arguments"].get("sold", False) for c in calls} == {True, False}
    rows = store.rows()
    assert {x["sold"] for x in rows} == {True, False} and all(x["category"] == "상의" for x in rows)


def test_refresh_reports_when_extension_is_not_connected(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_MCP_DOWN", "1")
    store = PriceStore(str(tmp_path / "m.sqlite3"), lambda: 1.0)
    with pytest.raises(McpUnavailable, match="확장"):
        refresh_market(snapshot(bundle("레테")), FAKE, store, slots=["상의"], max_searches=2)


def test_refresh_route_is_admin_only_and_disabled_without_command(tmp_path):
    from fastapi.testclient import TestClient
    from server.admin import make_password_hash
    from server.app import create_app
    mk = lambda cmd: TestClient(create_app(lambda n, d: bundle("레테"), str(tmp_path / "c.sqlite3"),  # noqa: E731
                                           admin_password_hash=make_password_hash("pw", 1000), session_secret="s" * 32,
                                           auction_mcp_command=cmd))
    off = mk(None)
    assert off.post("/api/market/refresh", json={"name": "x"}).status_code == 401
    off.post("/api/admin/login", json={"password": "pw"})
    r = off.post("/api/market/refresh", json={"name": "x"})
    assert r.status_code == 503 and "AUCTION_MCP" in r.json()["message"]
    on = mk(FAKE)
    on.post("/api/admin/login", json={"password": "pw"})
    r = on.post("/api/market/refresh", json={"name": "내신부레테", "slots": ["상의"], "max_searches": 2}).json()
    assert r["searched"] == 2 and r["recorded"] >= 1
    paths = on.get("/api/character/내신부레테/paths").json()
    assert any(p["path"] == "구매" and p["slot"] == "상의" for p in paths["all"])
