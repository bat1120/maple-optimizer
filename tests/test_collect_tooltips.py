"""인터넷 툴팁 자동 수집: robots.txt가 허용한 메이플 게시판을 천천히 돌며, 코드가 툴팁이라고 판단한 이미지만 내 PC에 모은다."""
import sys

from test_tooltip_image import _frame, _tooltip

sys.path.insert(0, "tools")
from collect_tooltips import content_images, is_tooltip_image, post_date  # noqa: E402
from label_tooltips import verify  # noqa: E402


def test_tooltip_image_detection():
    assert is_tooltip_image(_tooltip())                       # 잘라 올린 툴팁
    assert is_tooltip_image(_frame([((520, 120), _tooltip())]))  # 툴팁이 뜬 전체 화면
    assert not is_tooltip_image(_frame([]))                   # 툴팁 없는 게임 화면


def test_post_date_and_same_day_images_only():
    html = ('<span class="date">2026-10-04 19:38</span>'
            '<img src="https://upload3.inven.co.kr/upload/2026/10/04/bbs/i111.png">'
            '<img src="https://upload3.inven.co.kr/upload/2025/12/03/bbs/i222.png">'  # 사이드바 등 다른 날 이미지
            '<img src="https://upload3.inven.co.kr/upload/2026/10/04/bbs/thumb/n333.jpg">')
    assert post_date(html) == "2026-10-04"
    assert content_images(html, "2026-10-04") == ["https://upload3.inven.co.kr/upload/2026/10/04/bbs/i111.png"]


def test_verify_keeps_only_labels_that_pass_code_checks():
    ok = {"name": "x", "total": {"STR": 76}, "breakdown": {"STR": [10, 45, 21]},
          "potential_lines": ["STR +12%"], "additional": ["STR +6%"], "starforce_source": "별 세기"}
    assert verify(ok) == (True, [])
    bad = {**ok, "total": {"STR": 276}, "potential_lines": ["STR +1즈%"]}
    passed, why = verify(bad)
    assert not passed and any("검산" in w for w in why) and any("옵션표" in w for w in why)
    assert verify({**ok, "potential_lines": [], "additional": []})[0] is False   # 잠재 줄이 없으면 장비 툴팁이 아니다
