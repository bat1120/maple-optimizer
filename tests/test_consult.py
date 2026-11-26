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


def test_potential_goal_is_exactly_the_index_of_wearing_those_lines():
    """잠재 목표(2026-11-26 사용자: 17·18·21·22성 템들의 잠재는 어떻게 되는가). 목표 잠재를 낀 실딜 = 그 줄을 실제로 낀 세팅의 실딜."""
    from engine.market.consult import _goals
    from engine.market.recommend import SWAP, _valued, line_tables
    snap, setting, b = _setup()
    same, two, three = consult(snap, setting, b, service.CATALOG, stars=(22,))
    assert [o["potential"] for o in (same, two, three)] == ["same", "legend2", "legend3"]
    assert [p["name"] for p in same["pieces"]] == [p["name"] for p in three["pieces"]]     # 템 구성은 같고 잠재만 다르다
    assert same["cube"] == [] and all(x["target"] is None for x in same["buy"])
    # 같은 세팅을 손으로 다시 낀다: 지금 그대로 세팅에 목표 줄을 얹은 것
    sw = _Swapper(snap, setting, b, service.CATALOG, None, 22)
    raws = {p["slot"]: (sw.like_current(p["slot"], p["name"]) if not p["kept"] or p["starforce"] > sw.pl.raw[p["slot"]].starforce
                        else sw.pl.raw[p["slot"]]) for p in same["pieces"]}
    worn = dict(sw.pl.items)
    worn.update({s: _valued(it, sw.pl.mains, sw.pl.per_sec) for s, it in raws.items()})
    assert (sw.pl.ev.index(worn) / sw.pl.base - 1) * 100 == same["delta_pct"]
    targets = {x["slot"]: x["target"] for x in three["buy"] if x["target"]} | {c["slot"]: c["target"] for c in three["cube"]}
    assert len(targets) >= 5
    for s, lines in targets.items():
        table = line_tables("잠재", "레전드리", s, raws[s].level)
        assert len(lines) == 3 and all(any(t in pos for pos in table) for t in lines), (s, lines)   # 공식 확률표에 있는 줄만
        worn[s] = _valued(SWAP["잠재"](raws[s], lines, snap.level), sw.pl.mains, sw.pl.per_sec)
    assert (sw.pl.ev.index(worn) / sw.pl.base - 1) * 100 == three["delta_pct"]
    pieces = {p["slot"]: p for p in same["pieces"]}
    assert set(_goals(sw, {**sw.pl.items, **{s: _valued(it, sw.pl.mains, sw.pl.per_sec) for s, it in raws.items()}}, raws,
                      list(raws), pieces, 3)) == set(targets)


def test_additional_goal_is_exactly_the_index_of_wearing_those_lines():
    """에디 목표(2026-11-26): 잠재 목표 위에 에디 줄까지 얹은 실딜 = 그 줄들을 실제로 낀 세팅의 실딜. 등급이 높을수록 실딜·비용이 내려가지 않는다."""
    from engine.market.recommend import SWAP, _valued, line_tables
    snap, setting, b = _setup()
    same, _, three = consult(snap, setting, b, service.CATALOG, stars=(22,))
    sw = _Swapper(snap, setting, b, service.CATALOG, None, 22)
    raws = {p["slot"]: (sw.like_current(p["slot"], p["name"]) if not p["kept"] or p["starforce"] > sw.pl.raw[p["slot"]].starforce
                        else sw.pl.raw[p["slot"]]) for p in same["pieces"]}
    pots = {x["slot"]: x["target"] for x in three["buy"] if x["target"]} | {c["slot"]: c["target"] for c in three["cube"]}
    for build, pot in ((same, {}), (three, pots)):
        opts = build["additional_options"]
        assert [a["key"] for a in opts] == ["epic2", "unique2", "legend2"]
        assert build["delta_pct"] < opts[0]["delta_pct"] < opts[1]["delta_pct"] < opts[2]["delta_pct"]
        cost = [sum(x["cost"] for x in a["slots"]) for a in opts]
        assert 0 < cost[0] < cost[1] < cost[2]
        for a, grade in zip(opts, ("에픽", "유니크", "레전드리")):
            worn = dict(sw.pl.items)
            for s, it in raws.items():
                if s in pot:
                    it = SWAP["잠재"](it, pot[s], snap.level)
                x = next((x for x in a["slots"] if x["slot"] == s), None)
                if x:
                    table = line_tables("에디", grade, s, it.level)
                    assert len(x["target"]) == 2 and all(any(t in pos for pos in table) for t in x["target"]), (s, x["target"])
                    assert x["gain_pct"] > 0 and x["per_100m"] == x["gain_pct"] / (x["cost"] / 1e8)
                    it = SWAP["에디"](it, x["target"], snap.level)
                worn[s] = _valued(it, sw.pl.mains, sw.pl.per_sec)
            assert (sw.pl.ev.index(worn) / sw.pl.base - 1) * 100 == a["delta_pct"]
            assert a["armor_delta_pct"] >= build["armor"]["delta_pct"] and a["accessory_delta_pct"] >= build["accessory"]["delta_pct"]
    # 에디 목표의 칸·줄·비용은 잠재 목표와 무관하다(줄은 '잠재 지금 그대로'에서 고른다)
    strip = lambda a: [(x["slot"], x["target"], x["cost"]) for x in a["slots"]]  # noqa: E731
    assert [strip(a) for a in same["additional_options"]] == [strip(a) for a in three["additional_options"]]


def test_higher_potential_goal_never_lowers_damage_or_cost():
    """목표가 높을수록 실딜도 큐브 비용도 내려가지 않는다. 지금 잠재가 이미 목표 이상인 칸은 건드리지 않는다(실딜이 내려가면 안 된다)."""
    snap, setting, b = _setup()
    builds = consult(snap, setting, b, service.CATALOG)
    assert [(o["starforce"], o["potential"]) for o in builds] == [(s, k) for s in (17, 18, 21, 22) for k in ("same", "legend2", "legend3")]
    cube = lambda o: sum(x["match"]["잠재"] or 0 for x in o["buy"]) + sum(c["cost"] or 0 for c in o["cube"])  # noqa: E731
    for i in range(0, len(builds), 3):
        same, two, three = builds[i:i + 3]
        assert same["delta_pct"] < two["delta_pct"] < three["delta_pct"]
        assert cube(same) < cube(two) < cube(three)
        assert same["raise_cost"] == two["raise_cost"] == three["raise_cost"] and same["set_change"] == three["set_change"]
        for o in (two, three):
            assert o["armor"]["delta_pct"] >= same["armor"]["delta_pct"] and o["accessory"]["delta_pct"] >= same["accessory"]["delta_pct"]
            assert all(c["cost"] is None or c["cost"] > 0 for c in o["cube"])
            assert not {c["slot"] for c in o["cube"]} & {x["slot"] for x in o["buy"]}
            # 칸별 몫: 그 칸만 목표 잠재로 바꾼 실딜 차이. 다 더하면 전체 차이와 거의 같다(주스탯%는 더해지므로 — 화면이 '약'으로 쓰는 근거)
            parts = [x["goal"] for x in o["buy"] if x["goal"]] + list(o["cube"])
            assert all(g["gain_pct"] > 0 and (g["cost"] is None or g["per_100m"] == g["gain_pct"] / (g["cost"] / 1e8)) for g in parts)
            whole = o["delta_pct"] - same["delta_pct"]
            assert abs(sum(g["gain_pct"] for g in parts) - whole) < 0.05 * whole
