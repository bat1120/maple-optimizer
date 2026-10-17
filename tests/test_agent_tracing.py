"""AI 상담 추적(2026-10-17 사용자: Langfuse). 키가 없으면 아무것도 안 한다. 추적이 실패해도 답변은 나간다.
대화 하나 = 추적 하나(agent), 모델 호출마다 generation(모델·토큰), 도구 호출마다 tool(입력·결과·오류)."""
import contextlib
import json
from types import SimpleNamespace as NS

from agent.loop import run_agent
from agent.tools import ToolBox
from agent.tracing import NoopTracer, from_env
from helpers import bundle
from nexon.convert import snapshot


class Obs:
    def __init__(self, log, name, as_type, kw):
        self.log, self.rec = log, {"name": name, "as_type": as_type, **kw, "updates": []}
        log.append(self.rec)

    def update(self, **kw):
        self.rec["updates"].append(kw)


class FakeTracer:
    def __init__(self, broken=False):
        self.log, self.conv, self.broken = [], None, broken

    @contextlib.contextmanager
    def conversation(self, **kw):
        self.conv = kw
        with self.observe("agent_chat", "agent", input=kw.get("input")) as root:
            yield root

    @contextlib.contextmanager
    def observe(self, name, as_type="span", **kw):
        if self.broken:
            raise RuntimeError("tracing down")
        yield Obs(self.log, name, as_type, kw)


def _fake_llm(script):
    calls = []

    def create(**kw):
        calls.append(kw)
        return script.pop(0)
    return NS(responses=NS(create=create)), calls


def _tool_turn(name, args):
    return NS(output=[NS(type="function_call", id="fc", call_id="c1", name=name, arguments=json.dumps(args))],
              output_text="", status="completed", usage=NS(input_tokens=100, output_tokens=10))


def _text_turn(text):
    msg = NS(type="message", role="assistant", content=[NS(type="output_text", text=text)])
    return NS(output=[msg], output_text=text, status="completed", usage=NS(input_tokens=200, output_tokens=20))


def test_conversation_records_generations_and_tools():
    llm, _ = _fake_llm([_tool_turn("starforce_cost", {"level": 200, "start": 0, "target": 17, "destroy_cost": 0}),
                        _text_turn("평균 비용이에요.")])
    tb = ToolBox(lambda name, date=None: snapshot(bundle("레테")))
    tr = FakeTracer()
    events = list(run_agent(llm, tb, [{"role": "user", "content": "17성 비용?"}], tracer=tr,
                            trace_user="admin", trace_meta={"public": False}))
    assert events[-1]["type"] == "done"
    assert tr.conv["user_id"] == "admin" and tr.conv["metadata"] == {"public": False}
    kinds = [(r["as_type"], r["name"]) for r in tr.log]
    assert kinds[0] == ("agent", "agent_chat")
    gens = [r for r in tr.log if r["as_type"] == "generation"]
    tools = [r for r in tr.log if r["as_type"] == "tool"]
    assert len(gens) == 2 and gens[0]["model"]
    assert gens[0]["updates"][-1]["usage_details"] == {"input": 100, "output": 10}
    assert tools[0]["name"] == "starforce_cost" and tools[0]["input"]["target"] == 17
    assert "output" in tools[0]["updates"][-1]
    assert tr.log[0]["updates"][-1]["output"] == "평균 비용이에요."


def test_broken_tracer_never_breaks_the_answer():
    llm, _ = _fake_llm([_text_turn("답")])
    tb = ToolBox(lambda name, date=None: snapshot(bundle("레테")))
    events = list(run_agent(llm, tb, [{"role": "user", "content": "x"}], tracer=FakeTracer(broken=True)))
    assert [e["type"] for e in events] == ["text", "done"]


def test_from_env_is_noop_without_keys(monkeypatch):
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    assert isinstance(from_env(), NoopTracer)


def test_server_traces_chat_with_admin_or_hashed_user(tmp_path):
    from fastapi.testclient import TestClient
    from server.admin import make_password_hash
    from server.app import create_app
    llm, _ = _fake_llm([_text_turn("답"), _text_turn("답")])
    tr = FakeTracer()
    tr.flushed = 0
    tr.flush = lambda: setattr(tr, "flushed", tr.flushed + 1)
    c = TestClient(create_app(lambda n, d: bundle("레테"), str(tmp_path / "c.sqlite3"), agent_client=llm,
                              admin_password_hash=make_password_hash("pw", iterations=1000), session_secret="s" * 32,
                              agent_tracer=tr))
    c.post("/api/agent/chat", json={"messages": [{"role": "user", "content": "안녕"}]})
    public_user = tr.conv["user_id"]
    assert public_user and public_user != "admin" and "testclient" not in public_user and tr.conv["metadata"]["public"]
    c.post("/api/admin/login", json={"password": "pw"})
    c.post("/api/agent/chat", json={"messages": [{"role": "user", "content": "안녕"}]})
    assert tr.conv["user_id"] == "admin" and tr.conv["metadata"]["public"] is False
    assert tr.flushed == 2
