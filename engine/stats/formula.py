"""스탯공격력 공식 (스펙 §5.1, 실측 검증됨).

최대 스탯공격력 = (주스탯×4 + 부스탯)/100 × 공(마) × (1+데미지%) × (1+최종 데미지%) × 무기 상수
"""
from engine.stats.jobs import JobProfile
from engine.stats.model import FinalStats
from engine.stats.weapons import weapon_constant


def stat_value(final: FinalStats, job: JobProfile) -> float:
    return (4 * sum(final.stats[m] for m in job.mains) + sum(final.stats[s] for s in job.subs)) / 100


def stat_attack_max(final: FinalStats, job: JobProfile, weapon_part: str) -> float:
    attack = final.matk if job.attack == "MATK" else final.atk
    return (stat_value(final, job) * attack * (1 + final.dmg / 100) * (1 + final.fd / 100)
            * weapon_constant(weapon_part))
