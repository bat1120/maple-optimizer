"""매물 검색 추천과 전체 부위 로드맵.

부위마다 윗잠(잠재)·에디를 등급별 단계(에픽 2줄 → 에픽 3줄 → 유니크 2줄 → … → 레전드리 3줄)로 나눠, 각 단계에서
가장 좋은 '흔한' 조합(줄마다 공식 확률 2% 이상인 옵션 중 단독 기여가 가장 큰 것, 2·3번째 줄은 1번째 줄 수치인
'이탈'을 빼고)의 보스 실딜 상승을 계산한다.
추천 카드는 실딜이 처음 오르는 단계, 즉 '지금보다 한 단계 위'다(2026-10-04 실사용 피드백: 고점 한 번에 추천 X).

- 줄 수치·확률: engine/data/cube_tables.json (공식 큐브 확률표, tools/fetch_cube_tables.py). 201레벨부터 수치 +1.
- 쿨감(스킬 재사용 대기시간 -N초) 줄은 실딜 공식으로 값을 매길 수 없어 유지한다. '쿨감 1초 = 주스탯 N%'를 주면 환산해 넣는다.
- 제네시스·데스티니 무기는 경매장에서 살 수 없어 검색 추천에서 빼고, 로드맵에 '큐브' 경로로만 보여 준다.
"""
import copy
import functools
import json
import pathlib
import re
from dataclasses import dataclass, field

from engine.market.cube_value import expected_cost
from engine.options import StatLine, parse_option
from engine.stats.evaluate import Evaluator
from engine.stats.jobs import job_profile
from engine.stats.metrics import BossProfile
from engine.stats.sets import SPECIAL_WEAPON, SetCatalog
from engine.stats.snapshot import CharacterSnapshot, Item, Setting

SKIP_SLOTS = ("훈장", "뱃지", "포켓 아이템", "기계 심장", "예비 특수 반지")
GRADES = ("에픽", "유니크", "레전드리")
KINDS = ("잠재", "에디")
COMMON_MIN_PROB = 2.0  # % — 이보다 드문 줄은 '흔한 조합'에 넣지 않는다
MIN_GAIN = 0.1         # % — 이보다 작은 실딜 상승은 '다음 단계'로 치지 않는다(노이즈 수준 교체 방지)
_COOLDOWN = re.compile(r"^스킬 재사용 대기시간\s*:?\s*-(\d+)초$")
_TABLES = pathlib.Path(__file__).resolve().parents[1] / "data" / "cube_tables.json"


@dataclass
class Recommendation:
    slot: str
    kind: str                         # 잠재 | 에디
    grade: str
    lines_good: int                   # 유효 줄 수
    target: list[str]
    delta_pct: float
    probability: float                # 이 조합이 한 번에 나올 확률(참고, 공식표 줄 확률의 곱)
    min_starforce: int
    current_name: str
    current: list[str] = field(default_factory=list)
    kept: list[str] = field(default_factory=list)
    route: str = "경매장"


@functools.lru_cache(maxsize=1)
def _tables() -> dict:
    return json.loads(_TABLES.read_text(encoding="utf-8"))["tables"]


def _part(slot: str) -> str:
    return slot.rstrip("0123456789")


def line_tables(kind: str, grade: str, slot: str, level: int) -> list[dict[str, float]] | None:
    """[{옵션: 확률%}] × 3. 레벨 201 이상은 '250' 구간, 그 구간이 없는 부위는 '200' 구간."""
    bands = _tables().get(kind, {}).get(grade, {}).get(_part(slot))
    if not bands:
        return None
    return bands["250"] if level > 200 and "250" in bands else bands["200"]


def cooldown_seconds(it: Item) -> int:
    return sum(int(m[1]) for t in it.potentials + it.after if (m := _COOLDOWN.match(t.strip())))


def _rebuild(it: Item, potentials: list[str], after: list[str], additional: list[str], level: int) -> Item:
    stats = copy.deepcopy(it.core)
    excluded = []
    for t in potentials + after:
        parsed = parse_option(t, level)
        if parsed is None:
            excluded.append(t)
            continue
        for line in parsed:
            stats.add(line)
    return Item(slot=it.slot, part=it.part, name=it.name, starforce=it.starforce, stats=stats, excluded=excluded,
                potentials=list(potentials), core=it.core, after=list(after), additional=list(additional),
                level=it.level, potential_grade=it.potential_grade, additional_grade=it.additional_grade)


def _check(it: Item) -> None:
    if it.core is None:
        raise ValueError(f"{it.slot}: 잠재를 바꿀 수 없는 아이템이에요")


def with_potentials(it: Item, lines: list[str], level: int) -> Item:
    """윗잠만 lines로 바꾼 아이템. 에디·소울·기본 옵션은 그대로 둔다."""
    _check(it)
    return _rebuild(it, list(lines), it.after, it.additional, level)


def with_additional(it: Item, lines: list[str], level: int) -> Item:
    """에디만 lines로 바꾼 아이템. 윗잠·소울·기본 옵션은 그대로 둔다."""
    _check(it)
    rest = it.after[len(it.additional):]
    return _rebuild(it, it.potentials, list(lines) + rest, list(lines), level)


SWAP = {"잠재": with_potentials, "에디": with_additional}


def _valued(it: Item, main: str, per_sec: float | None) -> Item:
    """쿨감 환산: 쿨감 초 × N%를 주스탯%로 더한 사본(per_sec가 없거나 쿨감이 없으면 그대로)."""
    sec = cooldown_seconds(it)
    if not per_sec or not sec:
        return it
    out = copy.copy(it)
    out.stats = copy.deepcopy(it.stats)
    out.stats.add(StatLine(main, sec * per_sec, True))
    return out


class _Planner:
    def __init__(self, snap, setting, boss, catalog, cooldown_main_pct):
        job = job_profile(snap.character_class)
        self.snap, self.main, self.per_sec = snap, job.mains[0], cooldown_main_pct
        self.useful = {self.main, job.attack, "BOSS", "IED", "CD", "DMG"}
        self.ev = Evaluator(snap, setting, boss, catalog)
        self.raw = self.ev.base_items()
        self.items = {s: _valued(it, self.main, cooldown_main_pct) for s, it in self.raw.items()}
        self.base = self.ev.index(self.items)

    def delta(self, slot: str, kind: str, lines: list[str]) -> float:
        trial = dict(self.items)
        trial[slot] = _valued(SWAP[kind](self.raw[slot], lines, self.snap.level), self.main, self.per_sec)
        return (self.ev.index(trial) / self.base - 1) * 100

    def is_useful(self, option: str) -> bool:
        parsed = parse_option(option, self.snap.level)
        return bool(parsed) and any(line.key in self.useful for line in parsed)

    def tiers(self, slot: str, kind: str) -> list[dict]:
        it = self.raw[slot]
        kept = [t for t in it.potentials if _COOLDOWN.match(t.strip())] if kind == "잠재" else []
        single: dict[str, float] = {}
        out = []
        for grade in GRADES:
            tables = line_tables(kind, grade, slot, it.level)
            if not tables or any(k not in tables[0] for k in kept):  # 쿨감 -2초는 레전드리 1번째 줄에만 있다
                continue
            for n in (2, 3):
                chosen, prob = [], 1.0
                for pos in range(len(kept), min(3, len(kept) + n)):
                    cands = [o for o, p in tables[pos].items() if p >= COMMON_MIN_PROB and self.is_useful(o)
                             and (pos == 0 or o not in tables[0])]
                    if not cands:
                        break
                    for o in cands:
                        if o not in single:
                            single[o] = self.delta(slot, kind, kept + [o])
                    best = max(cands, key=lambda o: single[o])
                    chosen.append(best)
                    prob *= tables[pos][best] / 100
                if not chosen:
                    continue
                target = kept + chosen
                reach = self.reach(slot, kind, tables, kept, chosen, single)
                cur = it.potential_grade if kind == "잠재" else it.additional_grade
                cost = expected_cost(kind, it.level, cur, grade, reach)
                delta = self.delta(slot, kind, target)
                out.append({"grade": grade, "lines_good": len(chosen), "target": target, "probability": prob,
                            "reach_probability": reach, "delta_pct": delta, "cube_cost": cost,
                            "per_100m": delta / (cost / 1e8) if cost else None})
        return out

    def reach(self, slot, kind, tables, kept, chosen, single) -> float:
        """재설정 한 번에 이 단계 이상(줄별 단독 기여의 합이 목표 조합 이상)이 나올 확률.
        줄 기여를 더해서 비교하는 근사다 — 실딜은 곱연산이라 정확한 값과 조금 다를 수 있다."""
        key0 = ("__kept__", kind)
        if key0 not in single:
            single[key0] = self.delta(slot, kind, list(kept))
        s0 = single[key0]
        factor = 1.0
        for pos, k in enumerate(kept):
            factor *= tables[pos].get(k, 0.0) / 100
        dists = []
        for pos in range(len(kept), 3):
            dist, mass = [], 0.0
            for o, pr in tables[pos].items():
                if self.is_useful(o):
                    if o not in single:
                        single[o] = self.delta(slot, kind, list(kept) + [o])
                    dist.append((single[o] - s0, pr / 100))
                    mass += pr / 100
            dist.append((0.0, max(0.0, 1 - mass)))
            dists.append(dist)
        goal = sum(single[o] - s0 for o in chosen) - 1e-9
        acc = [(0.0, 1.0)]
        for dist in dists:
            merged: dict[float, float] = {}
            for a, pa in acc:
                for b, pb in dist:
                    key = round(a + b, 9)
                    merged[key] = merged.get(key, 0.0) + pa * pb
            acc = list(merged.items())
        return min(1.0, factor * sum(pr for v, pr in acc if v >= goal))

    def slots(self):
        for slot, it in self.raw.items():
            if slot in SKIP_SLOTS or it.core is None or not it.potentials:
                continue
            if not line_tables("잠재", "레전드리", slot, it.level):
                continue
            yield slot, it


def _route(it: Item) -> str:
    return "큐브" if it.name.startswith(SPECIAL_WEAPON) else "경매장"


def roadmap(snap: CharacterSnapshot, setting: Setting, boss: BossProfile, catalog: SetCatalog,
            cooldown_main_pct: float | None = None) -> dict:
    """부위 → {name, starforce, route, current, 잠재/에디: [단계…], next: {종류: 처음 오르는 단계 번호|None}}."""
    pl = _Planner(snap, setting, boss, catalog, cooldown_main_pct)
    out = {}
    for slot, it in pl.slots():
        row = {"name": it.name, "starforce": it.starforce, "route": _route(it),
               "current": {"잠재": list(it.potentials), "에디": list(it.additional)}, "next": {}}
        for kind in KINDS:
            tiers = pl.tiers(slot, kind)
            row[kind] = tiers
            row["next"][kind] = next((i for i, t in enumerate(tiers) if t["delta_pct"] >= MIN_GAIN), None)
        out[slot] = row
    return out


def value_ranking(rm: dict) -> list[dict]:
    """가격 대비 순위: 부위·종류마다 억당 실딜 상승률이 가장 높은 큐브 단계 하나씩, 억당 내림차순.
    실딜이 MIN_GAIN 미만이거나 큐브로 갈 수 없는(지금보다 낮은 등급·잠재 없음) 단계는 뺀다."""
    out = []
    for slot, row in rm.items():
        for kind in KINDS:
            cands = [t for t in row[kind] if t["delta_pct"] >= MIN_GAIN and t["cube_cost"]]
            if cands:
                t = max(cands, key=lambda x: x["per_100m"])
                out.append({"slot": slot, "kind": kind, "name": row["name"], "route": row["route"],
                            "current": row["current"][kind], **t})
    return sorted(out, key=lambda x: x["per_100m"], reverse=True)


def recommend_searches(snap: CharacterSnapshot, setting: Setting, boss: BossProfile, catalog: SetCatalog,
                       top: int = 5, cooldown_main_pct: float | None = None,
                       include_cube_route: bool = False) -> list[Recommendation]:
    """경매장 검색 카드: 부위·종류(잠재/에디)마다 실딜이 처음 오르는 단계를 상승률 내림차순으로."""
    rm = roadmap(snap, setting, boss, catalog, cooldown_main_pct)
    out = []
    for slot, row in rm.items():
        if row["route"] != "경매장" and not include_cube_route:
            continue
        for kind in KINDS:
            i = row["next"][kind]
            if i is None:
                continue
            t = row[kind][i]
            kept = [x for x in t["target"] if _COOLDOWN.match(x.strip())]
            out.append(Recommendation(slot, kind, t["grade"], t["lines_good"], t["target"], t["delta_pct"],
                                      t["probability"], row["starforce"], row["name"], row["current"][kind], kept,
                                      row["route"]))
    out.sort(key=lambda r: r.delta_pct, reverse=True)
    return out[:top]
