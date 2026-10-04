"""화면 분석 통합: 툴팁을 찾아 원래 크기로 잘라 함께 보내고, 별은 코드가 세고, 이름 오타는 세트 장비 이름으로 바로잡는다."""
import base64
import io
import json
from types import SimpleNamespace as NS

from test_tooltip_image import _frame, _tooltip

from server.vision import _PROMPT, _SCHEMA, analyze_frame

KEYS = ("STR", "DEX", "INT", "LUK", "HP", "ATK", "MATK", "ALL%", "BOSS", "IED", "DMG")


def _url(img):
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def _listing(name, starforce, tooltip):
    return {"name": name, "category": "장갑", "part": "장갑", "starforce": starforce, "level": 250,
            "potential_grade": "레전드리", "additional_grade": "에픽", "total": {k: None for k in KEYS} | {"STR": 253},
            "breakdown": {k: None for k in KEYS}, "potentials": ["크리티컬 데미지 +8%"], "additional": ["STR +5%"],
            "price": 10_000_000_000, "equipped": False, "tooltip": tooltip}


class FakeClient:
    def __init__(self, listings):
        self.calls, self.listings = [], listings
        self.responses = NS(create=self._create)

    def _create(self, **kw):
        self.calls.append(kw)
        out = {"tooltip_visible": True, "fee_rate": None, "listings": self.listings}
        return NS(output=[], output_text=json.dumps(out, ensure_ascii=False), status="completed",
                  usage=NS(input_tokens=1, output_tokens=1))


def _images(call):
    return [c for c in call["input"][0]["content"] if c["type"] == "input_image"]


def test_schema_asks_which_tooltip_and_prompt_has_example():
    assert "tooltip" in _SCHEMA["properties"]["listings"]["items"]["required"]
    assert "예시" in _PROMPT and "breakdown" in _PROMPT


def test_sends_full_frame_plus_original_size_tooltip_crops():
    fake = FakeClient([_listing("에테르넬 나이트글러브", 18, 0)])
    analyze_frame(fake, _url(_frame([((520, 120), _tooltip(lit=18))])))
    imgs = _images(fake.calls[0])
    assert len(imgs) == 2 and all(i["detail"] == "high" for i in imgs)


def test_starforce_is_replaced_by_counted_stars():
    fake = FakeClient([_listing("에테르넬 나이트글러브", 25, 0)])
    data = analyze_frame(fake, _url(_frame([((520, 120), _tooltip(lit=18))])))
    x = data["listings"][0]
    assert (x["starforce"], x["starforce_ai"], x["starforce_source"]) == (18, 25, "별 세기")


def test_starforce_stays_unverified_when_stars_cannot_be_counted():
    fake = FakeClient([_listing("에테르넬 나이트글러브", 22, None)])
    data = analyze_frame(fake, _url(_frame([])))
    x = data["listings"][0]
    assert x["starforce"] == 22 and x["starforce_source"] == "화면 판독(확인 필요)"
    assert len(_images(fake.calls[0])) == 1


def test_name_misread_is_corrected_with_set_item_names():
    fake = FakeClient([_listing("에테르널 나이트글러브", 18, 0)])
    data = analyze_frame(fake, _url(_frame([((520, 120), _tooltip(lit=18))])))
    x = data["listings"][0]
    assert (x["name"], x["name_read"]) == ("에테르넬 나이트글러브", "에테르널 나이트글러브")
