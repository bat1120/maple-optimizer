"""평가 지표 (스펙 §5.2). 전투력은 계산하지 않는다."""
from dataclasses import dataclass

from engine.stats.formula import stat_attack_max
from engine.stats.jobs import JobProfile


@dataclass(frozen=True)
class BossProfile:
    name: str
    defense: float  # 방어율 %, 예: 300.0


def stat_attack(pred, job: JobProfile, weapon_part: str) -> float:
    return stat_attack_max(pred, job, weapon_part)


def boss_index(pred, job: JobProfile, weapon_part: str, boss: BossProfile) -> float:
    """보스 실딜 지수 = 스탯공격력 × (1+데미지+보공)/(1+데미지) × (1.35+크뎀) × (1 − 방어율 × (1 − 방무))."""
    sa = stat_attack(pred, job, weapon_part)
    damage = (1 + (pred.dmg + pred.boss) / 100) / (1 + pred.dmg / 100)
    crit = 1.35 + pred.cd / 100
    armor = max(0.0, 1 - boss.defense / 100 * (1 - pred.ied / 100))
    return sa * damage * crit * armor
