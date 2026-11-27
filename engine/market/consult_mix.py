"""섞은 목표(2026-11-26): 가진 메소(큐브에 쓸 몫) 안에서 칸마다 잠재·에디 목표를 따로 골라 보스 실딜이 가장 큰 조합.

컨설팅(engine/market/consult.py)의 목표는 '모든 칸 레전드리 3줄'처럼 한 단계를 전 칸에 건다. 그런데 레테 운영 값으로
무기 에디 레전드리 2줄은 100억당 +2.22%, 무기 잠재 3줄은 +0.09%라, 답은 '칸마다 다른 목표'인 경우가 흔하다.

방법(숫자를 새로 만들지 않는다):
- 칸마다 선택지 = 컨설팅이 이미 잰 단계(잠재: 그대로·레전드리 2줄·3줄, 에디: 그대로·에픽·유니크·레전드리 2줄)의 몫·큐브 평균
- 고르기: 칸별 몫을 더한 값이 예산 안에서 가장 큰 조합(칸마다 한 단계 — 묶음 배낭, 1억 단위 동적 계획법). 예산이 늘면 이 값은 줄지 않는다
- 고른 조합은 그 줄들을 실제로 낀 세팅으로 다시 정확히 잰다(delta_pct). 고를 때 쓴 칸별 몫의 합은 approx_pct로 따로 준다
비용 기준: 살 템은 잠재·에디 없는 매물을 사서 레어부터 큐브(지금 템 수준으로 맞추는 것도 선택지), 쓰던 템은 지금 등급에서.
"""

import numpy as np

from engine.market.consult import consult
from engine.market.recommend import SWAP, _valued
from engine.market.swaps import _Swapper
from engine.market.symbol_paths import extra_of
from engine.market.symbol_paths import step as symbol_step
from engine.stats import symbols as SYM

FRAGMENT_PRICE = 7e6  # 솔 에르다 조각 1개 기본값(메소) — 사용자 지정 기본값(2026-11-27), 화면에서 바꾼다
UNIT = 1e8  # 동적 계획법의 메소 단위(1억). 비용은 올림 — 예산을 넘는 조합은 고르지 않는다


def _options(builds: list[dict]) -> dict[tuple[str, str], list[dict]]:
    """(칸, 잠재|에디) → 선택지 [{label, target, cost, gain_pct, name, group}] — '그대로'(비용 0, 몫 0)는 따로 넣는다."""
    by = {b["potential"]: b for b in builds}
    out: dict[tuple[str, str], list[dict]] = {}
    for key, label in (("legend2", "레전드리 2줄"), ("legend3", "레전드리 3줄")):
        b = by.get(key)
        if not b:
            continue
        for x in b["buy"]:
            if x.get("goal") and x["goal"]["cost"]:
                out.setdefault((x["slot"], "잠재"), []).append(
                    {"label": label, "target": x["target"], "cost": x["goal"]["cost"], "gain_pct": x["goal"]["gain_pct"],
                     "name": x["name"], "group": x["group"], "kept": False})
        for c in b["cube"]:
            if c["cost"]:
                out.setdefault((c["slot"], "잠재"), []).append(
                    {"label": label, "target": c["target"], "cost": c["cost"], "gain_pct": c["gain_pct"],
                     "name": c["name"], "group": c["group"], "kept": True})
    same = by["same"]
    for a in same["additional_options"]:
        label = {"epic2": "에픽 2줄", "unique2": "유니크 2줄", "legend2": "레전드리 2줄"}[a["key"]]
        for x in a["slots"]:
            if x["cost"]:
                out.setdefault((x["slot"], "에디"), []).append(
                    {"label": label, "target": x["target"], "cost": x["cost"], "gain_pct": x["gain_pct"],
                     "name": x["name"], "group": x["group"], "kept": x["kept"]})
    return out


def pick(options: dict[tuple[str, str], list[dict]], budget: float) -> dict[tuple[str, str], dict]:
    """칸마다 한 단계(또는 그대로)를 골라 몫의 합이 가장 큰 조합 — 비용 합 ≤ budget. 묶음 배낭(1억 단위 올림)."""
    cap = int(budget // UNIT)
    if cap <= 0 or not options:
        return {}
    keys = list(options)
    best = np.zeros(cap + 1)
    choice = []                                             # 단계마다 예산별로 고른 선택지 번호(-1 = 그대로)
    for k in keys:
        nxt, pick_ = best.copy(), np.full(cap + 1, -1, dtype=np.int16)
        for i, o in enumerate(options[k]):
            c = int(np.ceil(o["cost"] / UNIT))
            if c > cap or o["gain_pct"] <= 0:
                continue
            cand = np.full(cap + 1, -np.inf)
            cand[c:] = best[:cap + 1 - c] + o["gain_pct"]
            better = cand > nxt
            nxt[better], pick_[better] = cand[better], i
        best = nxt
        choice.append(pick_)
    out, b = {}, cap
    for k, pick_ in zip(reversed(keys), reversed(choice)):    # 거꾸로 따라가며 고른 것을 꺼낸다
        i = int(pick_[b])
        if i >= 0:
            out[k] = options[k][i]
            b -= int(np.ceil(options[k][i]["cost"] / UNIT))
    return out


def _flame_match(sw: _Swapper, catalog, slot: str, it) -> dict | None:
    """살 템(it — 지금 그 자리 템의 추옵을 옮겨 놓은 것)의 추옵을 메소 재설정으로 그 수준 이상 맞추는 평균 비용.
    경로 비교의 추옵 경로와 같은 방법(engine/market/paths._flame_paths): 점수 = 추옵 줄이 주는 실딜(키마다 기울기를 잰 선형 근사),
    확률 = 한 번 재설정에 그 점수 이상이 나올 확률(공식 확률표), 비용 = 3,000,000 메소 ÷ 확률. 잴 수 없으면 None."""
    from engine.enhance import flame
    from engine.market.paths import _flame_weights
    from engine.market.recommend import _part
    if not it.level or flame.no_flame_part(_part(slot)) or not flame.is_boss_item(it.name, it.part, catalog):
        return None
    weapon = _part(slot) == "무기"
    w = _flame_weights(sw.px, slot, it, weapon)
    current = sum(w.get(k, 0.0) * v for k, v in it.add_option.items())
    if current <= 0:
        return None
    dist = flame.score_distribution(flame.MESO_RESET, weapon, it.level, True,
                                    lambda o: {st: sum(w.get(k, 0.0) * v for k, v in flame.line_value(o, st, it.level, weapon, it.base_attack).items())
                                               for st in range(3, 8)})
    prob = flame.target_stats(dist, current)["probability"]
    if prob <= 0:
        return None
    return {"cost": flame.MESO_RESET_COST / prob, "tries": 1 / prob}


def mix(snap, setting, boss, catalog, star: int, budget: float, cooldown_main_pct: float | None = None,
        builds: list[dict] | None = None, sf=None, symbols: bool = True, flames: bool = True,
        fragment_price: float = FRAGMENT_PRICE) -> dict:
    """star성 세팅에서 큐브에 budget 메소를 쓸 때 칸마다 고른 잠재·에디 목표와, 그 조합을 실제로 낀 보스 실딜.

    살 템의 기준은 '잠재·에디 없는 매물'이다(2026-11-26 — 전에는 지금 그 자리 템의 잠재·에디를 공짜로 옮겨 실딜이 부풀었다).
    살 템마다 '지금 템 수준'(지금 그 자리 템의 잠재·에디를 레어부터 큐브로 맞추는 평균 — consult의 match)도 선택지로 넣어
    배낭이 다른 목표와 같이 고른다. 칸별 몫은 모두 이 기준 세팅에서 그 칸만 바꿔 다시 잰다."""
    if builds is None:                                       # best_star는 성마다 한 번 계산한 것을 넘긴다
        builds = consult(snap, setting, boss, catalog, stars=(star,), cooldown_main_pct=cooldown_main_pct, sf=sf)
    same = next(b for b in builds if b["potential"] == "same")
    options = _options(builds)
    sw = _Swapper(snap, setting, boss, catalog, cooldown_main_pct, star)
    raw, current = {}, {}                                   # 기준 세팅(쿨감 환산 전 템), 살 템에 옮겨 놓았던 지금 수준 줄
    flamed, assumed = {}, 0                                 # 추옵을 지금 수준으로 맞춘 살 템(잠재·에디 없음), 추옵을 못 재 그대로 둔 살 템 수
    for p in same["pieces"]:
        cur = sw.pl.raw[p["slot"]]
        it = sw.like_current(p["slot"], p["name"]) if not p["kept"] or p["starforce"] > cur.starforce else cur
        if not p["kept"]:
            current[p["slot"]] = {"잠재": list(it.potentials), "에디": list(it.additional)}
            it = SWAP["에디"](SWAP["잠재"](it, [], snap.level), [], snap.level)
            # 추옵(2026-11-27): 살 템에 지금 템의 추옵을 공짜로 옮기던 것도 같은 문제다 — 보스 장비로 확인되는 템이고 메소 재설정
            # (공식 1회 300만 메소)으로 지금 수준 이상이 나올 확률을 잴 수 있으면, 기준은 '추옵 없음'으로 두고 맞추기를 선택지로 넣는다.
            # 잴 수 없는 템(보스 장비로 확인 안 됨)은 전처럼 지금 수준이 붙어 있다고 본다(flame_assumed로 센다)
            fl = _flame_match(sw, catalog, p["slot"], it) if it.add_option and flames else None
            if fl:
                flamed[p["slot"]] = it
                it = SWAP["에디"](SWAP["잠재"](sw.like_current(p["slot"], p["name"], add={}), [], snap.level), [], snap.level)
                options[(p["slot"], "추옵")] = [{"label": "지금 템 수준", "target": [], "cost": fl["cost"], "gain_pct": 0.0, "name": p["name"],
                                              "group": p["group"], "kept": False, "tries": fl["tries"]}]
            elif it.add_option:
                assumed += 1
        raw[p["slot"]] = it
    for s, _ in options:
        raw.setdefault(s, sw.pl.raw[s])                     # 무기·보조무기·엠블렘: 템은 그대로
    for x in same["buy"]:                                   # 살 템의 '지금 템 수준' 선택지
        for kind in ("잠재", "에디"):
            cost, lines = (x.get("match") or {}).get(kind), current.get(x["slot"], {}).get(kind)
            if cost and lines:
                options.setdefault((x["slot"], kind), []).insert(0, {"label": "지금 템 수준", "target": lines, "cost": cost, "gain_pct": 0.0,
                                                                     "name": x["name"], "group": x["group"], "kept": False})
    valued = {s: _valued(it, sw.pl.mains, sw.pl.per_sec) for s, it in raw.items()}
    base_items = {**sw.pl.items, **valued}
    base_index = sw.pl.ev.index(base_items)
    # 심볼(2026-11-27): 갈아타기 뒤 남는 메소로 심볼 레벨업도 같이 고른다 — 심볼마다 '지금 → n레벨'이 선택지(강화 메소 합,
    # 실딜은 늘어난 주스탯·포스를 넣어 잰다 — engine/market/symbol_paths와 같은 방법). 심볼은 거래가 안 돼 모자란 개수·날수를 같이 준다
    if symbols:
        for sym in snap.symbol_items:
            if sym["kind"] not in SYM.KINDS:
                continue
            for target in range(sym["level"] + 1, SYM.max_level(sym["kind"]) + 1):
                st = symbol_step(sym, sym["level"], target, snap.character_class)
                # 지금 모은 심볼로 할 수 있는 레벨까지만 — 더 모아야 하는 레벨(레테: 아르크스 11레벨까지 2,598개 · 약 174일)을
                # 메소만으로 되는 것처럼 고르면 '이 메소로 +x%'가 거짓이 된다(2026-11-27 로컬 화면에서 확인)
                if st is None or st["remaining_symbols"] > 0:
                    break
                if st["meso"] <= 0:
                    continue
                options.setdefault((sym["name"], "심볼"), []).append(
                    {"label": f"{sym['level']}→{target}레벨", "target": [], "cost": float(st["meso"]), "gain_pct": 0.0, "name": sym["name"],
                     "group": "심볼", "kept": True, "stat_gain": st["stat_gain"], "force_gain": st["force_gain"],
                     "remaining_symbols": st["remaining_symbols"], "days": st["days"]})
    # HEXA 코어(2026-11-27): 직업별 스킬 딜 지분(내 연무장 기록, 없으면 직업 기준값)으로 코어마다 '다음 1레벨'의 실딜 — 경로 비교의
    # HEXA 코어와 같은 계산(engine/market/hexa_core_paths). 비용 = 조각 개수 × 조각 값(fragment_price, 0이면 넣지 않는다).
    # 넥슨 API가 다음 1레벨 효과만 줘서 코어당 1레벨까지다. 솔 에르다는 거래가 안 돼 개수만 같이 준다
    hexa_source = None
    if fragment_price and snap.hexa_cores:
        from engine.market.hexa_core_paths import core_paths, job_shares
        shares, hexa_source = (snap.own_shares, "내 연무장 기록") if snap.own_shares else (
            (job_shares(snap.character_class) or {}).get("shares") or {}, "직업 기준값(연무장 상위 기록 중앙값)")
        if not shares:
            hexa_source = None
        for p in core_paths(snap, shares, fragment_price, boss.defense, hexa_source or ""):
            core, label = p["name"].rsplit(" ", 1)
            options[(core, "헥사")] = [{"label": label, "target": [], "cost": float(p["cost"]), "gain_pct": 0.0, "name": core, "group": "헥사",
                                       "kept": True, "hexa_pct": p["delta_pct"], "fragments": p["fragments"], "erda": p["erda"]}]
    for (s, kind), opts in options.items():                 # 칸별 몫을 기준 세팅에서 다시 잰다
        for o in opts:
            if kind == "헥사":                               # 스킬 배율이라 장비와 곱해진다 — 기준 세팅의 지수에 곱한 몫
                o["gain_pct"] = o["hexa_pct"] * base_index / sw.pl.base
                continue
            if kind == "심볼":
                o["gain_pct"] = (sw.pl.ev.index(base_items, extra_of(o["stat_gain"], o["force_gain"])) - base_index) / sw.pl.base * 100
                continue
            trial = dict(base_items)
            new = flamed[s] if kind == "추옵" else SWAP[kind](raw[s], o["target"], snap.level)
            trial[s] = _valued(new, sw.pl.mains, sw.pl.per_sec)
            o["gain_pct"] = (sw.pl.ev.index(trial) - base_index) / sw.pl.base * 100
    chosen = pick(options, budget)
    stat, force, hexa = {}, {}, 0.0
    for (s, kind) in chosen:                                # 추옵을 맞추는 살 템은 그 템에서 시작한다(그 위에 잠재·에디)
        if kind == "추옵":
            raw[s] = flamed[s]
    for (s, kind), o in sorted(chosen.items(), key=lambda kv: kv[0][1] != "잠재"):   # 잠재 먼저, 그 위에 에디
        if kind == "추옵":
            continue
        if kind == "헥사":
            hexa += o["hexa_pct"]
            continue
        if kind == "심볼":
            for k, v in o["stat_gain"].items():
                stat[k] = stat.get(k, 0.0) + v
            for k, v in o["force_gain"].items():
                force[k] = force.get(k, 0) + v
            continue
        raw[s] = SWAP[kind](raw[s], o["target"], snap.level)
    worn = dict(sw.pl.items)
    worn.update({s: _valued(it, sw.pl.mains, sw.pl.per_sec) for s, it in raw.items()})
    # 코어마다 올리는 스킬이 달라 코어끼리는 더하고(지분 × 배율 증가), 장비·심볼로 오른 지수에는 곱한다
    delta = (sw.pl.ev.index(worn, extra_of(stat, force) if (stat or force) else None) / sw.pl.base * (1 + hexa / 100) - 1) * 100
    base_delta = (base_index / sw.pl.base - 1) * 100
    picks = [{"slot": "심볼" if kind == "심볼" else "헥사" if kind == "헥사" else s, "kind": kind,
              **{k: o[k] for k in ("name", "group", "kept", "label", "target", "cost", "gain_pct")},
              **({"remaining_symbols": o["remaining_symbols"], "days": o["days"]} if kind == "심볼" else {}),
              **({"tries": o["tries"]} if kind == "추옵" else {}),
              **({"fragments": o["fragments"], "erda": o["erda"]} if kind == "헥사" else {})}
             for (s, kind), o in chosen.items()]
    picks.sort(key=lambda x: -x["gain_pct"] / x["cost"])
    return {"starforce": star, "budget": budget, "base_delta_pct": base_delta, "delta_pct": delta,
            # 참고: 살 템에 지금 템 수준 잠재·에디가 공짜로 붙어 있다고 본 컨설팅 '지금 그대로' 값
            "with_current_delta_pct": same["delta_pct"], "bare_buys": len(current), "flame_assumed": assumed,
            "approx_pct": base_delta + sum(x["gain_pct"] for x in picks), "cost": sum(x["cost"] for x in picks),
            "fragment_price": fragment_price, "hexa_source": hexa_source,
            "picks": picks, "candidates": sum(len(v) for v in options.values())}


__all__ = ["best_star", "mix", "pick"]


def best_star(snap, setting, boss, catalog, total: float, prices: float = 0.0, stars: tuple[int, ...] | None = None,
              cooldown_main_pct: float | None = None, sf=None, builds_for=None, fragment_price: float = FRAGMENT_PRICE) -> dict:
    """가진 메소 전체(total, 강화 + 큐브)로 성까지 같이 고른다: 성마다 큐브 예산 = total − 그 성 강화 평균 − 넣은 살 템 시세(prices),
    그 예산의 추천 조합을 정확히 잰 실딜이 가장 큰 성. 강화도 못 하는 성은 short(모자란 메소)만 적는다.
    살 템 시세는 성마다 따로 받지 않는다(같은 템의 성만 다르다) — 넣은 값을 모든 성에서 똑같이 뺀다."""
    from engine.market.consult import STARS
    rows, best = [], None
    for star in stars or STARS:
        r = None
        # builds_for: 성마다 컨설팅 계산을 저장해 둔 것(서버가 넘긴다 — 가진 메소만 바꿔 다시 물을 때 다시 계산하지 않게)
        builds = builds_for(star) if builds_for else consult(snap, setting, boss, catalog, stars=(star,),
                                                             cooldown_main_pct=cooldown_main_pct, sf=sf)
        raise_cost = builds[0]["raise_cost"]
        left = total - raise_cost - prices
        if left >= 0:
            r = mix(snap, setting, boss, catalog, star, float(int(left // UNIT) * UNIT), cooldown_main_pct, builds=builds, fragment_price=fragment_price)
            if best is None or r["delta_pct"] > best["delta_pct"]:
                best = r
        rows.append({"starforce": star, "raise_cost": raise_cost, "cube_budget": max(0.0, left), "short": max(0.0, -left),
                     "delta_pct": r["delta_pct"] if r else None, "cost": r["cost"] if r else None})
    return {"total": total, "prices": prices, "best": best["starforce"] if best else None, "stars": rows, "mix": best}
