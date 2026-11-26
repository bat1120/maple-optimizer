"""섞은 목표(engine/market/consult_mix.py): 예산 안에서 칸마다 다른 잠재·에디 목표를 고른 조합."""
from helpers import bundle
from engine.market.consult import consult
from engine.market.consult_mix import _options, mix, pick
from engine.market.recommend import SWAP, _valued
from engine.market.swaps import _Swapper
from nexon.convert import snapshot
from server import service


def _setup():
    snap = snapshot(bundle("레테"))
    b = service.boss(300.0)
    return snap, service.rank_settings(snap, b, service.CATALOG)[0][0], b


def test_mixed_pick_is_exactly_the_index_of_wearing_those_lines():
    snap, setting, b = _setup()
    r = mix(snap, setting, b, service.CATALOG, 22, 3000e8)
    assert r["picks"] and r["cost"] <= 3000e8 and r["delta_pct"] > r["base_delta_pct"]
    assert len({(x["slot"], x["kind"]) for x in r["picks"]}) == len(r["picks"])            # 칸·종류마다 하나
    # 손으로 다시 낀다: 지금 그대로 세팅 + 고른 줄
    same = next(o for o in consult(snap, setting, b, service.CATALOG, stars=(22,)) if o["potential"] == "same")
    sw = _Swapper(snap, setting, b, service.CATALOG, None, 22)
    raw = {p["slot"]: (sw.like_current(p["slot"], p["name"]) if not p["kept"] or p["starforce"] > sw.pl.raw[p["slot"]].starforce
                       else sw.pl.raw[p["slot"]]) for p in same["pieces"]}
    for p in same["pieces"]:                                # 살 템은 잠재·에디 없는 매물이 기준
        if not p["kept"]:
            raw[p["slot"]] = SWAP["에디"](SWAP["잠재"](raw[p["slot"]], [], snap.level), [], snap.level)
    for x in sorted(r["picks"], key=lambda x: x["kind"] != "잠재"):
        raw.setdefault(x["slot"], sw.pl.raw[x["slot"]])
        raw[x["slot"]] = SWAP[x["kind"]](raw[x["slot"]], x["target"], snap.level)
    worn = dict(sw.pl.items)
    worn.update({s: _valued(it, sw.pl.mains, sw.pl.per_sec) for s, it in raw.items()})
    assert (sw.pl.ev.index(worn) / sw.pl.base - 1) * 100 == r["delta_pct"]
    # 기준(살 템 잠재·에디 없음)은 컨설팅 '지금 그대로'(살 템에 지금 수준이 공짜로 붙음)보다 낮고, '지금 템 수준'도 선택지다
    assert r["base_delta_pct"] < r["with_current_delta_pct"] and r["bare_buys"] == len(same["buy"])
    assert any(x["label"] == "지금 템 수준" and x["target"] for x in mix(snap, setting, b, service.CATALOG, 22, 1500e8)["picks"])   # 싼 칸은 지금 수준으로 맞추는 게 효율이 좋다
    # 레테: 섞으면 같은 예산의 한 단계 목표보다 낫다 — 무기류 에디처럼 효율 좋은 칸이 섞인다
    assert {x["group"] for x in r["picks"]} >= {"무기"} and {x["kind"] for x in r["picks"]} == {"잠재", "에디"}


def test_more_budget_never_lowers_the_pick_and_zero_budget_is_the_same_build():
    snap, setting, b = _setup()
    builds = consult(snap, setting, b, service.CATALOG, stars=(22,))
    options = _options(builds)
    sums = []
    for budget in (0, 300e8, 1000e8, 2000e8, 4000e8, 8000e8, 1e14):
        chosen = pick(options, budget)
        assert sum(o["cost"] for o in chosen.values()) <= budget
        sums.append(sum(o["gain_pct"] for o in chosen.values()))
    assert sums[0] == 0 and all(a <= b for a, b in zip(sums, sums[1:]))
    assert pick(options, 1e14) == {k: max(v, key=lambda o: o["gain_pct"]) for k, v in options.items()
                                   if max(o["gain_pct"] for o in v) > 0}                       # 예산이 넉넉하면 칸마다 가장 큰 단계
    zero = mix(snap, setting, b, service.CATALOG, 22, 0)
    assert zero["picks"] == [] and zero["delta_pct"] == zero["base_delta_pct"]


def test_pick_is_optimal_on_a_small_case():
    """작은 경우를 전부 따져 본 답과 같다(칸 A: 3억 +3 / 5억 +4, 칸 B: 4억 +3.5, 예산 8억 → A 3억 + B 4억 = +6.5)."""
    opts = {("A", "잠재"): [{"cost": 3e8, "gain_pct": 3.0}, {"cost": 5e8, "gain_pct": 4.0}],
            ("B", "에디"): [{"cost": 4e8, "gain_pct": 3.5}]}
    got = pick(opts, 8e8)
    assert got == {("A", "잠재"): opts[("A", "잠재")][0], ("B", "에디"): opts[("B", "에디")][0]}
    assert pick(opts, 5e8) == {("A", "잠재"): opts[("A", "잠재")][1]}


def test_best_star_picks_the_star_with_the_highest_exact_damage_within_total():
    """가진 메소 전체(강화 + 큐브)로 성까지 같이 고른다 — 고른 성의 결과는 그 성의 큐브 예산으로 돌린 mix와 같고,
    가진 메소가 늘면 고른 결과의 실딜이 내려가지 않는다."""
    from engine.market.consult_mix import UNIT, best_star
    snap, setting, b = _setup()
    seen = []
    for total in (0, 1000e8, 3000e8, 6000e8, 12000e8):
        r = best_star(snap, setting, b, service.CATALOG, total, prices=50e8)
        assert [x["starforce"] for x in r["stars"]] == [17, 18, 21, 22]
        for x in r["stars"]:
            assert x["cube_budget"] == max(0.0, total - x["raise_cost"] - 50e8) and x["short"] == max(0.0, x["raise_cost"] + 50e8 - total)
            assert (x["delta_pct"] is None) == (x["short"] > 0)
        ok = [x for x in r["stars"] if x["delta_pct"] is not None]
        if not ok:
            assert r["best"] is None and r["mix"] is None
            seen.append(None)
            continue
        top = max(ok, key=lambda x: x["delta_pct"])
        assert r["best"] == top["starforce"] == r["mix"]["starforce"]
        again = mix(snap, setting, b, service.CATALOG, top["starforce"], float(int(top["cube_budget"] // UNIT) * UNIT))
        assert again["delta_pct"] == r["mix"]["delta_pct"] and again["picks"] == r["mix"]["picks"]
        seen.append(r["mix"]["delta_pct"])
    got = [v for v in seen if v is not None]
    assert got == sorted(got) and len(got) >= 3
