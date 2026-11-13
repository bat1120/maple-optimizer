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


def test_same_tooltip_again_reuses_previous_reading_without_ai():
    """실측(2026-10-05): 화면 46장 중 쓸모 있는 판독 15개 — 같은 툴팁을 다시 보면 AI를 부르지 않고 이전 판독을 쓴다."""
    from server.vision import FrameCache
    cache = FrameCache()
    fake = FakeClient([_listing("에테르넬 나이트글러브", 18, 0)])
    frame = _url(_frame([((520, 120), _tooltip(lit=18))]))
    analyze_frame(fake, frame, cache=cache)
    again = analyze_frame(fake, _url(_frame([((520, 120), _tooltip(lit=18))])), cache=cache)
    assert len(fake.calls) == 1 and again["cached"] is True
    other = analyze_frame(fake, _url(_frame([((520, 120), _tip_with(["LUK +12%", "DEX +9%", "Crit Damage +8%"], lit=7, seed=9))])),
                          cache=cache)  # 글자가 다른 툴팁(별만 다르면 재사용하고 별은 다시 센다 — 아래 테스트)
    assert len(fake.calls) == 2 and other.get("cached") is not True


def test_unchanged_screen_without_tooltip_is_not_sent_again():
    from server.vision import FrameCache
    cache = FrameCache()
    fake = FakeClient([])
    analyze_frame(fake, _url(_frame([])), cache=cache)
    again = analyze_frame(fake, _url(_frame([])), cache=cache)
    assert len(fake.calls) == 1 and again["cached"] is True


def test_frame_without_tooltip_is_skipped_without_ai_when_tooltips_only():
    """실측(2026-10-05 장비창 훑기): 46장 중 31장이 툴팁 없는 화면이었고 AI도 아무것도 못 읽음 — 보내지 않는다."""
    fake = FakeClient([])
    data = analyze_frame(fake, _url(_frame([])), tooltips_only=True)
    assert len(fake.calls) == 0 and data["listings"] == [] and data["skipped"] == "툴팁 없음"
    analyze_frame(fake, _url(_frame([])), tooltips_only=False)   # 목록 화면도 읽기: 그대로 보낸다
    assert len(fake.calls) == 1


def test_same_tooltip_arriving_concurrently_calls_ai_once():
    """화면이 동시에 3장까지 보내면(2026-10-06) 같은 툴팁이 읽는 중에 또 올 수 있다 — 먼저 온 판독을 기다렸다가 재사용한다."""
    import threading
    import time
    from server.vision import FrameCache
    cache = FrameCache()
    fake = FakeClient([_listing("에테르넬 나이트글러브", 18, 0)])
    slow = fake._create
    fake.responses = NS(create=lambda **kw: (time.sleep(0.3), slow(**kw))[1])
    frames = [_url(_frame([((520, 120), _tooltip(lit=18))])) for _ in range(3)]
    out = [None] * 3
    ts = [threading.Thread(target=lambda i=i: out.__setitem__(i, analyze_frame(fake, frames[i], cache=cache)))
          for i in range(3)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert len(fake.calls) == 1
    assert sum(bool(o.get("cached")) for o in out) == 2
    assert all(o["listings"][0]["name"] == "에테르넬 나이트글러브" for o in out)


def _tip_with(lines, lit=18, seed=1):
    """별 줄은 _tooltip 그대로, 본문은 큰 글꼴(실제 툴팁 글자 크기)로 lines를 쓴다. 기본 몸통 12줄 + lines."""
    from PIL import ImageDraw, ImageFont
    t = _tooltip(lit=lit, seed=seed)
    d = ImageDraw.Draw(t)
    d.rectangle([2, 60, t.width - 3, t.height - 3], fill=(50, 57, 66))
    font = ImageFont.load_default(size=15)
    body = [f"STR +{100 + k * 7} ({k} +{k * 3})" for k in range(12)] + list(lines)
    for k, line in enumerate(body):
        d.text((16, 66 + k * 24), line, fill=(235, 235, 235), font=font)
    return t


def test_same_tooltip_on_changing_background_is_reused_by_text():
    """툴팁은 반투명이라 뒤 배경이 비친다 — 대고 있는 동안 0.5초마다 보내도(2026-10-06) 글자가 같으면 AI를 다시 부르지 않는다.
    별 줄(반짝이)은 지문에서 빼고, 재사용할 때 별은 지금 화면에서 다시 센다."""
    from server.vision import FrameCache
    cache = FrameCache()
    fake = FakeClient([_listing("에테르넬 나이트글러브", 18, 0)])
    tip = _tip_with(["INT +12%"])
    analyze_frame(fake, _url(_frame([((520, 120), tip)])), cache=cache)
    moved = _tip_with(["INT +12%"], lit=17, seed=5)            # 반짝이·별 바뀜, 1px 이동
    again = analyze_frame(fake, _url(_frame([((521, 121), moved)])), cache=cache)
    assert len(fake.calls) == 1 and again["cached"] is True
    assert again["listings"][0]["starforce"] == 17


def test_tooltip_at_another_position_is_read_again():
    """마우스를 다른 매물·다른 장비 칸으로 옮기면 툴팁 위치가 바뀐다 — 글자가 거의 같아도(숫자 하나 차이) 다시 읽는다.
    그림만으로는 숫자 하나 차이를 못 가른다(실측: 재압축만으로 글자 픽셀 925개 어긋남, 숫자 하나는 26개)."""
    from server.vision import FrameCache
    cache = FrameCache()
    fake = FakeClient([_listing("에테르넬 나이트글러브", 18, 0)])
    analyze_frame(fake, _url(_frame([((520, 120), _tip_with(["INT +12%", "INT +9%", "INT +9%"]))])), cache=cache)
    analyze_frame(fake, _url(_frame([((520, 180), _tip_with(["INT +12%", "INT +12%", "INT +9%"]))])), cache=cache)
    assert len(fake.calls) == 2


def test_same_position_after_a_while_is_read_again():
    """재사용은 '방금 대고 있던 툴팁'만(3초) — 목록을 넘긴 뒤 같은 자리에 온 다른 매물을 옛 판독으로 덮지 않는다."""
    from server.vision import FrameCache
    now = [100.0]
    cache = FrameCache(clock=lambda: now[0])
    fake = FakeClient([_listing("에테르넬 나이트글러브", 18, 0)])
    frame = _url(_frame([((520, 120), _tip_with(["INT +12%"]))]))
    analyze_frame(fake, frame, cache=cache)
    now[0] += 2.0
    assert analyze_frame(fake, frame, cache=cache)["cached"] is True    # 대고 있는 중(2초) → 재사용, 시간 연장
    now[0] += 2.5
    assert analyze_frame(fake, frame, cache=cache)["cached"] is True    # 마지막 재사용 2.5초 뒤 → 여전히 대고 있음
    now[0] += 4.0
    assert analyze_frame(fake, frame, cache=cache).get("cached") is not True
    assert len(fake.calls) == 2


def _auction_list_frame(tips=()):
    """다크모드 경매장 목록(실제 캡처의 목록 부분, tests/fixtures/auction_list/p1.png)을 게임 화면에 붙인 프레임."""
    import pathlib
    from PIL import Image
    fr = _frame(list(tips))
    fr.paste(Image.open(pathlib.Path(__file__).parent / "fixtures" / "auction_list" / "p1.png").convert("RGB"), (470, 240))
    for (x, y), tip in tips:  # 툴팁은 목록 위에 뜬다
        fr.paste(tip, (x, y))
    return fr


def test_dark_mode_auction_list_alone_is_not_sent_to_ai():
    """2026-11-13 실사용(경매장 다크모드): 목록만 보이는 화면을 '툴팁 3개'로 보고 AI를 불렀다(판독 한도·토큰 낭비).
    실제 캡처 3장 모두 가짜 상자 3개, 진짜 툴팁 2개는 별 줄(18성)이 있고 가짜는 0개 —
    목록의 동전 줄이 보이는 화면에서는 별 줄 없는 상자를 툴팁으로 보지 않는다."""
    fake = FakeClient([])
    data = analyze_frame(fake, _url(_auction_list_frame()), tooltips_only=True)
    assert len(fake.calls) == 0 and data["skipped"] == "툴팁 없음"
    assert len(data["list_rows"]) >= 6


def test_tooltip_over_dark_mode_list_is_sent_alone():
    fake = FakeClient([_listing("커맨더 포스 이어링", 18, 0)])
    data = analyze_frame(fake, _url(_auction_list_frame([((40, 60), _tooltip())])), tooltips_only=True)
    assert len(fake.calls) == 1 and data["tooltips_found"] == 1
    assert len(_images(fake.calls[0])) == 2  # 화면 전체 + 툴팁 조각 하나(목록 판넬 조각 없이)


def _tip_power(text):
    """경매장 툴팁: 오른쪽 위 큰 분홍 '전투력 증가량' 숫자만 다르고 나머지는 같다."""
    from PIL import ImageDraw, ImageFont
    t = _tip_with(["INT +9%", "INT +9%", "ALL +6%"])
    ImageDraw.Draw(t).text((150, 70), text, fill=(235, 45, 120), font=ImageFont.load_default(size=30))
    return t


def test_same_spot_different_power_number_is_read_again():
    """2026-11-14 실사용: 경매장 툴팁은 어느 줄에 대든 같은 자리에 뜬다 — 18성 커포링(-177만 4480) 판독을
    바로 다음에 댄 -9만 8551 매물에 재사용했다(글자 지문 거리 0.0117 < 0.02, 위치 차 3px).
    큰 색 글자(전투력 증가량)가 다르면 다시 읽는다 — 실측 불일치: 다른 매물 0.75~0.81, 같은 툴팁 재압축 0.20~0.24."""
    from server.vision import FrameCache
    cache = FrameCache()
    fake = FakeClient([_listing("커맨더 포스 이어링", 18, 0)])
    analyze_frame(fake, _url(_frame([((520, 120), _tip_power("-1774480"))])), cache=cache)
    other = analyze_frame(fake, _url(_frame([((520, 120), _tip_power("-98551"))])), cache=cache)
    assert len(fake.calls) == 2 and other.get("cached") is not True
    same = analyze_frame(fake, _url(_frame([((520, 120), _tip_power("-98551"))])), cache=cache)
    assert len(fake.calls) == 2 and same["cached"] is True


def test_tooltip_with_power_number_is_reused_when_hovered_again_later():
    """2026-11-14 실사용: 같은 매물에 다시 대면 3초가 지나 AI를 또 불렀다(131만 매물 3번) — 느리고 한도를 쓴다.
    전투력 숫자까지 같으면 다른 매물일 수 없으니 60초 안에는 재사용한다. 숫자가 없는 툴팁은 3초 그대로."""
    from server.vision import FrameCache
    now = [100.0]
    cache = FrameCache(clock=lambda: now[0])
    fake = FakeClient([_listing("커맨더 포스 이어링", 18, 0)])
    analyze_frame(fake, _url(_frame([((520, 120), _tip_power("-1310390"))])), cache=cache)
    now[0] += 20.0
    again = analyze_frame(fake, _url(_frame([((520, 120), _tip_power("-1310390"))])), cache=cache)
    assert len(fake.calls) == 1 and again["cached"] is True
    now[0] += 61.0
    analyze_frame(fake, _url(_frame([((520, 120), _tip_power("-1310390"))])), cache=cache)
    assert len(fake.calls) == 2
