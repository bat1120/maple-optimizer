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
        "profile": {k: snap.profile.get(k) for k in ("name", "world", "guild", "image", "class_level", "date_create")},
        "equipment_presets": {str(n): [{"slot": it.slot, "name": it.name, "starforce": it.starforce, "icon": it.icon,
                                        "potential_grade": it.potential_grade, "additional_grade": it.additional_grade,
                                        "potentials": list(it.potentials), "additional": list(it.additional),
                                        "level": it.level, "special_ring_level": it.special_ring_level}
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
    from server.score import expected_from_item
    worn = [it for preset in (snap.equipment_presets.values() if snap else []) for it in preset.values()]
    own = {(it.name, tuple(sorted(it.potentials))) for it in worn if it.potentials}
    # 잠재 없는 착용 템(포켓·훈장·특수 반지)은 이름 + 총 옵션으로 알아본다
    own_plain = {(it.name, _total_key(expected_from_item(it)["total"])) for it in worn
                 if not it.potentials and it.core is not None}
    own_rings = [it for it in worn if it.special_ring_level]
    for x in listings:
        sig = signature(x)
        from server.vision import checksum_failures, unverified_lines
        row = {"signature": sig, "read": x, "evaluated": False,
               "unverified_lines": unverified_lines(list(x.get("potentials") or [])),
               "unverified_totals": checksum_failures(x),
               "starforce_note": ("스타포스는 툴팁 별을 코드로 센 값이에요" if x.get("starforce_source") == "별 세기" else
                                  "스타포스는 화면 판독값이라 틀릴 수 있어요(확인 필요) — 실딜은 총 옵션으로 계산해서 영향이 없어요")}
        if sig in seen:
            out.append(row)
            continue
        if snap is None:
            row["reason"] = "캐릭터를 먼저 조회해 주세요 — 조회하면 자동으로 다시 평가해요"
            out.append(row)
            continue
        main_lines = sorted(x.get("potential_lines") or x.get("potentials") or [])
        if (main_lines and (x.get("name"), tuple(main_lines)) in own) or (
                not main_lines and (x.get("name"), _total_key(x.get("total"))) in own_plain):
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
        if cat == "보조무기":
            # 보조무기는 직업마다 종류가 다르다(engine/market/secondary.py) — 낄 수 없는 종류는 평가하지 않는다
            from engine.market.recommend import UNTRADEABLE_SECONDARY_JOBS
            from engine.market.secondary import secondary_fits
            if snap.character_class in UNTRADEABLE_SECONDARY_JOBS:
                row["reason"] = f"{snap.character_class}는 보조무기를 경매장에서 살 수 없어요(교환 불가) — 지금 보조무기에 큐브만 가능해요"
                out.append(row)
                continue
            mine = snap.equipment_presets.get(chosen.equipment, {}).get("보조무기")
            fits = secondary_fits(mine.part if mine else None, job_profile(snap.character_class).branches,
                                  x.get("equip_type"), x.get("job_groups"))
            if fits is False:
                row["reason"] = (f"이 캐릭터가 낄 수 없는 보조무기로 보여요(매물 {x.get('equip_type')}"
                                 + (f"·{'/'.join(x.get('job_groups') or [])}" if x.get("job_groups") else "")
                                 + f", 지금 낀 보조무기는 {mine.part if mine else '없음'}) — 평가하지 않아요")
                out.append(row)
                continue
            if fits is None:
                row["secondary_note"] = "툴팁의 장비분류(보조무기 종류)를 못 읽어서, 이 캐릭터가 낄 수 있는 보조무기인지 확인이 필요해요"
        slots = SLOTS_BY_CATEGORY.get(cat, (cat,))
        item = item_from_input(slots[0], x.get("part") or cat, x.get("name") or "?", x.get("total") or {},
                               x.get("potentials") or [], snap.level, x.get("starforce") or 0)
        scored = [(s, swap_item(snap, chosen, s, item, b, CATALOG)) for s in slots]
        slot, new = max(scored, key=lambda t: t[1])
        delta = (new / base - 1) * 100 if base else None
        gain = equivalent_main_stat(predict_setting(snap, chosen, CATALOG), job_profile(snap.character_class),
                                    new / base) if base else None
        price = x.get("price")
        ring = next((it for it in own_rings if it.name == x.get("name")), None) or (
            own_rings[0] if own_rings and x.get("special_ring_level") else None)
        if ring is not None or x.get("special_ring_level"):
            lv = x.get("special_ring_level")
            row["special_ring_note"] = (
                "특수 반지 스킬 효과는 실딜 계산에 없어요 — 스탯만 계산했어요. "
                f"이 매물 {f'{lv}레벨' if lv else '레벨 못 읽음'}"
                + (f" · 지금 낀 {ring.name} {ring.special_ring_level}레벨" if ring else ""))
        try:
            row["scouter"] = scouter_delta(snap, chosen, slot, item)  # 환산 계산기에 옮길 변화량(복사 버튼)
        except Exception:  # 변화량을 못 구해도 평가는 보여 준다
            row["scouter"] = None
        row.update({"evaluated": True, "slot": slot, "setting": asdict(chosen), "delta_pct": delta,
                    "main_stat_gain": gain, "excluded": item.excluded,
                    "per_100m": (delta / (price / 1e8)) if (delta is not None and price) else None})
        out.append(row)
    return out


def _total_key(total: dict | None) -> tuple:
    """총 옵션 비교용: 값이 있는 칸만, 정렬해서."""
    return tuple(sorted((k, v) for k, v in (total or {}).items() if v))


def _cooldown(snap: CharacterSnapshot, cooldown_main_pct: float | None) -> tuple[dict, str]:
    """쿨감을 어떻게 반영했는지(출처 포함)와 안내 문구."""
    from engine.market.recommend import cooldown_valuer
    _, src = cooldown_valuer(snap.character_class, cooldown_main_pct)
    if src["kind"] == "manual":
        return src, f"쿨감 1초를 주스탯 {cooldown_main_pct:g}%로 환산했어요(직접 입력)."
    if src["kind"] == "table":
        steps = "·".join(f"{s}초 {v:g}%" for s, v in sorted(src["cumulative"].items()))
        return src, (f"{src['job']} 쿨감: {steps}({src['unit']}, 출처 {src['source']} · {src['date']}). "
                     "표에 없는 초수는 반영하지 않아요(계단식이라 짐작하지 않아요).")
    if src["kind"] == "reference":
        return src, (f"{src['job']} 쿨감은 {src['unit']} 단위 자료만 있어 실딜에 넣지 않았어요({src['source']}). "
                     "쿨감 1초 = 주스탯 몇 %인지 직접 입력하면 넣어요.")
    return src, "이 직업은 출처 있는 쿨감 수치를 못 찾아 실딜에 넣지 않았어요 — 쿨감 1초 = 주스탯 몇 %인지 직접 입력하면 넣어요."


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
    cd, cd_note = _cooldown(snap, cooldown_main_pct)
    return {"evaluation_setting": asdict(chosen), "boss": asdict(b), "recommendations": cards,
            "cooldown_main_pct": cooldown_main_pct, "cooldown": cd,
            "note": ("부위·잠재/에디마다 지금보다 한 단계 위(실딜이 0.1% 이상 처음 오르는 등급·줄 수)를 골랐어요. "
                     "줄 수치는 공식 큐브 확률표의 흔한 줄(확률 2% 이상, 이탈 제외)이고, 그 줄만 바꾼 같은 템 기준이에요. "
                     "쿨감 줄은 유지해요 — " + cd_note)}


def paths(snap: CharacterSnapshot, defense: float, observed: list[dict] | None = None,
          cooldown_main_pct: float | None = None, top: int = 30, events=None) -> dict:
    """업그레이드 경로 비교: 구매·직작·지금 템 큐브를 억당 실딜로(세트 효과 반영)."""
    from engine.market.paths import balanced, upgrade_paths
    b = boss(defense)
    chosen = rank_settings(snap, b, CATALOG)[0][0]
    from engine.market.events import Events
    events = events or Events()
    r = upgrade_paths(snap, chosen, b, CATALOG, observed, cooldown_main_pct, events)
    fmt = lambda ps: [{**p, "cost_text": meso_text(p["cost"])} for p in ps]  # noqa: E731
    return {"evaluation_setting": asdict(chosen), "boss": asdict(b), "events": {**asdict(events), "label": events.label()},
            "all": fmt(balanced(r["all"], max(1, top // 4))),
            "best_by_slot": fmt(r["best_by_slot"]), "observed_count": len(observed or []),
            "note": ("구매 = 관측 매물을 그대로 끼운 실딜(세트 개수를 다시 세서 세트 효과 변화 포함, set_change), 다른 월드 매물은 +10%. "
                     "직작 = 관측 매물 가격 + 그 매물 등급에서 단계까지 메소 재설정 평균. 큐브 = 지금 템에 메소 재설정 평균. "
                     "스타포스 = 지금 템을 목표 성까지 메소 기대값(강화 + 흔적 복구 메소, 고른 이벤트 반영). 파괴되면 같은 장비가 복구에 필요해요"
                     "(18성 이하 1개·19~20성 2개·21성 3개·22성 이상 4개) — expected_spares가 평균 스페어 개수, 스페어 값을 넣으면 비용에 더해요. "
                     "sold=true는 판매 완료 체결가(시세), false는 판매 중 호가. 비용은 평균 기대값이고 지금 템 판매 대금은 빼지 않았어요.")}


def roadmap(snap: CharacterSnapshot, defense: float, cooldown_main_pct: float | None = None,
            observed: list[dict] | None = None, miracle: bool = False) -> dict:
    """전체 부위 로드맵: 부위마다 잠재·에디 등급별 단계와 각 단계의 보스 실딜 상승."""
    from engine.market.recommend import roadmap as build
    from engine.market.recommend import value_ranking
    b = boss(defense)
    chosen = rank_settings(snap, b, CATALOG)[0][0]
    rm = build(snap, chosen, b, CATALOG, cooldown_main_pct, observed, miracle=miracle)
    rows = [{"slot": slot, **row} for slot, row in rm.items()]
    value = [{**v, "cube_cost_text": meso_text(v["cube_cost"])} for v in value_ranking(rm)]
    cd, cd_note = _cooldown(snap, cooldown_main_pct)
    return {"evaluation_setting": asdict(chosen), "boss": asdict(b), "cooldown_main_pct": cooldown_main_pct,
            "cooldown": cd, "slots": rows, "value_ranking": value,
            "value_note": ("가격 대비 순위: 메소 재설정(윗잠=블랙 큐브, 에디=화이트 에디셔널 큐브)으로 그 단계까지 가는 평균 비용 "
                           "(등급 상승·천장 포함)과 억당 실딜 상승률. 도달 확률은 줄별 기여를 더해 비교한 근사예요. "
                           "경매장에서 그 단계 템을 이보다 싸게 사면 그쪽이 이득이에요 — 화면 매물 평가로 비교하세요."),
            "market_note": (f"관측 시세: 지금까지 화면 분석으로 읽은 매물 {len(observed or [])}건 중 같은 부위·스타포스 이상·"
                            "그 단계 줄을 모두 갖춘 매물의 가격(최근 30일). 다른 옵션(스타포스·추옵·다른 쪽 잠재)은 "
                            "다를 수 있어 참고용이에요."),
            "note": ("각 단계 = 그 등급에서 흔한 줄(확률 2% 이상, 이탈 제외)로 2줄·3줄을 맞춘 경우예요. probability는 큐브 한 번에 "
                     "그 조합이 나올 확률(참고)이에요. route가 '큐브'인 부위(제네시스 무기 등)는 경매장에서 살 수 없어요. "
                     + cd_note)}


_SCOUTER_ATTACK = {"MATK": "마력", "ATK": "공격력"}


def scouter_delta(snap: CharacterSnapshot, setting, slot: str, new_item) -> dict:
    """환산 계산기(MapleScouter) 입력칸 기준 변화량: slot을 new_item으로 바꿨을 때 스탯 출처 합(장비·세트 등)의 차이.
    칸 이름 그대로(INT|기본, INT|%, 마력|기본, 보스 데미지 …). 방무는 곱연산이라 더해진·빠진 줄을 따로(ied_add/ied_remove)."""
    from collections import Counter
    from engine.market.recommend import cooldown_seconds
    from engine.stats.residual import preset_items, sources_for
    job = job_profile(snap.character_class)
    before = preset_items(snap, setting.equipment)
    after = {**before, slot: new_item}
    sa, sb = sources_for(snap, setting, CATALOG, after), sources_for(snap, setting, CATALOG, before)
    a, b = sa.pct, sb.pct  # % 적용 출처(장비·세트·칭호·링크·유니온) — 템 교체는 여기만 바뀐다
    flat = lambda blk, k: blk.flat.get(k, 0.0)  # noqa: E731
    pct = lambda blk, k: blk.pct.get(k, 0.0)  # noqa: E731
    r = lambda x: round(x, 4)  # noqa: E731
    fields = {}
    for m in list(job.mains) + list(job.subs):
        fields[f"{m}|기본"] = r(flat(a, m) - flat(b, m))
        fields[f"{m}|%"] = r(pct(a, m) - pct(b, m))
        fields[f"{m}|% 미적용"] = r(flat(sa.nopct, m) - flat(sb.nopct, m))  # 하이퍼·어빌·심볼(템 교체로는 0)
    atk = _SCOUTER_ATTACK[job.attack]
    fields[f"{atk}|기본"] = r(flat(a, job.attack) - flat(b, job.attack))
    fields[f"{atk}|%"] = r(pct(a, job.attack) - pct(b, job.attack))
    fields.update({"데미지": r(a.dmg - b.dmg), "보스 데미지": r(a.boss - b.boss), "최종 데미지": r(a.fd - b.fd),
                   "크리티컬 확률": r(a.cr - b.cr), "크리 데미지": r(a.cd - b.cd)})
    old = before.get(slot)
    fields["초"] = (cooldown_seconds(new_item) - (cooldown_seconds(old) if old else 0))
    ca, cb = Counter(a.ied), Counter(b.ied)
    return {"slot": slot, "from": old.name if old else None, "to": new_item.name, "fields": fields,
            "job": snap.character_class, "level": snap.level, "name": (snap.profile or {}).get("name"),
            "ied_add": sorted((ca - cb).elements()), "ied_remove": sorted((cb - ca).elements()),
            "rows": {"main": list(job.mains), "sub": list(job.subs), "attack": atk}}
