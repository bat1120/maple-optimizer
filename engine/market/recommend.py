"""매물 검색 추천: 부위마다 '지금보다 한 단계 위' 잠재를 찾고, 그때의 보스 실딜 상승을 계산해 순위를 매긴다.

한 번에 고점(레전 3줄 이탈)으로 건너뛰지 않는다. 부위별 잠재 사다리를 낮은 단계부터 올라가며 실딜이 처음으로
오르는 단계를 추천한다(2026-10-04 실사용 피드백). 게임 경매장에서 그대로 검색할 수 있게 부위·잠재·최소 스타포스를 돌려준다.

줄 수치(Ruling, 근거 파일):
- 무기·보조무기·엠블렘 공/마%: 레전드리 12/9, 보공 40/35/30, 방무 40/35/30 — engine/data/cube_black.json(200제 무기 공식 확률표)
- 주스탯%: 착용 레벨 250 이상 레전 13/10·유니크 10/7, 그 밖 레전 12/9·유니크 9/6 — 레테 장비 실측(250제 장갑 13·10, 160제 신발 9·6)
- 쿨감(스킬 재사용 대기시간 -N초) 줄은 실딜 공식으로 값을 매길 수 없어 바꾸지 않고 유지한다.
  사용자가 '쿨감 1초 = 주스탯 N%'를 주면 그 환산으로 실딜에 넣는다.
"""
import copy
import re
from dataclasses import dataclass, field

from engine.options import StatLine, parse_option
from engine.stats.evaluate import Evaluator
from engine.stats.jobs import job_profile
from engine.stats.metrics import BossProfile
from engine.stats.sets import SetCatalog
from engine.stats.snapshot import CharacterSnapshot, Item, Setting

# 잠재를 바꿔 살 대상이 아닌 슬롯(잠재가 없거나 경매장 거래 대상이 아님)
SKIP_SLOTS = ("훈장", "뱃지", "포켓 아이템", "기계 심장", "예비 특수 반지")
_ATK_NAME = {"ATK": "공격력", "MATK": "마력"}
_COOLDOWN = re.compile(r"^스킬 재사용 대기시간\s*:?\s*-(\d+)초$")
_EPS = 1e-9


@dataclass
class Recommendation:
    slot: str
    target_potentials: list[str]
    delta_pct: float                 # 현재 세팅 대비 보스 실딜 상승률(%)
    min_starforce: int               # 현재 템 스타포스 이상
    current_name: str
    current_potentials: list[str] = field(default_factory=list)
    step: int = 1                    # 사다리 몇 단계인가(1이 가장 흔한 잠재)
    steps: int = 1
    kept: list[str] = field(default_factory=list)  # 유지한 줄(쿨감)


def cooldown_seconds(it: Item) -> int:
    return sum(int(m[1]) for t in it.potentials + it.after if (m := _COOLDOWN.match(t.strip())))


def with_potentials(it: Item, lines: list[str], level: int) -> Item:
    """윗잠만 lines로 바꾼 아이템. 에디·소울·기본 옵션은 그대로 둔다."""
    if it.core is None:
        raise ValueError(f"{it.slot}: 잠재를 바꿀 수 없는 아이템이에요")
    stats = copy.deepcopy(it.core)
    excluded = [t for t in it.excluded if t not in it.potentials]
    for t in list(lines) + it.after:
        parsed = parse_option(t, level)
        if parsed is None:
            if t in lines:
                excluded.append(t)
            continue
        for line in parsed:
            stats.add(line)
    return Item(slot=it.slot, part=it.part, name=it.name, starforce=it.starforce, stats=stats, excluded=excluded,
                potentials=list(lines), core=it.core, after=it.after, level=it.level)


def ladder(slot: str, main: str, attack: str, level: int) -> list[list[list[str]]]:
    """부위별 잠재 단계. 각 단계는 같은 정도로 흔한 3줄(또는 2줄) 조합 목록이다."""
    a = _ATK_NAME[attack]
    A12, A9 = f"{a} +12%", f"{a} +9%"
    if slot in ("무기", "보조무기"):
        return [[[A12, A9]],
                [[A12, A9, A9], [A12, "보스 몬스터 데미지 +30%", A9], [A12, A9, "몬스터 방어율 무시 +30%"]],
                [[A12, "보스 몬스터 데미지 +35%", A9], [A12, "보스 몬스터 데미지 +30%", "보스 몬스터 데미지 +30%"]],
                [[A12, "보스 몬스터 데미지 +40%", A9], [A12, A12, A9]]]
    if slot == "엠블렘":
        return [[[A12, A9]],
                [[A12, A9, A9], [A12, A9, "몬스터 방어율 무시 +30%"]],
                [[A12, "몬스터 방어율 무시 +35%", A9]],
                [[A12, A12, A9], [A12, "몬스터 방어율 무시 +40%", A9]]]
    hi = level >= 250
    lp, ln, up, un = (13, 10, 10, 7) if hi else (12, 9, 9, 6)
    M = lambda v: f"{main} +{v}%"  # noqa: E731
    if slot == "장갑":
        return [[["크리티컬 데미지 +8%", M(lp)]],
                [["크리티컬 데미지 +8%", "크리티컬 데미지 +8%"]],
                [["크리티컬 데미지 +8%", "크리티컬 데미지 +8%", M(ln)]]]
    return [[[M(up), M(un)]],
            [[M(up), M(un), M(un)], [M(lp), M(ln)]],
            [[M(lp), M(ln), M(ln)]],
            [[M(lp), M(lp), M(ln)]]]


def _valued(it: Item, main: str, per_sec: float | None) -> Item:
    """쿨감 환산: 쿨감 초 × N%를 주스탯%로 더한 사본(per_sec가 없거나 쿨감이 없으면 그대로)."""
    sec = cooldown_seconds(it)
    if not per_sec or not sec:
        return it
    out = copy.copy(it)
    out.stats = copy.deepcopy(it.stats)
    out.stats.add(StatLine(main, sec * per_sec, True))
    return out


def recommend_searches(snap: CharacterSnapshot, setting: Setting, boss: BossProfile, catalog: SetCatalog,
                       top: int = 5, cooldown_main_pct: float | None = None) -> list[Recommendation]:
    """부위마다 실딜이 처음 오르는 사다리 단계를 골라, 상승률 내림차순으로."""
    job = job_profile(snap.character_class)
    main = job.mains[0]
    ev = Evaluator(snap, setting, boss, catalog)
    items = {s: _valued(it, main, cooldown_main_pct) for s, it in ev.base_items().items()}
    raw = ev.base_items()
    base = ev.index(items)
    out = []
    for slot, it in raw.items():
        if slot in SKIP_SLOTS or it.core is None or not it.potentials:
            continue
        kept = [t for t in it.potentials if _COOLDOWN.match(t.strip())]
        tiers = ladder(slot, main, job.attack, it.level)
        for n, tier in enumerate(tiers, 1):
            best = None
            for option in tier:
                target = kept + option[:3 - len(kept)]
                trial = dict(items)
                trial[slot] = _valued(with_potentials(it, target, snap.level), main, cooldown_main_pct)
                delta = (ev.index(trial) / base - 1) * 100
                if best is None or delta > best[1]:
                    best = (target, delta)
            if best and best[1] > _EPS:
                out.append(Recommendation(slot, best[0], best[1], it.starforce, it.name, list(it.potentials),
                                          step=n, steps=len(tiers), kept=kept))
                break
    out.sort(key=lambda r: r.delta_pct, reverse=True)
    return out[:top]
