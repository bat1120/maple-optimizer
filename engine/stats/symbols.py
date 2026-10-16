"""아케인·어센틱 심볼 성장표(2026-10-11): engine/data/symbol_tables.json — 나무위키 성장표와 공식 공지(출처·확인 날짜는 파일 안).

- need(kind, L)·meso(kind, 지역, L): L레벨 → L+1레벨에 필요한 성장치(심볼 개수)와 강화 메소
- stats_at(kind, L, 직업): L레벨 심볼이 주는 스탯(%미적용). 제논은 STR·DEX·LUK 각각, 데몬어벤져는 최대 HP
- 그랜드 어센틱심볼은 주스탯이 없다(경험치·메소·드롭률만)
- force_at(kind, L): L레벨 심볼의 포스(보스 포스 보정은 engine/stats/force.py)
"""
import json
import pathlib

from engine.stats.jobs import job_profile

PATH = pathlib.Path(__file__).parent.parent / "data" / "symbol_tables.json"
_T = json.loads(PATH.read_text(encoding="utf-8"))
KINDS = _T["kinds"]


def split_name(name: str) -> tuple[str, str]:
    """'어센틱심볼 : 세르니움' → ('어센틱심볼', '세르니움')."""
    kind, _, region = name.partition(":")
    return kind.strip(), region.strip()


def max_level(kind: str) -> int:
    return KINDS[kind]["max_level"]


def force_at(kind: str, level: int) -> int:
    """L레벨 심볼의 포스: 아케인 10(L+2), 어센틱·그랜드 10L(나무 성장표, 픽스처 symbol_force로 검산)."""
    f = KINDS[kind]["force"]
    return f["per_level"] * (level + f["add"]) if level > 0 else 0


def force_kind(kind: str) -> str:
    """심볼 종류 → 포스 종류('아케인' 또는 '어센틱')."""
    return "아케인" if kind.startswith("아케인") else "어센틱"


def need(kind: str, level: int) -> int:
    return KINDS[kind]["need"][level - 1]


def meso(kind: str, region: str, level: int) -> int | None:
    row = KINDS[kind]["meso"].get(region)
    return row[level - 1] if row else None


def daily(kind: str, region: str) -> int | None:
    return KINDS[kind].get("daily", {}).get(region)


def _keys(character_class: str) -> tuple[str, tuple[str, ...]]:
    if character_class == "데몬어벤져":
        return "데몬어벤져", ("HP",)
    if character_class == "제논":
        return "제논", ("STR", "DEX", "LUK")
    return "일반", (job_profile(character_class).mains[0],)


def stats_at(kind: str, level: int, character_class: str) -> dict[str, float]:
    st = KINDS[kind]["stat"]
    if not st or level <= 0:
        return {}
    unit, keys = _keys(character_class)
    v = float(KINDS[kind]["unit"][unit] * (st["mult"] * level + st["add"]))
    return {k: v for k in keys}


def gain(kind: str, level: int, target: int, character_class: str) -> dict[str, float]:
    a, b = stats_at(kind, level, character_class), stats_at(kind, target, character_class)
    return {k: b[k] - a.get(k, 0.0) for k in b if b[k] - a.get(k, 0.0)}
