"""세팅·교체 평가: 스냅샷을 활성 세팅으로 보정하고, 다른 세팅·교체를 보스 실딜 지수로 비교한다."""
import itertools

from engine.stats.jobs import job_profile
from engine.stats.metrics import BossProfile, boss_index
from engine.stats.residual import calibrate, predict, preset_items, sources_for
from engine.stats.sets import SetCatalog
from engine.stats.snapshot import CharacterSnapshot, Item, Setting


def _index(snap: CharacterSnapshot, setting: Setting, items: dict[str, Item], boss: BossProfile,
           catalog: SetCatalog) -> float:
    pred = predict(calibrate(snap, catalog), sources_for(snap, setting, catalog, items))
    return boss_index(pred, job_profile(snap.character_class), items["무기"].part, boss)


def evaluate_setting(snap: CharacterSnapshot, setting: Setting, boss: BossProfile, catalog: SetCatalog) -> float:
    return _index(snap, setting, preset_items(snap, setting.equipment), boss, catalog)


def swap_item(snap: CharacterSnapshot, setting: Setting, slot: str, new_item: Item, boss: BossProfile,
              catalog: SetCatalog) -> float:
    items = preset_items(snap, setting.equipment)
    items[slot] = new_item
    return _index(snap, setting, items, boss, catalog)


def rank_settings(snap: CharacterSnapshot, boss: BossProfile, catalog: SetCatalog) -> list[tuple[Setting, float]]:
    """장비 × 하이퍼 × 어빌리티 프리셋 조합 전부(비어 있는 장비 프리셋은 제외)를 실딜 지수 내림차순으로."""
    equips = [n for n in (1, 2, 3) if snap.equipment_presets.get(n)]
    out = [(s, evaluate_setting(snap, s, boss, catalog))
           for s in (Setting(e, h, a) for e, h, a in itertools.product(equips, (1, 2, 3), (1, 2, 3)))]
    return sorted(out, key=lambda x: x[1], reverse=True)
