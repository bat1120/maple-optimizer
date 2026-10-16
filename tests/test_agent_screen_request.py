"""AI가 먼저 추천하고, 필요하면 채팅 안에서 경매장 화면을 요청한다(2026-10-12 사용자: 관리자만, 'A + 버튼으로 보내기').
- request_auction_screen: 검색 조건을 돌려주면 화면이 채팅 안에 [화면 연결] 카드를 띄운다
- GET /api/admin/session: 캐릭터 화면이 관리자에게만 AI 상담을 보이게 쓴다"""
from fastapi.testclient import TestClient

from agent.loop import SYSTEM
from agent.tools import TOOL_DEFS, ToolBox, openai_tools
from helpers import bundle
from nexon.convert import snapshot
from server.admin import make_password_hash
from server.app import create_app


def test_request_auction_screen_tool_is_defined_and_echoes_search():
    names = [t["name"] for t in TOOL_DEFS]
    assert "request_auction_screen" in names
    tool = next(t for t in openai_tools() if t["name"] == "request_auction_screen")
    assert tool["parameters"]["additionalProperties"] is False
    tb = ToolBox(lambda name, date=None: snapshot(bundle("레테")))
    out = tb.run("request_auction_screen", {"category": "보조무기", "potentials": ["마력 +12%"],
                                            "additional": ["마력 +9%"], "min_starforce": 0, "note": "에디도 같이"})
    assert out["status"] == "requested"
    assert out["search"] == {"category": "보조무기", "potentials": ["마력 +12%"], "additional": ["마력 +9%"], "min_starforce": 0}
    assert "error" not in out


def test_system_prompt_tells_ai_to_request_screen_for_auction_questions():
    assert "request_auction_screen" in SYSTEM


def test_admin_session_endpoint(tmp_path):
    app = create_app(lambda n, d: bundle("레테"), str(tmp_path / "c.sqlite3"),
                     admin_password_hash=make_password_hash("pw", iterations=1000), session_secret="s" * 32)
    c = TestClient(app)
    assert c.get("/api/admin/session").json() == {"admin": False}
    assert c.post("/api/admin/login", json={"password": "pw"}).status_code == 200
    assert c.get("/api/admin/session").json() == {"admin": True}
