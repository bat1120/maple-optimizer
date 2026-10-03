"""한 시점의 캐릭터: API 최종 스탯 + 프리셋별 출처 StatBlock."""
from dataclasses import dataclass, field

from engine.stats.model import FinalStats, StatBlock


@dataclass(frozen=True)
class Setting:
    """장비·하이퍼스탯·어빌리티 프리셋 번호 조합."""
    equipment: int
    hyper: int
    ability: int


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
    titles: dict[int, StatBlock] = field(default_factory=dict)  # 장비 프리셋 번호 → 칭호
    symbols: StatBlock = field(default_factory=StatBlock)        # 아케인·어센틱 심볼 (%미적용)
    union: StatBlock = field(default_factory=StatBlock)          # 유니온 공격대원 효과 (스탯은 %미적용)

    @property
    def active_setting(self) -> Setting:
        return Setting(self.active_equipment_preset, self.active_hyper_preset, self.active_ability_preset)
