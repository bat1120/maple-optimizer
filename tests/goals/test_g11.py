"""G11 판정 — 관리자 전용 AI 에이전트(OpenAI Responses API). 모델 응답은 가짜 클라이언트로 고정한다(실호출은 H5)."""
import json
import pathlib
from types import SimpleNamespace as NS

from fastapi.testclient import TestClient

from agent.loop import run_agent
from agent.numbers import unverified_numbers
from agent.tools import ToolBox
from helpers import bundle
from nexon.convert import snapshot
from server.admin import make_password_hash
from server.app import create_app

RESULTS = pathlib.Path(__file__).resolve().parents[2] / "goals" / "results" / "G11.json"
_m: dict = {}


def _record(k, v):
    _m[k] = v
    RESULTS.write_text(json.dumps(_m, ensure_ascii=False, indent=1), encoding="utf-8")


class FakeLLM:
    """OpenAI client.responses.create 흉내. 스크립트된 응답을 순서대로 돌려주고 호출 인자를 기록한다."""

    def __init__(self, script):
        self.script, self.calls = list(script), []
        self.responses = NS(create=self._create)

    def _create(self, **kw):
        self.calls.append(kw)
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def tool_turn(*calls):
    items = [NS(type="reasoning", id="rs_1")] + [
        NS(type="function_call", id=f"fc{i}", call_id=f"call_{i}", name=n, arguments=json.dumps(a, ensure_ascii=False))
        for i, (n, a) in enumerate(calls)]
    return NS(output=items, output_text="", status="completed", usage=NS(input_tokens=1000, output_tokens=100))


def text_turn(text):
    msg = NS(type="message", role="assistant", content=[NS(type="output_text", text=text)])
    return NS(output=[msg], output_text=text, status="completed", usage=NS(input_tokens=1200, output_tokens=200))


def run(script, question, toolbox):
    fake = FakeLLM(script)
    events = list(run_agent(fake, toolbox, [{"role": "user", "content": question}], max_turns=6))
    return fake, events


def toolbox():
    return ToolBox(lambda name, date=None: snapshot(bundle("레테")))


def tool_results(events):
    return [e["result"] for e in events if e["type"] == "tool_result"]


def test_criterion1_four_scenarios_call_the_right_tools():
    tb = toolbox()
    scenarios = {
        "보스 세팅": ([("rank_settings", {"name": "내신부레테", "boss_defense": 300})], "rank_settings"),
        "매물": ([("evaluate_listings", {"name": "내신부레테", "boss_defense": 300, "listings": [
            {"slot": "반지4", "part": "반지", "name": "센 반지", "total": {"INT": 90, "LUK": 59, "MATK": 30},
             "potentials": ["INT +12%", "LUK +9%", "INT +9%"], "price": 3_000_000_000}]})], "evaluate_listings"),
        "스타포스": ([("starforce_cost", {"level": 200, "start": 0, "target": 22, "destroy_cost": 3_000_000_000})], "starforce_cost"),
        "예산": ([("optimize_budget", {"name": "내신부레테", "budget": 5_000_000_000, "boss_defense": 300, "candidates": [
            {"slot": "반지4", "part": "반지", "name": "센 반지", "total": {"INT": 90, "MATK": 30}, "potentials": [],
             "price": 3_000_000_000}]})], "optimize_budget"),
    }
    ok = 0
    for label, (calls, expected) in scenarios.items():
        fake, events = run([tool_turn(*calls), text_turn("계산 결과를 정리했어요.")], label, tb)
        names = [e["name"] for e in events if e["type"] == "tool_call"]
        results = tool_results(events)
        if names == [expected] and results and "error" not in results[0] and events[-1]["type"] == "done":
            ok += 1
        from agent.loop import DEFAULT_MODEL
        assert fake.calls[0]["model"] == DEFAULT_MODEL
        assert fake.calls[0]["store"] is False and fake.calls[0]["reasoning"] == {"effort": "medium"}
        assert {t["name"] for t in fake.calls[0]["tools"]} >= {expected}
        assert all(t["parameters"]["additionalProperties"] is False for t in fake.calls[0]["tools"])
    _record("criterion1_scenarios_ok", f"{ok}/4")
    assert ok == 4


def test_criterion2_number_provenance():
    tb = toolbox()
    fake, events = run([tool_turn(("starforce_cost", {"level": 200, "start": 21, "target": 22, "destroy_cost": 0})),
                        text_turn("placeholder")], "21→22 비용", tb)
    res = tool_results(events)[0]
    mean = res["exact_mean"]
    honest = f"21성에서 22성까지 평균 {mean / 1e8:.2f}억 메소가 듭니다."
    forged = "21성에서 22성까지 평균 999억 메소가 듭니다."
    assert unverified_numbers(honest, [res]) == []
    caught = unverified_numbers(forged, [res])
    _record("criterion2", {"honest_unverified": 0, "forged_caught": caught})
    assert caught  # 위조 숫자 검출
    # 루프의 done 이벤트도 같은 검사를 붙인다
    fake, events = run([tool_turn(("starforce_cost", {"level": 200, "start": 21, "target": 22, "destroy_cost": 0})),
                        text_turn(forged)], "21→22 비용", tb)
    assert events[-1]["type"] == "done" and events[-1]["unverified_numbers"]


def _app(tmp_path, script, budget=1_000_000):
    fake = FakeLLM(script)
    app = create_app(lambda n, d: bundle("레테"), str(tmp_path / "c.sqlite3"),
                     agent_client=fake, admin_password_hash=make_password_hash("secret-pw", iterations=1000),
                     session_secret="s" * 32, agent_daily_token_budget=budget)
    return fake, TestClient(app)


def _sse(text):
    return [json.loads(line[6:]) for line in text.splitlines() if line.startswith("data: ")]


def test_criterion3_admin_auth(tmp_path):
    fake, c = _app(tmp_path, [text_turn("안녕하세요")])
    body = {"messages": [{"role": "user", "content": "안녕"}]}
    assert c.post("/api/agent/chat", json=body).status_code == 401
    assert c.post("/api/admin/login", json={"password": "wrong"}).status_code == 401
    assert c.post("/api/admin/login", json={"password": "secret-pw"}).status_code == 200
    r = c.post("/api/agent/chat", json=body)
    _record("criterion3", {"chat_after_login": r.status_code})
    assert r.status_code == 200 and _sse(r.text)[-1]["type"] == "done"


def test_criterion4_daily_budget_blocks_calls(tmp_path):
    fake, c = _app(tmp_path, [text_turn("첫 답")] * 3, budget=1000)
    c.post("/api/admin/login", json={"password": "secret-pw"})
    first = _sse(c.post("/api/agent/chat", json={"messages": [{"role": "user", "content": "1"}]}).text)  # 1400 토큰 사용
    calls_before = len(fake.calls)
    second = _sse(c.post("/api/agent/chat", json={"messages": [{"role": "user", "content": "2"}]}).text)
    _record("criterion4", {"calls_after_budget": len(fake.calls) - calls_before, "message": second[0].get("message")})
    assert first[-1]["type"] == "done"
    assert len(fake.calls) == calls_before
    assert second[0]["type"] == "error" and "토큰" in second[0]["message"] and second[-1]["type"] == "done"


def test_criterion5_errors_surface_as_sse_events(tmp_path):
    fake, c = _app(tmp_path, [RuntimeError("upstream down")])
    c.post("/api/admin/login", json={"password": "secret-pw"})
    events = _sse(c.post("/api/agent/chat", json={"messages": [{"role": "user", "content": "x"}]}).text)
    _record("criterion5", [e["type"] for e in events])
    assert [e["type"] for e in events][-2:] == ["error", "done"]
