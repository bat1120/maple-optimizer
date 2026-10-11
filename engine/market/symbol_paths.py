"""심볼 경로(2026-10-11): 심볼마다 지금 레벨 → 최대 레벨까지 한 단계씩 강화했을 때의 실딜·강화 메소.

- 실딜: 늘어난 주스탯(%미적용)을 extra nopct로 넣어 보스 지수를 다시 계산(HEXA 스탯 경로와 같은 방식)
- 비용: 강화 메소 합(engine/data/symbol_tables.json, 나무위키 성장표). 심볼은 거래 불가라 비용에 넣지 않고
  필요 심볼 개수·지금 성장치로 남은 개수·일일 퀘스트 기준 약 N일을 같이 준다(이미 다 찼으면 메소만)
- 포스 보정(2026-10-11): 심볼 레벨업으로 늘어난 포스(force_gain, engine/stats/symbols.force_at)를 extra['force']로 넣어
  요구 포스가 있는 보스(engine/data/bosses.json)면 격차별 피해 비율이 바뀐 만큼 실딜에 들어간다. force_after = 올린 뒤 보정
- 그랜드 어센틱심볼은 주스탯이 없어 포스만 오른다 — 어센틱 보스를 골랐을 때만 실딜이 생긴다
- 넣지 않은 것: 11레벨 지역 보스 '데미지 +20%'(공지·API·나무에 최종뎀인지 데미지%인지 없음 — max_effect로 문구만 보여 준다)
"""
import math

from engine.market.recommend import MIN_GAIN
from engine.stats import symbols as S
from engine.stats.force import character_force, force_info
from engine.stats.model import StatBlock

PATH = "심볼"


def extra_of(stat: dict, force: dict | None = None) -> dict:
    """심볼 변화 → Evaluator.index extra: 주스탯(%미적용)과 포스 증가량({'아케인'|'어센틱': n})."""
    out = {"nopct": StatBlock(flat=dict(stat))}
    if force:
        out["force"] = dict(force)
    return out


def step(sym: dict, level: int, target: int, character_class: str) -> dict | None:
    """sym(snap.symbol_items 한 줄)을 level → target으로: 스탯·메소·필요/남은 심볼. 계산할 수 없으면 None."""
    kind, region = sym["kind"], sym["region"]
    if kind not in S.KINDS or not (level < target <= S.max_level(kind)):
        return None
    g = S.gain(kind, level, target, character_class)
    costs = [S.meso(kind, region, lv) for lv in range(level, target)]
    force = {S.force_kind(kind): S.force_at(kind, target) - S.force_at(kind, level)}
    if not (g or force[S.force_kind(kind)]) or None in costs:
        return None
    need = sum(S.need(kind, lv) for lv in range(level, target))
    # 지금 쌓인 성장치는 필요치를 넘을 수 있다 — 넘친 몫은 다음 레벨로 이어진다
    have = max(0, sym["growth"] - sum(S.need(kind, lv) for lv in range(sym["level"], level)))
    remaining = max(0, need - have)
    per_day = S.daily(kind, region)
    return {"stat_gain": g, "force_gain": force, "meso": sum(costs), "need_symbols": need, "growth": have, "remaining_symbols": remaining,
            "daily": per_day, "days": math.ceil(remaining / per_day) if per_day else None,
            "max_effect": sym.get("other_effect") if target == S.max_level(kind) else None}


def symbol_paths(pl) -> list[dict]:
    cls = pl.snap.character_class
    out = []
    for sym in pl.snap.symbol_items:
        if sym["kind"] not in S.KINDS:
            continue
        for target in range(sym["level"] + 1, S.max_level(sym["kind"]) + 1):
            s = step(sym, sym["level"], target, cls)
            if s is None:
                break
            d = (pl.ev.index(pl.items, extra_of(s["stat_gain"], s["force_gain"])) / pl.base - 1) * 100
            if d < MIN_GAIN or s["meso"] <= 0:
                continue
            after = force_info(pl.ev.boss, character_force(pl.snap, pl.ev.setting, s["force_gain"]))
            out.append({"slot": PATH, "path": PATH, "name": sym["name"], "kind": sym["kind"], "region": sym["region"],
                        "from_level": sym["level"], "to_level": target, "cost": float(s["meso"]), "delta_pct": d,
                        "per_100m": d / (s["meso"] / 1e8), "set_change": [], "force_after": after, **s})
    return out
