"""방어구 세트 조합(2026-11-16 사용자: 카루타·앱솔랩스·아케인셰이드·에테르넬을 어떤 조합으로 맞추는 게 나은지 — 3카5앱처럼).
방어구 7칸마다 지금 템 또는 네 세트 템을 골라, 세트 구성(세트별 개수)이 같은 묶음마다 가장 좋은 배치를 실딜로 잰다."""
import itertools

import pytest

from engine.market.armor_sets import ARMOR_SLOTS, armor_combos, slot_candidates
from engine.market.swaps import _Swapper
from engine.stats.evaluate import rank_settings
from engine.stats.metrics import BossProfile
from engine.stats.sets import SetCatalog
from helpers import bundle
from nexon.convert import snapshot

CAT, BOSS = SetCatalog.load(), BossProfile("기준", 300.0)


@pytest.fixture(scope="module")
def xenon():
    snap = snapshot(bundle("제논"))  # 3카(모상하) + 3앱(신장망) + 에테르넬 어깨, 데스티니 무기
    return snap, rank_settings(snap, BOSS, CAT)[0][0]


def _exact(sw, pieces):
    trial = dict(sw.pl.items)
    trial.update(pieces)
    return (sw.pl.ev.index(trial) / sw.pl.base - 1) * 100


def test_rows_are_exact_and_sorted(xenon):
    snap, setting = xenon
    rows = armor_combos(snap, setting, BOSS, CAT, starforce=18)
    assert rows
    assert [r["delta_pct"] for r in rows] == sorted((r["delta_pct"] for r in rows), reverse=True)
    sw = _Swapper(snap, setting, BOSS, CAT, starforce=18)
    cands = slot_candidates(sw)
    for r in rows[:5]:
        pieces = {s: next(c.item for c in cands[s] if c.name == p["name"]) for s, p in r["pieces"].items()}
        assert abs(_exact(sw, pieces) - r["delta_pct"]) < 1e-9


def test_best_matches_brute_force_on_two_sets(xenon):
    """세트를 둘(카루타·앱솔)로 줄이면 전부 다 재 볼 수 있다 — 묶음별 최선을 정확히 잰 1위가 전수 최댓값과 같아야 한다."""
    snap, setting = xenon
    sets = ("루타비스", "앱솔랩스")
    rows = armor_combos(snap, setting, BOSS, CAT, starforce=18, sets=sets)
    sw = _Swapper(snap, setting, BOSS, CAT, starforce=18)
    cands = slot_candidates(sw, sets)
    best = max(_exact(sw, dict(zip(ARMOR_SLOTS, (c.item for c in combo))))
               for combo in itertools.product(*(cands[s] for s in ARMOR_SLOTS)))
    assert abs(rows[0]["delta_pct"] - best) < 0.02


def test_classic_three_rootabyss_four_absolab_is_listed(xenon):
    """3카4앱(모상하 카루타 + 신장망어 앱솔) 같은 대표 조합이 이름과 함께 나온다."""
    snap, setting = xenon
    rows = armor_combos(snap, setting, BOSS, CAT, starforce=18)
    hit = [r for r in rows if r["label"] == "카루타(도적) 3 · 앱솔(도적) 4"]  # 제논은 도적·해적 템을 다 껴서 계열을 붙인다
    assert hit
    p = hit[0]["pieces"]
    assert all(p[s]["set"] == "카루타" for s in ("모자", "상의", "하의"))
    assert all(p[s]["set"] == "앱솔" for s in ("신발", "장갑", "망토", "어깨장식"))
    # 지금 템을 그대로 둔 칸(kept)은 원래 성, 바꾼 칸은 고른 성(그 템 최대 성 이하)
    assert all(x["starforce"] <= 18 or x["kept"] for x in p.values())
    # 지금 세팅(3카3앱 + 에테르넬 어깨)도 같은 이름 규칙으로 0%에 있다
    now = [r for r in rows if all(x["kept"] for x in r["pieces"].values())]
    assert len(now) == 1 and now[0]["label"] == "카루타(도적) 3 · 앱솔(도적) 3 · 에테르넬(도적) 1" and abs(now[0]["delta_pct"]) < 1e-9


def test_current_items_outside_the_four_sets_are_named_by_their_set():
    """2026-11-16 행복누림공익: 22성 도전자 장비 7칸이 '지금 템 7'로 나왔다 → 세트 이름으로."""
    snap = snapshot(bundle("레테"))  # 보스 프리셋: 22성 도전자 6칸 + 에테르넬 장갑
    setting = rank_settings(snap, BOSS, CAT)[0][0]
    rows = armor_combos(snap, setting, BOSS, CAT, starforce=18)
    now = [r for r in rows if all(x["kept"] for x in r["pieces"].values())]
    assert now and now[0]["label"] == "에테르넬 1 · 도전자의 장비 6"  # 마법사 한 계열이라 (계열) 없음


def test_classics_listed_even_outside_top():
    """대표 조합(3카4앱·3카4아케인·4에테3아케인 …)은 순위 밖이어도 따로 준다 — 계열은 그중 나은 쪽 하나."""
    from engine.market.armor_sets import CLASSICS, classic_rows
    snap = snapshot(bundle("제논"))
    setting = rank_settings(snap, BOSS, CAT)[0][0]
    rows = armor_combos(snap, setting, BOSS, CAT, starforce=18)
    out = classic_rows(rows)
    names = [r["classic"] for r in out]
    assert "3카 4앱" in names and "7에테" in names and len(names) == len(set(names))
    for r in out:
        want = CLASSICS[r["classic"]]
        got = {}
        for p in r["pieces"].values():
            got[p["set"]] = got.get(p["set"], 0) + 1
        assert got == want
        same = [x for x in rows if x is not r and {k: v for k, v in got.items()} == want and
                {p["set"] for p in x["pieces"].values()} == set(want) and
                sum(1 for p in x["pieces"].values()) == 7 and
                all(sum(p["set"] == k for p in x["pieces"].values()) == v for k, v in want.items())]
        assert all(x["delta_pct"] <= r["delta_pct"] for x in same)


def test_route(tmp_path):
    from fastapi.testclient import TestClient
    from server.app import create_app
    c = TestClient(create_app(lambda n, d: bundle("제논"), str(tmp_path / "c.sqlite3")))
    r = c.get("/api/character/x/armor-sets?starforce=22").json()
    assert r["starforce"] == 22 and r["combos"] and {"label", "pieces", "delta_pct", "set_change"} <= set(r["combos"][0])
    assert any(x["classic"] == "3카 4앱" for x in r["classics"])
    assert c.get("/api/character/x/armor-sets?starforce=19").status_code == 422
