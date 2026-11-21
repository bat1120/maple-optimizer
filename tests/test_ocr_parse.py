"""OCR 글자 줄 → 매물 정보. 아래 줄은 2026-11-13 실제 경매장 툴팁을 PP-OCRv5(한국어)로 읽은 결과다(오독 포함 —
매물 쪽 '홀스탯 +6%'는 같은 날 다른 프레임에서 나온 오독을 옮겨 넣었다).
코드로 확인되지 않는 판독은 버리고 AI로 넘긴다(None) — 실측값 원칙."""
import pytest

from server.ocr import parse_tooltip
from server.vision import checksum_failures

LISTING = [  # (x, y, 글자)
    (97, 58, "커맨더포스 이어링"), (47, 78, "장착 시 교환불가(가위 사용 잔여횟수:5/5)"),
    (242, 100, "전투력 증가량"), (188, 124, "116만 2430"), (219, 168, "장신구"), (270, 167, "귀고리"),
    (17, 184, "착용 직업"), (101, 184, "공용"), (17, 200, "요구레벨"), (100, 201, "Lv. 175 (200 - 25)"),
    (16, 222, "세트 효과e"), (101, 222, "칠혹의 보스 세트"),
    (17, 239, "STR"), (46, 239, "+92 (7 +85)"), (16, 255, "DEX"), (45, 255, "+116 (7+85 +24)"),
    (16, 271, "INT"), (45, 271, "+146 (7 +85 +54)"), (17, 288, "LUK"), (44, 287, "+122 (7 +85 +30)"),
    (16, 302, "최대 HP"), (50, 303, "+500"), (17, 319, "최대MP"), (55, 320, "+3500 (500 +3000)"),
    (17, 333, "공격력 +44 (5 +39)"), (16, 350, "마력  +44 (5 +39)"), (17, 367, "방어력 +255 (100 +155)"),
    (17, 387, "주문서 강화 없음(잔여 7회, 복구 가능 0회)"), (17, 403, "NPC/채집키를 통해 강화 정보 상세 확인 가능"),
    (16, 424, "잠재능력:레전드리"), (18, 441, "INT +12%"), (19, 457, "•홀스탯 +6%"), (28, 473, "INT +9%"),
    (30, 493, "에디셔널잠재능력:없음"), (31, 512, "익셉셔널: 없음(최대1회)"),
    (192, 542, "1"), (215, 540, "2  3  4  5  6"), (78, 591, "20,703,604,835.62517.035%]"),
]
EQUIPPED = [
    (107, 59, "에스텔라이어링"), (63, 78, "교환 불가(가위 사용 잔여 윗수: 10/ 10)"),
    (243, 100, "전투력 증가량"), (150, 127, "현재 장착 중인 장비"), (219, 167, "장신구"), (270, 167, "귀고리"),
    (16, 184, "착용 직업"), (101, 184, "공용"), (16, 200, "요구 레벨"), (100, 201, "Lv. 160"),
    (16, 221, "세트 효과"), (101, 222, "여명의 보스 세트"),
    (16, 239, "STR"), (45, 239, "+111 (7 +79 +25)"), (16, 255, "DEX"), (45, 255, "+111 (7 +79 +25)"),
    (16, 271, "INT"), (45, 271, "+136 (7 +79+50)"), (16, 287, "LUK"), (45, 286, "+86 (7 +79)"),
    (16, 302, "홀스탯"), (53, 302, "+5%(0% +5%)"), (16, 318, "최대 HP"), (61, 319, "+300"),
    (16, 334, "최대MP"), (57, 335, "+300"), (17, 350, "공격력 +35 (2 +33)"), (17, 366, "마력 +71 (2 +33 +30 +6)"),
    (16, 382, "방어력 +255 (100 +155)"), (17, 403, "주문서 강화 7회(잔여0회, 복구 가능 0회)"),
    (17, 419, "NPC/채집키를 통해 강화 정보 상세 확인 가능"),
    (15, 440, "잠재능력:유니크"), (18, 457, "INT +9%"), (18, 473, "•INT +6%"), (19, 489, "• DEX +6%"),
    (16, 509, "B에디셔널잠재능력: 레어"), (18, 524, "마력+10"), (18, 540, "마력+3"), (17, 556, "점프력+4"),
    (17, 576, "플래티넘카르마의가위사용시1회교환 가능"),
]


def _swap(rows, old, new):
    assert any(t == old for _, _, t in rows)
    return [(x, y, new if t == old else t) for x, y, t in rows]


def test_listing_tooltip_is_read_without_ai():
    x = parse_tooltip(LISTING)
    assert x["name"] == "커맨더 포스 이어링" and x["category"] == x["part"] == "귀고리" and x["equipped"] is False
    assert x["power_delta_text"] == "116만 2430" and x["level"] == 200
    assert x["total"] == {"STR": 92, "DEX": 116, "INT": 146, "LUK": 122, "HP": 500, "ATK": 44, "MATK": 44}
    assert x["breakdown"]["DEX"] == [7, 85, 24] and "HP" not in x["breakdown"]
    assert checksum_failures(x) == []
    assert x["potential_grade"] == "레전드리" and x["potentials"] == ["INT +12%", "올스탯 +6%", "INT +9%"]  # 홀스탯 → 올스탯
    assert x["additional_grade"] is None and x["additional"] == []
    assert x["price"] is None and x["price_text"] is None  # 툴팁에는 가격이 없다


def test_equipped_comparison_tooltip():
    x = parse_tooltip(EQUIPPED)
    assert x["name"] == "에스텔라 이어링" and x["equipped"] is True and x["power_delta_text"] is None
    assert x["total"]["ALL%"] == 5 and x["breakdown"]["ALL%"] == [0, 5] and x["total"]["MATK"] == 71
    assert x["potential_grade"] == "유니크" and x["potentials"] == ["INT +9%", "INT +6%", "DEX +6%"]
    assert x["additional_grade"] == "레어" and x["additional"] == ["마력 +10", "마력 +3", "점프력 +4"]


@pytest.mark.parametrize("old, new", [
    ("+116 (7+85 +24)", "+116 (7+85 +4)"),      # 괄호 합이 안 맞는다
    ("커맨더포스 이어링", "가나다라 마바사"),          # 모르는 이름
    ("INT +12%", "INT +72%"),                    # 공식 옵션표에 없는 줄
    ("귀고리", "한손검"),                          # 무기·모르는 분류는 AI가 읽는다
    ("최대 HP", "죄대 HQ"),                       # 스탯 이름을 알 수 없는 줄
    ("잠재능력:레전드리", "잠재능력:레전드"),           # 등급을 못 읽었는데 옵션 줄이 있다
])
def test_unverifiable_reading_is_left_to_ai(old, new):
    assert parse_tooltip(_swap(LISTING, old, new)) is None


def test_option_digits_are_never_guessed():
    """글자는 공식 옵션표로 고쳐도 숫자는 고치지 않는다 — '홀스탯 +8%'를 '올스탯 +6%'로 바꾸지 않는다."""
    assert parse_tooltip(_swap(LISTING, "•홀스탯 +6%", "•홀스탯 +8%")) is None


def test_special_ring_goes_to_ai():
    rows = _swap(LISTING, "귀고리", "반지") + [(18, 530, "리스트레인트 링 4레벨")]
    assert parse_tooltip(rows) is None
