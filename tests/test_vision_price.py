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
