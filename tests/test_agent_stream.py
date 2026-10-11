"""AI 상담 스트림이 오래 조용하면 끊기던 문제(2026-10-12: 데모에서 recommend_searches 31초 + 모델 응답 동안 아무것도 안 보내
'호출'에서 멈춘 채 답이 안 옴). 기다리는 동안 SSE 주석(': ping')을 보내 연결을 살려 둔다."""
import json
import time
from types import SimpleNamespace as NS

from fastapi.testclient import TestClient

from helpers import bundle
from server.admin import make_password_hash
from server.app import create_app


class SlowLLM:
    def __init__(self, delay):
        self.delay = delay
        self.responses = NS(create=self._create)

    def _create(self, **kw):
        time.sleep(self.delay)
        msg = NS(type="message", role="assistant", content=[NS(type="output_text", text="답")])
        return NS(output=[msg], output_text="답", status="completed", usage=NS(input_tokens=1, output_tokens=1))


def test_agent_stream_sends_keepalive_while_waiting(tmp_path):
    app = create_app(lambda n, d: bundle("레테"), str(tmp_path / "c.sqlite3"), agent_client=SlowLLM(0.5),
                     admin_password_hash=make_password_hash("pw", iterations=1000), session_secret="s" * 32,
                     agent_ping_seconds=0.1)
    c = TestClient(app)
    assert c.post("/api/admin/login", json={"password": "pw"}).status_code == 200
    r = c.post("/api/agent/chat", json={"messages": [{"role": "user", "content": "안녕"}]})
    assert r.status_code == 200
    assert ": ping" in r.text
    events = [json.loads(ln[6:]) for ln in r.text.splitlines() if ln.startswith("data: ")]
    assert [e["type"] for e in events][-2:] == ["text", "done"]
