"""목표 세팅 컨설팅(2026-11-26 사용자: 메이플 템 세팅은 한 단계씩이 아니라, 메소를 모아 오래 쓸 템들로 한 번에 갈아타는 것).

한 자리씩 바꾸는 계산(갈아타기)은 세트 효과 때문에 답이 틀어진다 — 귀고리 하나만 다른 세트로 바꾸면 지금 세트가 깨져 손해로
나오지만, 장신구 여러 개를 같이 바꾸면 새 세트 효과가 켜진다. 여기서는 세팅 전체를 한 번에 잰다.

- 방어구 7칸: 방어구 세트 조합(engine/market/armor_sets.py)의 실딜 1위
- 장신구: 칸마다 '지금 템' 또는 보스 장신구 계열 세트 템을 골라, 세트 구성이 같은 묶음마다 템 자체 몫이 가장 큰 배치를 남기고
  (방어구 조합과 같은 방법) 세트 효과까지 넣어 정확히 잰 것 중 1위
- 둘을 같이 낀 세팅을 다시 정확히 잰다(방어구·장신구가 서로의 세트 개수를 바꾸지는 않지만 실딜은 곱으로 겹친다)

가정(갈아타기와 같다 — 숫자 추정 금지): 바꿀 템의 기본 옵션·주문서 칸 수는 넥슨 API 실측 표(BASES), 스타포스는 고른 성(그 템 최대 성 이하),
잠재·에디·추옵·주문서 수치는 지금 그 자리 템 것을 옮긴다고 본다. 가격은 여기서 다루지 않는다(시세는 화면으로 읽거나 사용자가 넣는다).
"""

from engine.enhance.starforce import StarforceConditions, expected_totals
from engine.market.armor_sets import ARMOR_SLOTS, _anon, armor_combos
from engine.market.recommend import UNTRADEABLE_PREFIX, _part, _valued
from engine.market.swaps import BASES, _Swapper
from engine.stats.metrics import BossProfile
from engine.stats.sets import SetCatalog, count_sets
from engine.stats.snapshot import CharacterSnapshot, Setting

ACCESSORY_PARTS = ("반지", "펜던트", "귀고리", "얼굴장식", "눈장식", "벨트", "포켓 아이템", "뱃지")
ACCESSORY_SETS = ("칠흑의 보스 세트", "여명의 보스 세트", "보스 장신구 세트", "광휘의 보스 세트")
STARS = (17, 18, 21, 22)  # 2026-11-16·2026-11-26 사용자: 대표적인 성
NONE = "-"


def _short(set_name: str) -> str:
    return {"칠흑의 보스 세트": "칠흑", "여명의 보스 세트": "여명", "보스 장신구 세트": "보스 장신구", "광휘의 보스 세트": "광휘"}.get(set_name, set_name)


def match_cost(sw: _Swapper, slot: str, item) -> dict:
    """살 템(item — 지금 그 자리 템의 잠재·에디를 옮겨 놓은 것)에 그 잠재·에디를 큐브로 처음부터 맞추는 평균 비용.
    2026-11-26 사용자 결정(권장안): '잠재까지 지금 수준으로 맞추면 얼마'와 '잠재 없는 템만 사면 얼마'를 같이 보여 준다 —
    잠재가 붙은 매물을 사는 경우가 많아 이 값은 상한에 가깝다.
    방법(숫자 추정 없음): 지금 줄들 중 실딜에 쓰이는 줄의 기여 합 이상이 재설정 한 번에 나올 확률(_Planner.reach — 그 템 레벨·부위의
    공식 확률표)로, 레어에서 지금 등급까지 올리고 그 줄 수준이 나올 때까지의 평균 메소(cube_value.expected_cost).
    돌려주는 값: {'잠재': 메소|0|None, '에디': …} — 0 = 맞출 줄이 없다, None = 계산 못 함(확률표 없음·재설정 불가 템 등)."""
    import copy as _copy

    from engine.enhance.fixed import fixed_reason
    from engine.market.cube_value import expected_cost
    from engine.market.recommend import line_tables
    sub = _copy.copy(sw.pl)
    sub.raw = dict(sw.pl.raw)
    sub.raw[slot] = item
    out = {}
    for kind, lines, grade in (("잠재", item.potentials, item.potential_grade), ("에디", item.additional, item.additional_grade)):
        chosen = [t for t in (lines or []) if sub.is_useful(t)]
        if not chosen or grade is None:
            out[kind] = 0.0
            continue
        tables = line_tables(kind, grade, slot, item.level)
        if not tables or fixed_reason(item):
            out[kind] = None
            continue
        single = {o: sub.delta(slot, kind, [o]) for o in set(chosen)}
        reach = sub.reach(slot, kind, tables, [], chosen, single)
        out[kind] = expected_cost(kind, item.level, "레어", grade, reach) if reach > 0 else None
    return out


def accessory_slots(sw: _Swapper) -> list[str]:
    """바꿔 볼 장신구 칸: 지금 템이 있고, 특수 반지(스킬 반지)가 아닌 칸."""
    return [s for s, it in sw.pl.raw.items() if _part(s) in ACCESSORY_PARTS and not it.special_ring_level]


def accessory_candidates(sw: _Swapper, catalog: SetCatalog) -> dict[str, list[dict]]:
    """칸마다 후보: 지금 템 + 보스 장신구 계열 세트의 그 부위 템(레벨 이하·구매 가능). 실측 표로 못 만드는 템은 뺀다."""
    out = {}
    for slot in accessory_slots(sw):
        cur = sw.pl.raw[slot]
        kept_item, kept_star = sw.pl.items[slot], cur.starforce
        if cur.name in BASES and sw.star_for(cur, cur.name) > cur.starforce:    # 지금 템도 고른 성까지 강화한다고 본다
            up = sw.like_current(slot, cur.name)
            if up is not None:
                kept_item, kept_star = _valued(up, sw.pl.mains, sw.pl.per_sec), up.starforce
        cs = [{"name": cur.name, "set": catalog.items.get(cur.name) or NONE, "item": kept_item, "starforce": kept_star, "kept": True}]
        for name, b in BASES.items():
            if (b["part"] != _part(slot) or b.get("set") not in ACCESSORY_SETS or b["level"] > sw.snap.level
                    or name == cur.name or name.startswith(UNTRADEABLE_PREFIX)):
                continue
            it = sw.like_current(slot, name)
            if it is None:
                continue
            cs.append({"name": name, "set": b["set"], "item": _valued(it, sw.pl.mains, sw.pl.per_sec), "starforce": it.starforce,
                       "kept": False, "raw": it})
        out[slot] = cs
    return out


def accessory_builds(sw: _Swapper, catalog: SetCatalog, top: int = 5) -> list[dict]:
    """장신구 세팅을 통째로: 세트 구성 묶음마다 최선의 배치를 세트 효과까지 넣어 정확히 잰 것(실딜 순 위 top개).
    같은 이름의 템은 한 번만 낀다(반지·펜던트는 같은 템을 두 개 못 낀다)."""
    cands = accessory_candidates(sw, catalog)
    slots = list(cands)
    base, ev = sw.pl.base, sw.pl.ev
    own = {}
    for s in slots:
        for i, c in enumerate(cands[s]):
            trial = dict(sw.pl.items)
            trial[s] = _anon(c["item"])
            own[s, i] = ev.index(trial) / base - 1
    best: dict[tuple, tuple[float, tuple[int, ...], frozenset]] = {(): (0.0, (), frozenset())}
    for s in slots:
        nxt: dict[tuple, tuple[float, tuple[int, ...], frozenset]] = {}
        for sig, (score, idx, used) in best.items():
            for i, c in enumerate(cands[s]):
                if c["name"] in used:
                    continue
                k = tuple(sorted(sig + (c["set"],)))
                v = score + own[s, i]
                if k not in nxt or v > nxt[k][0]:
                    nxt[k] = (v, idx + (i,), used | {c["name"]})
        best = nxt
    before = count_sets(sw.pl.items.values(), sw.job.branches, catalog)
    rows = []
    # 세트 효과가 클 수 있는 묶음을 놓치지 않게 전부 정확히 잰다(묶음 수는 세트 종류가 적어 수백 개)
    for _, idx, _ in best.values():
        combo = [cands[s][i] for s, i in zip(slots, idx)]
        trial = dict(sw.pl.items)
        trial.update({s: c["item"] for s, c in zip(slots, combo)})
        after = count_sets(trial.values(), sw.job.branches, catalog)
        # 이름표는 그 세팅을 낀 뒤의 실제 세트 개수로(바꾸지 않는 자리 — 엠블렘 등 — 의 세트 템도 센다. 운영 확인: 고른 칸만 세니
        # '칠흑 6'인데 세트 효과 변화는 '칠흑 3→7개'라 서로 달랐다)
        n = {k: after[k] for k in ACCESSORY_SETS if after.get(k)}
        rows.append({
            "label": " · ".join(f"{_short(k)} {v}" for k, v in sorted(n.items(), key=lambda x: ACCESSORY_SETS.index(x[0]))) or "지금 그대로",
            "pieces": {s: {"name": c["name"], "set": None if c["set"] == NONE else c["set"], "starforce": c["starforce"], "kept": c["kept"]}
                       for s, c in zip(slots, combo)},
            "set_change": [{"set": k, "before": before.get(k, 0), "after": after.get(k, 0)}
                           for k in sorted(set(before) | set(after)) if before.get(k, 0) != after.get(k, 0)],
            "delta_pct": (ev.index(trial) / base - 1) * 100,
            "_items": {s: c["item"] for s, c in zip(slots, combo)},
            "_raw": {s: c["raw"] for s, c in zip(slots, combo) if not c["kept"]},
        })
    rows.sort(key=lambda r: r["delta_pct"], reverse=True)
    return rows[:top]


def consult(snap: CharacterSnapshot, setting: Setting, boss: BossProfile, catalog: SetCatalog,
            stars: tuple[int, ...] = STARS, cooldown_main_pct: float | None = None,
            potentials: tuple[str, ...] = ("same", "legend2", "legend3")) -> list[dict]:
    """성(17·18·21·22) × 잠재 목표(지금 그대로·레전드리 2줄·3줄)마다 목표 세팅 하나: 방어구 1위 조합 + 장신구 1위 조합을 같이 낀
    세팅의 보스 실딜(지금 = 0%). 템 구성은 성마다 하나(잠재 목표는 그 템들에 얹는다)."""
    out = []
    for star in stars:
        sw = _Swapper(snap, setting, boss, catalog, cooldown_main_pct, star)
        acc = accessory_builds(sw, catalog, top=1)
        armor = armor_combos(snap, setting, boss, catalog, starforce=star, cooldown_main_pct=cooldown_main_pct, top=1, raise_kept=True)
        trial = dict(sw.pl.items)
        pieces, raws = {}, {}
        if armor:
            from engine.market.armor_sets import slot_candidates
            by = {s: {c.name: c for c in cs} for s, cs in slot_candidates(sw, raise_kept=True).items()}
            for s, p in armor[0]["pieces"].items():
                trial[s] = by[s][p["name"]].item
                pieces[s] = {**p, "group": "방어구"}
                if not p["kept"]:
                    raws[s] = sw.like_current(s, p["name"])
        if acc:
            raws.update(acc[0]["_raw"])
            trial.update(acc[0]["_items"])
            pieces.update({s: {**p, "group": "장신구"} for s, p in acc[0]["pieces"].items()})
        before = count_sets(sw.pl.items.values(), sw.job.branches, catalog)
        after = count_sets(trial.values(), sw.job.branches, catalog)
        order = [s for s in sw.pl.raw if s in pieces]
        for s in order:                                    # 지금 템을 그대로 쓰되 성을 올리는 칸: 몇 성에서 몇 성으로, 평균 얼마
            cur, p = sw.pl.raw[s], pieces[s]
            p["from_star"] = cur.starforce if p["kept"] else None
            p["raise_cost"] = None
            if p["kept"] and p["starforce"] > cur.starforce:
                t = expected_totals(cur.level, cur.starforce, p["starforce"], StarforceConditions(), 0.0)
                p["raise_cost"], p["raise_destroys"] = t["meso"], t["destroys"]
            if p["kept"]:                                  # 잠재 목표 계산에 쓸 원본(쿨감 환산 전) 템
                up = sw.like_current(s, cur.name) if p["starforce"] > cur.starforce and cur.name in BASES else None
                raws[s] = up if up is not None else cur
        match = {s: match_cost(sw, s, raws[s]) if raws.get(s) is not None else {"잠재": None, "에디": None}
                 for s in order if not pieces[s]["kept"]}
        set_change = [{"set": k, "before": before.get(k, 0), "after": after.get(k, 0)}
                      for k in sorted(set(before) | set(after)) if before.get(k, 0) != after.get(k, 0)]
        ladder: dict = {}                                  # 칸마다 레전드리 단계는 한 번만 잰다(2줄·3줄 목표가 같이 쓴다 — 운영에서 첫 응답 5초)
        for key in potentials:
            goal = _goals(sw, trial, raws, order, pieces, POTENTIALS[key], ladder) if POTENTIALS[key] else {}
            worn = dict(trial)
            worn.update({s: g["item"] for s, g in goal.items()})
            part = {}                                      # 방어구만·장신구만 낀 실딜(잠재 목표 포함)
            for group in ("방어구", "장신구"):
                only = dict(sw.pl.items)
                only.update({s: worn[s] for s in order if pieces[s]["group"] == group})
                part[group] = (sw.pl.ev.index(only) / sw.pl.base - 1) * 100
            out.append({
                "starforce": star, "potential": key,
                "delta_pct": (sw.pl.ev.index(worn) / sw.pl.base - 1) * 100,
                "armor": {"label": armor[0]["label"], "delta_pct": part["방어구"] if goal else armor[0]["delta_pct"]} if armor else None,
                "accessory": {"label": acc[0]["label"], "delta_pct": part["장신구"] if goal else acc[0]["delta_pct"]} if acc else None,
                "pieces": [{"slot": s, **pieces[s]} for s in order],
                # match: 살 템의 잠재·에디를 큐브로 처음부터(레어에서) 맞추는 평균 — 잠재 목표를 고르면 잠재 쪽은 그 목표까지
                "buy": [{"slot": s, "name": pieces[s]["name"], "starforce": pieces[s]["starforce"], "group": pieces[s]["group"],
                         "target": goal[s]["target"] if s in goal else None,
                         "match": {**match[s], "잠재": goal[s]["cost"]} if s in goal else match[s]}
                        for s in order if not pieces[s]["kept"]],
                "raise": [{"slot": s, "name": pieces[s]["name"], "from_star": pieces[s]["from_star"], "starforce": pieces[s]["starforce"],
                           "cost": pieces[s]["raise_cost"], "destroys": pieces[s].get("raise_destroys"), "group": pieces[s]["group"]}
                          for s in order if pieces[s]["raise_cost"] is not None],
                "raise_cost": sum(pieces[s]["raise_cost"] or 0 for s in order),
                # cube: 그대로 쓰는 템의 잠재를 지금 등급에서 목표까지 큐브로 올리는 평균(None = 계산 못 함)
                "cube": [{"slot": s, "name": pieces[s]["name"], "group": pieces[s]["group"], "from_grade": raws[s].potential_grade,
                          "target": goal[s]["target"], "cost": goal[s]["cost"]} for s in order if pieces[s]["kept"] and s in goal],
                "_order": order,
                "set_change": set_change,
            })
    return out


# 잠재 목표(2026-11-26 사용자: "저 17 18 21 22성 템들은 잠재랑 추옵은 어떻게 되는거야?" — 오래 쓸 세팅인데 잠재가 지금 수준에 머물렀다).
# None = 지금 그대로, 숫자 = 레전드리에서 맞출 좋은 줄 수
POTENTIALS = {"same": None, "legend2": 2, "legend3": 3}


def _goals(sw: _Swapper, trial: dict, raws: dict, order: list[str], pieces: dict, lines: int,
           ladder: dict | None = None) -> dict[str, dict]:
    """세팅(trial)을 낀 상태에서 칸마다 잠재를 '레전드리 좋은 줄 lines개'로 바꾼 템과 그 큐브 평균 비용.
    목표 줄은 짓지 않는다 — 그 템 레벨·부위의 공식 확률표에서 흔한(2% 이상) 줄 중 실딜이 가장 오르는 조합(_Planner.tiers).
    지금 잠재가 이미 그 이상인 칸(바꾸면 실딜이 안 오르는 칸), 잠재가 없는 칸, 재설정이 안 되는 템은 그대로 둔다(결과에 없다).
    비용: 살 템은 레어에서, 그대로 쓰는 템은 지금 등급에서 목표 등급까지 올리고 그 줄 수준이 나올 때까지(cube_value.expected_cost).
    쿨감 줄(모자)은 남기고 나머지 줄을 고른다 — 그 칸은 lines가 3이어도 좋은 줄 2개까지다."""
    import copy as _copy

    from engine.enhance.fixed import fixed_reason
    from engine.market.cube_value import expected_cost
    from engine.market.recommend import SWAP
    sub = _copy.copy(sw.pl)
    sub.raw = {**sw.pl.raw, **{s: raws[s] for s in order if raws.get(s) is not None}}
    sub.items = trial
    sub.base = sw.pl.ev.index(trial)
    ladder = {} if ladder is None else ladder
    out = {}
    for s in order:
        it = raws.get(s)
        if it is None or not it.potentials or fixed_reason(it):
            continue
        if s not in ladder:
            ladder[s] = sub.tiers(s, "잠재", grades=("레전드리",))
        fit = [t for t in ladder[s] if t["lines_good"] <= lines]
        if not fit:
            continue
        t = max(fit, key=lambda t: t["lines_good"])
        if t["delta_pct"] <= 0:
            continue
        cost = expected_cost("잠재", it.level, "레어", "레전드리", t["reach_probability"]) if not pieces[s]["kept"] else t["cube_cost"]
        new = SWAP["잠재"](it, t["target"], sw.snap.level)
        out[s] = {"item": _valued(new, sw.pl.mains, sw.pl.per_sec), "target": t["target"], "cost": cost}
    return out


__all__ = ["ACCESSORY_PARTS", "ACCESSORY_SETS", "ARMOR_SLOTS", "POTENTIALS", "STARS", "accessory_builds", "accessory_candidates", "consult"]
