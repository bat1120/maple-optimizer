"""추옵(환생의 불꽃·메소 재설정) 경로(2026-10-08): 지금 템의 추옵을 다시 돌려 목표 점수 이상이 나올 때까지의 기대 비용.

- 확률·수치: engine/data/flame.json(출처·미확인 부분은 그 파일에). 보스 장비 기준 4줄, 각 줄 단계 확률은 독립
- 옵션 고르기: 19종 중 서로 다른 4개를 같은 확률로(미확인 — 결과에 unverified=True를 붙인다)
- 점수: 옵션 하나가 실딜에 주는 값(실딜 %/단위, 지금 템에 조금 더해 본 기울기)의 합 → 정확히 셈(시뮬레이션 아님)
- 비용: 목표 이상이 나올 확률 p면 평균 1/p회 × 재설정 1회 값(사용자가 넣는다 — 지금 메소 재설정 값은 확인 못 함)
- 무기는 공·마 공식이 실측 검산되지 않아 뺀다. 도전자 장비(고정 추옵)도 뺀다
"""
import itertools
import json
import math
import pathlib

_FILE = pathlib.Path(__file__).resolve().parents[1] / "data" / "flame.json"
DATA = json.loads(_FILE.read_text(encoding="utf-8"))
TIERS: dict[str, dict[int, float]] = {k: {int(t): p for t, p in v.items()} for k, v in DATA["tier_prob"].items()}
POOL: list[str] = DATA["armor_pool"]
LINES: int = DATA["boss_lines"]
_STATS = ("STR", "DEX", "INT", "LUK")
_API = {"str": "STR", "dex": "DEX", "int": "INT", "luk": "LUK", "attack_power": "ATK", "magic_power": "MATK",
        "all_stat": "ALL%"}
_OTHER_API = ("max_hp", "max_mp", "armor", "speed", "jump", "equipment_level_decrease")  # 한 줄씩, 점수 0
QUANTILES = (0.2, 0.05, 0.01, 0.002)  # 목표: 한 번 돌렸을 때 이 확률(상위 20·5·1·0.2%)로 나오는 점수 이상
PER_SLOT = 2


def single_const(level: int) -> int:
    return DATA["values"]["single_cap_at_250"] if level >= 250 else level // 20 + 1


def double_const(level: int) -> int:
    return level // 40 + 1


def amounts(option: str, tier: int, level: int) -> dict[str, float]:
    """옵션 한 줄이 주는 스탯(실딜에 쓰는 키만: STR DEX INT LUK ATK MATK ALL%)."""
    if option in _STATS:
        return {option: single_const(level) * tier}
    if "+" in option:
        a, b = option.split("+")
        return {a: double_const(level) * tier, b: double_const(level) * tier}
    return {"공격력": {"ATK": tier}, "마력": {"MATK": tier}, "올스탯%": {"ALL%": tier}}.get(option, {})


def current_lines(add: dict, level: int) -> dict[str, float]:
    """넥슨 API item_add_option → 실딜에 쓰는 키별 합."""
    return {_API[k]: float(v) for k, v in add.items() if k in _API and float(v or 0)}


def explains(add: dict, level: int, tiers=range(1, 8)) -> bool:
    """추옵 값이 '서로 다른 옵션 4줄 이하 · 단계 tiers'로 정확히 나뉘는가(실측 검산용)."""
    target = {s: float(add.get(s.lower(), 0) or 0) for s in _STATS}
    lines = sum(1 for k in ("attack_power", "magic_power", "all_stat") + _OTHER_API if float(add.get(k, 0) or 0))
    for k in ("attack_power", "magic_power", "all_stat"):
        v = float(add.get(k, 0) or 0)
        if v and v not in tiers:
            return False
    a, b = single_const(level), double_const(level)
    doubles = list(itertools.combinations(_STATS, 2))
    for nd in range(0, LINES - lines + 1):
        for ds in itertools.combinations(doubles, nd):
            for ts in itertools.product(tiers, repeat=nd):
                rem = dict(target)
                for (x, y), t in zip(ds, ts):
                    rem[x] -= b * t
                    rem[y] -= b * t
                if any(v < 0 for v in rem.values()):
                    continue
                singles = [v for v in rem.values() if v]
                if all(v % a == 0 and v // a in tiers for v in singles) and lines + nd + len(singles) <= LINES:
                    return True
    return False


def score_of(stats: dict[str, float], weights: dict[str, float]) -> float:
    return sum(weights.get(k, 0.0) * v for k, v in stats.items())


def reach_table(weights: dict[str, float], level: int, kind: str = "메소 재설정") -> list[tuple[float, float]]:
    """한 번 돌린 결과 점수의 분포 → [(점수, P(점수 ≥ 그 점수))], 점수 내림차순. 정확한 계산."""
    tiers = TIERS[kind]
    per = {}
    for o in POOL:
        d = {}
        for t, p in tiers.items():
            s = round(score_of(amounts(o, t, level), weights), 9)
            d[s] = d.get(s, 0.0) + p
        if set(d) != {0.0}:
            per[o] = d
    n, r = len(POOL), len(per)
    total = math.comb(n, LINES)
    pmf: dict[float, float] = {}
    for j in range(0, min(LINES, r) + 1):
        w = math.comb(n - r, LINES - j) / total  # 쓸모 있는 줄이 정확히 이 j개일 확률(고른 조합마다)
        if not w:
            continue
        for sub in itertools.combinations(per, j):
            dist = {0.0: 1.0}
            for o in sub:
                nxt: dict[float, float] = {}
                for s1, p1 in dist.items():
                    for s2, p2 in per[o].items():
                        k = round(s1 + s2, 9)
                        nxt[k] = nxt.get(k, 0.0) + p1 * p2
                dist = nxt
            for s, p in dist.items():
                pmf[s] = pmf.get(s, 0.0) + w * p
    out, acc = [], 0.0
    for s in sorted(pmf, reverse=True):
        acc += pmf[s]
        out.append((s, min(acc, 1.0)))
    return out


def targets(table: list[tuple[float, float]], now: float) -> list[dict]:
    """QUANTILES마다: 한 번에 그 확률 이상으로 나오는 가장 높은 점수(지금보다 높을 때만)."""
    out = []
    for q in QUANTILES:
        hit = [(s, p) for s, p in table if p >= q]
        if not hit:
            continue
        s, p = hit[0]
        if s > now and not any(o["score"] == s for o in out):
            out.append({"quantile": q, "score": s, "reach_probability": p})
    return out


ZERO_WEAPON_PARTS = ("대검", "태도")  # 제로는 보조무기 칸에도 무기(라피스·라즐리)가 들어간다


def flame_eligible(it) -> bool:
    weapon = it.slot == "무기" or it.part in ZERO_WEAPON_PARTS
    return bool(it.add_option) and not weapon and not it.name.startswith("도전자의") and it.level > 0


__all__ = ["DATA", "TIERS", "POOL", "amounts", "current_lines", "explains", "reach_table", "targets",
           "single_const", "double_const", "flame_eligible", "score_of", "PER_SLOT"]
