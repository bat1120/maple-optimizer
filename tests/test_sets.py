from engine.stats.jobs import job_profile
from engine.stats.sets import EXTERNAL_SETS, SetCatalog, count_sets, set_block
from helpers import bundle, classes, pair_bundle
from nexon.convert import snapshot

CAT = SetCatalog.load()


def _api_counts(b):
    return {x["set_name"]: x["total_set_count"] for x in b["character/set-effect"]["set_effect"]}


def _engine_counts(b):
    s = snapshot(b)
    items = s.equipment_presets[s.active_equipment_preset].values()
    return count_sets(items, job_profile(s.character_class).branches, CAT)


def test_lete_hunt_and_boss_counts_match_api_exactly():
    for b in (bundle("레테"), pair_bundle("레테_boss")):
        api = _api_counts(b)
        eng = _engine_counts(b)
        for name, n in api.items():
            if name.startswith(EXTERNAL_SETS):
                continue
            assert eng.get(name, 0) == n, (name, n, eng.get(name, 0))


def test_equipment_set_counts_match_api_for_95pct_of_pairs():
    total = match = 0
    for c in classes():
        if c == "데몬어벤져":
            continue
        b = bundle(c)
        eng = _engine_counts(b)
        for name, n in _api_counts(b).items():
            if name.startswith(EXTERNAL_SETS):
                continue
            total += 1
            match += eng.get(name, 0) == n
    assert match / total >= 0.95, (match, total)


def test_set_block_sums_active_tiers():
    blk, excluded = set_block({"여명의 보스 세트": 4}, 287, CAT)
    # 2·3·4세트 단계 합: 올스탯 30, 공마 30, 보공 10, 방무 10
    assert blk.flat["INT"] == 30 and blk.flat["MATK"] == 30 and blk.boss == 10 and blk.ied == [10]
    assert excluded == []


def test_unknown_set_is_reported_not_guessed():
    blk, excluded = set_block({"처음보는 세트": 3}, 287, CAT)
    assert blk.flat == {} and excluded == ["처음보는 세트"]
