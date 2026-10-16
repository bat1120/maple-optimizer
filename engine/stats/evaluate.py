"""세팅·교체 평가: 스냅샷을 활성 세팅으로 보정하고, 다른 세팅·교체를 보스 실딜 지수로 비교한다."""
import itertools

from engine.stats.force import character_force, force_mult
from engine.stats.jobs import job_profile
from engine.stats.metrics import BossProfile, boss_index
from engine.stats.model import StatBlock
from engine.stats.residual import Sources, calibrate, predict, preset_items, sources_for
from engine.stats.sets import SetCatalog
from engine.stats.snapshot import CharacterSnapshot, Item, Setting


def _index(snap: CharacterSnapshot, setting: Setting, items: dict[str, Item], boss: BossProfile,
           catalog: SetCatalog) -> float:
    cal = calibrate(snap, catalog)
    pred = predict(cal, sources_for(snap, setting, catalog, items))
    # 실효 크확(Evaluator.index와 같게, 2026-10-11): 그 세팅의 원래 장비를 100%로 보고 교체로 줄어든 만큼만 뺀다
    # (기준을 지금 착용 세팅으로 하면 크확을 덜 찍은 보스 하이퍼 프리셋이 밀려 실제 보스 세팅이 1등에서 빠졌다)
    base_cr = predict(cal, sources_for(snap, setting, catalog, preset_items(snap, setting.equipment))).cr
    return boss_index(pred, job_profile(snap.character_class), items["무기"].part, boss, min(100.0, 100.0 + pred.cr - base_cr),
                      force_mult(boss, character_force(snap, setting)))


def predict_setting(snap: CharacterSnapshot, setting: Setting, catalog: SetCatalog,
                    items: dict[str, Item] | None = None):
    """세팅(과 선택적 아이템 교체)의 예측 최종 스탯."""
    items = preset_items(snap, setting.equipment) if items is None else items
    return predict(calibrate(snap, catalog), sources_for(snap, setting, catalog, items))


def evaluate_setting(snap: CharacterSnapshot, setting: Setting, boss: BossProfile, catalog: SetCatalog) -> float:
    return _index(snap, setting, preset_items(snap, setting.equipment), boss, catalog)


def swap_item(snap: CharacterSnapshot, setting: Setting, slot: str, new_item: Item, boss: BossProfile,
              catalog: SetCatalog) -> float:
    items = preset_items(snap, setting.equipment)
    items[slot] = new_item
    return _index(snap, setting, items, boss, catalog)


def rank_settings(snap: CharacterSnapshot, boss: BossProfile, catalog: SetCatalog) -> list[tuple[Setting, float]]:
    """장비 × 하이퍼 × 어빌리티 × 유니온 × 링크 프리셋 조합 전부(비어 있는 장비·유니온 프리셋은 제외)를 실딜 지수 내림차순으로."""
    equips = [n for n in (1, 2, 3) if snap.equipment_presets.get(n)]
    unions = sorted(snap.union_states) or [None]
    links = sorted(n for n in snap.link_presets if n) or [None]
    out = [(s, evaluate_setting(snap, s, boss, catalog))
           for s in (Setting(e, h, a, u, l) for e, h, a, u, l in
                     itertools.product(equips, (1, 2, 3), (1, 2, 3), unions, links))]
    return sorted(out, key=lambda x: x[1], reverse=True)


class Evaluator:
    """한 스냅샷·세팅·보스에 대해 보정을 한 번만 하고 여러 아이템 조합을 평가한다 (최적화용)."""

    def __init__(self, snap: CharacterSnapshot, setting: Setting, boss: BossProfile, catalog: SetCatalog):
        self.snap, self.setting, self.boss, self.catalog = snap, setting, boss, catalog
        self._cal = calibrate(snap, catalog)
        self._job = job_profile(snap.character_class)
        self._base_cr = None

    def base_items(self) -> dict[str, Item]:
        return preset_items(self.snap, self.setting.equipment)

    def index(self, items: dict[str, Item], extra: dict | None = None) -> float:
        """extra: 장비 밖 스탯 변화 {'pct': StatBlock, 'nopct': StatBlock}(예: HEXA 스탯 바꾸기)
        와 포스 변화 {'force': {'아케인'|'어센틱': 증가량}}(심볼 레벨업 — 요구 포스가 있는 보스만 실딜이 바뀐다)."""
        src = sources_for(self.snap, self.setting, self.catalog, items)
        if extra:
            src = Sources(src.pct + extra.get("pct", StatBlock()), src.nopct + extra.get("nopct", StatBlock()), src.excluded)
        pred = predict(self._cal, src)
        # 실효 크확: 지금 상태를 딱 100%(여유 없음)로 보고 변경으로 줄어든 만큼만 뺀다 — 크확을 깎는 큐브·교체가 손해로 잡힌다
        if self._base_cr is None:
            self._base_cr = predict(self._cal, sources_for(self.snap, self.setting, self.catalog, self.base_items())).cr
        crit_rate = min(100.0, 100.0 + pred.cr - self._base_cr)
        fm = force_mult(self.boss, character_force(self.snap, self.setting, (extra or {}).get("force")))
        return boss_index(pred, self._job, items["무기"].part, self.boss, crit_rate, fm)
