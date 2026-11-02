"""AI 상담을 모두에게(2026-10-17 사용자: 모두 쓸 수 있게, 일반 사용자는 제한).
- 로그인 없이 채팅 가능. 일반 사용자는 IP당 하루 agent_public_daily번(관측 DB에 날짜별 HMAC 해시로 센다 — IP 원문 저장 없음)
- 관리자는 횟수 제한 없음. 하루 토큰 한도(agent_daily_token_budget)는 모두에게 그대로
- 일반 사용자는 refresh_market(웹 경매장 검색 — 일일 검색 한도 소진) 도구를 못 쓴다
- GET /api/agent/quota: 화면이 남은 횟수를 보여 준다"""
import json
from types import SimpleNamespace as NS

from fastapi.testclient import TestClient

from helpers import bundle
from server.admin import make_password_hash
from server.app import create_app


class Fake:
    def __init__(self):
        self.calls = []
        self.responses = NS(create=self._create)

    def _create(self, **kw):
        self.calls.append(kw)
        msg = NS(type="message", role="assistant", content=[NS(type="output_text", text="답")])
        return NS(output=[msg], output_text="답", status="completed", usage=NS(input_tokens=1, output_tokens=1))


def _app(tmp_path, fake, **kw):
    return TestClient(create_app(lambda n, d: bundle("레테"), str(tmp_path / "c.sqlite3"), agent_client=fake,
                                 admin_password_hash=make_password_hash("pw", iterations=1000), session_secret="s" * 32,
                                 auction_mcp_command="echo", **kw))


BODY = {"messages": [{"role": "user", "content": "안녕"}]}


def _types(r):
    return [json.loads(ln[6:])["type"] for ln in r.text.splitlines() if ln.startswith("data: ")]


def test_public_user_can_chat_until_daily_limit(tmp_path):
    fake = Fake()
    c = _app(tmp_path, fake, agent_public_daily=2)
    assert c.get("/api/agent/quota").json() == {"admin": False, "limit": 2, "remaining": 2}
    for _ in range(2):
        r = c.post("/api/agent/chat", json=BODY)
        assert r.status_code == 200 and _types(r)[-1] == "done"
    assert c.get("/api/agent/quota").json()["remaining"] == 0
    r = c.post("/api/agent/chat", json=BODY)
    assert r.status_code == 429 and r.json()["code"] == "AGENT_QUOTA" and len(fake.calls) == 2


def test_admin_has_no_question_limit_and_quota_survives_restart(tmp_path):
    fake = Fake()
    c = _app(tmp_path, fake, agent_public_daily=1)
    assert c.post("/api/agent/chat", json=BODY).status_code == 200
    c2 = _app(tmp_path, fake, agent_public_daily=1)  # 재시작해도 이어서 센다
    assert c2.post("/api/agent/chat", json=BODY).status_code == 429
    assert c2.post("/api/admin/login", json={"password": "pw"}).status_code == 200
    assert c2.get("/api/agent/quota").json() == {"admin": True, "limit": None, "remaining": None}
    for _ in range(3):
        assert c2.post("/api/agent/chat", json=BODY).status_code == 200


def test_public_user_cannot_refresh_market(tmp_path):
    fake = Fake()
    c = _app(tmp_path, fake)
    c.post("/api/agent/chat", json=BODY)
    assert "refresh_market" not in {t["name"] for t in fake.calls[0]["tools"]}
    c.post("/api/admin/login", json={"password": "pw"})
    c.post("/api/agent/chat", json=BODY)
    assert "refresh_market" in {t["name"] for t in fake.calls[1]["tools"]}
