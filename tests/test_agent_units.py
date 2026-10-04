from agent.numbers import extract, unverified_numbers
from server.admin import check_password, make_password_hash, sign_session, valid_session


def test_extract_korean_money_and_percent():
    got = {raw: v for raw, v, _ in extract("평균 178억 8700만, 확률 2.765%, 22성, 1,234회")}
    assert got["178억 8700만"] == 17_887_000_000
    assert got["2.765%"] == 2.765
    assert got["1,234"] == 1234
    assert "22" not in got  # 30 이하 정수(서수)는 검사 대상 아님


def test_numbers_match_with_display_rounding_and_fraction_to_percent():
    src = [{"exact_mean": 17_887_123_456, "probability": 0.027650, "relative_to_active": 1.42}]
    assert unverified_numbers("평균 178.87억, 확률 2.77%, 42.0% 더 셉니다", src) == []
    assert unverified_numbers("평균 200억", src) == ["200억"]


def test_password_hash_and_session():
    h = make_password_hash("pw", iterations=1000)
    assert check_password("pw", h) and not check_password("nope", h) and not check_password("pw", "garbage")
    tok = sign_session("k" * 32, now=1000.0)
    assert valid_session(tok, "k" * 32, now=2000.0)
    assert not valid_session(tok, "x" * 32, now=2000.0)          # 다른 비밀키
    assert not valid_session(tok, "k" * 32, now=1000.0 + 13 * 3600)  # 만료
    assert not valid_session(tok.replace(".", ".0"), "k" * 32, now=2000.0)


def _client(*responses):
    from types import SimpleNamespace as NS
    seq = list(responses)
    return NS(responses=NS(create=lambda **kw: seq.pop(0)))


def _toolbox():
    from agent.tools import ToolBox
    return ToolBox(lambda name, date=None: None)


def test_refusal_and_incomplete_become_error_events():
    from types import SimpleNamespace as NS
    from agent.loop import run_agent
    usage = NS(input_tokens=1, output_tokens=1)
    refused = NS(output=[NS(type="message", content=[NS(type="refusal", refusal="정책상 불가")])], output_text="",
                 status="completed", usage=usage)
    ev = list(run_agent(_client(refused), _toolbox(), [{"role": "user", "content": "x"}]))
    assert [e["type"] for e in ev] == ["error", "done"] and "정책상 불가" in ev[0]["message"]
    cut = NS(output=[], output_text="", status="incomplete", usage=usage)
    ev = list(run_agent(_client(cut), _toolbox(), [{"role": "user", "content": "x"}]))
    assert [e["type"] for e in ev] == ["error", "done"]


def test_bad_tool_arguments_are_returned_to_model_as_error():
    from types import SimpleNamespace as NS
    from agent.loop import run_agent
    usage = NS(input_tokens=1, output_tokens=1)
    bad = NS(output=[NS(type="function_call", call_id="c1", name="starforce_cost", arguments="{broken")],
             output_text="", status="completed", usage=usage)
    final = NS(output=[NS(type="message", content=[NS(type="output_text", text="다시 할게요")])], output_text="다시 할게요",
               status="completed", usage=usage)
    ev = list(run_agent(_client(bad, final), _toolbox(), [{"role": "user", "content": "x"}]))
    results = [e for e in ev if e["type"] == "tool_result"]
    assert results and "JSON" in results[0]["result"]["error"] and ev[-1]["type"] == "done"


def test_setup_secrets_update_env_keeps_other_lines():
    import importlib.util, pathlib
    spec = importlib.util.spec_from_file_location("setup_secrets", pathlib.Path(__file__).parents[1] / "tools" / "setup_secrets.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    out = m.update_env("NEXON_API_KEY=abc\nOPENAI_API_KEY=\n# 주석\n", {"OPENAI_API_KEY": "k1", "SESSION_SECRET": "s"})
    assert out == "NEXON_API_KEY=abc\nOPENAI_API_KEY=k1\n# 주석\nSESSION_SECRET=s\n"
