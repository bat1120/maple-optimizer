"""목표 세팅 컨설팅(engine/market/consult.py): 세팅 전체를 한 번에 잰 값이 '그 템들을 실제로 다 낀 실딜'과 같은지."""
from helpers import bundle
from engine.market.consult import accessory_builds, consult
from engine.market.swaps import _Swapper
from nexon.convert import snapshot
from server import service


def _setup(name="레테"):
    snap = snapshot(bundle(name))
    b = service.boss(300.0)
    return snap, service.rank_settings(snap, b, service.CATALOG)[0][0], b


def test_accessory_build_is_exactly_the_index_of_wearing_those_items():
    snap, setting, b = _setup()
    sw = _Swapper(snap, setting, b, service.CATALOG, None, 22)
    rows = accessory_builds(sw, service.CATALOG, top=3)
    assert rows and rows[0]["delta_pct"] >= rows[-1]["delta_pct"]
    for r in rows:
        trial = dict(sw.pl.items)
        trial.update(r["_items"])
        assert r["delta_pct"] == (sw.pl.ev.index(trial) / sw.pl.base - 1) * 100
        names = [p["name"] for p in r["pieces"].values()]
        assert len(names) == len(set(names))
        # 이름표의 세트 개수는 그 세팅을 낀 뒤의 실제 개수와 같다
        from engine.stats.sets import count_sets
        after = count_sets(trial.values(), sw.job.branches, service.CATALOG)
        for part in r["label"].split(" · "):
            short, n = part.rsplit(" ", 1)
            full = {"칠흑": "칠흑의 보스 세트", "여명": "여명의 보스 세트", "보스 장신구": "보스 장신구 세트", "광휘": "광휘의 보스 세트"}[short]
            assert after[full] == int(n)


def test_whole_build_beats_the_best_single_slot_swap():
    """한 자리씩 보면 세트가 깨져 손해로 나오는 템도, 통째로 바꾸면 새 세트 효과가 켜진다 — 통째 세팅이 한 자리 최선보다 낮을 수 없다."""
    snap, setting, b = _setup()
    best_single = max((r["same"] for r in service.swaps(snap, 300.0, starforce=22)["swaps"] if r.get("same") is not None), default=0.0)
    top = consult(snap, setting, b, service.CATALOG, stars=(22,))[0]
    assert top["delta_pct"] >= best_single > 0


def test_kept_items_are_raised_to_the_target_star():
    snap, setting, b = _setup()
    top = consult(snap, setting, b, service.CATALOG, stars=(22,))[0]
    for p in top["pieces"]:
        if p["kept"] and p["raise_cost"] is not None:
            assert p["from_star"] < p["starforce"] <= 22
    assert any(p["kept"] for p in top["pieces"]) and top["buy"]


def test_match_cost_is_the_cube_cost_to_reach_current_potential_from_rare():
    """살 템에 지금 수준의 잠재·에디를 큐브로 처음부터 맞추는 평균 비용(2026-11-26 사용자 결정: 위쪽 한계로 같이 보여 준다).
    맞출 줄이 없으면 0, 줄이 좋을수록(같은 등급에서 쓸모 있는 줄이 많을수록) 비싸다."""
    import dataclasses

    from engine.market.consult import match_cost
    snap, setting, b = _setup()
    sw = _Swapper(snap, setting, b, service.CATALOG, None, 22)
    top = consult(snap, setting, b, service.CATALOG, stars=(22,))[0]
    assert all(set(x["match"]) == {"잠재", "에디"} for x in top["buy"])
    assert any((x["match"]["잠재"] or 0) > 0 for x in top["buy"])
    slot = next(x["slot"] for x in top["buy"] if (x["match"]["잠재"] or 0) > 0)
    it = sw.like_current(slot, next(x["name"] for x in top["buy"] if x["slot"] == slot))
    full = match_cost(sw, slot, it)["잠재"]
    useful = [t for t in it.potentials if sw.pl.is_useful(t)]
    fewer = match_cost(sw, slot, dataclasses.replace(it, potentials=useful[:1]))["잠재"]
    none = match_cost(sw, slot, dataclasses.replace(it, potentials=[]))["잠재"]
    assert none == 0.0 and 0 < fewer <= full
