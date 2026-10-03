"""잔차 보정: 보이지 않는 출처(패시브 스킬, 버프, 펫·캐시, 링크 등)를 한 스냅샷에서 역산해 고정한다.

출처 분류 (스펙 §5.4, G1 계획의 실측 근거):
- pct(%적용) 블록: 장비 아이템, 세트 효과, 칭호, 링크 스킬(조건 없는 효과), 유니온 프리셋 효과(점령)
- nopct(%미적용) 블록: 하이퍼스탯, 어빌리티, 아케인·어센틱 심볼, 유니온 공격대원 효과
  (유니온 프리셋 효과의 %적용은 2026-10-04 같은 상태 짝으로 실측: INT 오차 −350/+332 → +41/−39.
   하이퍼·공격대원을 %적용으로 바꾸면 오히려 나빠졌다)

주·부스탯   최종 = ⌊(AP + pct 고정) × (1 + (pct% + 잔차%)/100)⌋ + nopct 고정      잔차 = %
공격력/마력 최종 = ⌊(모든 고정 + 잔차 고정) × (1 + 공마%/100)⌋                     잔차 = 고정값
데미지·보공·크뎀·크확  합연산 잔차 / 최종뎀 곱연산 잔차 / 방무 곱연산 잔차
"""
import math
from dataclasses import dataclass, field

from engine.stats.model import StatBlock
from engine.stats.sets import NOT_WORN_SLOTS, SetCatalog, count_sets, set_block
from engine.stats.jobs import job_profile
from engine.stats.snapshot import CharacterSnapshot, Item, Setting

STATS = ("STR", "DEX", "INT", "LUK")
ATTACKS = ("ATK", "MATK")


@dataclass
class Sources:
    pct: StatBlock
    nopct: StatBlock
    excluded: list[str] = field(default_factory=list)

    def total(self) -> StatBlock:
        return self.pct + self.nopct


@dataclass(frozen=True)
class Calibration:
    ap: dict[str, int]
    stat_pct: dict[str, float]    # 주·부스탯 잔차 %
    attack_flat: dict[str, float]  # 공격력/마력 잔차 고정값
    dmg: float
    boss: float
    cd: float
    cr: float
    fd_factor: float
    ied_remain: float              # 잔차 방무의 (1 - x) 곱


@dataclass(frozen=True)
class Predicted:
    stats: dict[str, float]
    atk: float
    matk: float
    dmg: float
    boss: float
    fd: float
    cd: float
    cr: float
    ied: float


def preset_items(snap: CharacterSnapshot, equipment_preset: int) -> dict[str, Item]:
    """프리셋 장비. 프리셋에 비어 있는 슬롯은 현재 착용 템으로 채운다 (Ruling, G1 계획)."""
    worn = snap.equipment_presets[snap.active_equipment_preset]
    items = dict(worn)
    items.update(snap.equipment_presets.get(equipment_preset) or {})
    return items


def sources_for(snap: CharacterSnapshot, setting: Setting, catalog: SetCatalog,
                items: dict[str, Item] | None = None) -> Sources:
    items = preset_items(snap, setting.equipment) if items is None else items
    worn = [it for it in items.values() if it.slot not in NOT_WORN_SLOTS]
    pct = StatBlock()
    for it in worn:
        pct = pct + it.stats
    counts = count_sets(worn, job_profile(snap.character_class).branches, catalog)
    sets, excluded = set_block(counts, snap.level, catalog)
    link = setting.link if setting.link is not None else snap.active_link_preset
    union_state = snap.union_states.get(setting.union or snap.active_union_preset, StatBlock())
    pct = (pct + sets + snap.titles.get(setting.equipment, StatBlock()) + snap.link_presets.get(link, StatBlock())
           + union_state)
    nopct = (snap.hyper_presets.get(setting.hyper, StatBlock()) + snap.ability_presets.get(setting.ability, StatBlock())
             + snap.symbols + snap.union)
    return Sources(pct, nopct, excluded)


def _ied_remain(values: list[float]) -> float:
    r = 1.0
    for x in values:
        r *= 1 - x / 100
    return r


def calibrate(snap: CharacterSnapshot, catalog: SetCatalog) -> Calibration:
    src = sources_for(snap, snap.active_setting, catalog)
    f, p, n = snap.final, src.pct, src.nopct
    stat_pct = {}
    for k in STATS:
        base = f.ap.get(k, 0) + p.flat.get(k, 0)
        known = p.pct.get(k, 0) + n.pct.get(k, 0)
        stat_pct[k] = ((f.stats[k] - n.flat.get(k, 0)) / base - 1) * 100 - known if base > 0 else 0.0
    total = src.total()
    attack_flat = {}
    for k, final in (("ATK", f.atk), ("MATK", f.matk)):
        attack_flat[k] = final / (1 + total.pct.get(k, 0) / 100) - total.flat.get(k, 0)
    remain = _ied_remain(total.ied)
    return Calibration(
        ap=dict(f.ap),
        stat_pct=stat_pct,
        attack_flat=attack_flat,
        dmg=f.dmg - total.dmg,
        boss=f.boss - total.boss,
        cd=f.cd - total.cd,
        cr=f.cr - total.cr,
        fd_factor=(1 + f.fd / 100) / (1 + total.fd / 100),
        ied_remain=(1 - f.ied / 100) / remain if remain > 0 else 1.0,
    )


def predict(cal: Calibration, src: Sources) -> Predicted:
    p, n, total = src.pct, src.nopct, src.total()
    stats = {}
    for k in STATS:
        base = cal.ap.get(k, 0) + p.flat.get(k, 0)
        pct = p.pct.get(k, 0) + n.pct.get(k, 0) + cal.stat_pct[k]
        stats[k] = math.floor(base * (1 + pct / 100) + 1e-9) + n.flat.get(k, 0)
    atk = {k: math.floor((total.flat.get(k, 0) + cal.attack_flat[k]) * (1 + total.pct.get(k, 0) / 100) + 1e-9)
           for k in ATTACKS}
    return Predicted(
        stats=stats,
        atk=atk["ATK"],
        matk=atk["MATK"],
        dmg=total.dmg + cal.dmg,
        boss=total.boss + cal.boss,
        fd=((1 + total.fd / 100) * cal.fd_factor - 1) * 100,
        cd=total.cd + cal.cd,
        cr=total.cr + cal.cr,
        ied=(1 - _ied_remain(total.ied) * cal.ied_remain) * 100,
    )
