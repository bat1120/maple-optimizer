"""직업별 주스탯·부스탯·공격 스탯. 근거: 2026-10-02 fixture 46명에서 무기 상수가 깨끗이 떨어지는 조합(스펙 §5.1)."""
from dataclasses import dataclass


class UnsupportedJob(Exception):
    """계산할 수 없는 직업. 숫자를 추정하지 않는다."""


@dataclass(frozen=True)
class JobProfile:
    name: str
    mains: tuple[str, ...]
    subs: tuple[str, ...]
    attack: str  # "ATK" | "MATK"


_GROUPS = [
    (("STR",), ("DEX",), "ATK",
     "히어로 팔라딘 다크나이트 소울마스터 미하일 블래스터 데몬슬레이어 아란 카이저 아델 제로 바이퍼 캐논마스터 스트라이커 은월 아크 렌"),
    (("DEX",), ("STR",), "ATK",
     "보우마스터 신궁 패스파인더 윈드브레이커 와일드헌터 메르세데스 카인 메카닉 캡틴 엔젤릭버스터"),
    (("INT",), ("LUK",), "MATK",
     "아크메이지(불,독) 아크메이지(썬,콜) 비숍 플레임위자드 배틀메이지 에반 루미너스 일리움 라라 키네시스 레테"),
    (("LUK",), ("DEX",), "ATK", "나이트로드 나이트워커 팬텀 칼리 호영"),
    (("LUK",), ("DEX", "STR"), "ATK", "섀도어 듀얼블레이더 카데나"),
    (("STR", "DEX", "LUK"), (), "ATK", "제논"),
]
_TABLE = {name: JobProfile(name, mains, subs, atk) for mains, subs, atk, names in _GROUPS for name in names.split()}
_UNSUPPORTED = {"데몬어벤져": "API가 HP를 표시 상한(500,000)으로만 줘서 순수/추가 HP를 나눌 수 없음"}


def job_profile(character_class: str) -> JobProfile:
    if character_class in _UNSUPPORTED:
        raise UnsupportedJob(f"{character_class}: {_UNSUPPORTED[character_class]}")
    try:
        return _TABLE[character_class]
    except KeyError:
        raise UnsupportedJob(f"직업 테이블에 없는 직업: {character_class}") from None
