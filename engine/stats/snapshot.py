"""한 시점의 캐릭터: API 최종 스탯 + 프리셋별 출처 StatBlock."""
from dataclasses import dataclass, field

from engine.stats.model import FinalStats, StatBlock


@dataclass
class Item:
    slot: str
    part: str
    name: str
    starforce: int
    stats: StatBlock
    excluded: list[str] = field(default_factory=list)  # 해석 못 한 옵션 원문 (계산 제외)


@dataclass
class CharacterSnapshot:
    character_class: str
    level: int
    date: str | None
    final: FinalStats
    equipment_presets: dict[int, dict[str, Item]]  # 프리셋 번호 → 슬롯 → 아이템
    active_equipment_preset: int
    hyper_presets: dict[int, StatBlock]
    active_hyper_preset: int
    ability_presets: dict[int, StatBlock]
    active_ability_preset: int
    excluded: list[str] = field(default_factory=list)
