"""HEXA 스탯(2026-10-07): engine/data/hexa_stat.json.

- 강화 1회: 메인 스탯이 p(지금 메인 레벨)로 +1, 아니면 부가 스탯 둘 중 하나 +1. 조각 비용도 지금 메인 레벨로 정해진다
  → 메인 레벨의 변화는 (등급, 메인 레벨)만으로 정확히 계산된다(부가 스탯과 무관)
- 썬데이: 메인 5레벨 이상일 때 p ×1.2
- 수치: 메인은 레벨별 누적 단위(main_units), 부가는 레벨 × 단위. 주력 스탯은 %미적용, 공격력/마력은 %적용 고정값
"""
import functools
import json
import pathlib

from engine.stats.model import StatBlock

_T = json.loads((pathlib.Path(__file__).resolve().parent.parent / "data" / "hexa_stat.json").read_text(encoding="utf-8"))
MAX_G, MAX_L, RESET_MIN = _T["max_grade"], _T["max_level"], _T["reset_min_grade"]


def _p(m: int, sunday: bool) -> float:
    p = _T["main_up"][m]
    return min(1.0, p * _T["sunday_mult"]) if sunday and m >= _T["sunday_from"] else p


def _c(m: int) -> float:
    return _T["fragments"][m]


def main_distribution(grade: int, main: int, sunday: bool = False) -> tuple[dict[int, float], float]:
    """지금 (등급, 메인 레벨)에서 20등급까지 강화했을 때 최종 메인 레벨 분포와 기대 조각."""
    dist, frag = {main: 1.0}, 0.0
    for _ in range(grade, MAX_G):
        nxt: dict[int, float] = {}
        for m, q in dist.items():
            frag += q * _c(m)
            p = _p(m, sunday)
            if p:
                nxt[m + 1] = nxt.get(m + 1, 0.0) + q * p
            nxt[m] = nxt.get(m, 0.0) + q * (1 - p)
        dist = nxt
    return dist, frag


def reach_cost(target: int, reset_fragments: float, sunday: bool = False) -> dict:
    """초기화부터 20등급까지 강화해 메인 target레벨 이상을 얻을 때까지, 10등급 이상에서 최적으로 초기화를 섞은 기대 조각
    (나무위키 기대값표 재현: 6레벨 715·8레벨 3,104개 대비 1% 이내). reset_fragments: 초기화 1회 메소를 조각으로 바꾼 값.
"""
    def solve(v0: float, per_reset: float, per_try) -> float:
        @functools.lru_cache(maxsize=None)
        def v(g: int, m: int) -> float:
            if g >= MAX_G:
                return 0.0 if m >= target else per_reset + v0
            p = _p(m, sunday)
            go = per_try(m) + (p * v(g + 1, m + 1) if p else 0.0) + (1 - p) * v(g + 1, m)
            if m >= target or g < RESET_MIN:
                return go
            return min(go, per_reset + v0)
        return v(0, 0)

    v0 = 0.0
    for _ in range(5000):  # V(0,0) 고정점
        new = solve(v0, reset_fragments, _c)
        if abs(new - v0) < 1e-9:
            break
        v0 = new
    return {"fragments": v0}


_ATTR = {"크리티컬 데미지 증가": "cd", "보스 데미지 증가": "boss", "데미지 증가": "dmg"}


def stat_block(lines: list[tuple[str, int, bool]], main_stat: str, xenon: bool = False) -> dict:
    """[(스탯 이름, 레벨, 메인인가)] → {'pct': %적용 StatBlock, 'nopct': %미적용 StatBlock, 'unknown': [이름]}."""
    pct, nopct, unknown = StatBlock(), StatBlock(), []
    for name, level, is_main in lines:
        if name not in _T["unit"]:
            unknown.append(name)
            continue
        units = _T["main_units"][level] if is_main else level
        v = units * _T["unit"][name]
        if name in _ATTR:
            setattr(pct, _ATTR[name], getattr(pct, _ATTR[name]) + v)
        elif name == "방어율 무시 증가":
            if v:
                pct.ied.append(v)
        elif name in ("공격력 증가", "마력 증가"):
            key = "ATK" if name == "공격력 증가" else "MATK"
            pct.flat[key] = pct.flat.get(key, 0.0) + v
        else:  # 주력 스탯 증가
            keys = ("STR", "DEX", "LUK") if xenon else (main_stat,)
            for k in keys:
                nopct.flat[k] = nopct.flat.get(k, 0.0) + v * (_T["xenon_main_mult"] if xenon else 1)
    return {"pct": pct, "nopct": nopct, "unknown": unknown}


def delta(new: dict, old: dict) -> dict:
    """stat_block 두 개의 차이(new − old). 방무는 곱연산이라 old 쪽은 역수가 되는 값으로 넣는다."""
    out = {}
    for part in ("pct", "nopct"):
        a, b = new[part], old[part]
        d = StatBlock(flat={k: a.flat.get(k, 0.0) - b.flat.get(k, 0.0) for k in set(a.flat) | set(b.flat)},
                      dmg=a.dmg - b.dmg, boss=a.boss - b.boss, cd=a.cd - b.cd, cr=a.cr - b.cr, fd=a.fd - b.fd,
                      ied=list(a.ied) + [100 * (1 - 1 / (1 - x / 100)) for x in b.ied])
        out[part] = d
    return out
