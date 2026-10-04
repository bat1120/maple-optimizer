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


def test_man_particle_is_not_ten_thousand():
    """"프리셋 2만의 효과"의 '만'은 '오직'이다 (2026-10-04 실사용 오탐)."""
    assert unverified_numbers("이건 프리셋 2만의 효과가 아니라 조합 전체 값입니다.", [{}]) == []
    got = {raw: v for raw, v, _ in extract("가격 3000만 메소, 45억 3000만")}
    assert got["3000만"] == 30_000_000 and got["45억 3000만"] == 4_530_000_000


def test_vision_signature_ignores_ocr_noise_in_price_and_totals():
    from server.vision import signature
    a = {"name": "에테르넬 메이지햇", "starforce": 22, "potentials": ["LUK +13%", "스킬 재사용 대기시간 -2초"],
         "price": 4_500_000_000, "total": {"INT": 120}}
    b = {**a, "price": 4_500_000_001, "total": {"INT": 121}}
    assert signature(a) == signature(b)


def test_vision_item_without_total_options_is_not_evaluated():
    """총 옵션을 못 읽으면 기본 스탯 0인 템처럼 평가돼 큰 음수가 나온다 → 평가 보류."""
    from helpers import bundle
    from nexon.convert import snapshot
    from server.service import vision_items
    snap = snapshot(bundle("레테"))
    row = vision_items(snap, None, 300, [{"name": "에테르넬 메이지햇", "category": "모자", "part": "모자", "starforce": 22,
                                          "total": {}, "potentials": ["LUK +13%"], "price": 4_500_000_000}], set())[0]
    assert row["evaluated"] is False and "총 옵션" in row["reason"]


def test_negative_numbers_and_numbers_inside_strings_are_verified():
    """2026-10-04 실호출 오탐: '-10.43%'(도구 값 -10.43)와 잠재 문자열 'INT +12%' 속 숫자."""
    src = [{"listings": [{"potentials": ["INT +12%", "LUK +13%"]}]},
           {"ranking": [{"delta_pct": -10.4312, "per_100m": -0.2318}]}]
    text = "실딜 -10.43%, 억당 -0.23%, 잠재 INT 12%·LUK 13%"
    assert unverified_numbers(text, src) == []
    assert unverified_numbers("실딜 -55.5%", src) == ["55.5%"]


def test_lookup_character_reports_boss_setting_as_evaluation_basis():
    from helpers import bundle
    from nexon.convert import snapshot
    from agent.tools import ToolBox
    r = ToolBox(lambda name, date=None: snapshot(bundle("레테"))).run("lookup_character", {"name": "x"})
    assert r["active_setting"]["equipment"] == 1                     # 지금은 사냥 세팅
    assert r["evaluation_setting"] == {"equipment": 2, "hyper": 3, "ability": 2, "union": 3, "link": 2}
    assert "보스" in r["evaluation_note"]
