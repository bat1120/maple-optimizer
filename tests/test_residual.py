import pytest

from engine.stats.evaluate import evaluate_setting, rank_settings, swap_item
from engine.stats.formula import stat_attack_max
from engine.stats.jobs import job_profile
from engine.stats.metrics import BossProfile, boss_index, stat_attack
from engine.stats.residual import calibrate, predict, sources_for
from engine.stats.sets import SetCatalog
from engine.stats.snapshot import Setting
from helpers import bundle, classes
from nexon.convert import snapshot

CAT = SetCatalog.load()
BOSS = BossProfile("기준", 300.0)
SUPPORTED = [c for c in classes() if c != "데몬어벤져"]


@pytest.mark.parametrize("cls", SUPPORTED)
def test_active_setting_reproduces_api(cls):
    snap = snapshot(bundle(cls))
    pred = predict(calibrate(snap, CAT), sources_for(snap, snap.active_setting, CAT))
    f = snap.final
    for k in ("STR", "DEX", "INT", "LUK"):
        assert abs(pred.stats[k] - f.stats[k]) <= 1, (k, pred.stats[k], f.stats[k])
    assert abs(pred.atk - f.atk) <= 1 and abs(pred.matk - f.matk) <= 1
    for k in ("dmg", "boss", "fd", "cd", "ied"):
        assert getattr(pred, k) == pytest.approx(getattr(f, k), abs=1e-6), k
    weapon = snap.equipment_presets[snap.active_equipment_preset]["무기"].part
    assert stat_attack(pred, job_profile(cls), weapon) == pytest.approx(f.stat_attack_max, rel=1e-3)


def test_boss_index_formula():
    snap = snapshot(bundle("레테"))
    pred = predict(calibrate(snap, CAT), sources_for(snap, snap.active_setting, CAT))
    job = job_profile("레테")
    sa = stat_attack(pred, job, "카르타")
    expected = sa * (1 + (pred.dmg + pred.boss) / 100) / (1 + pred.dmg / 100) * (1.35 + pred.cd / 100) \
        * (1 - 3.0 * (1 - pred.ied / 100))
    assert boss_index(pred, job, "카르타", BOSS) == pytest.approx(expected)
    assert stat_attack(pred, job, "카르타") == stat_attack_max(pred, job, "카르타")


def test_ied_and_boss_move_index_in_right_direction():
    snap = snapshot(bundle("레테"))
    base = evaluate_setting(snap, snap.active_setting, BOSS, CAT)
    weapon = snap.equipment_presets[1]["무기"]
    import copy
    stronger = copy.deepcopy(weapon)
    stronger.stats.boss += 10
    stronger.stats.ied.append(20)
    assert swap_item(snap, snap.active_setting, "무기", stronger, BOSS, CAT) > base


def test_rank_settings_covers_all_presets_sorted():
    snap = snapshot(bundle("레테"))
    ranked = rank_settings(snap, BOSS, CAT)
    assert len(ranked) == 162  # 장비 3 × 하이퍼 3 × 어빌 3 × 유니온 3 × 링크 2
    assert [v for _, v in ranked] == sorted((v for _, v in ranked), reverse=True)
    assert all(isinstance(s, Setting) for s, _ in ranked)


def test_missing_slot_in_preset_falls_back_to_worn_item():
    """나이트로드: 장비 프리셋 1·3에 장갑·신발·망토가 없다 → 현재 착용 템으로 채운다 (Ruling)."""
    snap = snapshot(bundle("나이트로드"))
    src = sources_for(snap, Setting(1, snap.active_hyper_preset, snap.active_ability_preset), CAT)
    active = sources_for(snap, snap.active_setting, CAT)
    assert src.pct.flat.get("LUK", 0) > 0.5 * active.pct.flat.get("LUK", 0)


def test_union_preset_changes_prediction():
    snap = snapshot(bundle("레테"))
    hunt_union = evaluate_setting(snap, Setting(2, 3, 2, 2), BOSS, CAT)
    boss_union = evaluate_setting(snap, Setting(2, 3, 2, 3), BOSS, CAT)
    assert boss_union > hunt_union * 1.2   # 보공 40%·방무 40% 차이
    assert evaluate_setting(snap, Setting(2, 3, 2), BOSS, CAT) == hunt_union  # union 생략 = 현재 적용 프리셋


def test_equivalent_main_stat_gain():
    from engine.stats.metrics import equivalent_main_stat
    from engine.stats.residual import Predicted
    pred = Predicted(stats={"STR": 3540, "DEX": 3397, "INT": 56012, "LUK": 6768}, atk=0, matk=5008, dmg=91, boss=438,
                     fd=186.7, cd=79, cr=93, ied=95.15)
    lete = job_profile("레테")
    assert equivalent_main_stat(pred, lete, 1.01) == pytest.approx(0.01 * (4 * 56012 + 6768) / 4)
    assert equivalent_main_stat(pred, lete, 1.0) == 0
    xenon = job_profile("제논")  # 주스탯 3개, 부스탯 없음 → 주스탯 합 기준
    assert equivalent_main_stat(pred, xenon, 1.02) == pytest.approx(0.02 * (3540 + 3397 + 6768))
