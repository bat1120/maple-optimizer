"""목표 배율 로드맵(2026-10-09): 지금 보스 배율 → 목표 배율까지 억당 효율 순으로 업그레이드를 쌓는다.

- 배율(예: MapleScouter 효율·보스컷의 익스트림 스우 34.52%)은 사용자가 넣는다 — 우리 엔진은 상대 실딜만 계산하므로
  '배율은 실딜 %만큼 비례해서 오른다'고 본다(레벨·포스 보정은 그대로)
- 후보: 큐브(부위·잠재/에디마다 효율이 가장 좋은 단계 1개), HEXA 코어(다음 1레벨), HEXA 스탯(코어마다 1개),
  스타포스(같은 부위를 한 성씩 이어서 — 고를 때마다 지금 상태 기준으로 실딜·비용을 다시 계산)
- 큐브·HEXA 실딜은 처음 상태 기준값을 그대로 곱한다(근사). 경매장 구매·직작은 넣지 않는다(관측 매물에 따라 크게 바뀐다)
- 크확을 깎는 큐브는 기본으로 빼고(keep_crit), 실딜 평가 자체도 크확이 줄면 손해로 잡는다(engine/stats/evaluate.py)
"""
import copy
import dataclasses

from engine.enhance.starforce import expected_totals, max_star
from engine.enhance.starforce_stats import eligible, gain
from engine.market.events import Events
from engine.market.paths import upgrade_paths
from engine.market.recommend import SWAP, _Planner, _valued


def apply_star(it, target: int):
    """target성으로 올린 템(스탯·코어·스타포스 옵션까지). 계산할 수 없으면 None."""
    g = gain(it, target)
    if not g:
        return None, None
    stats, core = copy.deepcopy(it.stats), (copy.deepcopy(it.core) if it.core is not None else None)
    sf = dict(it.sf_option)
    for k, v in g.items():
        stats.flat[k] = stats.flat.get(k, 0.0) + v
        if core is not None:
            core.flat[k] = core.flat.get(k, 0.0) + v
        sf[k] = sf.get(k, 0.0) + v
    return dataclasses.replace(it, starforce=target, stats=stats, core=core, sf_option=sf), g


def target_roadmap(snap, setting, boss, catalog, events: Events | None, observed, current_ratio: float,
                   target_ratio: float, max_steps: int = 120, keep_crit: bool = True) -> dict:
    """keep_crit: 크확을 깎는 큐브는 고르지 않는다(기본). MapleScouter는 크확 100% 미만이면 결과를 안 보여 주고,
    넥슨 스탯창 크확에는 직업 스킬 크확이 빠져 있어 여유분을 알 수 없다(2026-10-09)."""
    events = events or Events()
    need = target_ratio / current_ratio if current_ratio > 0 else float("inf")
    out = {"current_ratio": current_ratio, "target_ratio": target_ratio, "needed_multiplier": need, "steps": [],
           "reached": need <= 1, "final_ratio": current_ratio, "total_cost": 0.0, "changed": {}, "hexa_stat": {}}
    if need <= 1:
        return out
    pl = _Planner(snap, setting, boss, catalog, None, events.miracle)
    raw = dict(pl.raw)  # 지금까지 바뀐 상태(큐브·스타포스 반영)

    def index_of(items):
        return pl.ev.index({s: _valued(it, pl.mains, pl.per_sec) for s, it in items.items()})

    cands: dict = {}
    for p in upgrade_paths(snap, setting, boss, catalog, observed, None, events)["all"]:
        if p["path"] == "큐브":
            key = ("큐브", p["slot"], p["kind"])
            if keep_crit:
                new = SWAP[p["kind"]](raw[p["slot"]], p["target"], snap.level)
                if new.stats.cr < raw[p["slot"]].stats.cr:
                    continue
        elif p["path"] == "HEXA 코어":
            key = ("HEXA 코어", p["name"].rsplit(" ", 1)[0])
        elif p["path"] == "HEXA 스탯":
            key = ("HEXA 스탯", p["core"])
        else:
            continue  # 스타포스는 아래에서 한 성씩, 구매·직작은 넣지 않는다
        if key not in cands or p["per_100m"] > cands[key]["per_100m"]:
            cands[key] = p

    def sf_candidate(slot):
        it = raw[slot]
        if not eligible(it) or it.starforce + 1 > max_star(it.level):
            return None
        new, g = apply_star(it, it.starforce + 1)
        if new is None:
            return None
        cur = index_of(raw)
        d = (index_of({**raw, slot: new}) / cur - 1) * 100
        t = expected_totals(it.level, it.starforce, it.starforce + 1, events.starforce(), events.spare_price)
        if d <= 0 or t["cost"] <= 0:
            return None
        return {"slot": slot, "path": "스타포스", "name": it.name, "from_star": it.starforce, "to_star": it.starforce + 1,
                "cost": t["cost"], "delta_pct": d, "per_100m": d / (t["cost"] / 1e8), "expected_destroys": t["destroys"],
                "expected_spares": t["spares"], "gain": g, "_item": new}

    for slot in raw:
        c = sf_candidate(slot)
        if c:
            cands[("스타포스", slot)] = c

    mult = 1.0
    for _ in range(max_steps):
        if not cands or mult >= need:
            break
        key = max(cands, key=lambda k: cands[k]["per_100m"])
        p = cands.pop(key)
        mult *= 1 + p["delta_pct"] / 100
        out["total_cost"] += p["cost"]
        step = {k: v for k, v in p.items() if not k.startswith("_")}
        step.update({"ratio_after": current_ratio * mult, "multiplier": mult, "total_cost": out["total_cost"]})
        out["steps"].append(step)
        if p["path"] == "스타포스":
            raw[p["slot"]] = p["_item"]
            out["changed"][p["slot"]] = p["_item"]
        elif p["path"] == "큐브":
            raw[p["slot"]] = SWAP[p["kind"]](raw[p["slot"]], p["target"], snap.level)
            out["changed"][p["slot"]] = raw[p["slot"]]
        elif p["path"] == "HEXA 스탯":
            out["hexa_stat"][p["core"]] = p.get("target_level")
        if p["path"] in ("스타포스", "큐브"):  # 이 부위의 다음 한 성(지금 상태 기준으로 다시)
            c = sf_candidate(p["slot"])
            if c:
                cands[("스타포스", p["slot"])] = c
            else:
                cands.pop(("스타포스", p["slot"]), None)
    out["final_ratio"] = current_ratio * mult
    out["reached"] = mult >= need
    return out
