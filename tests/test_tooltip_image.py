"""화면 공유 프레임에서 툴팁 찾기·별 세기·이름 보정. 실제 게임 화면은 저작권 때문에 저장소에 넣지 않고, 같은 특징을 그린 합성 화면으로 검증한다
(실측은 로컬 골든셋으로 따로 한다 — goal-log 2026-10-04)."""
import math
import random

import pytest

from PIL import Image, ImageDraw

from server.tooltip import correct_name, count_stars, find_tooltips

PANEL = (34, 40, 52)


def _star(d, cx, cy, r, fill):
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.45
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    d.polygon(pts, fill=fill)


def _tooltip(w=300, h=520, lit=18, sparkles=True, seed=1):
    rnd = random.Random(seed)
    im = Image.new("RGB", (w, h), PANEL)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, w - 1, h - 1], outline=(150, 160, 175))
    for k in range(30):  # 별 15개씩 두 줄, 5개마다 간격
        row, col = divmod(k, 15)
        x = 40 + col * 15 + (col // 5) * 8
        y = 12 + row * 16
        _star(d, x, y, 6, (255, 214, 0) if k < lit else (70, 72, 80))
    if sparkles:  # 별 주변 반짝이(작은 노란 점)
        for _ in range(40):
            x, y = rnd.randrange(5, w - 5), rnd.randrange(2, 45)
            d.rectangle([x, y, x + 1, y + 1], fill=(255, 230, 90))
    for i in range(18):  # 글자 줄 흉내
        d.text((20, 70 + i * 22), "STR +316 (80 +80 +156)", fill=(230, 230, 230))
    return im


def _frame(tips):
    rnd = random.Random(7)
    fr = Image.new("RGB", (1366, 768), (120, 170, 210))  # 하늘색 맵 바탕
    d = ImageDraw.Draw(fr)
    for _ in range(400):  # 알록달록한 게임 배경
        x, y = rnd.randrange(0, 1366), rnd.randrange(0, 768)
        d.rectangle([x, y, x + rnd.randrange(10, 80), y + rnd.randrange(10, 80)],
                    fill=(rnd.randrange(90, 255), rnd.randrange(90, 255), rnd.randrange(90, 255)))
    for (x, y), tip in tips:
        fr.paste(tip, (x, y))
    return fr


def test_finds_one_tooltip_box():
    tip = _tooltip()
    boxes = find_tooltips(_frame([((520, 120), tip)]))
    assert len(boxes) == 1
    x0, y0, x1, y1 = boxes[0]
    assert abs(x0 - 520) <= 8 and abs(y0 - 120) <= 8 and abs(x1 - 820) <= 8 and abs(y1 - 640) <= 8


def test_finds_hovered_and_comparison_tooltips_side_by_side():
    boxes = find_tooltips(_frame([((400, 100), _tooltip(seed=2)), ((720, 100), _tooltip(lit=0, seed=3))]))
    assert len(boxes) == 2 and boxes[0][0] < boxes[1][0]


def test_no_tooltip_on_plain_game_screen():
    assert find_tooltips(_frame([])) == []


def test_counts_lit_stars_ignoring_sparkles():
    assert count_stars(_tooltip(lit=18)) == 18
    assert count_stars(_tooltip(lit=24, seed=5)) == 24
    assert count_stars(_tooltip(lit=0, sparkles=False)) is None   # 노란 별이 없으면 모른다(0이라고 단정하지 않음)


def test_name_correction_fixes_one_or_two_letter_misreads_only():
    names = ["에테르넬 나이트글러브", "에테르넬 메이지햇", "미트라의 분노 : 마법사"]
    assert correct_name("에테르널 나이트글러브", names) == ("에테르넬 나이트글러브", True)
    assert correct_name("에테르넬 나이트글러브", names) == ("에테르넬 나이트글러브", False)
    assert correct_name("순록의 우유", names) == ("순록의 우유", False)
    # 목록에 없는 진짜 이름을 두 글자 다른 이름으로 바꾸면 안 된다(실측: 아케인셰이드 나이트글러브 → 메이지글러브 오보정)
    assert correct_name("에테르넬 메이지글러브", ["에테르넬 나이트글러브"]) == ("에테르넬 메이지글러브", False)


@pytest.mark.parametrize("read", ["캐런던 포스 이어링", "캐먼더 포스 이어링"])
def test_name_correction_fixes_look_alike_letters(read):
    """2026-11-13 실사용: 커맨더 포스 이어링을 '캐런던/캐먼더'로 읽어 템을 못 알아봄 — 모양이 비슷한 글자(자모가 겹침)면 고친다."""
    from server.vision import _item_names
    assert correct_name(read, _item_names()) == ("커맨더 포스 이어링", True)


def test_name_correction_does_not_add_misfixes_when_a_real_item_is_missing():
    """진짜 템이 목록에 없을 때(하나씩 빼 본다) 다른 템으로 바뀌는 경우가 한 글자 규칙(2026-10-05)보다 늘지 않는다.
    늘어난 것은 '아케인셰이드 초선→체인' 하나(초선은 목록에 있어 실제로는 안 생긴다) — 모음만 같은 글자는 고치지 않아
    대거↔해머·보우↔폴암 같은 다른 무기로는 바꾸지 않는다."""
    from server.tooltip import _distance
    from server.vision import _item_names
    names = set(_item_names())
    misfix = {n: c for n in names if (c := correct_name(n, names - {n})[0]) != n}
    one_letter = {n for n in names if any(_distance(n, k) <= 1 for k in names - {n})}
    assert {n: c for n, c in misfix.items() if n not in one_letter} == {"아케인셰이드 초선": "아케인셰이드 체인"}
    assert "아케인셰이드 초선" in names


def test_counts_second_star_row_on_real_auction_frame():
    """2026-11-14 실사용(1368×800 화면 공유 프레임): 18성 커맨더 포스 이어링을 15성으로 셈 — 둘째 별 줄(16~18성)이
    별 띠(상자 위 48px) 바로 아래에 걸쳐 잘렸다. 프레임 71장 실측: 56px 이상이면 모두 18."""
    import pathlib
    from server.tooltip import stars_near
    img = Image.open(pathlib.Path(__file__).parent / "fixtures" / "tooltip_stars" / "two_rows_18.png").convert("RGB")
    assert stars_near(img, (4, 42, 351, 150)) == 18  # 실제 프레임의 툴팁 상자(507,192,854,…)를 잘라 옮긴 좌표
