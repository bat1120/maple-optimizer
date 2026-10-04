"""엔진 호출을 API 응답 형태로 묶는다. 계산은 전부 engine이 한다."""
from dataclasses import asdict

from engine.market.listing import DEFAULT_FEE_RATE, Listing, item_from_input, net_resale, rank_listings
from engine.market.recommend import cooldown_seconds
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


def meso_text(v: float | None) -> str | None:
    """메소 → "327억 9999만". 만 미만은 버린다(답변에 그대로 인용하도록 도구 결과에 싣는다)."""
    if v is None:
        return None
    eok, man = int(v // 100_000_000), int(v % 100_000_000 // 10_000)
    return " ".join(p for p in (f"{eok}억" if eok else "", f"{man}만" if man else "") if p) or f"{int(v)}"


_NO_TOTAL = "총 옵션이 없어 평가하지 않았어요 — 툴팁 윗부분이 보이게 띄워 주세요"


def listings(snap: CharacterSnapshot, setting: Setting | None, defense: float, inputs: list,
             fee_rate: float = DEFAULT_FEE_RATE) -> dict:
    if not 0 <= fee_rate <= 0.1:
        raise ValueError(f"수수료율은 0~0.1 사이여야 해요(5%면 0.05): {fee_rate}")
    b = boss(defense)
    chosen = setting or rank_settings(snap, b, CATALOG)[0][0]
    # 총 옵션 없이 평가하면 기본 스탯 0인 템처럼 계산돼 큰 음수가 나온다(2026-10-04 실사용 -19.5%) → 보류
    held = [{"name": x.name, "price_text": meso_text(x.price), "reason": _NO_TOTAL} for x in inputs if not x.total]
    built = [Listing(x.slot, item_from_input(x.slot, x.part, x.name, x.total, x.potentials, snap.level, x.starforce),
                     x.price, x.resale, fee_rate) for x in inputs if x.total]
    ranked = rank_listings(snap, chosen, built, b, CATALOG) if built else []
    return {"setting": asdict(chosen), "boss": asdict(b), "held": held, "fee_rate": fee_rate,
            "fee_note": "판매 수수료는 사는 가격엔 붙지 않고, 지금 템 판매 대금(resale)에서만 빠져요.",
            "ranking": [{"slot": e.listing.slot, "name": e.listing.item.name, "price": e.listing.price,
                         "price_text": meso_text(e.listing.price),
                         "cooldown_s_not_valued": cooldown_seconds(e.listing.item),  # 실딜 계산에 안 들어간 쿨감 초
                         "resale": e.listing.resale, "net_resale": net_resale(e.listing.resale, fee_rate),
                         "net_cost": e.listing.price - net_resale(e.listing.resale, fee_rate),
                         "net_cost_text": meso_text(e.listing.price - net_resale(e.listing.resale, fee_rate)),
                         "delta_pct": e.delta_pct, "per_100m": e.per_100m,
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


def optimize(snap: CharacterSnapshot, setting: Setting | None, defense: float, budget: float, candidates: list,
             fee_rate: float = DEFAULT_FEE_RATE) -> dict:
    from engine.optimize.budget import Action, greedy
    from engine.stats.evaluate import Evaluator
    b = boss(defense)
    chosen = setting or rank_settings(snap, b, CATALOG)[0][0]
    actions = [Action(x.slot, item_from_input(x.slot, x.part, x.name, x.total, x.potentials, snap.level, x.starforce),
                      x.price - net_resale(x.resale, fee_rate), x.name) for x in candidates]
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
    own = {(it.name, tuple(sorted(it.potentials))) for preset in (snap.equipment_presets.values() if snap else [])
           for it in preset.values() if it.potentials}
    for x in listings:
        sig = signature(x)
        from server.vision import checksum_failures, unverified_lines
        row = {"signature": sig, "read": x, "evaluated": False,
               "unverified_lines": unverified_lines(list(x.get("potentials") or [])),
               "unverified_totals": checksum_failures(x),
               "starforce_note": "스타포스는 화면 판독값이라 틀릴 수 있어요(확인 필요) — 실딜은 총 옵션으로 계산해서 영향이 없어요"}
        if sig in seen:
            out.append(row)
            continue
        if snap is None:
            row["reason"] = "캐릭터를 먼저 조회해 주세요 — 조회하면 자동으로 다시 평가해요"
            out.append(row)
            continue
        main_lines = sorted(x.get("potential_lines") or x.get("potentials") or [])
        if main_lines and (x.get("name"), tuple(main_lines)) in own:
            # 넥슨 API의 착용 템과 이름·윗잠이 같다 = 옆에 뜬 '현재 장착 중인 장비' 비교 툴팁(AI가 놓쳐도 잡는다)
            row["equipped"] = True
            row["reason"] = "지금 착용 중인 템이에요(비교 툴팁) — 매물로 평가하지 않아요"
            out.append(row)
            continue
        if row["unverified_totals"]:
            # 괄호 합이 안 맞으면 숫자를 잘못 읽은 것 — 틀린 숫자로 평가하지 않는다(실측값 원칙)
            row["reason"] = ("총 옵션 검산이 맞지 않아요(" + ", ".join(row["unverified_totals"])
                             + ") — 화면이 작게 잡혔을 수 있어요. 툴팁을 다시 띄워 주세요")
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


def _cooldown_note(cooldown_main_pct: float | None) -> str:
    return (f"쿨감 1초를 주스탯 {cooldown_main_pct:g}%로 환산했어요." if cooldown_main_pct
            else "쿨감 효율은 실딜에 넣지 않았어요(쿨감 1초 = 주스탯 몇 %인지 정하면 넣어요).")


def recommend(snap: CharacterSnapshot, defense: float, top: int = 5, cooldown_main_pct: float | None = None) -> dict:
    """게임 경매장 검색 조건 카드(잠재·에디). 평가는 언제나 보스 실딜 최적 세팅 기준(사냥 세팅이어도).
    제네시스·데스티니 무기처럼 경매장에서 살 수 없는 템은 빠진다(로드맵에서 큐브 경로로 본다)."""
    from engine.market.recommend import recommend_searches
    b = boss(defense)
    chosen = rank_settings(snap, b, CATALOG)[0][0]
    cards = []
    for r in recommend_searches(snap, chosen, b, CATALOG, top=top, cooldown_main_pct=cooldown_main_pct):
        category = r.slot.rstrip("0123456789") or r.slot
        cards.append({"slot": r.slot, "category": category, "kind": r.kind, "grade": r.grade,
                      "lines_good": r.lines_good, "target_potentials": r.target, "min_starforce": r.min_starforce,
                      "delta_pct": r.delta_pct, "probability": r.probability, "kept": r.kept,
                      "search": f"{category} · {r.kind} {r.grade} {' / '.join(r.target)} · {r.min_starforce}성 이상",
                      "current": {"name": r.current_name, "starforce": r.min_starforce, "potentials": r.current}})
    return {"evaluation_setting": asdict(chosen), "boss": asdict(b), "recommendations": cards,
            "cooldown_main_pct": cooldown_main_pct,
            "note": ("부위·잠재/에디마다 지금보다 한 단계 위(실딜이 0.1% 이상 처음 오르는 등급·줄 수)를 골랐어요. "
                     "줄 수치는 공식 큐브 확률표의 흔한 줄(확률 2% 이상, 이탈 제외)이고, 그 줄만 바꾼 같은 템 기준이에요. "
                     "쿨감 줄은 유지해요 — " + _cooldown_note(cooldown_main_pct))}


def paths(snap: CharacterSnapshot, defense: float, observed: list[dict] | None = None,
          cooldown_main_pct: float | None = None, top: int = 30) -> dict:
    """업그레이드 경로 비교: 구매·직작·지금 템 큐브를 억당 실딜로(세트 효과 반영)."""
    from engine.market.paths import upgrade_paths
    b = boss(defense)
    chosen = rank_settings(snap, b, CATALOG)[0][0]
    r = upgrade_paths(snap, chosen, b, CATALOG, observed, cooldown_main_pct)
    fmt = lambda ps: [{**p, "cost_text": meso_text(p["cost"])} for p in ps]  # noqa: E731
    return {"evaluation_setting": asdict(chosen), "boss": asdict(b), "all": fmt(r["all"][:top]),
            "best_by_slot": fmt(r["best_by_slot"]), "observed_count": len(observed or []),
            "note": ("구매 = 관측 매물을 그대로 끼운 실딜(세트 개수를 다시 세서 세트 효과 변화 포함, set_change), 다른 월드 매물은 +10%. "
                     "직작 = 관측 매물 가격 + 그 매물 등급에서 단계까지 메소 재설정 평균. 큐브 = 지금 템에 메소 재설정 평균. "
                     "sold=true는 판매 완료 체결가(시세), false는 판매 중 호가. 비용은 평균 기대값이고 지금 템 판매 대금은 빼지 않았어요.")}


def roadmap(snap: CharacterSnapshot, defense: float, cooldown_main_pct: float | None = None,
            observed: list[dict] | None = None) -> dict:
    """전체 부위 로드맵: 부위마다 잠재·에디 등급별 단계와 각 단계의 보스 실딜 상승."""
    from engine.market.recommend import roadmap as build
    from engine.market.recommend import value_ranking
    b = boss(defense)
    chosen = rank_settings(snap, b, CATALOG)[0][0]
    rm = build(snap, chosen, b, CATALOG, cooldown_main_pct, observed)
    rows = [{"slot": slot, **row} for slot, row in rm.items()]
    value = [{**v, "cube_cost_text": meso_text(v["cube_cost"])} for v in value_ranking(rm)]
    return {"evaluation_setting": asdict(chosen), "boss": asdict(b), "cooldown_main_pct": cooldown_main_pct,
            "slots": rows, "value_ranking": value,
            "value_note": ("가격 대비 순위: 메소 재설정(윗잠=블랙 큐브, 에디=화이트 에디셔널 큐브)으로 그 단계까지 가는 평균 비용 "
                           "(등급 상승·천장 포함)과 억당 실딜 상승률. 도달 확률은 줄별 기여를 더해 비교한 근사예요. "
                           "경매장에서 그 단계 템을 이보다 싸게 사면 그쪽이 이득이에요 — 화면 매물 평가로 비교하세요."),
            "market_note": (f"관측 시세: 지금까지 화면 분석으로 읽은 매물 {len(observed or [])}건 중 같은 부위·스타포스 이상·"
                            "그 단계 줄을 모두 갖춘 매물의 가격(최근 30일). 다른 옵션(스타포스·추옵·다른 쪽 잠재)은 "
                            "다를 수 있어 참고용이에요."),
            "note": ("각 단계 = 그 등급에서 흔한 줄(확률 2% 이상, 이탈 제외)로 2줄·3줄을 맞춘 경우예요. probability는 큐브 한 번에 "
                     "그 조합이 나올 확률(참고)이에요. route가 '큐브'인 부위(제네시스 무기 등)는 경매장에서 살 수 없어요. "
                     + _cooldown_note(cooldown_main_pct))}
