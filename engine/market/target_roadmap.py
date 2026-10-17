"""목표 배율 로드맵(2026-10-09): 지금 보스 배율 → 목표 배율까지 억당 효율 순으로 업그레이드를 쌓는다.

- 배율(예: MapleScouter 효율·보스컷의 익스트림 스우 34.52%)은 사용자가 넣는다 — 우리 엔진은 상대 실딜만 계산하므로
  '배율은 실딜 %만큼 비례해서 오른다'고 본다(레벨 보정은 그대로, 포스 보정은 고른 보스·심볼 포스로 계산)
- 후보: 큐브(부위·잠재/에디마다 효율이 가장 좋은 단계 1개), HEXA 코어(다음 1레벨), HEXA 스탯(코어마다 1개),
  스타포스(같은 부위를 한 성씩 이어서 — 고를 때마다 지금 상태 기준으로 실딜·비용을 다시 계산),
  심볼(2026-10-11: 같은 심볼을 한 레벨씩 이어서 — 비용은 강화 메소, 실딜은 그때까지 오른 심볼 스탯·포스 기준으로 다시)
- (2026-10-17) 후보는 고르기 직전에 지금 상태 기준으로 다시 잰다(지연 탐욕) — 처음 상태 실딜을 그대로 곱하면
  같은 칸(보공·주스탯%)을 채울수록 줄어드는 효과가 빠져 '도달'을 거짓으로 보였다. 배율은 고른 변경을 모두 적용해 다시 잰 값.
  HEXA 코어(스킬 최종뎀)·HEXA 스탯 '강화 계속'(분포 평균)만 그 값을 곱한다. 경매장 구매·직작은 넣지 않는다
- 크확을 깎는 큐브는 기본으로 빼고(keep_crit), 실딜 평가 자체도 크확이 줄면 손해로 잡는다(engine/stats/evaluate.py)
"""
import copy
import dataclasses

from engine.enhance.starforce import expected_totals, max_star
from engine.enhance.starforce_stats import eligible, gain
from engine.market.events import Events
from engine.market.paths import upgrade_paths
from engine.market.recommend import SWAP, _Planner, _valued
from engine.market.hexa_paths import _block, _lines
from engine.market.symbol_paths import extra_of, step as symbol_step
from engine.stats import hexa as H
from engine.stats.jobs import job_profile
from engine.stats.model import StatBlock


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
           "reached": need <= 1, "final_ratio": current_ratio, "total_cost": 0.0, "changed": {}, "hexa_stat": {},
           "symbols": {}}
    if need <= 1:
        return out
    pl = _Planner(snap, setting, boss, catalog, None, events.miracle)
    raw = dict(pl.raw)  # 지금까지 바뀐 상태(큐브·스타포스 반영)
    job = job_profile(snap.character_class)

    sym_level = {sym["name"]: sym["level"] for sym in snap.symbol_items}  # 지금까지 올린 심볼 레벨
    sym_stat: dict = {}  # 처음보다 늘어난 심볼 스탯(%미적용)
    sym_force: dict = {}  # 처음보다 늘어난 포스(요구 포스가 있는 보스면 피해 비율이 바뀐다)
    hexa = {"pct": StatBlock(), "nopct": StatBlock()}  # 고른 HEXA 스탯 초기화로 바뀐 스탯(처음 대비)
    fixed = [1.0]  # 상태로 나타낼 수 없는 배율(HEXA 코어 = 스킬 최종뎀, HEXA 스탯 '강화 계속' = 분포 평균)

    def index_of(items=None, stat=None, force=None, hx=None):
        e = extra_of(sym_stat if stat is None else stat, sym_force if force is None else force)
        h = hexa if hx is None else hx
        e["pct"] = e.get("pct", StatBlock()) + h["pct"]
        e["nopct"] = e.get("nopct", StatBlock()) + h["nopct"]
        return pl.ev.index({s: _valued(it, pl.mains, pl.per_sec) for s, it in (raw if items is None else items).items()}, e)

    base = index_of()

    def true_mult():
        """처음 상태 대비 지금 상태의 실제 배율(고른 변경을 모두 적용해 다시 잰 값) × 상태로 못 나타내는 배율."""
        return index_of() / base * fixed[0]

    def hexa_extra(p):
        """HEXA 스탯 '초기화 → L레벨' 경로의 스탯 변화(처음 대비). '강화 계속'은 분포 평균이라 None."""
        if p.get("target_level") is None:
            return None
        core = next((c for c in snap.hexa_stat if c["core"] == p["core"]), None)
        if core is None:
            return None
        sub = (H.MAX_G - p["target_level"]) / 2
        return H.delta(_block(_lines(core, p["target_level"], (sub, sub)), job), _block(core["lines"], job))

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
        d = (index_of({**raw, slot: new}) / index_of() - 1) * 100
        t = expected_totals(it.level, it.starforce, it.starforce + 1, events.starforce(), events.spare_for(slot))
        if d <= 0 or t["cost"] <= 0:
            return None
        return {"slot": slot, "path": "스타포스", "name": it.name, "from_star": it.starforce, "to_star": it.starforce + 1,
                "cost": t["cost"], "delta_pct": d, "per_100m": d / (t["cost"] / 1e8), "expected_destroys": t["destroys"],
                "expected_spares": t["spares"], "gain": g, "_item": new}

    for slot in raw:
        c = sf_candidate(slot)
        if c:
            cands[("스타포스", slot)] = c

    def symbol_candidate(sym):
        lv = sym_level[sym["name"]]
        st = symbol_step(sym, lv, lv + 1, snap.character_class)
        if st is None:
            return None
        stat, force = dict(sym_stat), dict(sym_force)
        for k, v in st["stat_gain"].items():
            stat[k] = stat.get(k, 0.0) + v
        for k, v in st["force_gain"].items():
            force[k] = force.get(k, 0) + v
        d = (index_of(raw, stat, force) / index_of() - 1) * 100
        if d <= 0 or st["meso"] <= 0:
            return None
        return {"slot": "심볼", "path": "심볼", "name": sym["name"], "kind": sym["kind"], "region": sym["region"],
                "from_level": lv, "to_level": lv + 1, "cost": float(st["meso"]), "delta_pct": d,
                "per_100m": d / (st["meso"] / 1e8), **st, "_sym": sym}

    for sym in snap.symbol_items:
        c = symbol_candidate(sym)
        if c:
            cands[("심볼", sym["name"])] = c

    def refresh(p):
        """후보를 지금 상태 기준으로 다시 잰다(2026-10-17: 처음 상태 실딜을 그대로 곱해 '도달'을 거짓으로 보였다).
        다른 단계가 같은 칸(보공·주스탯%)을 먼저 채우면 효과가 줄어든다 — 없으면 None."""
        if p["path"] == "스타포스":
            return sf_candidate(p["slot"])
        if p["path"] == "심볼":
            return symbol_candidate(p["_sym"])
        if p["path"] == "큐브":
            new = SWAP[p["kind"]](raw[p["slot"]], p["target"], snap.level)
            if keep_crit and new.stats.cr < raw[p["slot"]].stats.cr:
                return None
            d = (index_of({**raw, p["slot"]: new}) / index_of() - 1) * 100
            return {**p, "delta_pct": d, "per_100m": d / (p["cost"] / 1e8), "_item": new}
        if p["path"] == "HEXA 스탯":
            ex = p.get("_hextra") or hexa_extra(p)
            if ex is not None:
                hx = {k: hexa[k] + ex[k] for k in ("pct", "nopct")}
                d = (index_of(hx=hx) / index_of() - 1) * 100
                return {**p, "delta_pct": d, "per_100m": d / (p["cost"] / 1e8), "_hextra": ex}
        return p  # HEXA 코어(스킬 최종뎀 — 스탯과 곱으로 독립)·'강화 계속'은 그대로

    step_no, fresh = 0, {}  # fresh[key] = 그 후보를 마지막으로 다시 잰 단계 번호
    guard = 0
    while step_no < max_steps and cands and true_mult() < need and guard < max_steps * 200:
        guard += 1
        key = max(cands, key=lambda k: cands[k]["per_100m"])
        if fresh.get(key) != step_no:  # 이번 단계에 아직 안 쟀으면 다시 재고, 순위가 바뀌면 다음 후보를 본다(지연 탐욕)
            p = refresh(cands[key])
            if p is None or p["delta_pct"] <= 0:
                cands.pop(key)
                continue
            cands[key], fresh[key] = p, step_no
            continue
        p = cands.pop(key)
        step_no += 1
        if p["path"] in ("스타포스", "큐브"):
            raw[p["slot"]] = p["_item"]
            out["changed"][p["slot"]] = p["_item"]
        elif p["path"] == "HEXA 스탯":
            out["hexa_stat"][p["core"]] = p.get("target_level")
            if p.get("_hextra") is not None:
                for k in ("pct", "nopct"):
                    hexa[k] = hexa[k] + p["_hextra"][k]
            else:
                fixed[0] *= 1 + p["delta_pct"] / 100
        elif p["path"] == "HEXA 코어":
            fixed[0] *= 1 + p["delta_pct"] / 100
        elif p["path"] == "심볼":  # 같은 심볼의 다음 1레벨(지금까지 오른 스탯 기준으로 다시)
            sym = p["_sym"]
            sym_level[sym["name"]] = p["to_level"]
            out["symbols"][sym["name"]] = p["to_level"]
            for k, v in p["stat_gain"].items():
                sym_stat[k] = sym_stat.get(k, 0.0) + v
            for k, v in p["force_gain"].items():
                sym_force[k] = sym_force.get(k, 0) + v
            c = symbol_candidate(sym)
            if c:
                cands[("심볼", sym["name"])] = c
        if p["path"] in ("스타포스", "큐브"):  # 이 부위의 다음 한 성(지금 상태 기준으로 다시)
            c = sf_candidate(p["slot"])
            if c:
                cands[("스타포스", p["slot"])] = c
            else:
                cands.pop(("스타포스", p["slot"]), None)
        mult = true_mult()
        out["total_cost"] += p["cost"]
        step = {k: v for k, v in p.items() if not k.startswith("_")}
        step.update({"ratio_after": current_ratio * mult, "multiplier": mult, "total_cost": out["total_cost"]})
        out["steps"].append(step)
    out["final_ratio"] = current_ratio * true_mult()
    out["reached"] = out["final_ratio"] >= target_ratio
    out["stopped_at_max_steps"] = step_no >= max_steps and not out["reached"]  # 불가능이 아니라 단계 상한에서 멈춤
    return out
