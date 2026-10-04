"""매물 검색 추천: 부위마다 윗잠을 목표 잠재로 바꿨을 때 보스 실딜이 얼마 오르는지 계산해 순위를 매긴다.

게임 경매장에서 그대로 검색할 수 있게 '부위 · 잠재 조건 · 최소 스타포스'를 함께 돌려준다.
목표 잠재는 레전드리 3줄 기준의 대표 조합이다 — 잠재 등급·레벨별 최대치는 따지지 않는다(검색 조건의 출발점).
"""
import copy
from dataclasses import dataclass, field

from engine.options import parse_option
from engine.stats.evaluate import Evaluator
from engine.stats.jobs import job_profile
from engine.stats.metrics import BossProfile
from engine.stats.sets import SetCatalog
from engine.stats.snapshot import CharacterSnapshot, Item, Setting

# 잠재를 바꿔 살 대상이 아닌 슬롯(잠재가 없거나 경매장 거래 대상이 아님)
SKIP_SLOTS = ("훈장", "뱃지", "포켓 아이템", "기계 심장", "예비 특수 반지")
_ATK_NAME = {"ATK": "공격력", "MATK": "마력"}


@dataclass
class Recommendation:
    slot: str
    target_potentials: list[str]
    delta_pct: float                 # 현재 세팅 대비 보스 실딜 상승률(%)
    min_starforce: int               # 현재 템 스타포스 이상
    current_name: str
    current_potentials: list[str] = field(default_factory=list)


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
                potentials=list(lines), core=it.core, after=it.after)


def target_potentials(slot: str, main: str, attack: str) -> list[str]:
    atk = _ATK_NAME[attack]
    if slot in ("무기", "보조무기"):
        return [f"{atk} +12%", "보스 몬스터 데미지 +40%", f"{atk} +9%"]
    if slot == "엠블렘":
        return [f"{atk} +12%", f"{atk} +9%", "몬스터 방어율 무시 +35%"]
    if slot == "장갑":
        return ["크리티컬 데미지 +8%", "크리티컬 데미지 +8%", f"{main} +9%"]
    return [f"{main} +12%", f"{main} +9%", f"{main} +9%"]


def recommend_searches(snap: CharacterSnapshot, setting: Setting, boss: BossProfile, catalog: SetCatalog,
                       top: int = 5) -> list[Recommendation]:
    """잠재 교체로 실딜이 오르는 부위만, 상승률 내림차순으로."""
    job = job_profile(snap.character_class)
    ev = Evaluator(snap, setting, boss, catalog)
    items = ev.base_items()
    base = ev.index(items)
    out = []
    for slot, it in items.items():
        if slot in SKIP_SLOTS or it.core is None or not it.potentials:
            continue
        target = target_potentials(slot, job.mains[0], job.attack)
        trial = dict(items)
        trial[slot] = with_potentials(it, target, snap.level)
        delta = (ev.index(trial) / base - 1) * 100
        if delta > 0:
            out.append(Recommendation(slot, target, delta, it.starforce, it.name, list(it.potentials)))
    out.sort(key=lambda r: r.delta_pct, reverse=True)
    return out[:top]
