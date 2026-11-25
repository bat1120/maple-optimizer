"""테두리 선으로 툴팁 찾기(2026-11-25). 실사용에서 경매장 다크모드 화면의 툴팁을 잘못 잘라, 같은 매물을 화면마다 AI로 다시 읽었다
(귀고리 4개에 AI 판독 17~35회, 하루 토큰 한도 20만·100만 소진).

- 위쪽 테스트: 실제 화면에서 잰 테두리 무늬(바깥 어두운 선 43 · 밝은 테두리 79 · 안쪽 바탕 52, 창 바탕 58)를 그대로 그린 화면
- 아래쪽 테스트: 이 PC에만 있는 실제 화면(.data/auction_real — 캐릭터 이름이 보여 저장소에 올리지 않는다). 없으면 건너뛴다
"""
import base64
import io
import json
import pathlib
from types import SimpleNamespace as NS

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

from server.tooltip import crop, find_by_darkness, find_outlined, find_tooltips, stars_near
from server.vision import FrameCache, ScanRegistry, _power_mask, analyze_frame

REAL = pathlib.Path(__file__).resolve().parents[1] / ".data" / "auction_real"
W, H = 1368, 800
TIP_W = 321


def _dark_auction(seed: int = 0) -> Image.Image:
    """다크모드 경매장: 창 전체가 어둡고(58), 목록 줄·검색 조건 칸도 어둡다."""
    rnd = np.random.default_rng(seed)
    a = np.full((H, W, 3), (88, 150, 215), np.uint8)                       # 게임 배경(하늘)
    a[55:775, 172:1196] = (55, 59, 62)                                     # 경매장 창
    a[240:740, 190:446] = (45, 55, 59)                                     # 검색 조건 칸
    for y in range(245, 730, 61):                                          # 목록 줄
        a[y:y + 55, 470:1170] = (51, 61, 65)
        a[y + 8:y + 46, 478:516] = rnd.integers(60, 230, (38, 38, 3))      # 아이콘
    return Image.fromarray(a)


def _tooltip(height: int, number: str | None, stars: int = 0, lines: int = 14, seed: int = 1) -> Image.Image:
    """툴팁 한 장: [어두운 선 43][밝은 테두리 79][바탕 52]. number가 있으면 흰 큰 숫자(전투력 증가량)."""
    t = Image.new("RGB", (TIP_W + 2, height + 2), (43, 44, 46))            # 바깥 어두운 선
    d = ImageDraw.Draw(t)
    d.rectangle((1, 1, TIP_W, height), fill=(79, 80, 82))                  # 밝은 테두리
    d.rectangle((2, 2, TIP_W - 1, height - 1), fill=(46, 53, 59))          # 안쪽 바탕
    for i in range(stars):                                                 # 노란 별
        x, y = 60 + (i % 15) * 13 + (i % 15) // 5 * 8, 8 + (i // 15) * 14
        d.rectangle((x, y, x + 8, y + 8), fill=(255, 204, 0))
    d.rectangle((110, 34, 210, 44), fill=(235, 235, 235))                  # 이름
    if number:                                                             # 큰 흰 숫자(실제 글꼴로 그린다 — 숫자마다 모양이 다르다)
        d.text((300, 132), number, font=ImageFont.load_default(30), fill=(255, 255, 255), anchor="rs", stroke_width=1,
               stroke_fill=(255, 255, 255))
    else:
        d.rectangle((180, 86, 300, 98), fill=(200, 200, 200))              # '현재 장착 중인 장비'(회색 큰 글자)
    rnd = np.random.default_rng(seed)
    for i in range(lines):
        y = 190 + i * 17
        if y + 10 < height:
            d.rectangle((14, y, 14 + int(rnd.integers(60, 200)), y + 8), fill=(225, 225, 225))
    return t


def _frame(x: int, y: int, number: str, stars: int = 18, tip_h: int = 620, seed: int = 1) -> Image.Image:
    """매물 툴팁(왼쪽) + 착용 템 툴팁(오른쪽)이 붙어 뜬 화면. 화면 아래로 넘치면 잘린다(실제와 같다)."""
    fr = _dark_auction()
    fr.paste(_tooltip(tip_h, number, stars, seed=seed), (x - 1, y - 1))
    fr.paste(_tooltip(457, None, 5, lines=10, seed=9), (x + TIP_W + 3 - 1, y - 1))
    buf = io.BytesIO()
    fr.save(buf, "JPEG", quality=85)
    return Image.open(io.BytesIO(buf.getvalue())).convert("RGB")


def _key(fr: Image.Image) -> tuple:
    return tuple(FrameCache.textprint(crop(fr, b), b) for b in find_tooltips(fr))


def test_finds_exactly_the_two_tooltips_in_dark_auction():
    boxes = find_outlined(_frame(600, 226, "7372467"))
    assert [(b[0], b[1], b[2] - b[0]) for b in boxes] == [(600, 226, TIP_W), (600 + TIP_W + 3, 226, TIP_W)]
    assert boxes[1][3] - boxes[1][1] == 457
    assert find_outlined(_dark_auction()) == [] and find_tooltips(_dark_auction()) == find_by_darkness(_dark_auction())


def test_same_listing_is_one_key_wherever_the_tooltip_is():
    """마우스를 따라 옮겨 가고 화면 아래에 걸려 잘려도 같은 매물은 같은 것으로, 숫자가 다른 매물은 다른 것으로 본다."""
    base = _key(_frame(600, 226, "7372467"))
    for x, y in ((512, 290), (640, 177), (720, 300), (590, 240)):          # 290·300에서는 아래가 잘린다
        assert FrameCache.key_close(base, _key(_frame(x, y, "7372467"))), (x, y)
    for other in ("5306506", "7672027", "7372468", "1372467"):             # 전혀 다른 숫자, 두 자리·한 자리만 다른 숫자
        assert not FrameCache.key_close(base, _key(_frame(600, 226, other))), other
    assert not FrameCache.key_close(base, _key(_frame(640, 177, "9008903")))


def test_moving_tooltip_is_read_once_and_counted_once():
    """화면 평가 전체로: 같은 매물 위에서 마우스를 움직이면 AI는 한 번, '인식한 매물'도 1개. 다른 매물로 가면 2개.
    (2026-11-25 낮에 옛 방식 상자로 만든 같은 뜻의 테스트는 지웠다 — 실제 화면은 테두리 선으로 자르므로 이 테스트가 그 자리를 맡는다)"""
    def url(fr):
        buf = io.BytesIO()
        fr.save(buf, "JPEG", quality=85)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    ai, cache, scans = _CountingAI(), FrameCache(), ScanRegistry()
    mark = lambda k, done: scans.mark("s", k, done, 0.0)  # noqa: E731
    for x, y in ((600, 226), (512, 290), (640, 177), (720, 300), (600, 226)):
        out = analyze_frame(ai, url(_frame(x, y, "7372467")), cache=cache, tooltips_only=True, on_tip=mark)
        assert out["diag"]["tips"] == 1 and out["diag"]["listing_only"] is True      # 매물 툴팁만(착용 템 툴팁은 보내지 않는다)
    assert ai.calls == 1 and scans.counts("s", 0.0) == (1, 0)
    analyze_frame(ai, url(_frame(640, 177, "9008903")), cache=cache, tooltips_only=True, on_tip=mark)
    assert ai.calls == 2 and scans.counts("s", 0.0) == (2, 0)


def test_white_power_number_marks_the_listing_tooltip_only():
    fr = _frame(600, 226, "5306506", stars=0)
    listing, worn = (crop(fr, b) for b in find_tooltips(fr))
    assert int(_power_mask(listing).sum()) >= FrameCache.COLOR_MIN
    assert int(_power_mask(worn).sum()) < FrameCache.COLOR_MIN / 4
    assert [stars_near(fr, b) for b in find_tooltips(fr)] == [None, 5]     # 별 세기 자체는 그대로(노란 별이 없으면 모름)


def _url(p: pathlib.Path) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(p.read_bytes()).decode()


class _CountingAI:
    def __init__(self):
        self.calls = 0
        self.responses = NS(create=self._create)

    def _create(self, **kw):
        self.calls += 1
        return NS(output=[], output_text=json.dumps({"tooltip_visible": True, "fee_rate": None, "listings": []}), status="completed",
                  usage=NS(input_tokens=1, output_tokens=1))


@pytest.mark.skipif(not REAL.exists(), reason="실제 경매장 화면은 이 PC에만 있다(.data/auction_real)")
def test_real_dark_auction_frames_are_cut_exactly():
    tips = sorted(REAL.glob("tip*.jpg")) + sorted(REAL.glob("maple_frame_*.jpg"))
    assert len(tips) >= 20
    for p in tips:
        im = Image.open(p).convert("RGB")
        boxes = find_tooltips(im)
        assert [b[2] - b[0] for b in boxes] == [TIP_W, TIP_W], p.name      # 매물·착용 템 툴팁 둘만, 너비가 같다
        assert boxes[1][3] - boxes[1][1] == 457 and stars_near(im, boxes[1]) == 5, p.name   # 착용 템 '하프 이어링' 5성
    for p in sorted(REAL.glob("f0*.jpg")):
        assert find_outlined(Image.open(p).convert("RGB")) == [], p.name   # 툴팁 없는 화면


@pytest.mark.skipif(not REAL.exists(), reason="실제 경매장 화면은 이 PC에만 있다(.data/auction_real)")
def test_real_session_needs_no_ai_and_counts_each_listing_once():
    """실제 화면 한 판(매물 8개에 마우스를 대고 움직임): AI 0번, 매물마다 한 번만 읽고, '인식한 매물'도 8개."""
    from server.ocr import reader
    ocr = reader()
    if ocr is None:
        pytest.skip("로컬 OCR을 쓸 수 없다")
    tips = sorted(REAL.glob("tip*.jpg")) + sorted(REAL.glob("maple_frame_*.jpg"))
    negs = sorted(REAL.glob("f0*.jpg"))
    ai, cache, scans, seen, kinds = _CountingAI(), FrameCache(), ScanRegistry(), set(), {}
    for i, p in enumerate(tips):
        for q in (p, p, negs[i % len(negs)]):
            out = analyze_frame(ai, _url(q), cache=cache, tooltips_only=True, ocr=ocr, on_tip=lambda k, done: scans.mark("s", k, done, 0.0))
            kind = "건너뜀" if out.get("skipped") else "재사용" if out.get("cached") else "OCR" if out.get("ocr") else "AI"
            kinds[kind] = kinds.get(kind, 0) + 1
            seen |= {(x["name"], x["starforce"], x["power_delta_text"]) for x in out["listings"]}
    assert ai.calls == 0 and kinds.get("AI", 0) == 0
    assert seen == {("데아 시두스 이어링", 17, "779만 4789"), ("데아 시두스 이어링", 18, "737만 2467"), ("마이스터 이어링", 17, "631만 122"),
                    ("마이스터 이어링", 18, "767만 2027"), ("에스텔라 이어링", 0, "530만 6506"), ("에스텔라 이어링", 18, "1054만 6557"),
                    ("에스텔라 이어링", 18, "900만 8903"), ("에스텔라 이어링", 18, "962만 8478")}
    assert kinds["OCR"] == 8 and scans.counts("s", 0.0) == (8, 0)
