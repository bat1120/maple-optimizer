"""추가옵션(추옵) 재설정: 환생의 불꽃·메소 재설정 (engine/data/flame_tables.json).

- 단계 확률·옵션 개수·옵션 종류(균등)·레벨 제한: 공식 확률 페이지(Guide/OtherProbability/game/gameAddOption)
- 메소 재설정: 2026-03-19 업데이트 공지 — 1회 3,000,000 메소, 확률은 검은 환생의 불꽃과 같다
- 단계별 수치: 나무위키 '추가옵션' 공식(무기 공격력은 파프니르·아케인셰이드 표로 검산)
한 번 돌리면 옵션 종류 L개를 겹치지 않게 균등하게 고르고(보스 장비는 4개), 줄마다 단계를 독립적으로 뽑는다.
보스 장비인지 출처로 확인되지 않는 템은 계산하지 않는다(일반 장비는 개수·단계가 달라 짐작하면 틀린다).
"""
import functools
import json
import math
import pathlib
from collections.abc import Callable
from fractions import Fraction

_DATA = json.loads((pathlib.Path(__file__).resolve().parent.parent / "data" / "flame_tables.json").read_text(encoding="utf-8"))
MESO_RESET = _DATA["meso_reset"]["name"]
MESO_RESET_COST = _DATA["meso_reset"]["cost"]
KINDS = tuple(_DATA["kinds"])  # 불꽃 이름(카르마·대적자 접두어가 붙어도 확률은 같다)
_FOUR = ("STR", "DEX", "INT", "LUK")
_NO_VALUE = {"최대 MP", "착용 레벨 감소", "방어력", "이동속도", "점프력"}  # 실딜 무관 — 수치를 쓰지 않는다

Key = tuple[str, bool]  # (StatLine.key, percent)


def stage_distribution(name: str, boss: bool) -> dict[int, float]:
    """불꽃 이름 → {단계: 확률}. 보스 장비는 +2단계(3~7)."""
    table = _DATA["kinds"].get(name)
    if table is None:
        raise ValueError(f"알 수 없는 환생의 불꽃: {name}")
    bonus = _DATA["boss_stage_bonus"] if boss else 0
    return {s + 1 + bonus: pct / 100 for s, pct in enumerate(_DATA["stage_probability"][table]) if pct}


def options(weapon: bool, level: int) -> list[str]:
    """그 장비에 붙을 수 있는 옵션 종류(공식 표, 레벨 제한 반영)."""
    group = "무기" if weapon else "그 외"
    need = _DATA["level_min"][group]
    return [o for o in _DATA["options"][group] if level >= need.get(o, 0)]


def line_value(option: str, stage: int, level: int, weapon: bool, base_attack: dict[str, float]) -> dict[Key, float]:
    """옵션 한 줄의 수치. level = 착감 전 원래 렙제, base_attack = 순수 공격력·마력(무기만 쓴다)."""
    if option in _NO_VALUE:
        return {}
    if option in _FOUR:
        lv = 220 if level == 250 else level  # 나무위키 각주: 장비 레벨이 250이면 220으로 계산
        return {(option, False): (lv // 20 + 1) * stage}
    if "+" in option:
        a, b = option.split("+")
        return {(a, False): (level // 40 + 1) * stage, (b, False): (level // 40 + 1) * stage}
    if option == "최대 HP":
        return {("HP", False): (level // 10 * 10) * 3 * stage}
    if option in ("공격력", "마력"):
        key = "ATK" if option == "공격력" else "MATK"
        if not weapon:
            return {(key, False): stage}
        if stage < 3:
            raise ValueError("무기 공격력·마력 공식은 3~7단계(보스 장비)만 출처 표로 확인했어요")
        base = base_attack.get(key) or 0
        if not base:
            return {}
        pct = Fraction(int(base)) * (level // 40 + 1) * stage * Fraction(11, 10) ** (stage - 3) / 100
        return {(key, False): math.ceil(pct)}
    if option == "데미지%":
        return {("DMG", True): stage}
    if option == "보스 몬스터 데미지%":
        return {("BOSS", True): 2 * stage}
    if option == "올스탯%":
        return {(k, True): stage for k in _FOUR}
    raise ValueError(f"알 수 없는 추가옵션: {option}")


def _line_count(boss: bool) -> dict[int, float]:
    row = _DATA["line_count"]["보스 장비" if boss else "환생의 불꽃류"]
    return {n + 1: pct / 100 for n, pct in enumerate(row) if pct}


def _r(x: float) -> float:
    return round(x, 9)


def score_distribution(name: str, weapon: bool, level: int, boss: bool,
                       score_of: Callable[[str], dict[int, float]]) -> dict[float, float]:
    """한 번 재설정한 결과의 점수 분포 {점수: 확률}. score_of(옵션) → {단계: 점수}(없는 단계·옵션은 0점).
    옵션 L개 조합은 모두 같은 확률이라, 점수가 있는 옵션만 k개 고르는 경우를 합치고 나머지는 0점 옵션 개수로 센다."""
    stages = stage_distribution(name, boss)
    pool = options(weapon, level)
    dists = []
    for o in pool:
        sc = score_of(o)
        d: dict[float, float] = {}
        for s, p in stages.items():
            v = _r(sc.get(s, 0.0))
            d[v] = d.get(v, 0.0) + p
        if any(v for v in d):
            dists.append(d)
    counts = _line_count(boss)
    top = max(counts)
    dp: list[dict[float, float]] = [{0.0: 1.0}] + [{} for _ in range(top)]  # dp[k]: 점수 옵션 k개 조합의 합
    for d in dists:
        for k in range(min(top, len(dists)) - 1, -1, -1):
            if not dp[k]:
                continue
            nxt = dp[k + 1]
            for a, pa in dp[k].items():
                for b, pb in d.items():
                    s = _r(a + b)
                    nxt[s] = nxt.get(s, 0.0) + pa * pb
    zero = len(pool) - len(dists)
    out: dict[float, float] = {}
    for n, q in counts.items():
        total = math.comb(len(pool), n)
        for k in range(0, min(n, len(dists)) + 1):
            ways = math.comb(zero, n - k)
            if not ways:
                continue
            for s, w in dp[k].items():
                out[s] = out.get(s, 0.0) + q * w * ways / total
    return out


def target_stats(dist: dict[float, float], threshold: float) -> dict:
    """점수 threshold 이상이 나올 확률과, 그때(멈춘 결과) 평균 점수."""
    hits = [(s, p) for s, p in dist.items() if s >= threshold - 1e-12]
    prob = sum(p for _, p in hits)
    return {"probability": prob, "mean_score": sum(s * p for s, p in hits) / prob if prob > 0 else 0.0}


@functools.lru_cache(maxsize=None)
def _boss_rule() -> dict:
    return _DATA["boss_equipment"]


def is_boss_item(name: str, part: str, catalog) -> bool:
    """출처(나무위키 각주 2·28, 5.1절 예시)로 보스 장비임이 확인되는 템만 True. 추옵이 붙지 않는 부위는 False."""
    rule = _boss_rule()
    if part in _DATA["no_flame_parts"] or name in rule["excluded_names"]:
        return False
    if name.startswith(tuple(rule["weapon_prefixes"])):
        return True
    set_name = catalog.items.get(name) or ""
    return any(k in set_name for k in rule["set_keywords"])


def no_flame_part(part: str) -> bool:
    return part in _DATA["no_flame_parts"]
