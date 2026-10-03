"""무기 상수. 근거: 스탯공격력 공식으로 역산한 실측값(스펙 §5.1).

- 2026-10-02 fixture 46명
- 2026-10-03 무기 표본 8명(tests/fixtures/weapons): 한손검 1.24(미하일), 한손도끼 1.2(데몬슬레이어),
  두손둔기 1.34(팔라딘), 건틀렛 리볼버 1.7(블래스터) — 표본마다 2명, 소수 넷째 자리까지 일치
"""


class UnknownWeapon(Exception):
    """상수를 모르는 무기. 숫자를 추정하지 않는다."""


_GROUPS: dict[float, tuple[str, ...]] = {
    1.2: ("스태프", "완드", "카르타", "샤이닝 로드", "ESP 리미터", "매직 건틀렛", "한손둔기", "한손도끼"),
    1.24: ("한손검",),
    1.3: ("활", "듀얼 보우건", "에인션트 보우", "브레스 슈터", "단검", "장검", "차크람", "체인", "부채", "케인", "튜너"),
    1.3125: ("에너지소드",),
    1.34: ("두손검", "두손둔기"),
    1.35: ("석궁",),
    1.44: ("두손도끼",),
    1.49: ("창", "폴암", "태도"),
    1.5: ("건", "핸드캐논"),
    1.7: ("너클", "소울슈터", "건틀렛 리볼버"),
    1.75: ("아대",),
}
WEAPON_CONSTANTS: dict[str, float] = {name: k for k, names in _GROUPS.items() for name in names}


def weapon_constant(part: str) -> float:
    try:
        return WEAPON_CONSTANTS[part]
    except KeyError:
        raise UnknownWeapon(f"무기 상수 테이블에 없는 무기: {part}") from None
