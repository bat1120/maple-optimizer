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


def test_agent_prompt_requires_measured_values_only():
    for phrase in ("실측값 원칙", "측정값 없음", "기억이나 일반 지식으로 채우지 않는다", "글자 그대로", "평균 기대값", "근사"):
        assert phrase in SYSTEM, phrase


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
