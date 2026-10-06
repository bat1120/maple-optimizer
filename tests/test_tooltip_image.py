"""화면 공유 프레임에서 툴팁 찾기·별 세기·이름 보정. 실제 게임 화면은 저작권 때문에 저장소에 넣지 않고, 같은 특징을 그린 합성 화면으로 검증한다
(실측은 로컬 골든셋으로 따로 한다 — goal-log 2026-10-04)."""
import math
import random

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


def test_large_dark_area_is_not_a_tooltip():
    """어두운 맵·로딩 화면처럼 넓게 어두운 곳은 툴팁이 아니다(툴팁은 폭 600px 이하)."""
    fr = Image.new("RGB", (1366, 768), (20, 22, 30))
    assert find_tooltips(fr) == []



def test_thin_yellow_line_at_edge_is_not_a_star():
    tip = _tooltip(lit=0, sparkles=False)
    ImageDraw.Draw(tip).rectangle([tip.width - 3, 4, tip.width - 2, 20], fill=(255, 220, 40))  # 가장자리 가는 노란 선
    assert count_stars(tip) is None


def test_touching_tooltips_without_gap_are_split():
    """마우스를 올린 매물과 '현재 장착 중인 장비' 툴팁이 틈 없이 붙어 뜨는 경우(2026-10-05 실측: 둘이 한 상자로 잡혀 별이 섞임)."""
    left, right = _tooltip(w=290, lit=10, seed=4), _tooltip(w=290, lit=0, sparkles=False, seed=6)
    for t in (left, right):  # 실제 화면처럼 밝은 테두리 없이
        ImageDraw.Draw(t).rectangle([0, 0, t.width - 1, t.height - 1], outline=PANEL)
    boxes = find_tooltips(_frame([((400, 100), left), ((690, 100), right)]))
    assert len(boxes) == 2
    assert count_stars(left) == 10 and count_stars(right) is None


def test_orange_stars_are_counted():
    """화면에 따라 채워진 별이 주황색으로 보인다(실측: 19성을 못 셈)."""
    tip = _tooltip(lit=19, sparkles=False)
    a = tip.load()
    for y in range(0, 48):
        for x in range(tip.width):
            if a[x, y] == (255, 214, 0):
                a[x, y] = (250, 165, 20)
    assert count_stars(tip) == 19


def test_orange_text_below_name_is_not_stars():
    """별 없는 템(강화 불가)의 이름 아래 주황 글자('교환 불가' 등)를 별로 세면 안 된다(실측: 미트라 엠블렘을 18성으로 셈)."""
    tip = _tooltip(lit=0, sparkles=False)
    d = ImageDraw.Draw(tip)
    for i, word in enumerate(["TRADE LOCKED (5/5)", "MEMENTO 2026.10.31"]):
        d.text((60, 6 + i * 16), word, fill=(255, 150, 40))
    assert count_stars(tip) is None


def test_star_row_above_detected_box_is_still_counted():
    """실측(자동 프레임 40장): 툴팁 상자가 첫 별 줄 아래에서 시작해 15개가 빠짐(22→7) — 상자 위쪽까지 보고 센다."""
    from server.tooltip import stars_near
    tip = _tooltip(lit=18, sparkles=False)
    fr = _frame([((520, 160), tip.crop((0, 20, tip.width, tip.height)))])   # 패널은 둘째 별 줄부터
    d = ImageDraw.Draw(fr)
    for col in range(15):                                                   # 첫 별 줄(15개)은 패널 위 배경에 직접
        _star(d, 520 + 40 + col * 15 + (col // 5) * 8, 152, 6, (255, 214, 0))
    box = find_tooltips(fr)[0]
    assert box[1] >= 155                       # 상자는 첫 별 줄을 놓친다
    assert stars_near(fr, box) == 18


def test_yellowish_background_above_tooltip_does_not_hide_stars():
    """실측: 툴팁 위 배경(노을 등)의 노란 덩어리 때문에 별 세기가 멈춰 0성이 됨 — 위쪽 들쭉날쭉한 줄은 건너뛴다."""
    from server.tooltip import stars_near
    tip = _tooltip(lit=18, sparkles=False)
    fr = _frame([((520, 160), tip)])
    d = ImageDraw.Draw(fr)
    for x, w in ((500, 30), (560, 9), (600, 50), (700, 14)):     # 툴팁 위 배경의 노란·주황 덩어리(크기·간격 제각각)
        d.rectangle([x, 126, x + w, 126 + max(8, w // 2)], fill=(250, 180, 40))
    assert stars_near(fr, find_tooltips(fr)[0]) == 18


def test_short_medal_tooltip_cut_by_orange_name_plate_is_found():
    """훈장 툴팁(2026-10-06 실측 321×250): 짧은 데다 주황 이름표가 가로로 지나가 어두운 열이 168px 두 토막으로 끊겼다.
    짧은 끊김(3칸 이하)은 이어진 것으로 본다."""
    tip = Image.new("RGB", (320, 250), PANEL)
    d = ImageDraw.Draw(tip)
    d.rectangle([0, 0, 319, 249], outline=(150, 160, 175))
    d.rectangle([20, 50, 95, 125], fill=(200, 200, 205))        # 훈장 아이콘 칸(밝은 회색)
    d.rectangle([0, 168, 319, 192], fill=(230, 140, 30))        # 주황 이름표(툴팁 폭 전체, 실측 약 24px)
    for i in range(3):
        d.text((20, 195 + i * 16), "보스 몬스터 데미지 +5%", fill=(230, 230, 230))
    boxes = find_tooltips(_frame([((1000, 380), tip)]))
    assert len(boxes) == 1
    x0, y0, x1, y1 = boxes[0]
    assert abs(x0 - 1000) <= 8 and abs(x1 - 1320) <= 8 and abs(y0 - 380) <= 16 and abs(y1 - 630) <= 16


def test_extra_box_without_text_lines_is_not_a_tooltip():
    """보충 방식이 잡은 어두운 상자라도 글자 줄이 없으면(게임 속 깃발, 2026-10-06 실측) 툴팁이 아니다 — AI 비용 방지."""
    tip = Image.new("RGB", (320, 250), PANEL)
    d = ImageDraw.Draw(tip)
    d.rectangle([0, 168, 319, 192], fill=(230, 140, 30))
    assert find_tooltips(_frame([((1000, 380), tip)])) == []
