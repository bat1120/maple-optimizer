"""업그레이드 경로 비교: 구매(관측 매물) · 직작(관측 매물을 베이스로 사서 큐브) · 지금 템 큐브를 억당 실딜로 정렬한다.

- 구매: 매물을 그대로 끼운 실딜. 세트 개수는 템 이름으로 다시 센다(세트가 깨지거나 맞춰지는 효과가 실딜에 들어간다).
  다른 월드 매물은 메이플포인트 수수료 10%를 더한다.
- 직작: 매물 가격 + 매물의 지금 등급에서 로드맵 단계까지 메소 재설정 평균 비용. 스타포스는 매물 그대로 본다.
- 큐브: 지금 템에 메소 재설정(로드맵의 cube_cost).
가격이 없거나 총 옵션을 모르는 매물은 실딜을 계산할 수 없어 뺀다.
"""
from engine.market.cube_value import expected_cost
from engine.market.listing import item_from_input
from engine.market.recommend import KINDS, MIN_GAIN, SWAP, _part, _Planner, _valued, roadmap
from engine.stats.jobs import job_profile
from engine.stats.metrics import BossProfile
from engine.stats.sets import SetCatalog, count_sets
from engine.stats.snapshot import CharacterSnapshot, Item, Setting

SLOTS_BY_CATEGORY = {"반지": ("반지1", "반지2", "반지3", "반지4"), "펜던트": ("펜던트", "펜던트2")}
OTHER_WORLD_FEE = 0.10  # 다른 월드 매물 구매 시 가격의 10% 메이플포인트 (maple-auction-mcp 응답 설명)


def listing_item(slot: str, row: dict, level: int) -> Item:
    """관측 매물 → 잠재·에디를 갈아 끼울 수 있는 Item."""
    base = item_from_input(slot, row.get("part") or row["category"], row.get("name") or "?", row.get("total") or {},
                           [], level, row.get("starforce") or 0)
    it = Item(slot=slot, part=base.part, name=base.name, starforce=base.starforce, stats=base.stats,
              core=base.stats, level=row.get("level") or 0,
              potential_grade=row.get("potential_grade"), additional_grade=row.get("additional_grade"))
    it = SWAP["잠재"](it, list(row.get("potential_lines") or []), level)
    return SWAP["에디"](it, list(row.get("additional") or []), level)


class _Paths:
    def __init__(self, pl: _Planner, catalog: SetCatalog):
        self.pl, self.catalog = pl, catalog
        self.branches = job_profile(pl.snap.character_class).branches
        self.before = count_sets(pl.items.values(), self.branches, catalog)

    def delta(self, slot: str, item: Item) -> tuple[float, list[dict]]:
        trial = dict(self.pl.items)
        trial[slot] = _valued(item, self.pl.main, self.pl.per_sec)
        after = count_sets(trial.values(), self.branches, self.catalog)
        change = [{"set": k, "before": self.before.get(k, 0), "after": after.get(k, 0)}
                  for k in sorted(set(self.before) | set(after)) if self.before.get(k, 0) != after.get(k, 0)]
        return (self.pl.ev.index(trial) / self.pl.base - 1) * 100, change


def _entry(slot, path, cost, delta, **kw) -> dict:
    return {"slot": slot, "path": path, "cost": cost, "delta_pct": delta, "per_100m": delta / (cost / 1e8), **kw}


def upgrade_paths(snap: CharacterSnapshot, setting: Setting, boss: BossProfile, catalog: SetCatalog,
                  observed: list[dict] | None = None, cooldown_main_pct: float | None = None) -> dict:
    pl = _Planner(snap, setting, boss, catalog, cooldown_main_pct)
    rm = roadmap(snap, setting, boss, catalog, cooldown_main_pct, observed, planner=pl)
    px = _Paths(pl, catalog)
    out = []
    for slot, row in rm.items():  # 지금 템에 큐브
        for kind in KINDS:
            for t in row[kind]:
                if t["cube_cost"] and t["delta_pct"] >= MIN_GAIN:
                    out.append(_entry(slot, "큐브", t["cube_cost"], t["delta_pct"], kind=kind, name=row["name"],
                                      grade=t["grade"], lines_good=t["lines_good"], target=t["target"],
                                      cube_cost=t["cube_cost"], reach_probability=t["reach_probability"],
                                      set_change=[]))
    for obs in observed or []:
        if not obs.get("price") or not obs.get("total"):
            continue
        slots = [s for s in SLOTS_BY_CATEGORY.get(obs["category"], (obs["category"],)) if s in pl.raw]
        if not slots:
            continue
        price = obs["price"] * (1 + OTHER_WORLD_FEE if obs.get("other_world") else 1)
        meta = {"name": obs.get("name"), "sold": bool(obs.get("sold")), "seen_at": obs.get("seen_at"),
                "listing": {k: obs.get(k) for k in ("starforce", "potential_lines", "additional", "price")}}
        try:
            built = {s: listing_item(s, obs, snap.level) for s in slots}
        except ValueError:
            continue
        scored = {s: px.delta(s, built[s]) for s in slots}
        slot = max(slots, key=lambda s: scored[s][0])
        d, change = scored[slot]
        if d >= MIN_GAIN:
            out.append(_entry(slot, "구매", price, d, kind=None, set_change=change, **meta))
        base_item = built[slot]
        level = obs.get("level") or pl.raw[slot].level
        for kind in KINDS:
            grade = obs.get("potential_grade") if kind == "잠재" else obs.get("additional_grade")
            for t in rm.get(slot, {}).get(kind, []):
                cube = expected_cost(kind, level, grade, t["grade"], t["reach_probability"])
                if cube is None:
                    continue
                d, change = px.delta(slot, SWAP[kind](base_item, t["target"], snap.level))
                if d >= MIN_GAIN:
                    out.append(_entry(slot, "직작", price + cube, d, kind=kind, grade=t["grade"],
                                      lines_good=t["lines_good"], target=t["target"], base_price=price,
                                      cube_cost=cube, reach_probability=t["reach_probability"], set_change=change,
                                      **meta))
    out.sort(key=lambda p: p["per_100m"], reverse=True)
    best, seen = [], set()
    for p in out:
        if p["slot"] not in seen:
            seen.add(p["slot"])
            best.append(p)
    return {"all": out, "best_by_slot": best}


__all__ = ["upgrade_paths", "listing_item", "_part"]
