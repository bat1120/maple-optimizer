"""HEXA 스탯(2026-10-07): engine/data/hexa_stat.json — 나무위키 기대값표로 확률 모델을 검산하고, 코어별 실딜·조각 기대값을 낸다."""
import pytest

from engine.stats.hexa import main_distribution, reach_cost, stat_block

NAMU_GE = {6: 0.41296, 8: 0.07238, 10: 0.00116}
NAMU_SUNDAY_GE = {6: 0.44891, 7: 0.25768, 8: 0.10358, 9: 0.02456, 10: 0.00247}


def test_main_level_distribution_after_20_grades_matches_namu():
    dist, fragments = main_distribution(0, 0)
    for lv, p in NAMU_GE.items():
        assert sum(q for m, q in dist.items() if m >= lv) == pytest.approx(p, abs=5e-5)
    assert fragments == pytest.approx(321.7, abs=0.1)


def test_sunday_multiplies_probability_from_main_5():
    dist, _ = main_distribution(0, 0, sunday=True)
    for lv, p in NAMU_SUNDAY_GE.items():
        assert sum(q for m, q in dist.items() if m >= lv) == pytest.approx(p, abs=5e-5)


def test_reach_cost_with_resets_matches_namu_expectations():
    # 나무 가정: 초기화 1,000만 메소, 조각 600만 메소 → 초기화 1회 = 조각 10/6개
    assert reach_cost(6, reset_fragments=10 / 6)["fragments"] == pytest.approx(715, rel=0.01)
    assert reach_cost(8, reset_fragments=10 / 6)["fragments"] == pytest.approx(3104, rel=0.01)


def test_stat_block_main_vs_sub_units():
    b = stat_block([("크리티컬 데미지 증가", 7, True), ("마력 증가", 7, False), ("주력 스탯 증가", 6, False)], main_stat="INT")
    assert b["pct"].cd == pytest.approx(3.5) and b["pct"].flat["MATK"] == 35
    assert b["nopct"].flat["INT"] == 600


def test_snapshot_reads_hexa_stat_and_paths_value_upgrades():
    from engine.market.hexa_paths import hexa_stat_paths
    from engine.market.recommend import _Planner
    from engine.stats.evaluate import rank_settings
    from engine.stats.metrics import BossProfile
    from engine.stats.sets import SetCatalog
    from helpers import bundle
    from nexon.convert import snapshot
    snap = snapshot(bundle("레테"))
    assert len(snap.hexa_stat) == 3 and all(c["grade"] == 20 for c in snap.hexa_stat)
    assert snap.hexa_stat[0]["lines"][0] == ("주력 스탯 증가", 7, True)
    cat, boss = SetCatalog.load(), BossProfile("기준", 300.0)
    pl = _Planner(snap, rank_settings(snap, boss, cat)[0][0], boss, cat, None)
    assert hexa_stat_paths(pl, 0) == []  # 조각 시세 없으면 경로 없음
    ps = hexa_stat_paths(pl, 7_000_000)
    core2 = [p for p in ps if p["core"] == 2]  # 메인 크뎀 4레벨 → 5레벨 이상
    assert core2 and core2[0]["target_level"] == 5 and core2[0]["delta_pct"] > 0
    assert all(a["cost"] < b["cost"] for a, b in zip(core2, core2[1:]))  # 목표가 높을수록 비싸다
    # 같은 메인 레벨이면 변화 0: 지금 상태를 그대로 넣은 평가는 기준과 같다
    from engine.stats import hexa as H
    from engine.market.hexa_paths import _block
    from engine.stats.jobs import job_profile
    cur = _block(snap.hexa_stat[0]["lines"], job_profile("레테"))
    assert pl.ev.index(pl.items, H.delta(cur, cur)) == pytest.approx(pl.base)


def test_paths_api_includes_hexa_stat_when_fragment_price_given(tmp_path):
    from fastapi.testclient import TestClient
    from helpers import bundle
    from server.app import create_app
    c = TestClient(create_app(lambda n, d: bundle("레테"), str(tmp_path / "c.sqlite3")))
    assert not [p for p in c.get("/api/character/x/paths").json()["all"] if p["path"] == "HEXA 스탯"]
    r = c.get("/api/character/x/paths?fragment_price=7000000&hexa_sunday=true").json()
    hx = [p for p in r["all"] if p["path"] == "HEXA 스탯"]
    assert hx and all(p["fragments"] > 0 for p in hx) and "HEXA 스탯 확률" in r["events"]["label"]
