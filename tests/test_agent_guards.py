"""AI 상담: 프롬프트로 부탁하던 규칙을 코드로 막은 것들, 그리고 평가 세트(tools/agent_eval)의 채점기.
2026-11-22 평가에서 나온 문제 — 도구 결과가 너무 커 질문 하나가 토큰 한도를 넘고, 모델이 메소를 억·만으로 옮기다 자릿수를 틀렸다."""
import importlib.util
import json
import pathlib

import pytest

from agent.loop import SYSTEM, invented_argument
from agent.numbers import extract, unverified_numbers
from agent.tools import MAX_REFRESH_PER_QUESTION, TOOL_DEFS, ToolBox, compact
from helpers import bundle, classes
from nexon.convert import snapshot

EVAL = pathlib.Path(__file__).resolve().parent.parent / "tools" / "agent_eval"
RING = {"slot": "반지4", "part": "반지", "name": "어센던트 펄스 링", "total": {"INT": 59, "LUK": 59, "MATK": 16},
        "potentials": ["INT +12%", "LUK +9%", "INT +9%"], "price": 4_530_000_000}


def _box(**kw):
    return ToolBox(lambda name, date=None: snapshot(bundle("레테")), market=lambda: [], **kw)


def _size(result) -> int:
    return len(json.dumps(result, ensure_ascii=False, default=str))


def test_compact_keeps_meso_exact_and_shortens_small_floats():
    assert compact({"p": 0.007026608358000001, "cost": 63963369193.9246, "n": 3, "ok": True, "rows": [0.1 + 0.2]}) == \
        {"p": 0.00702661, "cost": 63963369194, "n": 3, "ok": True, "rows": [0.3]}


def test_tool_results_stay_small_enough_for_one_question():
    box = _box()
    assert _size(box.run("lookup_character", {"name": "x"})) < 8_000
    assert _size(box.run("upgrade_roadmap", {"name": "x"})) < 30_000
    assert _size(box.run("upgrade_paths", {"name": "x"})) < 25_000


def test_lookup_character_gives_boss_setting_equipment_only():
    r = _box().run("lookup_character", {"name": "x"})
    assert "equipment_presets" not in r and len(r["equipment"]) > 15
    hat = next(it for it in r["equipment"] if it["slot"] == "모자")
    assert hat["name"] and hat["potentials"] and "stats" not in hat


def test_roadmap_lists_only_next_step_and_the_one_after():
    r = _box().run("upgrade_roadmap", {"name": "x"})
    for row in r["slots"]:
        for kind in ("잠재", "에디"):
            assert len(row[kind]) <= 2
            assert row["next"][kind] == (0 if row[kind] else None)
            assert all(stage["cube_cost_text"].endswith("만") for stage in row[kind] if stage.get("cube_cost"))
    assert 0 < len(r["value_ranking"]) <= 15


def test_cost_tools_carry_text_the_model_can_quote():
    box = _box()
    sf = box.run("starforce_cost", {"level": 200, "start": 17, "target": 22, "destroy_cost": 0})
    assert sf["exact_mean_text"] == "87억 4687만" and set(sf["distribution_text"]) == {"mean", "median", "p75", "p90"}
    cube = box.run("cube_probability", {"option": "BOSS", "kind": "lines", "value": 3})
    assert cube["meso_text"]["mean"].endswith("만")
    craft = box.run("craft_compare", {"price": 5e9, "base_price": 1e9, "level": 200})
    assert craft["craft_mean_text"] and craft["distribution_text"]["median"]


def test_listing_price_in_wrong_unit_is_rejected_with_a_fix():
    r = _box().run("evaluate_listings", {"name": "x", "listings": [{**RING, "price": 45}]})
    assert "4530000000" in r["error"]
    assert "error" not in _box().run("evaluate_listings", {"name": "x", "listings": [RING]})


@pytest.mark.parametrize("tool,key", [("evaluate_listings", "listings"), ("optimize_budget", "candidates")])
def test_fee_rate_is_one_of_the_two_real_rates(tool, key):
    args = {"name": "x", key: [RING], **({"budget": 10**10} if tool == "optimize_budget" else {})}
    assert "fee_rate" in _box().run(tool, {**args, "fee_rate": 0.01})["error"]
    assert "error" not in _box().run(tool, {**args, "fee_rate": 0.03})


def test_refresh_market_is_limited_per_question():
    calls = []
    box = _box(refresh=lambda name, slots, n: calls.append(name) or {"searched": 1})
    results = [box.run("refresh_market", {"name": "x"}) for _ in range(MAX_REFRESH_PER_QUESTION + 1)]
    assert len(calls) == MAX_REFRESH_PER_QUESTION and "error" in results[-1] and "error" not in results[0]


def test_cooldown_value_must_come_from_the_user():
    asked = ["[조회한 캐릭터: 레테] 쿨감 가치도 넣어서 추천해줘"]
    assert "cooldown_main_pct" in invented_argument({"name": "레테", "cooldown_main_pct": 5}, asked)["error"]
    assert invented_argument({"name": "레테"}, asked) is None
    assert invented_argument({"name": "레테", "cooldown_main_pct": 5}, [*asked, "쿨감 1초를 주스탯 5%로 쳐줘"]) is None


def test_rules_moved_to_code_are_not_repeated_in_the_prompt():
    for phrase in ("두 번 넘게 부르지 않는다", "N을 대신 정하지 않는다", "가격은 메소 정수로 넣는다"):
        assert phrase not in SYSTEM, phrase
    listing_price = next(t for t in TOOL_DEFS if t["name"] == "evaluate_listings")["input_schema"]["properties"]["listings"]
    assert "4530000000" in listing_price["items"]["properties"]["price"]["description"]


def test_number_check_reads_commas_in_man_units():
    assert [v for _, v, _ in extract("약 87억 5,915만 메소")] == [8_759_150_000.0]
    assert [v for _, v, _ in extract("5,915만")] == [59_150_000.0]
    assert unverified_numbers("평균 87억 5,915만 메소입니다.", [{"mean": 8759151521}]) == []
    assert unverified_numbers("평균 8억 7,591만 메소입니다.", [{"mean": 8759151521}]) == ["8억 7,591만"]


def test_number_check_tells_money_from_only():
    assert unverified_numbers("재설정은 4395만으로 측정됐습니다.", [{"cube_cost_text": "4395만"}]) == []
    assert unverified_numbers("재설정은 4395만으로 측정됐습니다.", [{"cube_cost_text": "9999만"}]) == ["4395만"]
    assert extract("프리셋 2만의 차이") == [] and extract("프리셋 2만으로 충분") == []


def _grader():
    spec = importlib.util.spec_from_file_location("agent_eval_grade", EVAL / "grade.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_eval_cases_are_well_formed():
    spec = json.loads((EVAL / "cases.json").read_text(encoding="utf-8"))
    tools = {t["name"] for t in TOOL_DEFS}
    ids = [c["id"] for c in spec["cases"]]
    assert spec["character"] in classes() and len(ids) == len(set(ids)) >= 10
    for case in spec["cases"]:
        assert case["question"] and case["why"], case["id"]
        named = [n for want in case.get("must_call", []) for n in (want if isinstance(want, list) else [want])]
        named += case.get("must_not_call", []) + [r["tool"] for r in case.get("args", [])]
        assert set(named) <= tools, case["id"]


def test_eval_grader_judges_calls_arguments_and_answer():
    grade = _grader().grade
    case = {"must_call": [["upgrade_paths", "recommend_searches"]], "must_not_call": ["rank_settings"],
            "args": [{"tool": "evaluate_listings", "path": "listings.0.price", "equals": 4530000000},
                     {"tool": "evaluate_listings", "path": "setting", "absent": True}],
            "answer_matches": ["억당"], "answer_not_matches": ["프리셋을 바꾸세요"]}
    good = [{"type": "tool_call", "name": "upgrade_paths", "input": {"name": "레테"}},
            {"type": "tool_call", "name": "evaluate_listings", "input": {"name": "레테", "listings": [{"price": 4530000000}]}},
            {"type": "text", "text": "억당 +0.050%가 가장 높아요."}, {"type": "done", "unverified_numbers": []}]
    assert all(c["ok"] for c in grade(case, good))

    bad = [{"type": "tool_call", "name": "rank_settings", "input": {"name": "레테"}},
           {"type": "tool_call", "name": "evaluate_listings", "input": {"listings": [{"price": 45}], "setting": {"equipment": 1}}},
           {"type": "text", "text": "프리셋을 바꾸세요. 약 30억이에요."}, {"type": "done", "unverified_numbers": ["30억"]}]
    failed = {c["what"] for c in grade(case, bad) if not c["ok"]}
    assert len(failed) == 7, failed

    cut_off = [{"type": "error", "message": "질문 한 번에 쓸 수 있는 AI 양을 넘었어요."}, {"type": "done", "unverified_numbers": []}]
    assert {c["what"] for c in grade({}, cut_off) if not c["ok"]} == {"오류 없이 끝났다", "답변이 있다"}


def _tool_turn(input_tokens, text=""):
    from types import SimpleNamespace as NS
    return NS(output=[NS(type="function_call", id="fc", call_id="c", name="cube_probability",
                         arguments=json.dumps({"option": "BOSS", "kind": "lines", "value": 3}))],
              output_text=text, status="completed", usage=NS(input_tokens=input_tokens, output_tokens=100))


def _answer_turn(input_tokens, text):
    from types import SimpleNamespace as NS
    return NS(output=[NS(type="message", role="assistant", content=[NS(type="output_text", text=text)])],
              output_text=text, status="completed", usage=NS(input_tokens=input_tokens, output_tokens=100))


class _Scripted:
    def __init__(self, turns):
        from types import SimpleNamespace as NS
        self.turns, self.calls = list(turns), []
        self.responses = NS(create=self._create)

    def _create(self, **kw):
        self.calls.append(kw)
        return self.turns.pop(0)


def test_last_affordable_turn_answers_without_more_tools():
    """한도가 한 턴 분량만 남으면 도구를 막고 답하게 한다 — 6만 토큰을 쓰고 답 없이 끝나지 않게."""
    from agent.loop import run_agent
    client = _Scripted([_tool_turn(10_000), _tool_turn(20_000), _answer_turn(25_000, "지금까지 결과로 답해요.")])
    events = list(run_agent(client, _box(), [{"role": "user", "content": "x"}], max_tokens=60_000))
    assert [c.get("tool_choice") for c in client.calls] == [None, None, "none"]
    assert [e["type"] for e in events if e["type"] in ("text", "error")] == ["text"]
    assert events[-1]["type"] == "done"


def test_turns_run_freely_when_budget_is_ample_or_unlimited():
    from agent.loop import run_agent
    for limit in (None, 1_000_000):
        client = _Scripted([_tool_turn(10_000), _tool_turn(20_000), _answer_turn(25_000, "답")])
        list(run_agent(client, _box(), [{"role": "user", "content": "x"}], max_tokens=limit))
        assert all("tool_choice" not in c for c in client.calls)


def test_number_check_accepts_percentile_named_by_result_key():
    result = {"distribution_text": {"median": "78억 9058만", "p90": "143억 2743만"}}
    assert unverified_numbers("90% 지점은 143억 2743만입니다.", [result]) == []
    assert unverified_numbers("95% 지점은 143억 2743만입니다.", [result]) == ["95%"]


def test_number_check_accepts_numbers_in_result_names():
    assert unverified_numbers("30% 할인 이벤트는 적용하지 않았어요.", [{"conditions": {"discount30": False}}]) == []


def test_eval_case_needs_two_of_three_when_first_try_fails():
    spec = importlib.util.spec_from_file_location("agent_eval_run", EVAL / "run.py")
    run = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(run)

    def scripted(outcomes):
        left = list(outcomes)
        return lambda *_: {"ok": left.pop(0), "tokens": 10, "checks": [{"what": "확인", "ok": False, "detail": ""}]}

    once = run.run_case(None, "m", {}, "레테", attempt=scripted([True]))
    assert (once["ok"], once["attempts"], once["flaky"], once["tokens"]) == (True, [True], False, 10)
    flaky = run.run_case(None, "m", {}, "레테", attempt=scripted([False, True, True]))
    assert (flaky["ok"], flaky["attempts"], flaky["flaky"], flaky["tokens"]) == (True, [False, True, True], True, 30)
    assert flaky["failed_checks"] == ["확인"]
    broken = run.run_case(None, "m", {}, "레테", attempt=scripted([False, True, False]))
    assert (broken["ok"], broken["flaky"]) == (False, True)


def test_prompt_stays_minimal_and_names_no_tools():
    """프롬프트는 방향만 — 도구 이름·금지 목록을 다시 쌓지 않는다(2026-11-23 사용자 지시)."""
    assert len(SYSTEM) < 900
    for t in TOOL_DEFS:
        assert t["name"] not in SYSTEM, t["name"]
    for word in ("않는다", "금지", "말고"):
        assert word not in SYSTEM, word


def test_context_carries_the_looked_up_character():
    from agent.loop import context
    assert "레테" in context([{"role": "user", "content": "뭐부터?\n\n[조회한 캐릭터: 레테]"}])
    assert "닉네임을 받는다" in context([{"role": "user", "content": "뭐부터?"}])
    client = _Scripted([_answer_turn(100, "닉네임을 알려 주세요.")])
    from agent.loop import run_agent
    list(run_agent(client, _box(), [{"role": "user", "content": "뭐부터?"}]))
    assert client.calls[0]["instructions"].startswith(SYSTEM) and "조회한 캐릭터: 없음" in client.calls[0]["instructions"]


def test_character_name_must_come_from_the_user():
    assert "닉네임" in invented_argument({"name": "아무개"}, ["지금 뭐부터 올리면 돼?"])["error"]
    assert invented_argument({"name": "레테"}, ["[조회한 캐릭터: 레테] 뭐부터?"]) is None
    assert invented_argument({"name": "내신부레테"}, ["내신부 레테 봐줘"]) is None
    assert invented_argument({"option": "BOSS"}, ["확률?"]) is None


def test_answer_with_unsourced_number_is_rewritten_before_it_is_shown():
    from agent.loop import run_agent
    client = _Scripted([_tool_turn(1000), _answer_turn(1000, "평균 123억 4567만이에요."), _answer_turn(1000, "측정값 없음이에요.")])
    events = list(run_agent(client, _box(), [{"role": "user", "content": "얼마야?"}]))
    assert [e["text"] for e in events if e["type"] == "text"] == ["측정값 없음이에요."]
    assert client.calls[2]["tool_choice"] == "none"
    assert "123억 4567만" in client.calls[2]["input"][-1]["content"]
    assert events[-1] == {"type": "done", "unverified_numbers": []}


def test_rewrite_happens_once_then_the_warning_is_shown():
    from agent.loop import run_agent
    client = _Scripted([_answer_turn(1000, "평균 123억 4567만이에요."), _answer_turn(1000, "그래도 123억 4567만이에요.")])
    events = list(run_agent(client, _box(), [{"role": "user", "content": "얼마야?"}]))
    assert len(client.calls) == 2
    assert events[-1]["unverified_numbers"] == ["123억 4567만"]


def test_listings_are_held_or_expanded_by_code():
    base = {"slot": "반지4", "part": "반지", "name": "어센던트 펄스 링", "total": {"INT": 59, "LUK": 59, "MATK": 16},
            "potentials": ["INT +12%", "LUK +9%", "INT +9%"]}
    r = _box().run("evaluate_listings", {"name": "레테", "listings": [
        {**base, "name": "A", "price": 4_530_000_000, "unverified_lines": ["INT +1즈%"]},
        {**base, "name": "B", "price": None},
        {**base, "name": "C", "price": None, "list_prices": [3_000_000_000, 4_000_000_000]}]})
    assert "error" not in r
    reasons = {h["name"]: h["reason"] for h in r["held"]}
    assert "공식 옵션표" in reasons["A"] and "가격을 물어본다" in reasons["B"]
    assert sorted(row["price"] for row in r["ranking"]) == [3_000_000_000, 4_000_000_000]
    assert "C" in r["price_candidates_note"]


def test_budget_roadmap_stops_inside_the_budget():
    """재화에 맞춰 어디까지 올릴지(2026-11-23 사용자: 프로젝트 목적) — 누적 비용이 예산을 넘지 않는 데까지 자른다."""
    from server.service import meso_text
    r = _box().run("budget_roadmap", {"name": "레테", "budget": 5_000_000_000})
    assert "error" not in r and r["steps"] and r["budget_text"] == "50억"
    assert r["spent_text"] == r["steps"][-1]["total_cost_text"]
    gains = [s["gain_pct_after"] for s in r["steps"]]
    assert gains == sorted(gains) and r["gain_pct"] == gains[-1] > 0
    assert r["next_step"]["short_text"] and "평균 기대값" in r["note"]
    assert "추옵" in {s["path"] for s in r["steps"]}  # 효율 1위인 추옵 재설정이 빠지지 않는다
    assert _size(r) < 12_000
    small = _box().run("budget_roadmap", {"name": "레테", "budget": 1_000_000})
    assert small["steps"] == [] and small["gain_pct"] == 0 and small["left_text"] == meso_text(1_000_000)
    assert "메소 정수" in _box().run("budget_roadmap", {"name": "레테", "budget": 50})["error"]
