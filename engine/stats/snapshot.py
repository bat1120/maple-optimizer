"""한 시점의 캐릭터: API 최종 스탯 + 프리셋별 출처 StatBlock."""
from dataclasses import dataclass, field

from engine.stats.model import FinalStats, StatBlock


@dataclass(frozen=True)
class Setting:
    """장비·하이퍼스탯·어빌리티·유니온 프리셋 번호 조합. union=None이면 스냅샷에 적용 중인 유니온 프리셋."""
    equipment: int
    hyper: int
    ability: int
    union: int | None = None
    link: int | None = None  # 링크 스킬 프리셋. None이면 스냅샷에 적용 중인 프리셋


@dataclass
class Item:
    slot: str
    part: str
    name: str
    starforce: int
    stats: StatBlock
    excluded: list[str] = field(default_factory=list)  # 해석 못 한 옵션 원문 (계산 제외)
    # 잠재 교체(검색 추천)용: 윗잠 원문, 윗잠을 뺀 기본 블록, 윗잠 뒤에 더해지는 원문(에디·소울). core가 None이면 교체 불가
    potentials: list[str] = field(default_factory=list)
    core: StatBlock | None = None
    after: list[str] = field(default_factory=list)
    additional: list[str] = field(default_factory=list)  # 에디 원문(after의 앞부분)
    level: int = 0
    potential_grade: str | None = None   # 레어·에픽·유니크·레전드리
    additional_grade: str | None = None  # 착용 레벨(item_base_option.base_equipment_level). 잠재 줄 수치 구간을 정한다
    special_ring_level: int = 0  # 특수 반지 스킬 레벨(컨티뉴어스·리스트레인트 등). 0이면 특수 반지 아님. 효과는 실딜에 없다
    icon: str | None = None      # 넥슨 Open API item_icon 주소(화면 표시용, 저장하지 않는다)
    # 스타포스 강화 경로용(2026-10-07): 지금 스타포스 옵션(STR DEX INT LUK ATK MATK), 순수+주문서 공격력, 놀장 사용 여부
    sf_option: dict[str, float] = field(default_factory=dict)
    scroll_attack: dict[str, float] = field(default_factory=dict)
    amazing: bool = False
    add_option: dict[str, float] = field(default_factory=dict)  # 추옵 원본(넥슨 API item_add_option, 0 아닌 값만)


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
    union_states: dict[int, StatBlock] = field(default_factory=dict)  # 유니온 프리셋별 효과 (union_state_stat_preset)
    active_union_preset: int = 0
    link_presets: dict[int, StatBlock] = field(default_factory=dict)  # 링크 스킬 프리셋 (조건 없는 효과만)
    active_link_preset: int = 0
    profile: dict = field(default_factory=dict)  # 화면 표시용: 이름·월드·길드·캐릭터 이미지(넥슨 basic 그대로)
    # HEXA 스탯 코어(2026-10-07): [{"core": 1|2|3, "grade": n, "lines": [(이름, 레벨, 메인인가), …]}] — 적용 중인 것
    hexa_stat: list = field(default_factory=list)
    hexa_cores: list = field(default_factory=list)  # HEXA 코어 레벨: [{"name", "level", "type", "skills"}]
    hexa_skills: dict = field(default_factory=dict)  # 6차 스킬 이름 → {level, effect, next, description}
    own_shares: dict = field(default_factory=dict)   # 본인 최신 연무장 기록의 스킬별 딜 지분(%) — 없으면 비어 있다

    @property
    def active_setting(self) -> Setting:
        return Setting(self.active_equipment_preset, self.active_hyper_preset, self.active_ability_preset,
                       self.active_union_preset or None, self.active_link_preset or None)
