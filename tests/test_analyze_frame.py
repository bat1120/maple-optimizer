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


class SeqClient:
    """첫 호출은 매물 판독, 다음 호출은 줄 다시 읽기 응답."""

    def __init__(self, *outputs):
        self.calls, self.outputs = [], list(outputs)
        self.responses = NS(create=self._create)

    def _create(self, **kw):
        self.calls.append(kw)
        return NS(output=[], output_text=json.dumps(self.outputs.pop(0), ensure_ascii=False), status="completed",
                  usage=NS(input_tokens=1, output_tokens=1))


def _with_breakdown(parts):
    x = _listing("고통의 근원", 18, 0)
    x["total"] = {k: None for k in KEYS} | {"STR": 216}
    x["breakdown"] = {k: None for k in KEYS} | {"STR": parts}
    return x


def test_checksum_failure_triggers_focused_reread_that_fixes_small_parts():
    """실측: AI가 괄호 안 작은 값(+1)을 빠뜨려 검산 헛경보 — 그 줄만 다시 읽혀 맞으면 받아들인다."""
    first = {"tooltip_visible": True, "fee_rate": None, "listings": [_with_breakdown([10, 131, 74])]}
    again = {"lines": [{"key": "STR", "total": 216, "parts": [10, 131, 1, 74]}]}
    fake = SeqClient(first, again)
    data = analyze_frame(fake, _url(_frame([((520, 120), _tooltip(lit=18))])))
    x = data["listings"][0]
    assert x["breakdown"]["STR"] == [10, 131, 1, 74] and x["reread"] == ["STR"]
    assert len(fake.calls) == 2 and len(_images(fake.calls[1])) == 1   # 다시 읽기는 그 툴팁 한 장만


def test_reread_that_still_disagrees_keeps_failure():
    first = {"tooltip_visible": True, "fee_rate": None, "listings": [_with_breakdown([10, 131, 74])]}
    again = {"lines": [{"key": "STR", "total": 216, "parts": [10, 131, 70]}]}
    data = analyze_frame(SeqClient(first, again), _url(_frame([((520, 120), _tooltip(lit=18))])))
    from server.vision import checksum_failures
    assert checksum_failures(data["listings"][0]) and data["listings"][0].get("reread") == []


def test_no_reread_when_checksum_passes():
    first = {"tooltip_visible": True, "fee_rate": None, "listings": [_with_breakdown([10, 131, 1, 74])]}
    fake = SeqClient(first)
    analyze_frame(fake, _url(_frame([((520, 120), _tooltip(lit=18))])))
    assert len(fake.calls) == 1
