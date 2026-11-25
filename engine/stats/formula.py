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


# 컨버전 스타포스(0차 패시브): 장착 장비의 스타포스 합에 따라 최대 HP. 구간마다 1성당 증가량이 다르고 구간별로 쌓인다(최대 550성, 훈장 제외).
# 표 출처: 나무위키 데몬 어벤져/스킬(2026-11-23 판, 원출처 인벤 2294/450419). (구간 끝 성, 1성당 HP)
# 2026-11-25 실측(HP가 표시 상한 아래인 2명, 55성·63성): '구간별 누적 + HP% 적용'일 때만 스탯창 HP와 0.04~0.4% 안으로 맞았다
# ('총 성수 × 그 구간 값'이나 '%미적용'은 2~7% 어긋남).
DA_CONVERSION = ((10, 35), (35, 60), (60, 80), (90, 100), (125, 120), (150, 135), (175, 138), (200, 140), (225, 142), (250, 144),
                 (270, 146), (290, 148), (310, 150), (320, 152), (330, 154), (340, 156), (350, 158), (360, 160), (370, 162),
                 (380, 164), (390, 166), (435, 168), (550, 170))
DA_SKILL_HP = 600  # 이너 스트렝스(2차 패시브, 영구 최대 HP 600 — 스킬 설명문). 레벨에 따라 다른 패시브(바디 오브 스틸 등)는 잔차로 둔다


def demon_avenger_conversion_hp(stars: int) -> int:
    out, low = 0, 0
    for high, per_star in DA_CONVERSION:
        out += max(0, min(stars, high) - low) * per_star
        low = high
    return out


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
