"""화면 판독 가격 보정(2026-11-13 내신부레테 실사용 — 이름 보정은 tests/test_tooltip_image.py):
- 18성 레전드리 커맨더 포스 이어링 가격이 1,774,480메소로 기록됨(자릿수 빠짐) → AI가 억·만을 직접 환산하지 않고
  화면 글자(price_text)를 그대로 옮기고, 메소 환산은 코드가 한다."""
import pytest

from server.vision import _PROMPT, _SCHEMA, normalize_listing, parse_meso


@pytest.mark.parametrize("text,meso", [
    ("1,774,480,000", 1_774_480_000),
    ("17억 7,448만", 1_774_480_000),
    ("17억 7448만 메소", 1_774_480_000),
    ("8억", 800_000_000),
    ("883만 9385", 8_839_385),
    ("123,456", 123_456),
    ("1,234억", 123_400_000_000),
])
def test_parse_meso(text, meso):
    assert parse_meso(text) == meso


@pytest.mark.parametrize("text", [None, "", "가격", "판매 완료"])
def test_parse_meso_rejects_non_prices(text):
    assert parse_meso(text) is None


def test_price_text_overrides_ai_conversion():
    x = normalize_listing({"name": "커맨더 포스 이어링", "category": "귀고리", "part": "귀고리", "potentials": [],
                           "price": 1_774_480, "price_text": "17억 7,448만"})
    assert x["price"] == 1_774_480_000


def test_price_kept_when_text_missing_or_unreadable():
    assert normalize_listing({"name": "모자", "category": "모자", "part": "모자", "price": 5, "price_text": None})["price"] == 5
    assert normalize_listing({"name": "모자", "category": "모자", "part": "모자", "price": 5, "price_text": "??"})["price"] == 5


def test_schema_asks_for_verbatim_price_text():
    props = _SCHEMA["properties"]["listings"]["items"]
    assert "price_text" in props["required"] and "price_text" in props["properties"]
    assert "price_text" in _PROMPT
    assert "메소 정수로 바꾼다" not in _PROMPT  # 환산은 코드가 한다


def test_price_log_shows_what_was_read_for_tooltip_items():
    """2026-11-13: 80억 7999만 9999 매물을 1,931,721로 읽음 — 서버 로그에 툴팁 매물의 화면 가격 글자와 환산값을 남긴다."""
    from server.vision import price_log
    rows = [{"name": "커맨더 포스 이어링", "tooltip": 0, "price_text": "80억 7999만 9999", "price": 8_079_999_999},
            {"name": "목록 행", "tooltip": None, "price_text": "1억", "price": 100_000_000},
            {"name": "가격 없음", "tooltip": 1, "price_text": None, "price": None}]
    rows.append({"name": "빈 목록 행", "tooltip": None, "price_text": None, "price": None})
    assert price_log(rows) == ("커맨더 포스 이어링 [툴팁] '80억 7999만 9999'→8079999999, 목록 행 '1억'→100000000, "
                               "가격 없음 [툴팁] None→None")
    assert price_log([]) == ""


def test_combat_power_delta_is_never_taken_as_price():
    """2026-11-13 실사용 캡처: 가격 칸이 툴팁에 가려 안 보이자 툴팁의 '전투력 증가량 -193만 1721'을 가격 1,931,721로 읽음.
    전투력 증가량을 따로 옮기게 하고, 가격이 그 숫자와 같으면 버린다(가격 못 읽음 → 사용자가 입력)."""
    x = normalize_listing({"name": "커맨더 포스 이어링", "category": "귀고리", "part": "귀고리", "potentials": [],
                           "price": 1_931_721, "price_text": "193만 1721", "power_delta_text": "-193만 1721"})
    assert x["price"] is None and x["price_text"] is None
    y = normalize_listing({"name": "커맨더 포스 이어링", "category": "귀고리", "part": "귀고리", "potentials": [],
                           "price": 1_931_721, "price_text": None, "power_delta_text": "- 193만 1721"})
    assert y["price"] is None
    ok = normalize_listing({"name": "커맨더 포스 이어링", "category": "귀고리", "part": "귀고리", "potentials": [],
                            "price": None, "price_text": "80억 7999만 9999", "power_delta_text": "-193만 1721"})
    assert ok["price"] == 8_079_999_999


def test_prompt_separates_combat_power_from_price():
    props = _SCHEMA["properties"]["listings"]["items"]
    assert "power_delta_text" in props["required"] and "power_delta_text" in props["properties"]
    assert "전투력 증가량" in _PROMPT and "가려" in _PROMPT
