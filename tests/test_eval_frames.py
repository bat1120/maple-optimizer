"""자동 테스트셋: 검증된 툴팁을 게임 화면·경매장 창 위에 원래 크기로 붙여 화면 공유 프레임을 만들고, 프레임 판독을 툴팁 단독 라벨과 비교한다."""
import sys

from PIL import Image

from test_tooltip_image import _tooltip

sys.path.insert(0, "tools")
from eval_frames import compare, compose  # noqa: E402

LABEL = {"name": "고통의 근원", "level": 160, "starforce": 18, "starforce_source": "별 세기",
         "total": {"STR": 89, "INT": 134}, "potential_grade": "레전드리", "potential_lines": ["INT +12%", "INT +9%", "INT +9%"],
         "additional_grade": "에픽", "additional": ["INT +4%", "마력 +10", "방어력 +4%"]}


def test_compose_places_tooltip_at_original_size_and_jpeg_compresses():
    bg, win, tip = Image.new("RGB", (1366, 768), (120, 170, 210)), Image.new("RGB", (900, 630), (230, 230, 230)), _tooltip()
    frame, box = compose(bg, win, tip, seed=1)
    assert frame.size == (1366, 768) and frame.format == "JPEG"
    x0, y0, x1, y1 = box
    assert (x1 - x0, y1 - y0) == tip.size and 0 <= x0 and x1 <= 1366 and y1 <= 768


def test_compare_counts_each_field():
    ok, n, miss = compare(LABEL, dict(LABEL))
    assert ok == n == 13
    read = {**LABEL, "starforce": 17, "total": {"STR": 89, "INT": 184}, "additional": ["INT +4%", "마력 +10"]}
    ok, n, miss = compare(LABEL, read)
    assert n == 13 and ok == 10 and any("스타포스" in m for m in miss) and any("INT" in m for m in miss)


def test_compare_skips_starforce_when_label_did_not_count_stars():
    ok, n, _ = compare({**LABEL, "starforce_source": "화면 판독(확인 필요)"}, dict(LABEL))
    assert n == 12
