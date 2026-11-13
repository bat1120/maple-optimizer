"""경매장 목록 행의 가격·전투력 증가량 로컬 판독(server/listprice.py, 2026-11-13).

툴팁이 가격 칸을 가리면 AI가 가격을 못 읽거나 툴팁의 전투력 증가량을 가격으로 읽었다 — 툴팁이 뜨기 전 목록 화면에서
줄마다 (전투력 증가량, 가격)을 AI 없이 읽어 둔다. 정답은 실제 캡처의 화면 글자(tests/fixtures/auction_list/labels.json)."""
import io
import json
import pathlib
import sys

import numpy as np
import pytest
from PIL import Image

from server import listprice as lp

FIX = pathlib.Path(__file__).parent / "fixtures" / "auction_list"
LABELS = json.loads((FIX / "labels.json").read_text(encoding="utf-8"))
PAGES = [k for k in LABELS if not k.startswith("_")]


def _jpeg(im: Image.Image, q: int = 85) -> Image.Image:
    """화면 공유 프레임과 같은 품질(web/src/ScreenWatch.jsx toDataURL('image/jpeg', 0.85))."""
    b = io.BytesIO()
    im.convert("RGB").save(b, "JPEG", quality=q)
    return Image.open(io.BytesIO(b.getvalue())).convert("RGB")


def test_glyph_table_is_regenerated_from_fixtures():
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
    from derive_list_glyphs import collect
    assert json.loads(json.dumps(collect(), ensure_ascii=False)) == json.loads(lp.TABLE.read_text(encoding="utf-8"))
    assert set(lp.load_table()["chars"]) == set("-0123456789만억")


@pytest.mark.parametrize("page", PAGES)
def test_reads_every_row_of_a_capture(page):
    rows = lp.read_rows(Image.open(FIX / page))
    assert [r["price"] for r in rows] == [lp._price_value(p) for p in LABELS[page]["prices"]]
    assert [r["power"] for r in rows] == [lp._power_value(p) for p in LABELS[page]["powers"]]


@pytest.mark.parametrize("page", PAGES)
def test_jpeg_frames_read_prices_and_never_a_wrong_power(page):
    """JPEG로 흐려져도 가격은 다 맞고, 전투력은 못 읽을 수는 있어도(None) 틀린 값은 내지 않는다."""
    rows = lp.read_rows(_jpeg(Image.open(FIX / page)))
    assert [r["price"] for r in rows] == [lp._price_value(p) for p in LABELS[page]["prices"]]
    powers = [lp._power_value(p) for p in LABELS[page]["powers"]]
    assert all(r["power"] in (None, want) for r, want in zip(rows, powers))
    assert sum(r["power"] == want for r, want in zip(rows, powers)) >= 6


def test_values_only_when_the_format_fits():
    assert lp._price_value("81억 0000만 0000") == 8_100_000_000
    assert lp._price_value("7999만 9999") == 79_999_999
    assert lp._price_value("81억 000만 0000") is None    # 억 뒤 만은 4자리
    assert lp._price_value("81억 0?00만 0000") is None   # 못 읽은 글자
    assert lp._power_value("??? ????? -193만 1721") == 1_931_721
    assert lp._power_value("-9만 8551") == 98_551
    assert lp._power_value("-19만 17") is None
    assert lp._power_value("193만 1721") is None         # '-'가 없으면 전투력 줄이 아니다


def test_screen_without_a_list_reads_nothing():
    blank = Image.new("RGB", (800, 600), (40, 44, 52))
    assert lp.read_rows(blank) == []
    one = np.full((300, 300, 3), 40, dtype=np.uint8)
    one[100:113, 100:113] = (240, 190, 40)  # 동전 하나(보유 메소 칸 등) — 줄로 보지 않는다
    assert lp.find_coins(np.asarray(one, dtype=int)) == []


def test_memory_matches_power_and_refuses_ambiguous_or_stale_or_other_users():
    mem = lp.ListMemory(ttl=900)
    mem.remember("a", [{"power": 1_931_721, "price": 8_079_999_999}, {"power": 1_990_516, "price": 8_079_999_999}], now=0)
    assert mem.lookup("a", 1_931_721, now=10) == 8_079_999_999
    assert mem.lookup("b", 1_931_721, now=10) is None            # 다른 사용자(IP) 목록은 쓰지 않는다
    assert mem.lookup("a", 1_931_721, now=901) is None           # 오래된 목록(15분)은 버린다
    mem.remember("a", [{"power": 1_990_516, "price": 7_000_000_000}], now=20)
    assert mem.lookup("a", 1_990_516, now=21) is None            # 같은 전투력에 가격이 둘 → 어느 쪽인지 모른다
    mem.remember("a", [{"power": None, "price": 1}, {"power": 5, "price": None}], now=30)
    assert mem.lookup("a", 5, now=31) is None


def _data_url(im: Image.Image) -> str:
    import base64
    b = io.BytesIO()
    im.convert("RGB").save(b, "JPEG", quality=85)
    return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()


def test_tooltip_item_gets_the_price_read_from_the_list_frame(tmp_path):
    """2026-11-13 실사용 흐름: 목록 화면(가격 보임) → 매물에 마우스(툴팁이 가격 칸을 가림, AI 가격 null).
    툴팁의 전투력 증가량과 같은 목록 줄의 가격을 붙이고, 어디서 온 가격인지 표시한다."""
    from types import SimpleNamespace as NS
    from fastapi.testclient import TestClient
    from helpers import bundle
    from server.app import create_app

    tip = {"name": "커맨더 포스 이어링", "category": "귀고리", "part": "귀고리", "starforce": 18, "level": 200,
           "potential_grade": "레전드리", "additional_grade": None,
           "total": {k: None for k in ("STR", "DEX", "INT", "LUK", "HP", "ATK", "MATK", "ALL%", "BOSS", "IED", "DMG")}
           | {"STR": 122, "DEX": 128, "INT": 92, "LUK": 158, "ATK": 49, "MATK": 44},
           "breakdown": {k: None for k in ("STR", "DEX", "INT", "LUK", "HP", "ATK", "MATK", "ALL%", "BOSS", "IED", "DMG")},
           "potentials": ["올스탯 +9%", "INT +9%", "INT +9%"], "additional": [], "price": None, "price_text": None,
           "power_delta_text": "-193만 1721", "equipped": False, "tooltip": None, "special_ring_level": None,
           "equip_type": None, "job_groups": None}

    class Fake:
        calls = 0

        def __init__(self):
            self.responses = NS(create=self._create)

        def _create(self, **kw):
            Fake.calls += 1
            out = {"tooltip_visible": True, "fee_rate": None, "listings": [tip]}
            return NS(output=[], output_text=json.dumps(out, ensure_ascii=False), status="completed",
                      usage=NS(input_tokens=1, output_tokens=1))

    c = TestClient(create_app(lambda n, d: bundle("레테"), str(tmp_path / "c.sqlite3"), agent_client=Fake()))
    lst = c.post("/api/vision/listings", json={"image": _data_url(Image.open(FIX / "p1.png"))})
    assert lst.status_code == 200  # 목록 줄 읽기는 로컬(툴팁 찾기가 목록 줄을 툴팁으로 볼 때만 AI가 따로 불린다)
    r = c.post("/api/vision/listings", json={"image": "data:image/jpeg;base64,AAAA", "name": "x"})
    read = r.json()["items"][0]["read"]
    assert (read["price"], read["price_source"]) == (8_079_999_999, "목록")
    assert r.json()["items"][0]["per_100m"] is not None


LIVE = pathlib.Path(__file__).parent / "fixtures" / "auction_live"
LIVE_LABELS = json.loads((LIVE / "labels.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("page", [k for k in LIVE_LABELS if not k.startswith("_")])
def test_reads_the_real_browser_frame_including_plus_and_short_minus(page):
    """2026-11-13 실사용: 브라우저 프레임에서 '-'가 3픽셀로 짧게 찍혀 못 읽고, '+'(착용보다 좋은 매물)는 숫자와 붙어 4로 읽음
    → 8줄 중 전투력 1줄만 읽혀 툴팁 매물에 목록 가격이 안 붙었다. 부호는 모양(가로 한 줄 / 십자)으로 본다."""
    rows = lp.read_rows(Image.open(LIVE / page))
    want = LIVE_LABELS[page]
    assert [r["price"] for r in rows] == [lp._price_value(p) for p in want["prices"]]
    assert [r["power"] for r in rows] == [lp._power_value(p) for p in want["powers"]]
    assert lp._power_value("+372만 9056") == 3_729_056
