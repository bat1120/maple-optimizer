"""섞은 목표(2026-11-26): 가진 메소(큐브에 쓸 몫) 안에서 칸마다 잠재·에디 목표를 따로 골라 보스 실딜이 가장 큰 조합.

컨설팅(engine/market/consult.py)의 목표는 '모든 칸 레전드리 3줄'처럼 한 단계를 전 칸에 건다. 그런데 레테 운영 값으로
무기 에디 레전드리 2줄은 100억당 +2.22%, 무기 잠재 3줄은 +0.09%라, 답은 '칸마다 다른 목표'인 경우가 흔하다.

방법(숫자를 새로 만들지 않는다):
- 칸마다 선택지 = 컨설팅이 이미 잰 단계(잠재: 그대로·레전드리 2줄·3줄, 에디: 그대로·에픽·유니크·레전드리 2줄)의 몫·큐브 평균
- 고르기: 칸별 몫을 더한 값이 예산 안에서 가장 큰 조합(칸마다 한 단계 — 묶음 배낭, 1억 단위 동적 계획법). 예산이 늘면 이 값은 줄지 않는다
- 고른 조합은 그 줄들을 실제로 낀 세팅으로 다시 정확히 잰다(delta_pct). 고를 때 쓴 칸별 몫의 합은 approx_pct로 따로 준다
비용 기준: 살 템은 잠재·에디 없이 산다고 보고(레어에서), 쓰던 템은 지금 등급에서 — 컨설팅의 '지금 그대로' 합계와 같은 기준.
"""

import numpy as np

from engine.market.consult import consult
from engine.market.recommend import SWAP, _valued
from engine.market.swaps import _Swapper

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


def mix(snap, setting, boss, catalog, star: int, budget: float, cooldown_main_pct: float | None = None) -> dict:
    """star성 세팅에서 큐브에 budget 메소를 쓸 때 칸마다 고른 잠재·에디 목표와, 그 조합을 실제로 낀 보스 실딜."""
    builds = consult(snap, setting, boss, catalog, stars=(star,), cooldown_main_pct=cooldown_main_pct)
    same = next(b for b in builds if b["potential"] == "same")
    options = _options(builds)
    chosen = pick(options, budget)
    sw = _Swapper(snap, setting, boss, catalog, cooldown_main_pct, star)
    raw = {}                                                # '지금 그대로' 세팅을 다시 낀다(consult와 같은 방법, 쿨감 환산 전 템)
    for p in same["pieces"]:
        cur = sw.pl.raw[p["slot"]]
        raw[p["slot"]] = sw.like_current(p["slot"], p["name"]) if not p["kept"] or p["starforce"] > cur.starforce else cur
    for s, _ in options:
        raw.setdefault(s, sw.pl.raw[s])                     # 무기·보조무기·엠블렘: 템은 그대로
    for (s, kind), o in sorted(chosen.items(), key=lambda kv: kv[0][1] != "잠재"):   # 잠재 먼저, 그 위에 에디
        raw[s] = SWAP[kind](raw[s], o["target"], snap.level)
    worn = dict(sw.pl.items)
    worn.update({s: _valued(it, sw.pl.mains, sw.pl.per_sec) for s, it in raw.items()})
    delta = (sw.pl.ev.index(worn) / sw.pl.base - 1) * 100
    picks = [{"slot": s, "kind": kind, **{k: o[k] for k in ("name", "group", "kept", "label", "target", "cost", "gain_pct")}}
             for (s, kind), o in chosen.items()]
    picks.sort(key=lambda x: -x["gain_pct"] / x["cost"])
    return {"starforce": star, "budget": budget, "base_delta_pct": same["delta_pct"], "delta_pct": delta,
            "approx_pct": same["delta_pct"] + sum(x["gain_pct"] for x in picks), "cost": sum(x["cost"] for x in picks),
            "picks": picks, "candidates": sum(len(v) for v in options.values())}


__all__ = ["mix", "pick"]
