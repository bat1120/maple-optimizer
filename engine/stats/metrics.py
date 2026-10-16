"""평가 지표 (스펙 §5.2). 전투력은 계산하지 않는다."""
from dataclasses import dataclass

from engine.stats.formula import stat_attack_max
from engine.stats.jobs import JobProfile


@dataclass(frozen=True)
class BossProfile:
    """보스. defense만 있으면 예전처럼 방어율만 본다. 보스 목록(engine/data/bosses.json)에서 고르면 요구 포스도 있다."""
    name: str
    defense: float  # 방어율 %, 예: 300.0
    id: str | None = None
    difficulty: str | None = None
    arcane: int | None = None      # 요구 아케인포스(주는 피해 100% 기준)
    authentic: int | None = None   # 요구 어센틱포스
    symbol_region: str | None = None  # 이 지역 어센틱심볼 11레벨 '데미지 +20%' 대상(종류 미확인이라 실딜 미반영)


def stat_attack(pred, job: JobProfile, weapon_part: str) -> float:
    return stat_attack_max(pred, job, weapon_part)


def boss_index(pred, job: JobProfile, weapon_part: str, boss: BossProfile, crit_rate: float | None = None,
               force_mult: float = 1.0) -> float:
    """보스 실딜 지수 = 스탯공격력 × (1+데미지+보공)/(1+데미지) × (1 + 크확×(0.35+크뎀)) × (1 − 방어율 × (1 − 방무)) × 포스 보정.
    force_mult: 요구 포스 대비 주는 피해 비율(engine/stats/force.py, 요구 포스가 없는 보스는 1).
    crit_rate: 실효 크확(%). 없으면 100%로 본다 — 넥슨 스탯창 크확은 직업 스킬 크확이 빠져 있어(렌 69% 등) 그대로 쓰지 않는다.
    0~100%로 잘라 100% 이상이면 예전 식(1.35+크뎀)과 같다(2026-10-09: 로드맵이 크확 줄을 빼 '크확 100%미만')."""
    sa = stat_attack(pred, job, weapon_part)
    damage = (1 + (pred.dmg + pred.boss) / 100) / (1 + pred.dmg / 100)
    p = min(1.0, max(0.0, (100.0 if crit_rate is None else crit_rate) / 100))
    crit = 1 + p * (0.35 + pred.cd / 100)
    armor = max(0.0, 1 - boss.defense / 100 * (1 - pred.ied / 100))
    return sa * damage * crit * armor * force_mult


def equivalent_main_stat(pred, job: JobProfile, ratio: float) -> float:
    """환산 주스탯 상승량: 실딜이 ratio배가 될 때 같은 효과를 내는 최종 주스탯 증가량 (스펙 §5.3).

    스탯공격력 ∝ (주스탯×4 + 부스탯) 이므로 ΔM = (ratio − 1) × (4×Σ주스탯 + Σ부스탯) / 4.
    주스탯이 여럿(제논)이면 주스탯 합 기준. 사이트마다 정의가 다르므로 화면에 이 정의를 적는다.
    """
    base = 4 * sum(pred.stats[m] for m in job.mains) + sum(pred.stats[s] for s in job.subs)
    return (ratio - 1) * base / 4
