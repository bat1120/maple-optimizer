"""할루시네이션 방지: 실제 측정값만 쓴다.
2026-10-04 골든셋 비교에서 AI가 옵션 문장을 줄이고(…회복 스킬 효율 +30% → …회복 스킬 +30%) 이름을 바꿔 적은 것을 확인했다.
지시문으로 금지하고, 공식 큐브 옵션표에 없는 줄은 코드로 '확인 필요' 표시한다."""
from agent.loop import SYSTEM
from helpers import bundle
from nexon.convert import snapshot
from server.service import vision_items
from server.vision import _PROMPT, normalize_listing, unverified_lines

GLOVE = {"name": "에테르넬 나이트글러브", "category": "장갑", "part": "장갑", "starforce": 18, "level": 250,
         "total": {"STR": 253, "DEX": 181, "ALL%": 5, "ATK": 101, "MATK": 45},
         "potentials": ["크리티컬 데미지 +8%", "크리티컬 데미지 +8%", "HP 회복 아이템 및 회복 스킬 +30%"],
         "additional": ["STR +5%", "최대 HP +3%", "STR +3%"], "price": 10_000_000_000}


def test_measured_values_only_is_carried_by_prompt_direction_tool_results_and_code():
    """2026-11-23 프롬프트를 방향만 남기고 다시 썼다 — 실측값 원칙은 세 곳이 나눠 진다."""
    from agent.loop import rewrite_request
    from agent.tools import ToolBox
    # 방향: 근거는 도구, 없으면 측정값 없음
    for phrase in ("근거는 도구", "그대로 옮긴다", "측정값 없음"):
        assert phrase in SYSTEM, phrase
    # 결과: 계산값의 성격(평균·근사)과 시세 없음은 도구 결과가 말한다
    r = ToolBox(lambda name, date=None: snapshot(bundle("레테")), market=lambda: []).run("upgrade_roadmap", {"name": "레테"})
    assert "평균 비용" in r["value_note"] and "근사" in r["value_note"]
    assert "측정값 없음" in r["market_status"] and "request_auction_screen" in r["market_status"]
    # 코드: 출처 없는 숫자는 보여 주기 전에 다시 쓰게 한다
    assert "12억" in rewrite_request(["12억"])


def test_vision_prompt_forbids_rewriting_and_guessing():
    for phrase in ("화면 글자를 그대로", "고치거나 줄이거나 바꿔 쓰지 않는다", "화면에 없는 값은 채우지 않는다", "별을 셀 수 있을 때만"):
        assert phrase in _PROMPT, phrase


def test_lines_not_in_official_option_table_are_flagged():
    assert unverified_lines(["크리티컬 데미지 +8%", "HP 회복 아이템 및 회복 스킬 +30%", "LUK +15"]) == \
        ["HP 회복 아이템 및 회복 스킬 +30%"]
    assert unverified_lines(["HP 회복 아이템 및 회복 스킬 효율 +30%", "스킬 재사용 대기시간 -2초"]) == []


def test_vision_row_carries_needs_check_lines():
    read = normalize_listing(dict(GLOVE))
    row = vision_items(snapshot(bundle("레테")), None, 300.0, [read], [])[0]
    assert row["unverified_lines"] == ["HP 회복 아이템 및 회복 스킬 +30%"]
    ok = normalize_listing({**GLOVE, "potentials": ["크리티컬 데미지 +8%", "크리티컬 데미지 +8%",
                                                     "HP 회복 아이템 및 회복 스킬 효율 +30%"]})
    assert vision_items(snapshot(bundle("레테")), None, 300.0, [ok], [])[0]["unverified_lines"] == []


def test_rare_grade_and_low_level_options_are_official():
    """실측(2026-10-05): 레어 등급·낮은 레벨 옵션이 표에 없어 헛경보 — 레어·레벨 10~250 구간 공식표로 넓혔다."""
    assert unverified_lines(["최대 HP +60", "점프력 +4", "마력 +3"]) == []


def test_lines_irrelevant_to_damage_are_not_flagged():
    """실딜 계산에 안 쓰는 줄(공격 시 HP 회복 등)은 레벨마다 숫자가 달라 표 대조에서 뺀다."""
    assert unverified_lines(["공격 시 3% 확률로 47의 HP 회복"]) == []
    assert unverified_lines(["STR +1즈%"]) == ["STR +1즈%"]


def test_special_ring_listing_result_says_effect_is_not_in_damage():
    """특수 반지 안내는 프롬프트가 아니라 평가 결과에 붙어 간다."""
    from agent.tools import ToolBox
    ring = {"slot": "반지4", "part": "반지", "name": "리스트레인트 링", "total": {"INT": 20, "MATK": 10}, "potentials": [],
            "price": 5_000_000_000, "special_ring_level": 4}
    r = ToolBox(lambda name, date=None: snapshot(bundle("레테"))).run("evaluate_listings", {"name": "레테", "listings": [ring]})
    note = r["ranking"][0]["special_ring_note"]
    assert "실딜 계산에 없어요" in note and "4레벨" in note and "레벨과 가격으로" in note
