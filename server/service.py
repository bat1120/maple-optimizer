"""엔진 호출을 API 응답 형태로 묶는다. 계산은 전부 engine이 한다."""
from dataclasses import asdict

from engine.market.listing import Listing, item_from_input, rank_listings
from engine.stats.evaluate import evaluate_setting, rank_settings
from engine.stats.formula import stat_attack_max
from engine.stats.jobs import job_profile
from engine.stats.metrics import BossProfile
from engine.stats.sets import SetCatalog
from engine.stats.snapshot import CharacterSnapshot, Setting

CATALOG = SetCatalog.load()


def boss(defense: float) -> BossProfile:
    return BossProfile(f"방어율 {defense:g}%", defense)


def summary(snap: CharacterSnapshot) -> dict:
    weapon = snap.equipment_presets[snap.active_equipment_preset]["무기"].part
    engine_sa = stat_attack_max(snap.final, job_profile(snap.character_class), weapon)
    f = snap.final
    return {
        "character_class": snap.character_class,
        "level": snap.level,
        "date": snap.date,
        "active_setting": asdict(snap.active_setting),
        "stat_attack": {"engine": engine_sa, "api": f.stat_attack_max},
        "combat_power_reference": f.combat_power,
        "final": {"stats": f.stats, "atk": f.atk, "matk": f.matk, "dmg": f.dmg, "boss": f.boss,
                  "fd": f.fd, "cd": f.cd, "ied": f.ied},
        "equipment_presets": {str(n): [{"slot": it.slot, "name": it.name, "starforce": it.starforce}
                                       for it in items.values()]
                              for n, items in snap.equipment_presets.items() if items},
        "excluded": sorted(set(snap.excluded)),
    }


def settings(snap: CharacterSnapshot, defense: float) -> dict:
    from engine.stats.evaluate import predict_setting
    from engine.stats.metrics import equivalent_main_stat
    b = boss(defense)
    ranked = rank_settings(snap, b, CATALOG)
    active = evaluate_setting(snap, snap.active_setting, b, CATALOG)
    base = predict_setting(snap, snap.active_setting, CATALOG)
    job = job_profile(snap.character_class)
    return {"boss": asdict(b),
            "ranking": [{"setting": asdict(s), "index": v, "relative_to_active": v / active if active > 0 else None,
                         "main_stat_vs_active": equivalent_main_stat(base, job, v / active) if active > 0 else None}
                        for s, v in ranked]}


def listings(snap: CharacterSnapshot, setting: Setting | None, defense: float, inputs: list) -> dict:
    b = boss(defense)
    chosen = setting or rank_settings(snap, b, CATALOG)[0][0]
    built = [Listing(x.slot, item_from_input(x.slot, x.part, x.name, x.total, x.potentials, snap.level, x.starforce),
                     x.price, x.resale) for x in inputs]
    ranked = rank_listings(snap, chosen, built, b, CATALOG)
    return {"setting": asdict(chosen), "boss": asdict(b),
            "ranking": [{"slot": e.listing.slot, "name": e.listing.item.name, "price": e.listing.price,
                         "resale": e.listing.resale, "delta_pct": e.delta_pct, "per_100m": e.per_100m,
                         "main_stat_gain": e.main_stat_gain, "main_stat_gain_per_100m": e.main_stat_gain_per_100m,
                         "excluded": e.listing.item.excluded} for e in ranked]}


def _conditions(c):
    from engine.enhance.starforce import StarforceConditions
    return StarforceConditions(**c.model_dump())


def _dist(d) -> dict:
    return {"mean": d.mean, "median": d.median, "p75": d.p75, "p90": d.p90}


def starforce(body) -> dict:
    from engine.enhance.starforce import expected_cost, simulate
    cond = _conditions(body.conditions)
    exact = expected_cost(body.level, body.start, body.target, body.destroy_cost, cond)
    mc = simulate(body.level, body.start, body.target, body.destroy_cost, cond, body.trials, seed=20261003)
    return {"exact_mean": exact, "distribution": _dist(mc), "conditions": body.conditions.model_dump(),
            "note": "확률은 2026-03 기준(스타캐치 상시 적용), 비용 공식은 비공식(나무위키)"}


def cube(body) -> dict:
    from engine.enhance.cube import CubeTable, cubes_needed, lines_at_least, reset_cost, stat_sum_at_least, \
        success_probability
    preds = [lines_at_least(k, n) for k, n in body.lines_at_least.items()]
    preds += [stat_sum_at_least(t.key, t.percent, t.value) for t in body.sum_at_least]
    if not preds:
        raise ValueError("목표 조건(lines_at_least 또는 sum_at_least)을 하나 이상 넣어 주세요")
    table = CubeTable.load(body.table)
    p = success_probability(table, lambda opts: all(f(opts) for f in preds))
    cost = reset_cost(body.level, body.grade)
    out = {"probability": p, "cost_per_reset": cost}
    if p > 0:
        d = cubes_needed(p)
        out["cubes"] = _dist(d)
        out["meso"] = {k: v * cost for k, v in _dist(d).items()}
    return out


def craft_compare(body) -> dict:
    from engine.market.craft import CraftPlan, compare_listing
    plan = CraftPlan(body.base_price, body.level, body.start_star, body.target_star, body.destroy_cost,
                     _conditions(body.conditions), body.cube_p, body.cube_cost)
    c = compare_listing(plan, body.price)
    return {"price": c.price, "craft_mean": c.craft_mean, "distribution": _dist(c.distribution),
            "ratio_to_mean": c.ratio_to_mean, "prob_craft_costs_more": c.prob_craft_costs_more,
            "note": "추옵(환불) 비용 미포함"}


def optimize(snap: CharacterSnapshot, setting: Setting | None, defense: float, budget: float, candidates: list) -> dict:
    from engine.optimize.budget import Action, greedy
    from engine.stats.evaluate import Evaluator
    b = boss(defense)
    chosen = setting or rank_settings(snap, b, CATALOG)[0][0]
    actions = [Action(x.slot, item_from_input(x.slot, x.part, x.name, x.total, x.potentials, snap.level, x.starforce),
                      x.price - x.resale, x.name) for x in candidates]
    plan = greedy(Evaluator(snap, chosen, b, CATALOG), actions, budget)
    return {"setting": asdict(chosen), "budget": budget, "spent": plan.spent, "gain_pct": plan.gain_pct,
            "actions": [{"slot": a.slot, "name": a.item.name, "cost": a.cost} for a in plan.actions]}


def vision_items(snap: CharacterSnapshot | None, setting: Setting | None, defense: float, listings: list[dict],
                 seen: set[str]) -> list[dict]:
    """비전으로 읽은 매물을 평가한다. 반지·펜던트는 슬롯 후보 중 실딜이 가장 오르는 자리를 고른다."""
    from engine.stats.evaluate import evaluate_setting, predict_setting, swap_item
    from engine.stats.metrics import equivalent_main_stat
    from server.vision import SLOTS_BY_CATEGORY, signature

    out = []
    b = boss(defense)
    chosen = (setting or rank_settings(snap, b, CATALOG)[0][0]) if snap else None
    base = evaluate_setting(snap, chosen, b, CATALOG) if snap else None
    for x in listings:
        sig = signature(x)
        row = {"signature": sig, "read": x, "evaluated": False}
        if sig in seen:
            out.append(row)
            continue
        if snap is None:
            row["reason"] = "캐릭터를 먼저 조회해 주세요"
            out.append(row)
            continue
        if not x.get("total"):
            # 총 옵션 없이 평가하면 기본 스탯 0인 템처럼 계산돼 큰 음수가 나온다 → 보류
            row["reason"] = "총 옵션을 읽지 못했어요 — 툴팁 윗부분(STR·INT·마력 합계)이 보이게 띄워 주세요"
            out.append(row)
            continue
        cat = x.get("category") or "기타"
        slots = SLOTS_BY_CATEGORY.get(cat, (cat,))
        item = item_from_input(slots[0], x.get("part") or cat, x.get("name") or "?", x.get("total") or {},
                               x.get("potentials") or [], snap.level, x.get("starforce") or 0)
        scored = [(s, swap_item(snap, chosen, s, item, b, CATALOG)) for s in slots]
        slot, new = max(scored, key=lambda t: t[1])
        delta = (new / base - 1) * 100 if base else None
        gain = equivalent_main_stat(predict_setting(snap, chosen, CATALOG), job_profile(snap.character_class),
                                    new / base) if base else None
        price = x.get("price")
        row.update({"evaluated": True, "slot": slot, "setting": asdict(chosen), "delta_pct": delta,
                    "main_stat_gain": gain, "excluded": item.excluded,
                    "per_100m": (delta / (price / 1e8)) if (delta is not None and price) else None})
        out.append(row)
    return out


def recommend(snap: CharacterSnapshot, defense: float, top: int = 5) -> dict:
    """게임 경매장 검색 조건 카드. 평가는 언제나 보스 실딜 최적 세팅 기준(사냥 세팅이어도)."""
    from engine.market.recommend import recommend_searches
    b = boss(defense)
    chosen = rank_settings(snap, b, CATALOG)[0][0]
    cards = []
    for r in recommend_searches(snap, chosen, b, CATALOG, top=top):
        category = r.slot.rstrip("0123456789") or r.slot
        cards.append({"slot": r.slot, "category": category, "target_potentials": r.target_potentials,
                      "min_starforce": r.min_starforce, "delta_pct": r.delta_pct,
                      "search": f"{category} · 잠재 {' / '.join(r.target_potentials)} · {r.min_starforce}성 이상",
                      "current": {"name": r.current_name, "starforce": r.min_starforce,
                                  "potentials": r.current_potentials}})
    return {"evaluation_setting": asdict(chosen), "boss": asdict(b), "recommendations": cards,
            "note": "윗잠만 목표 잠재로 바꾼 같은 템 기준이에요. 스타포스·추옵·에디는 지금 템과 같다고 보고 계산했어요."}
