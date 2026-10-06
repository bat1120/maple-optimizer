"""2026-10-04 실사용 화면 피드백 재현: 가격 자릿수 오보, 총옵션 없는 매물 평가, 보조무기 분류, 에디 접두어, 도커 해시."""
from agent.tools import ToolBox
from engine.options import parse_option
from helpers import bundle
from nexon.convert import snapshot
from server.admin import check_password, make_password_hash
from server.service import vision_items
from server.vision import normalize_listing


def _box():
    return ToolBox(lambda name, date=None: snapshot(bundle("레테")))


_PEN = {"slot": "보조무기", "part": "보조무기", "name": "이볼빙 녹스 마법깃펜", "starforce": 0,
        "total": {"INT": 10, "LUK": 10, "MATK": 5}, "potentials": ["마력 +12%", "보스 몬스터 데미지 +40%", "마력 +9%"],
        "price": 32_799_999_999}


def test_listing_result_carries_korean_price_text_to_quote():
    r = _box().run("evaluate_listings", {"name": "x", "listings": [_PEN]})
    assert r["ranking"][0]["price_text"] == "327억 9999만"


def test_listing_without_total_options_is_held_not_scored():
    blank = {**_PEN, "total": {}, "potentials": []}
    r = _box().run("evaluate_listings", {"name": "x", "listings": [_PEN, blank]})
    assert len(r["ranking"]) == 1
    assert r["held"] == [{"name": "이볼빙 녹스 마법깃펜", "price_text": "327억 9999만",
                          "reason": "총 옵션이 없어 평가하지 않았어요 — 툴팁 윗부분이 보이게 띄워 주세요"}]


def test_additional_potential_prefix_is_stripped():
    assert parse_option("에디셔널 잠재능력: 마력 +12%", 287) == parse_option("마력 +12%", 287)
    assert parse_option("잠재능력 : INT +9%", 287) == parse_option("INT +9%", 287)


def test_secondary_read_as_weapon_is_recategorized():
    x = normalize_listing({"name": "이볼빙 녹스 마법깃펜", "category": "무기", "part": "마법깃펜"})
    assert (x["category"], x["part"]) == ("보조무기", "보조무기")
    w = normalize_listing({"name": "제네시스 카르타", "category": "무기", "part": "카르타"})
    assert (w["category"], w["part"]) == ("무기", "카르타")


def test_pending_rows_can_be_reevaluated_once_character_is_known():
    read = {**_PEN, "category": "보조무기"}
    held = vision_items(None, None, 300.0, [read], [])[0]
    assert held["reason"].startswith("캐릭터를 먼저 조회")
    again = vision_items(snapshot(bundle("레테")), None, 300.0, [held["read"]], [])[0]
    assert again["evaluated"] and isinstance(again["delta_pct"], float)


def test_password_hash_survives_docker_compose_interpolation():
    h = make_password_hash("pw", iterations=1000)
    assert "$" not in h and check_password("pw", h) and not check_password("x", h)
    legacy = h.replace(":", "$")
    assert check_password("pw", legacy)


def test_vision_evaluate_route_reevaluates_without_login(tmp_path):
    """2026-10-07: 화면 평가를 일반 유저에게 열면서 재평가(AI 호출 없음)도 로그인 없이 쓴다."""
    from fastapi.testclient import TestClient
    from server.app import create_app
    c = TestClient(create_app(lambda n, d: bundle("레테"), str(tmp_path / "c.sqlite3"), agent_client=object(),
                              admin_password_hash=make_password_hash("pw", 1000), session_secret="s" * 40))
    body = {"name": "내신부레테", "listings": [{**_PEN, "category": "보조무기"}]}
    items = c.post("/api/vision/evaluate", json=body).json()["items"]
    assert items[0]["evaluated"] and items[0]["slot"] == "보조무기"


def test_numbers_the_user_wrote_are_not_flagged():
    """사용자가 쓴 "200억"·첨부 매물의 잠재 수치를 되풀이하는 건 지어낸 숫자가 아니다(2026-10-04 실사용)."""
    from types import SimpleNamespace as NS
    from agent.loop import run_agent
    usage = NS(input_tokens=1, output_tokens=1)
    final = NS(output=[], output_text="200억 예산이면 보스 몬스터 데미지 +40% 매물부터 봐요. 77억은 모르는 숫자", status="completed", usage=usage)
    seq = [final]
    client = NS(responses=NS(create=lambda **kw: seq.pop(0)))
    msgs = [{"role": "user", "content": '200억으로 뭐부터?\n[{"potentials":["보스 몬스터 데미지 +40%"]}]'}]
    done = list(run_agent(client, _box(), msgs))[-1]
    assert done["unverified_numbers"] == ["77억"]
