"""화면 공유 프레임 측정(2026-10-04)에서 드러난 문제를 코드로 막는다.
1) 옆에 뜬 '현재 장착 중인 장비' 비교 툴팁을 매물로 착각 → equipped=true는 매물에서 뺀다.
2) 큰 화면을 줄이면 숫자 오독(255→2550, 76→276) → 괄호 안 값(기본+추옵+강화) 합 검산, 안 맞으면 평가 보류."""
import json
from types import SimpleNamespace as NS

from helpers import bundle
from nexon.convert import snapshot
from server.service import vision_items
from server.vision import _PROMPT, _SCHEMA, checksum_failures, extract_listings

ITEM_PROPS = _SCHEMA["properties"]["listings"]["items"]


def _fake(payload):
    return NS(responses=NS(create=lambda **kw: NS(output=[], output_text=json.dumps(payload, ensure_ascii=False),
                                                   status="completed", usage=NS(input_tokens=1, output_tokens=1))))


def _item(name, equipped=False, total=None, breakdown=None):
    keys = ("STR", "DEX", "INT", "LUK", "HP", "ATK", "MATK", "ALL%", "BOSS", "IED", "DMG")
    t = {k: None for k in keys}
    t.update(total or {})
    b = {k: None for k in keys}
    b.update(breakdown or {})
    return {"name": name, "category": "반지", "part": "반지", "starforce": 18, "level": 130, "potential_grade": "레전드리",
            "additional_grade": "레어", "total": t, "breakdown": b, "potentials": ["LUK +9%"], "additional": ["INT +2%"],
            "price": 1_000_000_000, "equipped": equipped}


def test_schema_and_prompt_cover_equipped_and_breakdown():
    assert {"equipped", "breakdown"} <= set(ITEM_PROPS["required"])
    assert "현재 장착 중인 장비" in _PROMPT and "괄호" in _PROMPT


def test_equipped_comparison_tooltip_is_not_a_listing():
    payload = {"tooltip_visible": True, "fee_rate": None,
               "listings": [_item("어센던트 펄스 링"), _item("카오스 링", equipped=True)]}
    data = extract_listings(_fake(payload), "data:image/jpeg;base64,AAA")
    assert [x["name"] for x in data["listings"]] == ["어센던트 펄스 링"]
    assert data["equipped"] == ["카오스 링"]
    assert [x["name"] for x in data["equipped_items"]] == ["카오스 링"]   # 학습 데이터용으로 판독은 따로 남긴다


def test_checksum_flags_misread_totals():
    ok = {"total": {"ATK": 76, "HP": 255}, "breakdown": {"ATK": [10, 45, 21], "HP": [0, 255]}}
    assert checksum_failures(ok) == []
    bad = {"total": {"ATK": 276, "HP": 2550}, "breakdown": {"ATK": [10, 45, 21], "HP": [0, 255]}}
    assert checksum_failures(bad) == ["ATK: 276 ≠ 10+45+21", "HP: 2550 ≠ 0+255"]
    assert checksum_failures({"total": {"STR": 8}, "breakdown": {}}) == []   # 괄호가 없는 줄은 검산 대상 아님


def test_checksum_failure_holds_evaluation():
    read = {"name": "고통의 근원", "category": "펜던트", "part": "펜던트", "starforce": 17,
            "total": {"STR": 107, "HP": 2550}, "breakdown": {"STR": [10, 66, 1, 30], "HP": [0, 255]},
            "potentials": ["LUK +12%"], "potential_lines": ["LUK +12%"], "additional": [], "price": 1e9}
    row = vision_items(snapshot(bundle("레테")), None, 300.0, [read], [])[0]
    assert row["evaluated"] is False and row["unverified_totals"] == ["HP: 2550 ≠ 0+255"]
    assert "검산" in row["reason"]


def test_listing_matching_characters_own_equipment_is_dropped():
    """AI가 '현재 장착 중인 장비' 표시를 놓쳐도(측정: 8개 중 4개 놓침), 넥슨 API의 착용 템과 이름·잠재가 같으면 내 템이다."""
    snap = snapshot(bundle("레테"))
    mine = {"name": "에테르넬 메이지글러브", "category": "장갑", "part": "장갑", "starforce": 22, "total": {"INT": 100},
            "potentials": ["크리티컬 데미지 +8%", "INT +10%", "LUK +13%"],
            "potential_lines": ["크리티컬 데미지 +8%", "INT +10%", "LUK +13%"], "additional": [], "price": None}
    row = vision_items(snap, None, 300.0, [mine], [])[0]
    assert row["evaluated"] is False and row["equipped"] is True and "착용 중인 템" in row["reason"]
    other = {**mine, "potentials": ["크리티컬 데미지 +8%", "INT +13%"], "potential_lines": ["크리티컬 데미지 +8%", "INT +13%"]}
    assert vision_items(snap, None, 300.0, [other], [])[0].get("equipped") is not True


def test_starforce_from_screen_is_marked_unverified():
    """측정: AI 스타포스 판독이 자주 틀림(18→25/10, 17→12). 실딜은 총 옵션으로 계산해 영향이 없지만 값은 확인 필요로 표시."""
    read = {"name": "센 반지", "category": "반지", "part": "반지", "starforce": 25, "total": {"INT": 50},
            "potentials": ["INT +12%"], "potential_lines": ["INT +12%"], "additional": [], "price": 1e9}
    row = vision_items(snapshot(bundle("레테")), None, 300.0, [read], [])[0]
    assert "스타포스" in row["starforce_note"] and "총 옵션" in row["starforce_note"]


def _app_with(payload, tmp_path, rate_limit=3):
    from fastapi.testclient import TestClient
    from server.admin import make_password_hash
    from server.app import create_app
    c = TestClient(create_app(lambda n, d: bundle("레테"), str(tmp_path / "c.sqlite3"), agent_client=_fake(payload),
                              admin_password_hash=make_password_hash("pw", 1000), session_secret="s" * 32,
                              rate_limit=rate_limit))
    c.post("/api/admin/login", json={"password": "pw"})
    return c


def test_admin_screen_analysis_is_not_rate_limited_per_ip(tmp_path):
    """실측(2026-10-05): 0.5초 캡처가 IP당 분당 제한에 걸려 23번 중 5번 거절 — 관리자 화면 분석은 토큰 한도로만 묶는다."""
    payload = {"tooltip_visible": True, "fee_rate": None, "listings": [_item("어센던트 펄스 링")]}
    c = _app_with(payload, tmp_path)
    codes = [c.post("/api/vision/listings", json={"image": "data:image/jpeg;base64,AAA"}).status_code for _ in range(8)]
    assert codes == [200] * 8


def test_response_includes_equipped_tooltip_reads(tmp_path):
    """장비창 툴팁은 '착용 템'으로 분류돼 매물에서 빠진다 — 장비창 채점을 위해 판독은 따로 돌려준다."""
    payload = {"tooltip_visible": True, "fee_rate": None,
               "listings": [_item("어센던트 펄스 링"), _item("카오스 링", equipped=True)]}
    r = _app_with(payload, tmp_path, rate_limit=30).post(
        "/api/vision/listings", json={"image": "data:image/jpeg;base64,AAA"}).json()
    assert [x["name"] for x in r["equipped_items"]] == ["카오스 링"]
