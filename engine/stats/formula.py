"""스탯공격력 공식 (스펙 §5.1, 실측 검증됨).

최대 스탯공격력 = (주스탯×4 + 부스탯)/100 × 공(마) × (1+데미지%) × (1+최종 데미지%) × 무기 상수
"""
import math

from engine.stats.jobs import DEMON_AVENGER, JobProfile
from engine.stats.model import FinalStats
from engine.stats.weapons import weapon_constant


# 데몬어벤져(2026-11-25 사용자 제안으로 지원):
#   스탯 반영치 = ⌊순수 HP ÷ 3.5⌋ + 0.8 × ⌊(총 HP − 순수 HP) ÷ 3.5⌋ + STR        (나무위키 메이플스토리/스탯)
#   순수 HP = AP로 올린 HP(API 'AP 배분 HP' = 210 + AP×15) + 레벨×15 + 344     (AP를 전부 HP에 주면 90×레벨 + 554 — 같은 문서의 값)
# 실측: HP가 표시 상한(500,000) 아래인 2명 — 250레벨(HP 27,937 · AP 배분 10,785 · STR 1,080 · 공격력 281 · 데미지 25% → 37,968),
#       260레벨(HP 294,486 · 19,710 · 935 · 392 · 66% · 최종뎀 15% → 677,225) 모두 스탯창 최대 스탯공격력과 1 단위까지 같다.
#       내림 위치·상수(335~360)·무기 상수를 바꿔 보면 둘 다 맞는 조합은 이것뿐이었다.
DA_HP_PER_LEVEL, DA_HP_BASE, HP_DISPLAY_CAP = 15, 344, 500_000


def demon_avenger_pure_hp(ap_hp: float, level: int) -> float:
    return ap_hp + DA_HP_PER_LEVEL * level + DA_HP_BASE


def _pure_hp(x) -> float:
    """FinalStats는 ap["HP"]에(변환 때 순수 HP로 바꿔 둔다), 예측값(Predicted)은 pure_hp에."""
    return x.ap["HP"] if hasattr(x, "ap") else x.pure_hp


def demon_avenger_hp(stat_attack: float, pure_hp: float, strength: float, attack: float, dmg: float, fd: float, weapon_part: str) -> float:
    """스탯창 HP가 표시 상한에 걸렸을 때: 최대 스탯공격력에서 총 HP를 되짚는다(상한에 안 걸리는 값이라 가능).
    ⌊추가 HP ÷ 3.5⌋까지만 알 수 있어 그 구간의 가운데를 준다 — 오차는 HP ±1.75(스탯공격력에는 0)."""
    value = stat_attack * 100 / (attack * (1 + dmg / 100) * (1 + fd / 100) * weapon_constant(weapon_part, DEMON_AVENGER))
    units = round((value - math.floor(pure_hp / 3.5) - strength) / 0.8)
    return pure_hp + units * 3.5 + 1.75


def stat_value(final: FinalStats, job: JobProfile) -> float:
    if job.name == DEMON_AVENGER:
        pure = _pure_hp(final)
        return (math.floor(pure / 3.5) + 0.8 * math.floor((final.stats["HP"] - pure) / 3.5) + final.stats["STR"]) / 100
    return (4 * sum(final.stats[m] for m in job.mains) + sum(final.stats[s] for s in job.subs)) / 100


def stat_attack_max(final: FinalStats, job: JobProfile, weapon_part: str) -> float:
    attack = final.matk if job.attack == "MATK" else final.atk
    return (stat_value(final, job) * attack * (1 + final.dmg / 100) * (1 + final.fd / 100)
            * weapon_constant(weapon_part, job.name))
