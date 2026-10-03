"""G1 판정 테스트 — GOALS.md G1 성공 기준을 그대로 단언한다. 측정값은 goals/results/G1.json."""
import dataclasses
import json
import pathlib

from engine.stats.evaluate import evaluate_setting, rank_settings, swap_item
from engine.stats.jobs import job_profile
from engine.stats.metrics import BossProfile, stat_attack
from engine.stats.residual import calibrate, predict, sources_for
from engine.stats.sets import SetCatalog
from engine.stats.snapshot import Setting
from helpers import bundle, classes, pair_bundle
from nexon.convert import final_stats, snapshot

RESULTS = pathlib.Path(__file__).resolve().parents[2] / "goals" / "results" / "G1.json"
BOSS = BossProfile("기준 보스(방어율 300%)", 300.0)
BOSS_SETTING = Setting(equipment=2, hyper=3, ability=2, union=3, link=2)
CAT = SetCatalog.load()
_measured: dict = {}


def _record(key, value):
    _measured[key] = value
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(json.dumps(_measured, ensure_ascii=False, indent=1), encoding="utf-8")


def _predict_boss_sa(snap):
    cal = calibrate(snap, CAT)
    pred = predict(cal, sources_for(snap, BOSS_SETTING, CAT))
    weapon = snap.equipment_presets[BOSS_SETTING.equipment]["무기"].part
    return stat_attack(pred, job_profile(snap.character_class), weapon)


def test_criterion1_hunt_to_boss_prediction_within_1pct():
    actual = final_stats(pair_bundle("레테_boss")["character/stat"]).stat_attack_max
    hunt = snapshot(bundle("레테"))
    err = abs(_predict_boss_sa(hunt) / actual - 1)

    # 참고 측정: 보스 스냅샷과 같은 버프 상태였던 인게임 사냥 세팅 스크린샷(2026-10-03) 수치로 바꾼 입력
    same_buff = dataclasses.replace(hunt, final=dataclasses.replace(
        hunt.final, stats={**hunt.final.stats, "STR": 3413, "DEX": 3059, "INT": 51896, "LUK": 5960},
        matk=4852, dmg=84.0, fd=186.70, boss=294.0, ied=83.61, cd=58.0))
    err_same_buff = abs(_predict_boss_sa(same_buff) / actual - 1)
    _record("criterion1_err_fixture_pair", err)
    _record("criterion1_err_same_buff_pair_reference", err_same_buff)
    assert err <= 0.01, f"fixture 짝 오차 {err:.4%} (같은 버프 짝 참고값 {err_same_buff:.4%})"


def test_criterion2_self_swap_delta_is_zero_for_45_classes():
    worst = 0.0
    for c in classes():
        if c == "데몬어벤져":
            continue
        snap = snapshot(bundle(c))
        active = Setting(snap.active_equipment_preset, snap.active_hyper_preset, snap.active_ability_preset)
        base = evaluate_setting(snap, active, BOSS, CAT)
        for slot, it in snap.equipment_presets[active.equipment].items():
            delta = abs(swap_item(snap, active, slot, it, BOSS, CAT) - base)
            worst = max(worst, delta)
            assert delta < 1e-9, (c, slot, delta)
    _record("criterion2_worst_abs_delta", worst)


def test_criterion3_best_of_all_presets_is_at_least_actual_boss_setting():
    snap = snapshot(bundle("레테"))
    ranked = rank_settings(snap, BOSS, CAT)
    assert len(ranked) == 162  # 장비·하이퍼·어빌 각 3 × 유니온 3 × 링크 2 (2026-10-04 유니온·링크 추가)
    actual = evaluate_setting(snap, BOSS_SETTING, BOSS, CAT)
    best_setting, best = ranked[0]
    _record("criterion3_best_setting", dataclasses.asdict(best_setting))
    _record("criterion3_best_over_actual_boss_setting", best / actual)
    assert best >= actual
