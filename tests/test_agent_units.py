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
