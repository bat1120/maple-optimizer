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


def test_catalog_knows_set_pieces_not_worn_in_fixtures():
    # 나무위키 세트 문서(2026-10-17 확인)의 구성 장비. 픽스처 실측만으로는 빠져 있던 것들
    expect = {
        "에테르넬 메이지슈즈": "에테르넬 세트(마법사)",
        "에테르넬 메이지케이프": "에테르넬 세트(마법사)",
        "에테르넬 아처글러브": "에테르넬 세트(궁수)",
        "앱솔랩스 시프캡": "앱솔랩스 세트(도적)",
        "앱솔랩스 파이렛페도라": "앱솔랩스 세트(해적)",
        "아케인셰이드 메이지글러브": "아케인셰이드 세트(마법사)",
        "아케인셰이드 디키오": "아케인셰이드 세트(마법사)",
        "하이네스 레인져베레": "루타비스 세트(궁수)",
        "하이네스 원더러햇": "루타비스 세트(해적)",
        "지옥의 불꽃": "보스 장신구 세트",
        "오만의 원죄": "광휘의 보스 세트",
        "마이스터 숄더": "마이스터 세트",
        # ILP가 다른 세트로 잘못 붙였던 것(위키 기준으로 고침)
        "카오스 혼테일의 목걸이": "보스 장신구 세트",
        "매커네이터 펜던트": "보스 장신구 세트",
    }
    assert {k: CAT.items.get(k) for k in expect} == expect


def test_catalog_skips_pieces_shared_by_two_branches():
    # 제논 무기(에너지소드·에너지체인)는 도적·해적 두 세트에 걸쳐 있어 이름 하나로 정할 수 없다
    for name in ("앱솔랩스 에너지소드", "아케인셰이드 에너지체인", "파프니르 스플릿엣지"):
        assert name not in CAT.items


def test_lete_buying_eternel_mage_shoes_adds_an_eternel_piece():
    import dataclasses
    s = snapshot(bundle("레테"))
    items = list(s.equipment_presets[s.active_equipment_preset].values())
    branches = job_profile(s.character_class).branches
    before = count_sets(items, branches, CAT)
    swapped = [dataclasses.replace(it, name="에테르넬 메이지슈즈") if it.slot == "신발" else it for it in items]
    after = count_sets(swapped, branches, CAT)
    assert after["에테르넬 세트(마법사)"] == before["에테르넬 세트(마법사)"] + 1
    assert after["도전자의 장비 세트(마법사)"] == before["도전자의 장비 세트(마법사)"] - 1
