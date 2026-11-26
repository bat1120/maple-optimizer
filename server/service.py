"""엔진 호출을 API 응답 형태로 묶는다. 계산은 전부 engine이 한다."""
from dataclasses import asdict

from engine.market.listing import DEFAULT_FEE_RATE, Listing, NoDamage, item_from_input, net_resale, rank_listings
from engine.market.recommend import cooldown_seconds
from engine.stats.evaluate import evaluate_setting, rank_settings
from engine.stats.formula import stat_attack_max
from engine.stats.jobs import job_profile
from engine.stats.metrics import BossProfile
from engine.stats.sets import SetCatalog
from engine.stats.snapshot import CharacterSnapshot, Setting

CATALOG = SetCatalog.load()


def boss(defense: "float | BossProfile") -> BossProfile:
    """방어율 숫자(예전 boss_defense) 또는 이미 고른 BossProfile(보스 목록 id, choose)."""
    if isinstance(defense, BossProfile):
        return defense
    return BossProfile(f"방어율 {defense:g}%", defense)


# 계산 기준 고지(2026-10-17 점검) — 추천 화면마다 붙인다
BASIS_NOTE = ("실딜은 넥슨 스탯창(버프·도핑 없음) 기준이에요. 보스전 버프·도핑이 빠져 있어 방어율 무시·크리티컬 데미지 가치가 "
              "버프를 켠 기준(MapleScouter 등)보다 크게 나올 수 있어요. 크리티컬 확률은 스탯창 값을 하한으로 봐요.")
LOW_ARMOR = 0.5  # 방어율 계수(1 − 방어율×(1 − 방무))가 이보다 작으면 방무 줄 가치가 크게 부풀어 경고


def _basis_warning(snap, setting, b) -> str | None:
    from engine.stats.evaluate import predict_setting
    pred = predict_setting(snap, setting, CATALOG)
    armor = max(0.0, 1 - b.defense / 100 * (1 - pred.ied / 100))
    if armor >= LOW_ARMOR:
        return None
    return (f"이 캐릭터는 스탯창 방어율 무시가 {pred.ied:.1f}%라, 방어율 {b.defense:g}% 보스에서 들어가는 피해가 {armor * 100:.0f}%뿐이에요. "
            "이럴 때는 방어율 무시 줄 하나의 가치가 아주 크게 계산돼요 — 버프·도핑으로 오르는 방어율 무시가 빠진 값이라 "
            "실제보다 과장됐을 수 있으니, 방무 위주 추천은 환산 사이트로 한 번 더 확인해 주세요.")


def no_damage_text(snap, defense: float) -> str | None:
    """이 보스 방어율에 피해가 아예 안 들어가는 캐릭터면 안내 문구, 아니면 None.
    2026-11-24 직업별 측정: 계정의 200레벨 캐릭터 19개 직업이 방어율 300%에서 실딜 지수 0 → 추천 API가 전부 500이었다."""
    defense = getattr(defense, "defense", defense)       # 숫자 또는 BossProfile
    armor = 1 - defense / 100 * (1 - snap.final.ied / 100)
    if armor > 0:
        return None
    need = (1 - 100 / defense) * 100
    return (f"이 캐릭터는 방어율 무시가 {snap.final.ied:.1f}%라, 방어율 {defense:g}% 보스에는 피해가 들어가지 않아요"
            f"({need:.1f}%를 넘어야 해요). 지금 잡는 보스에 맞게 위의 보스 방어율을 낮추면 추천이 나와요.")


def with_basis(fn):
    """추천 결과(note·evaluation_setting·boss가 있는 dict)에 계산 기준 고지와 낮은 방어율 계수 경고를 붙인다."""
    import functools

    @functools.wraps(fn)
    def wrapper(snap, defense, *args, **kwargs):
        try:
            r = fn(snap, defense, *args, **kwargs)
        except ZeroDivisionError:
            text = no_damage_text(snap, defense)        # 지금 실딜이 0이면 '몇 % 오른다'를 정의할 수 없다
            if text is None:
                raise
            raise NoDamage(text) from None
        r["note"] = f"{r.get('note') or ''} {BASIS_NOTE}".strip()
        r["basis_warning"] = _basis_warning(snap, Setting(**r["evaluation_setting"]), boss(defense))
        return r
    return wrapper


def choose(snap: CharacterSnapshot | None, defense: float, boss_id: str | None = None,
           arcane_force: int | None = None, authentic_force: int | None = None):
    """(스냅샷, 보스). boss_id가 있으면 보스 목록(engine/data/bosses.json)의 방어율·요구 포스, 없으면 방어율 숫자만.
    arcane_force·authentic_force: 사용자가 넣은 총 포스(보스 세팅 기준) — 넣으면 API 값 대신 쓴다(하이퍼 프리셋 보정 없이).
    없는 보스 id면 KeyError."""
    import dataclasses
    from engine.stats.force import boss as listed
    b = listed(boss_id) if boss_id else boss(defense)
    if snap is not None and (arcane_force is not None or authentic_force is not None):
        snap = dataclasses.replace(
            snap, arcane_force=snap.arcane_force if arcane_force is None else arcane_force,
            authentic_force=snap.authentic_force if authentic_force is None else authentic_force,
            hyper_force=snap.hyper_force if arcane_force is None else {})
    return snap, b


def force_of(snap: CharacterSnapshot, setting: Setting, b: BossProfile) -> dict | None:
    """화면 표시: {'kind', 'required', 'current', 'damage_pct'} — 요구 포스 없는 보스는 None."""
    from engine.stats.force import character_force, force_info
    return force_info(b, character_force(snap, setting))


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
                                        "level": it.level, "special_ring_level": it.special_ring_level, "stats": it.tip_stats}
                                       for it in items.values()]
                              for n, items in snap.equipment_presets.items() if items},
        "excluded": sorted(set(snap.excluded)),
        "baseline": _baseline(snap),
    }


def _baseline(snap: CharacterSnapshot) -> dict | None:
    """버프 없는 기준을 썼는지(화면이 알려 줄 수 있게). 기준이 없으면 None."""
    if not snap.floors:
        return None
    from engine.stats.residual import FLOOR_KEYS, _raw_calibrate
    pending = bool(snap.floors.get("pending"))
    raw = _raw_calibrate(snap, CATALOG)
    lowered = [k for k in FLOOR_KEYS if k in snap.floors and getattr(raw, k) > snap.floors[k] + 1e-9]
    return {"pending": pending, "buffed": bool(lowered), "lowered": lowered,
            "note": ("접속을 끝낼 때 버프가 켜져 있던 스탯창이라, 버프가 없던 날 기준으로 계산했어요." if lowered else
                     "최근 며칠의 스탯창을 불러와 버프가 섞였는지 확인하는 중이에요." if pending else
                     "최근 며칠의 스탯창과 비교해 버프가 섞이지 않은 것을 확인했어요.")}


FREE_AXES = ("equipment", "hyper", "ability", "union", "link")


def free_breakdown(snap: CharacterSnapshot, top: Setting, b: BossProfile) -> list[dict]:
    """'먼저 무료로' 상승폭을 축별로: top이 지금 착용과 다른 축마다 그 축만 바꿨을 때의 실딜(큰 순).
    2026-11-16 사용자: +84.7%를 보고 장비가 빠져서인 줄 알았다 — 실제론 장비 +2.7%, 하이퍼·유니온이 +35%씩."""
    from dataclasses import replace
    active = snap.active_setting
    base = evaluate_setting(snap, active, b, CATALOG)
    if base <= 0:
        return []
    rows = [{"axis": ax, "from": getattr(active, ax), "to": getattr(top, ax),
             "relative_to_active": evaluate_setting(snap, replace(active, **{ax: getattr(top, ax)}), b, CATALOG) / base}
            for ax in FREE_AXES if getattr(top, ax) is not None and getattr(top, ax) != getattr(active, ax)]
    return sorted(rows, key=lambda x: x["relative_to_active"], reverse=True)


def settings(snap: CharacterSnapshot, defense: float) -> dict:
    from engine.stats.evaluate import predict_setting
    from engine.stats.residual import preset_items
    from engine.stats.metrics import equivalent_main_stat
    b = boss(defense)
    ranked = rank_settings(snap, b, CATALOG)
    active = evaluate_setting(snap, snap.active_setting, b, CATALOG)
    base = predict_setting(snap, snap.active_setting, CATALOG)
    job = job_profile(snap.character_class)
    # 화면 기본 = 보스 세팅(2026-10-17 사용자: 처음 들어가면 보스 최적 세팅으로). 1위 조합의 예측 최종 스탯·스공
    top, top_index = ranked[0]
    pred = predict_setting(snap, top, CATALOG)
    weapon = preset_items(snap, top.equipment)["무기"].part
    best = {"setting": asdict(top), "stat_attack": stat_attack_max(pred, job, weapon),
            "final": {"stats": pred.stats, "atk": pred.atk, "matk": pred.matk, "dmg": pred.dmg, "boss": pred.boss,
                      "fd": pred.fd, "cd": pred.cd, "ied": pred.ied}}
    return {"boss": asdict(b), "force": force_of(snap, ranked[0][0], b), "best": best,
            "free_breakdown": free_breakdown(snap, top, b),
            # 2026-11-26 사용자: 전부 보스 세팅 기준 — 지금 착용(사냥용일 수 있다)이 아니라 1위 조합과 비교한 값을 같이 준다
            "ranking": [{"setting": asdict(s), "index": v, "relative_to_active": v / active if active > 0 else None,
                         "main_stat_vs_active": equivalent_main_stat(base, job, v / active) if active > 0 else None,
                         "relative_to_best": v / top_index if top_index > 0 else None,
                         "main_stat_vs_best": equivalent_main_stat(pred, job, v / top_index) if top_index > 0 else None}
                        for s, v in ranked]}


def meso_text(v: float | None) -> str | None:
    """메소 → "327억 9999만". 만 미만은 버린다(답변에 그대로 인용하도록 도구 결과에 싣는다)."""
    if v is None:
        return None
    eok, man = int(v // 100_000_000), int(v % 100_000_000 // 10_000)
    return " ".join(p for p in (f"{eok}억" if eok else "", f"{man}만" if man else "") if p) or f"{int(v)}"


_NO_TOTAL = "총 옵션이 없어 평가하지 않았어요 — 툴팁 윗부분이 보이게 띄워 주세요"


def _resale(snap: CharacterSnapshot, setting: Setting, slot: str, resale: float) -> tuple[float, str | None]:
    """지금 그 부위 템을 팔 수 없으면(PC방 템, 2026-10-17) 판매 대금 0과 안내 문구."""
    from engine.enhance.fixed import cannot_sell
    from engine.stats.residual import preset_items
    cur = preset_items(snap, setting.equipment).get(slot)
    why = cannot_sell(cur) if cur is not None else None
    return (0, why) if why and resale else (resale, why)


def listings(snap: CharacterSnapshot, setting: Setting | None, defense: float, inputs: list,
             fee_rate: float = DEFAULT_FEE_RATE) -> dict:
    if not 0 <= fee_rate <= 0.1:
        raise ValueError(f"수수료율은 0~0.1 사이여야 해요(5%면 0.05): {fee_rate}")
    b = boss(defense)
    chosen = setting or rank_settings(snap, b, CATALOG)[0][0]
    # 총 옵션 없이 평가하면 기본 스탯 0인 템처럼 계산돼 큰 음수가 나온다(2026-10-04 실사용 -19.5%) → 보류
    held = [{"name": x.name, "price_text": meso_text(x.price), "reason": _NO_TOTAL} for x in inputs if not x.total]
    notes = {}
    built = []
    for x in inputs:
        if not x.total:
            continue
        resale, why = _resale(snap, chosen, x.slot, x.resale)
        if why:
            notes[x.slot] = why
        built.append(Listing(x.slot, item_from_input(x.slot, x.part, x.name, x.total, x.potentials, snap.level, x.starforce),
                             x.price, resale, fee_rate))
    ranked = rank_listings(snap, chosen, built, b, CATALOG) if built else []
    return {"setting": asdict(chosen), "boss": asdict(b), "force": force_of(snap, chosen, b), "held": held, "fee_rate": fee_rate,
            "fee_note": "판매 수수료는 사는 가격엔 붙지 않고, 지금 템 판매 대금(resale)에서만 빠져요.",
            "ranking": [{"slot": e.listing.slot, "name": e.listing.item.name, "price": e.listing.price,
                         "price_text": meso_text(e.listing.price),
                         "cooldown_s_not_valued": cooldown_seconds(e.listing.item),  # 실딜 계산에 안 들어간 쿨감 초
                         "resale": e.listing.resale, "net_resale": net_resale(e.listing.resale, fee_rate),
                         "net_cost": e.listing.price - net_resale(e.listing.resale, fee_rate),
                         "net_cost_text": meso_text(e.listing.price - net_resale(e.listing.resale, fee_rate)),
                         "delta_pct": e.delta_pct, "per_100m": e.per_100m,
                         "main_stat_gain": e.main_stat_gain, "main_stat_gain_per_100m": e.main_stat_gain_per_100m,
                         "excluded": e.listing.item.excluded,
                         **({"resale_note": notes[e.listing.slot]} if e.listing.slot in notes else {})} for e in ranked]}


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
                      x.price - net_resale(_resale(snap, chosen, x.slot, x.resale)[0], fee_rate), x.name) for x in candidates]
    plan = greedy(Evaluator(snap, chosen, b, CATALOG), actions, budget)
    return {"setting": asdict(chosen), "budget": budget, "spent": plan.spent, "gain_pct": plan.gain_pct,
            "actions": [{"slot": a.slot, "name": a.item.name, "cost": a.cost} for a in plan.actions]}


def _set_change(snap: CharacterSnapshot, setting: Setting, slot: str, item) -> list[dict]:
    """그 자리 템을 item으로 바꿀 때 개수가 달라지는 세트와, 그 때문에 사라지거나 켜지는 단계의 효과 문장."""
    from engine.stats.residual import preset_items
    from engine.stats.sets import count_sets
    worn = preset_items(snap, setting.equipment)
    branches = job_profile(snap.character_class).branches
    before = count_sets(list(worn.values()), branches, CATALOG)
    after = count_sets([item if s == slot else it for s, it in worn.items()] + ([] if slot in worn else [item]), branches, CATALOG)
    out = []
    for name in sorted(set(before) | set(after)):
        b, a = before.get(name, 0), after.get(name, 0)
        if a == b:
            continue
        tiers = {int(n): text for n, text in (CATALOG.tiers.get(name) or {}).items()}
        out.append({"set": name, "before": b, "after": a,
                    "lost": [" ".join(str(tiers[n]).split()) for n in sorted(tiers) if a < n <= b],
                    "gained": [" ".join(str(tiers[n]).split()) for n in sorted(tiers) if b < n <= a]})
    return out


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
        if not x.get("special_ring_level"):  # 일반 반지 매물은 특수 반지 칸에 넣지 않는다(2026-10-11)
            from engine.stats.residual import preset_items
            worn = preset_items(snap, chosen.equipment)
            slots = tuple(s for s in slots if not (worn.get(s) and worn[s].special_ring_level))
            if not slots:
                row["reason"] = "반지 칸이 모두 특수 반지예요 — 특수 반지 스킬 효과는 실딜에 없어서 일반 반지와 바꾸는 평가는 하지 않아요"
                out.append(row)
                continue
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
            row["scouter"] = scouter_delta(snap, chosen, slot, item)  # 사람이 읽는 변화량(변화량 복사 버튼)
        except Exception:  # noqa: BLE001 — 변화량을 못 구해도 평가는 보여 준다
            row["scouter"] = None
        # 세트 효과 변화: 옵션만 보면 좋아 보이는 매물이 낮게 나오는 까닭(2026-11-26 실사용 — 에스텔라를 데아 시두스로 바꾸면
        # 여명 3세트가 깨져 올스탯·마력이 빠지는데 화면에는 숫자만 있어 계산이 맞는지 알 수 없었다)
        row["set_change"] = _set_change(snap, chosen, slot, item)
        row.update({"evaluated": True, "slot": slot, "setting": asdict(chosen), "delta_pct": delta,
                    "main_stat_gain": gain, "excluded": item.excluded,
                    "per_100m": (delta / (price / 1e8)) if (delta is not None and price) else None})
        out.append(row)
    return out


@with_basis
def target_roadmap(snap: CharacterSnapshot, defense: float, observed: list[dict] | None, current_ratio: float,
                   target_ratio: float, events=None, budget: float | None = None, flames: bool = False,
                   max_steps: int = 120) -> dict:
    """목표 배율 로드맵 + 사람이 읽는 장비 변화량(변화량 복사: 큐브·스타포스·HEXA 스탯·심볼. HEXA 코어는 칸이 없어 빠진다)."""
    from engine.market.events import Events
    from engine.market.hexa_paths import _block, _lines
    from engine.market.symbol_paths import extra_of
    from engine.market.target_roadmap import target_roadmap as build
    from engine.stats.model import StatBlock
    from engine.stats import hexa as H
    events = events or Events()
    b = boss(defense)
    chosen = rank_settings(snap, b, CATALOG)[0][0]
    r = build(snap, chosen, b, CATALOG, events, observed or [], current_ratio, target_ratio, max_steps=max_steps, budget=budget, flames=flames)
    job = job_profile(snap.character_class)
    extra = None
    for core in snap.hexa_stat:
        lv = r["hexa_stat"].get(core["core"])
        if lv:
            sub_lv = (H.MAX_G - lv) / 2
            d = H.delta(_block(_lines(core, lv, (sub_lv, sub_lv)), job), _block(core["lines"], job))
            extra = d if extra is None else {k: extra[k] + d[k] for k in ("pct", "nopct")}
    sym_stat: dict = {}  # 심볼 단계로 늘어난 주스탯(%미적용) — MapleScouter '% 미적용' 칸
    for s in r["steps"]:
        if s["path"] == "심볼":
            for k, v in s["stat_gain"].items():
                sym_stat[k] = sym_stat.get(k, 0.0) + v
    if sym_stat:
        d = extra_of(sym_stat)
        extra = {"pct": StatBlock(), **d} if extra is None else {"pct": extra["pct"], "nopct": extra["nopct"] + d["nopct"]}
    steps = [{**s, "cost_text": meso_text(s["cost"]), "total_cost_text": meso_text(s["total_cost"])} for s in r["steps"]]
    eq = sum(1 for s in r["steps"] if s["path"] in ("큐브", "스타포스", "HEXA 스탯", "심볼"))
    scouter = (scouter_delta_multi(snap, chosen, r["changed"], extra, label=f"목표 {target_ratio:g}% 로드맵")
               if (r["changed"] or extra) else None)
    hexa_core = [s for s in r["steps"] if s["path"] == "HEXA 코어"]
    mult_core = 1.0
    for s in hexa_core:
        mult_core *= 1 + s["delta_pct"] / 100
    return {"evaluation_setting": asdict(chosen), "boss": asdict(b), "force": force_of(snap, chosen, b),
            "events": {**asdict(events), "label": events.label()},
            "current_ratio": current_ratio, "target_ratio": target_ratio, "needed_multiplier": r["needed_multiplier"],
            "reached": r["reached"], "final_ratio": r["final_ratio"], "total_cost": r["total_cost"],
            "total_cost_text": meso_text(r["total_cost"]), "steps": steps, "equipment_steps": eq,
            "scouter": scouter, "hexa_core_multiplier": mult_core, "skipped_first": r["skipped_first"],
            "cube_candidates": r["cube_candidates"],
            "note": ("스페어 값·썬데이 이벤트·추옵(환생의 불꽃)은 아직 로드맵에 넣지 않아요 — 실제 비용은 이보다 클 수 있어요. "
                     "배율은 실딜 %만큼 비례해서 오른다고 본 추정이에요(레벨 보정은 그대로, 포스 보정은 고른 보스의 요구 포스로 계산 — 심볼로 포스가 오르면 실딜에 들어가요). 스타포스는 한 성씩, 심볼은 한 레벨씩 이어서"
                     "(심볼 비용은 강화 메소만 — 심볼 개수는 단계마다 따로), "
                     "큐브·HEXA는 부위·코어마다 한 단계. 경매장 구매는 넣지 않았어요. 변화량 복사에는 HEXA 코어가 빠져요"
                     "(입력칸이 없어요) — 그 몫은 hexa_core_multiplier.")}


MIN_BUDGET = 10_000  # 이보다 작은 예산은 '50억'을 50으로 넣은 단위 실수다
PLAN_STEPS = 16  # 메소를 넣지 않았을 때 계산하는 단계 수(화면은 앞의 몇 줄과 경매장에서 살 수 있는 첫 줄을 보여 준다)
_BUDGET_STEP = ("slot", "path", "name", "kind", "grade", "lines_good", "target", "flame", "from_star", "to_star", "from_level", "to_level",
                "cost_text", "delta_pct", "per_100m", "total_cost_text")


def budget_roadmap(snap: CharacterSnapshot, defense: float, observed: list[dict] | None, budget: float | None = None,
                   steps: int | None = None) -> dict:
    """업그레이드 계획 하나(2026-11-23 사용자: 계획 하나로 합친다). 목표 배율 로드맵 엔진의 예산 모드 —
    억당 효율 순으로 쌓는다(추옵 재설정 포함). budget(가진 메소)이 있으면 남은 돈으로 못 하는 단계는 건너뛰어 예산을 채우고,
    없으면 효율 순서 앞의 steps개(기본 PLAN_STEPS). 큐브 단계에는 route(경매장에서 살 수 있는 템인지)를 붙인다."""
    if budget is not None and (not isinstance(budget, (int, float)) or budget < MIN_BUDGET):
        raise ValueError(f"budget은 메소 정수다(50억 → 5000000000). {budget}는 억·만 단위로 넣은 것 같다 — 메소로 다시 넣는다")
    from engine.market.recommend import _route
    from engine.stats.residual import preset_items
    limit = max(1, min(int(steps), 120)) if steps else (120 if budget is not None else PLAN_STEPS)
    r = target_roadmap(snap, defense, observed, 100.0, 1e9, None, budget=budget, flames=True, max_steps=limit)
    worn = preset_items(snap, r["evaluation_setting"]["equipment"])

    def brief(s):
        out = {k: s[k] for k in _BUDGET_STEP if s.get(k) is not None}
        if s["path"] == "큐브" and worn.get(s["slot"]) is not None:
            out["route"] = _route(worn[s["slot"]], snap.character_class)  # '경매장' = 사서 바꿀 수 있다, '큐브' = 지금 템에 큐브만
        return out

    done, spent, skipped = r["steps"], r["total_cost"], r["skipped_first"]
    # 경매장에서 찾는다면: 살 수 있는 큐브 후보 중 억당이 가장 좋은 것(계획에 이미 있어도 준다 — 화면이 겹치면 안 그린다)
    auction = next((b for b in (brief(c | {"cost_text": meso_text(c["cost"])}) for c in r["cube_candidates"]) if b.get("route") == "경매장"), None)
    return {"evaluation_setting": r["evaluation_setting"], "boss": r["boss"], "basis_warning": r.get("basis_warning"),
            "budget": budget, "budget_text": meso_text(budget) if budget is not None else None,
            "steps": [brief(s) | {"gain_pct_after": (s["multiplier"] - 1) * 100} for s in done],
            "spent_text": (meso_text(spent) if spent else "0"),
            "left_text": meso_text(budget - spent) if budget is not None else None,
            "gain_pct": (done[-1]["multiplier"] - 1) * 100 if done else 0.0,
            "auction_pick": auction,
            "next_step": None if skipped is None else (
                brief(skipped | {"cost_text": meso_text(skipped["cost"])})
                | {"short_text": meso_text(skipped["cost"] - (budget - spent))}),
            "note": ("억당 효율이 높은 단계부터 쌓았어요. 가진 메소를 넣으면 남은 돈으로 못 하는 단계는 건너뛰어 그다음 효율 단계로 예산을 채워요 — "
                     "next_step은 건너뛴 단계 중 효율이 가장 높은 것, short_text는 그 단계를 하려면 더 필요한 금액이에요. "
                     "비용은 평균 기대값이라 실제로는 더 들거나 덜 들 수 있어요. 추옵은 목표 이상에서 멈췄을 때의 평균 상승(근사)이에요. "
                     "큐브 단계의 비용은 내 템에 큐브를 직접 돌릴 때의 평균이에요 — 경매장에 그 옵션 매물이 이보다 싸면 사는 쪽이 이득이에요. "
                     "스타포스 스페어 값·이벤트 할인·경매장 구매는 들어 있지 않아요 — 매물은 화면으로 받아 따로 평가해요.")}


def _total_key(total: dict | None) -> tuple:
    """총 옵션 비교용: 값이 있는 칸만, 정렬해서."""
    return tuple(sorted((k, v) for k, v in (total or {}).items() if v))


def _cooldown(snap: CharacterSnapshot, cooldown_main_pct: float | None, setting=None, b=None) -> tuple[dict, str]:
    """쿨감을 어떻게 반영했는지(출처 포함)와 안내 문구. 최종뎀 단위 출처는 이 캐릭터 기준 주스탯%도 같이 적는다."""
    from engine.market.recommend import _Planner, cooldown_valuer
    _, src = cooldown_valuer(snap.character_class, cooldown_main_pct)
    if src["kind"] == "table_fd" and setting is not None:
        src = _Planner(snap, setting, b, CATALOG, cooldown_main_pct).cooldown_source
    if src["kind"] == "manual":
        return src, f"쿨감 1초를 주스탯 {cooldown_main_pct:g}%로 환산했어요(직접 입력)."
    if src["kind"] == "table":
        steps = "·".join(f"{s}초 {v:g}%" for s, v in sorted(src["cumulative"].items()))
        return src, (f"{src['job']} 쿨감: {steps}({src['unit']}, 출처 {src['source']} · {src['date']}). "
                     "표에 없는 초수는 반영하지 않아요(계단식이라 짐작하지 않아요).")
    if src["kind"] == "table_fd":
        conv = src.get("converted", {})
        if "per_sec" in src:
            fd = {s: s * src["per_sec"] for s in conv}
            head = f"1초당 최종뎀 {src['per_sec']:g}%(원문 범위의 낮은 값)"
        else:
            fd = src["cumulative"]
            head = "·".join(f"{s}초 최종뎀 {v:g}%" for s, v in sorted(fd.items()))
        steps = "·".join(f"{s}초 주스탯 {conv[s]:g}%" for s in sorted(conv))
        old = " 오래된 자료(밸런스 패치 전)라 지금과 다를 수 있어요." if src.get("stale") else ""
        return src, (f"{src['job']} 쿨감: {head}(출처 {src['source']} · {src['date']}) → 이 캐릭터 스펙으로 바꾸면 {steps}. "
                     f"원문은 최종뎀 단위이고, 주스탯 환산은 실딜이 같은 만큼 오르는 값으로 엔진이 계산했어요.{old}")
    if src["kind"] == "reference":
        return src, (f"{src['job']} 쿨감은 {src['unit']} 단위 자료만 있어 실딜에 넣지 않았어요({src['source']}). "
                     "쿨감 1초 = 주스탯 몇 %인지 직접 입력하면 넣어요.")
    return src, "이 직업은 출처 있는 쿨감 수치를 못 찾아 실딜에 넣지 않았어요 — 쿨감 1초 = 주스탯 몇 %인지 직접 입력하면 넣어요."


@with_basis
def recommend(snap: CharacterSnapshot, defense: float, top: int = 5, cooldown_main_pct: float | None = None) -> dict:
    """게임 경매장 검색 조건 카드(잠재·에디). 평가는 언제나 보스 실딜 최적 세팅 기준(사냥 세팅이어도).
    제네시스·데스티니 무기처럼 경매장에서 살 수 없는 템은 빠진다(로드맵에서 큐브 경로로 본다)."""
    from engine.market.recommend import combined_searches
    b = boss(defense)
    chosen = rank_settings(snap, b, CATALOG)[0][0]
    cards = []
    # 부위당 카드 하나: 윗잠·에디를 한 번에 검색(2026-10-11). 위쪽 키(kind·grade·target_potentials)는 첫 종류 — 예전 화면 호환
    for c in combined_searches(snap, chosen, b, CATALOG, top=top, cooldown_main_pct=cooldown_main_pct):
        category = c["slot"].rstrip("0123456789") or c["slot"]
        first = c["parts"][0]
        cond = " · ".join(f"{p['kind']} {p['grade']} {' / '.join(p['target'])}" for p in c["parts"])
        cards.append({"slot": c["slot"], "category": category, "kind": "+".join(p["kind"] for p in c["parts"]),
                      "grade": first["grade"], "lines_good": first["lines_good"], "target_potentials": first["target"],
                      "parts": c["parts"], "min_starforce": c["min_starforce"], "delta_pct": c["delta_pct"],
                      "probability": first["probability"], "kept": [k for p in c["parts"] for k in p["kept"]],
                      "search": f"{category} · {cond} · {c['min_starforce']}성 이상",
                      "current": {"name": c["current_name"], "starforce": c["min_starforce"],
                                  "potentials": next((p["current"] for p in c["parts"] if p["kind"] == "잠재"), []),
                                  "additional": next((p["current"] for p in c["parts"] if p["kind"] == "에디"), [])}})
    cd, cd_note = _cooldown(snap, cooldown_main_pct, chosen, b)
    return {"evaluation_setting": asdict(chosen), "boss": asdict(b), "force": force_of(snap, chosen, b),
            "recommendations": cards,
            "cooldown_main_pct": cooldown_main_pct, "cooldown": cd,
            "note": ("부위마다 잠재·에디를 한 번에 검색하는 카드예요. 각각 지금보다 한 단계 위(실딜이 0.1% 이상 처음 오르는 등급·줄 수)를 골랐고, "
                     "카드 실딜은 둘을 함께 바꾼 값이에요(종류별 실딜은 카드 안에). "
                     "줄 수치는 공식 큐브 확률표의 흔한 줄(확률 2% 이상, 이탈 제외)이고, 그 줄만 바꾼 같은 템 기준이에요. "
                     "쿨감 줄은 유지해요 — " + cd_note)}


@with_basis
def paths(snap: CharacterSnapshot, defense: float, observed: list[dict] | None = None,
          cooldown_main_pct: float | None = None, top: int = 30, events=None) -> dict:
    """업그레이드 경로 비교: 구매·직작·지금 템 큐브·스타포스·추옵·HEXA·심볼을 억당 실딜로(세트 효과 반영)."""
    from engine.market.paths import balanced, upgrade_paths
    b = boss(defense)
    chosen = rank_settings(snap, b, CATALOG)[0][0]
    from engine.market.events import Events
    events = events or Events()
    r = upgrade_paths(snap, chosen, b, CATALOG, observed, cooldown_main_pct, events)
    fmt = lambda ps: [{**p, "cost_text": meso_text(p["cost"])} for p in ps]  # noqa: E731
    # 딜 지분 자료가 없는 직업은 HEXA 코어 경로가 조용히 빠졌다(2026-10-17 점검) — 빠졌다고 알린다
    from engine.market.hexa_core_paths import job_shares
    hexa_note = ("HEXA 코어 = 이 직업은 딜 지분 자료가 없어(연무장 기록·직업 기준값 모두 없음) 계산하지 않았어요. "
                 if snap.hexa_cores and not snap.own_shares and not (job_shares(snap.character_class) or {}).get("shares") else "")
    return {"evaluation_setting": asdict(chosen), "boss": asdict(b), "force": force_of(snap, chosen, b),
            "events": {**asdict(events), "label": events.label()},
            "all": fmt(balanced(r["all"], max(1, top // 4))),
            "best_by_slot": fmt(r["best_by_slot"]), "observed_count": len(observed or []),
            "note": (hexa_note + "구매 = 관측 매물을 그대로 끼운 실딜(세트 개수를 다시 세서 세트 효과 변화 포함, set_change), 다른 월드 매물은 +10%. "
                     "직작 = 관측 매물 가격 + 그 매물 등급에서 단계까지 메소 재설정 평균. 큐브 = 지금 템에 메소 재설정 평균. "
                     "스타포스 = 지금 템을 목표 성까지 메소 기대값(강화 + 흔적 복구 메소, 고른 이벤트 반영). 파괴되면 같은 장비가 복구에 필요해요"
                     "(18성 이하 1개·19~20성 2개·21성 3개·22성 이상 4개) — expected_spares가 평균 스페어 개수, 스페어 값을 넣으면 비용에 더해요. "
                     "추옵 = 지금 템 추옵을 메소 재설정(공식 1회 300만 메소, 검은 환생의 불꽃과 같은 확률) 또는 가격을 넣은 "
                     "환생의 불꽃으로 목표 이상이 나올 때까지 — 비용 = 1개 값 × 평균 횟수, 실딜 = 목표 이상에서 멈췄을 때 평균 − 지금. "
                     "추옵 점수는 줄마다 실딜 기울기를 더한 근사이고, 보스 장비로 확인되는 템(보스 장신구·여명·칠흑·광휘·루타비스·"
                     "앱솔랩스·아케인셰이드·마이스터·제네시스 무기)만 계산해요. "
                     "심볼 = 아케인·어센틱 심볼을 다음 레벨부터 최대 레벨까지 — 비용은 강화 메소(나무위키 성장표), 심볼은 거래 불가라 "
                     "비용에 넣지 않고 필요 개수·지금 성장치로 남은 개수·일일 퀘스트 기준 날짜를 따로 줘요. 보스 목록에서 요구 포스가 있는 보스를 고르면 "
                     "심볼로 오르는 포스(force_gain)만큼 포스 보정(나무위키 격차별 피해 비율)이 바뀐 몫도 실딜에 넣어요(force_after). "
                     "11레벨 지역 보스 데미지 +20%는 최종뎀인지 데미지%인지 출처가 없어 실딜에 넣지 않았어요(max_effect에 문구만). "
                     "그랜드 어센틱심볼은 주스탯이 없어 어센틱 보스를 골랐을 때만 포스 몫으로 나와요. "
                     "sold=true는 판매 완료 체결가(시세), false는 판매 중 호가. 비용은 평균 기대값이고 지금 템 판매 대금은 빼지 않았어요.")}


@with_basis
def swaps(snap: CharacterSnapshot, defense: float, cooldown_main_pct: float | None = None, per_slot: int = 3,
          starforce: int | None = 18) -> dict:
    """다른 템으로 갈아타기(2026-11-13): 부위마다 다른 템(다른 세트)을 끼면 실딜이 어떻게 되는지와 손익분기."""
    from engine.market.swaps import swap_candidates
    b = boss(defense)
    chosen = rank_settings(snap, b, CATALOG)[0][0]
    rows = swap_candidates(snap, chosen, b, CATALOG, cooldown_main_pct, per_slot=per_slot, starforce=starforce)
    return {"evaluation_setting": asdict(chosen), "boss": asdict(b), "force": force_of(snap, chosen, b), "swaps": rows,
            "starforce": starforce,
            "note": ("다른 템으로 갈아탔을 때의 보스 실딜(지금 = 0%). 세트 개수를 템 이름으로 다시 세서 세트 효과 변화가 들어가요(set_change). "
                     "그 템의 기본 옵션·주문서 칸 수·추옵은 넥슨 API 실측(그 템을 낀 캐릭터들의 장비)이고, 스타포스는 성별 표예요. "
                     "same = 바꿀 템은 고른 스타포스(그 템 최대 성 이하), 잠재·에디·추옵 수치·주문서(칸 수 비율)는 지금 템 그대로 옮겼을 때. "
                     "flame = 추옵만 그 템 착용자들의 실제 추옵으로 바꿔 본 분포(better_share = 지금보다 나은 비율). "
                     "potential.break_even = 그 템에 그 잠재 단계(이상)를 띄우면 처음으로 지금보다 나아지는 단계. "
                     "market = 보통 매물 기준: 추옵은 착용자 실측 표본 중 실딜이 가운데인 표본, 에디는 없음 — 그때의 잠재 손익분기(market.break_even). "
                     "레벨이 높은 템은 잠재·추옵 줄 수치가 더 높게 나올 수 있어 same은 보수적이에요. 익셉셔널은 옮기지 않아요. "
                     "경매장에서 살 수 있는지는 확인된 구매 불가 템만 뺐어요.")}


@with_basis
def armor_sets(snap: CharacterSnapshot, defense: float, cooldown_main_pct: float | None = None, starforce: int = 18,
               top: int = 30) -> dict:
    """방어구 세트 조합(2026-11-16 사용자: 카루타·앱솔·아케인·에테르넬을 어떤 조합으로 맞출지 — 3카5앱처럼)."""
    from engine.market.armor_sets import armor_combos, classic_rows
    b = boss(defense)
    chosen = rank_settings(snap, b, CATALOG)[0][0]
    rows = armor_combos(snap, chosen, b, CATALOG, starforce=starforce, cooldown_main_pct=cooldown_main_pct)
    now = next((r for r in rows if all(p["kept"] for p in r["pieces"].values())), None)
    return {"evaluation_setting": asdict(chosen), "boss": asdict(b), "starforce": starforce, "total": len(rows),
            "current": now, "combos": rows[:top], "classics": classic_rows(rows),
            "note": ("방어구 7칸(모자·상의·하의·신발·장갑·망토·어깨)을 지금 템 또는 카루타·앱솔랩스·아케인셰이드·에테르넬 템으로 맞췄을 때의 "
                     "보스 실딜(지금 = 0%). 세트 효과는 무기(제네시스 무기의 행운 효과 포함)까지 넣어 세요. 바꾼 칸은 고른 스타포스(그 템 최대 성 이하), "
                     "잠재·에디·추옵·주문서는 지금 그 칸 템 것을 옮긴다고 가정해요. 템 기본 옵션은 넥슨 API 실측. "
                     "세트 구성(세트별 개수)이 같은 조합끼리는 템 자체 스탯이 가장 좋은 배치 하나만 보여 줘요. 한벌옷(앱솔·아케인 상의)은 아직 없어요.")}


POTENTIAL_LABELS = {"same": "지금 그대로", "legend2": "레전드리 2줄", "legend3": "레전드리 3줄"}


@with_basis
def consult(snap: CharacterSnapshot, defense: float, cooldown_main_pct: float | None = None) -> dict:
    """목표 세팅 컨설팅(2026-11-26 사용자): 메소를 모아 오래 쓸 템들로 한 번에 갈아탈 때의 세팅을 통째로 계산한다.
    성(17·18·21·22)마다 방어구·장신구 세팅 하나와, 살 템 목록·지금 템 강화 비용(평균)·세트 효과 변화를 준다. 템 시세는 없다."""
    from engine.market.consult import consult as consult_builds
    from engine.market.swaps import BASES
    b = boss(defense)
    setting = rank_settings(snap, b, CATALOG)[0][0]
    builds = consult_builds(snap, setting, b, CATALOG, cooldown_main_pct=cooldown_main_pct)
    for o in builds:
        o["raise_cost_text"] = meso_text(o["raise_cost"]) if o["raise_cost"] else None
        for r in o["raise"]:
            r["cost_text"] = meso_text(r["cost"])
        o.pop("_order", None)
        for x in o["buy"]:
            x["set"] = (BASES.get(x["name"]) or {}).get("set")
            x["level"] = (BASES.get(x["name"]) or {}).get("level")
            # 잠재·에디를 지금 그 자리 템 수준으로 큐브로 처음부터 맞추는 평균 비용(상한에 가깝다). None = 계산 못 함, 0 = 맞출 줄 없음
            m = x.pop("match")
            if x.get("goal") and x["goal"]["cost"]:
                x["goal"]["cost_text"] = meso_text(x["goal"]["cost"])
            x["match_cost"] = None if any(v is None for v in m.values()) else sum(m.values())
            x["match_parts"] = {k: (None if v is None else {"cost": v, "text": meso_text(v) if v else "0"}) for k, v in m.items()}
            x["match_text"] = meso_text(x["match_cost"]) if x["match_cost"] else ("0" if x["match_cost"] == 0 else None)
        o["match_cost"] = sum(x["match_cost"] or 0 for x in o["buy"])
        o["match_cost_text"] = meso_text(o["match_cost"]) if o["match_cost"] else None
        o["match_unknown"] = sum(1 for x in o["buy"] if x["match_cost"] is None)
        # 잠재 목표(레전드리 2줄·3줄)를 골랐을 때: 그대로 쓰는 템의 잠재를 지금 등급에서 목표까지 올리는 큐브 평균
        for c in o["cube"]:
            c["cost_text"] = meso_text(c["cost"]) if c["cost"] else None
        o["cube_cost"] = sum(c["cost"] or 0 for c in o["cube"])
        o["cube_cost_text"] = meso_text(o["cube_cost"]) if o["cube_cost"] else None
        o["cube_unknown"] = sum(1 for c in o["cube"] if c["cost"] is None)
        o["potential_label"] = POTENTIAL_LABELS[o["potential"]]
        for c in o["set_change"]:
            tiers = {int(n): text for n, text in (CATALOG.tiers.get(c["set"]) or {}).items()}
            c["lost"] = [" ".join(str(tiers[n]).split()) for n in sorted(tiers) if c["after"] < n <= c["before"]]
            c["gained"] = [" ".join(str(tiers[n]).split()) for n in sorted(tiers) if c["before"] < n <= c["after"]]
    return {"evaluation_setting": asdict(setting), "boss": asdict(b), "builds": builds,
            "note": ("세팅 전체를 한 번에 낀 보스 실딜이에요(지금 보스 세팅 = 0%) — 세트 효과가 같이 바뀌는 것까지 들어 있어요. "
                     "바꿀 템의 기본 옵션은 그 템을 낀 캐릭터들의 넥슨 API 실측이고, 스타포스는 고른 성(그 템 최대 성 이하), "
                     "잠재·에디·추옵·주문서는 지금 그 자리 템과 같은 수준으로 맞춘다고 봤어요. "
                     "잠재 목표를 '레전드리 2줄·3줄'로 고르면 방어구·장신구 칸의 윗잠재를 그 등급의 흔한 좋은 줄(공식 확률표에서 2% 이상인 줄 중 "
                     "실딜이 가장 오르는 조합)로 바꿔 세팅 전체를 다시 계산해요 — 지금 잠재가 이미 그 이상인 칸과 잠재가 없는 칸은 그대로 두고, "
                     "모자의 쿨타임 감소 줄은 남겨요. 큐브 비용은 평균이에요(살 템은 레어에서, 그대로 쓰는 템은 지금 등급에서 시작). "
                     "칸마다 적힌 '+x% · 100억당'은 그 칸의 잠재만 목표로 바꿨을 때의 몫이에요 — 체크를 풀어 그 칸을 빼면 합계는 정확히, "
                     "실딜은 칸별 몫을 빼는 방법으로(그래서 '약') 다시 보여 줘요. "
                     "에디셔널 잠재와 추옵은 어느 목표에서나 지금 그대로예요(환생의 불꽃 가격은 넥슨이 주지 않아 비용을 낼 수 없어요). "
                     "'잠재까지 맞추면'은 살 템에 지금 수준의 잠재·에디를 큐브로 처음부터(레어에서) 맞추는 평균 비용을 더한 값이에요 — "
                     "잠재가 붙은 매물을 사면 그보다 덜 드니 위쪽 한계로 보세요. 추옵·주문서를 맞추는 비용은 들어 있지 않아요. "
                     "지금 템을 그대로 쓰는 자리는 고른 성까지 강화한다고 봤고, 그 비용은 이벤트 없는 평균이에요(파괴 시 스페어 값 제외). "
                     "살 템의 시세는 넥슨이 주지 않아서 직접 넣어야 합계가 나와요. 무기·보조무기·엠블렘·특수 반지는 그대로 둬요.")}


@with_basis
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
    cd, cd_note = _cooldown(snap, cooldown_main_pct, chosen, b)
    return {"evaluation_setting": asdict(chosen), "boss": asdict(b), "force": force_of(snap, chosen, b),
            "cooldown_main_pct": cooldown_main_pct, "cooldown": cd, "slots": rows, "value_ranking": value,
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
    return scouter_delta_multi(snap, setting, {slot: new_item})


def scouter_delta_multi(snap: CharacterSnapshot, setting, changes: dict, extra: dict | None = None,
                        label: str | None = None) -> dict:
    """여러 부위를 한꺼번에 바꾼 변화량(changes: 부위 → 새 템) + 장비 밖 변화(extra: HEXA 스탯 등 {'pct','nopct'})."""
    from collections import Counter
    from engine.market.recommend import cooldown_seconds
    from engine.stats.model import StatBlock
    from engine.stats.residual import Sources, preset_items, sources_for
    job = job_profile(snap.character_class)
    before = preset_items(snap, setting.equipment)
    after = {**before, **changes}
    sa, sb = sources_for(snap, setting, CATALOG, after), sources_for(snap, setting, CATALOG, before)
    if extra:
        sa = Sources(sa.pct + extra.get("pct", StatBlock()), sa.nopct + extra.get("nopct", StatBlock()), sa.excluded)
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
    fields["초"] = sum(cooldown_seconds(it) - (cooldown_seconds(before[s]) if s in before else 0) for s, it in changes.items())
    ca, cb = Counter(a.ied), Counter(b.ied)
    one = len(changes) == 1 and not extra and not label
    slot, new_item = next(iter(changes.items())) if changes else (None, None)
    old = before.get(slot) if one else None
    return {"slot": slot if one else "로드맵", "from": old.name if old else (None if one else "지금 템"),
            "to": new_item.name if one else (label or f"로드맵 {len(changes)}개 부위"), "fields": fields,
            "job": snap.character_class, "level": snap.level, "name": (snap.profile or {}).get("name"),
            "ied_add": sorted((ca - cb).elements()), "ied_remove": sorted((cb - ca).elements()),
            "rows": {"main": list(job.mains), "sub": list(job.subs), "attack": atk}}
