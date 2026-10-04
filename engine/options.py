"""메이플 옵션 문자열 → StatLine.

다루는 표기:
- 잠재 신 표기 "STR +12%", 구 표기 "STR : +12%"
- 레벨당 옵션 "캐릭터 기준 9레벨 당 INT +2" (구 표기는 "... STR : +2")
- 하이퍼스탯·어빌리티 "지력 180 증가", "보스 몬스터 공격 시 데미지 47% 증가"
- 세트 효과 "공격력  +30, 마력  +30, 보스 몬스터 데미지 +10%" (쉼표로 여러 개)

반환: 딜 관련 → StatLine 리스트, 딜 무관 → [], 모르는 표기 → None.
"""
import re
from dataclasses import dataclass

_FOUR = ("STR", "DEX", "INT", "LUK")


@dataclass(frozen=True)
class StatLine:
    key: str  # STR DEX INT LUK HP ATK MATK DMG BOSS IED CD CR FD
    value: float
    percent: bool


_NAMES: dict[str, tuple[str, ...]] = {
    "STR": ("STR",), "힘": ("STR",),
    "DEX": ("DEX",), "민첩성": ("DEX",),
    "INT": ("INT",), "지력": ("INT",),
    "LUK": ("LUK",), "운": ("LUK",),
    "올스탯": _FOUR, "모든 능력치": _FOUR,
    "최대 HP": ("HP",),
    "공격력": ("ATK",), "마력": ("MATK",),
    "공격력과 마력": ("ATK", "MATK"), "공격력/마력": ("ATK", "MATK"),
    "데미지": ("DMG",),
    "보스 몬스터 데미지": ("BOSS",), "보스 몬스터 공격 시 데미지": ("BOSS",),
    "몬스터 방어율 무시": ("IED",), "방어율 무시": ("IED",),
    "크리티컬 데미지": ("CD",), "크리티컬 확률": ("CR",),
    "최종 데미지": ("FD",),
}

_IRRELEVANT_NAMES = {
    "최대 MP", "아이템 드롭률", "메소 획득량", "획득 경험치", "방어력", "이동속도", "점프력",
    "일반 몬스터 공격 시 데미지", "일반 몬스터 데미지", "상태 이상 내성", "아케인포스",
    "HP 회복 아이템 및 회복 스킬 효율", "모든 스킬의 MP 소모", "버프 스킬의 지속 시간",
    "스킬 재사용 대기시간", "최대 데몬 포스/타임 포스", "상태 이상에 걸린 대상 공격 시 데미지",
    "추가 경험치", "스타포스", "경험치 획득량", "소환수 지속시간", "버프 지속시간", "최대 MP 회복",
}

_IRRELEVANT_PREFIXES = (
    "공격 시 ", "피격 시 ", "<", "[", "스킬 사용 시 ", "다수 공격 스킬", "방어력의 ",
    "모든 스킬의 재사용 대기시간", "파티퀘스트", "스킬 재사용 대기시간", "적 공격마다", "이동속도",
)

_PER_LEVEL = re.compile(r"^캐릭터 기준\s*(\d+)레벨 당\s*(\S+)\s*:?\s*\+(\d+)$")
_PLUS = re.compile(r"^(?P<name>.+?)\s*:?\s*(?P<sign>[+-])\s*(?P<num>\d+(?:\.\d+)?)\s*(?P<unit>%|초)?$")
_INCREASE = re.compile(r"^(?P<name>.+?)\s+(?P<num>\d+(?:\.\d+)?)(?P<unit>%)?\s*증가$")


_GRADE_PREFIX = re.compile(r"^(?:에디셔널\s*)?잠재\s*능력\s*:\s*")  # 화면 판독이 붙이는 머리말 "에디셔널 잠재능력: "


def parse_option(text: str, level: int) -> list[StatLine] | None:
    text = _GRADE_PREFIX.sub("", text.strip())
    if text.startswith(_IRRELEVANT_PREFIXES):
        return []
    parts = [text] if "(" in text else [p.strip() for p in text.split(",")]
    out: list[StatLine] = []
    for part in parts:
        lines = _parse_one(part, level)
        if lines is None:
            return None
        out.extend(lines)
    return out


def _parse_one(part: str, level: int) -> list[StatLine] | None:
    if part.startswith(_IRRELEVANT_PREFIXES):  # 세트 효과처럼 쉼표로 섞인 경우
        return []
    m = _PER_LEVEL.match(part)
    if m:
        keys = _NAMES.get(m[2])
        if keys is None:
            return None
        value = (level // int(m[1])) * int(m[3])
        return [StatLine(k, value, False) for k in keys]
    m = _PLUS.match(part) or _INCREASE.match(part)
    if not m:
        return None
    name = m["name"].strip()
    if name in _IRRELEVANT_NAMES:
        return []
    keys = _NAMES.get(name)
    if keys is None:
        return None
    value = float(m["num"])
    if m.groupdict().get("sign") == "-":
        value = -value
    return [StatLine(k, value, m["unit"] == "%") for k in keys]
