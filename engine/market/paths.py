"""업그레이드 경로 비교: 구매(관측 매물) · 직작(관측 매물을 베이스로 사서 큐브) · 지금 템 큐브를 억당 실딜로 정렬한다.

- 구매: 매물을 그대로 끼운 실딜. 세트 개수는 템 이름으로 다시 센다(세트가 깨지거나 맞춰지는 효과가 실딜에 들어간다).
  다른 월드 매물은 메이플포인트 수수료 10%를 더한다.
- 직작: 매물 가격 + 매물의 지금 등급에서 로드맵 단계까지 메소 재설정 평균 비용. 스타포스는 매물 그대로 본다.
- 큐브: 지금 템에 메소 재설정(로드맵의 cube_cost).
- 스타포스: 지금 템을 목표 성까지(성별 스탯 표 engine/enhance/starforce_stats.py). 비용은 메소 기대값만이고 파괴 시 스페어 비용은
  빼고 평균 파괴 횟수(expected_destroys)를 따로 준다.
가격이 없거나 총 옵션을 모르는 매물은 실딜을 계산할 수 없어 뺀다.
"""
import copy
import dataclasses

from engine.enhance.starforce import expected_totals as sf_expected_totals
from engine.enhance.starforce import max_star as sf_max_star
from engine.enhance.starforce_stats import eligible
from engine.enhance.starforce_stats import gain as sf_gain
from engine.market.cube_value import expected_cost
from engine.market.events import Events
from engine.market.hexa_core_paths import core_paths, job_shares
from engine.market.hexa_paths import hexa_stat_paths
from engine.market.listing import item_from_input
from engine.market.secondary import secondary_fits
from engine.market.recommend import KINDS, MIN_GAIN, SWAP, UNTRADEABLE_SECONDARY_JOBS, _part, _Planner, _valued, roadmap
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
        trial[slot] = _valued(item, self.pl.mains, self.pl.per_sec)
        after = count_sets(trial.values(), self.branches, self.catalog)
        change = [{"set": k, "before": self.before.get(k, 0), "after": after.get(k, 0)}
                  for k in sorted(set(self.before) | set(after)) if self.before.get(k, 0) != after.get(k, 0)]
        return (self.pl.ev.index(trial) / self.pl.base - 1) * 100, change


def _entry(slot, path, cost, delta, **kw) -> dict:
    return {"slot": slot, "path": path, "cost": cost, "delta_pct": delta, "per_100m": delta / (cost / 1e8), **kw}


SF_TARGETS = (17, 18, 19, 20, 21, 22, 23, 24, 25)  # 목표 성 후보(지금 성보다 높고 최대 성 이하만)
SF_PER_SLOT = 2  # 부위마다 억당 효율 상위 목표 성만(목록이 스타포스로 넘치지 않게)


def _starforce_paths(pl, px, events: Events) -> list[dict]:
    """지금 템을 목표 성까지 강화: 실딜은 성별 스탯 표(engine/enhance/starforce_stats.py), 비용은 메소 기대값
    (engine/enhance/starforce.py, 이벤트·파괴 방지 없음, 파괴 시 스페어·복구 비용 제외)."""
    out = []
    for slot, it in pl.raw.items():
        if not eligible(it):
            continue
        cap = sf_max_star(it.level)
        mine = []
        for target in (t for t in SF_TARGETS if it.starforce < t <= cap):
            g = sf_gain(it, target)
            if not g:
                continue
            stats = copy.deepcopy(it.stats)
            core = copy.deepcopy(it.core) if it.core is not None else None
            for k, v in g.items():
                stats.flat[k] = stats.flat.get(k, 0.0) + v
                if core is not None:
                    core.flat[k] = core.flat.get(k, 0.0) + v
            new = dataclasses.replace(it, starforce=target, stats=stats, core=core)
            d, change = px.delta(slot, new)
            # 평균 메소(강화 + 흔적 복구 메소), 평균 파괴·스페어 소모. 스페어 값을 주면 비용에 '스페어 × 값'도 더한다
            t = sf_expected_totals(it.level, it.starforce, target, events.starforce(), events.spare_price)
            if d >= MIN_GAIN and t["cost"] > 0:
                mine.append(_entry(slot, "스타포스", t["cost"], d, kind=None, name=it.name, from_star=it.starforce,
                                   to_star=target, gain=g, expected_destroys=t["destroys"], expected_spares=t["spares"],
                                   meso=t["meso"], spare_price=events.spare_price, set_change=change))
        out += sorted(mine, key=lambda p: p["per_100m"], reverse=True)[:SF_PER_SLOT]
    return out


def balanced(paths: list[dict], per_path: int) -> list[dict]:
    """경로 종류(구매·직작·큐브·스타포스)마다 억당 상위 per_path개씩 모아 다시 억당 순으로(한 종류가 목록을 다 채우지 않게)."""
    count: dict[str, int] = {}
    keep = []
    for p in sorted(paths, key=lambda p: p["per_100m"], reverse=True):
        if count.get(p["path"], 0) < per_path:
            count[p["path"]] = count.get(p["path"], 0) + 1
            keep.append(p)
    return keep


def upgrade_paths(snap: CharacterSnapshot, setting: Setting, boss: BossProfile, catalog: SetCatalog,
                  observed: list[dict] | None = None, cooldown_main_pct: float | None = None,
                  events: Events | None = None) -> dict:
    events = events or Events()
    pl = _Planner(snap, setting, boss, catalog, cooldown_main_pct, events.miracle)
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
    out += _starforce_paths(pl, px, events)  # 지금 템 스타포스 강화
    out += hexa_stat_paths(pl, events.fragment_price, events.hexa_sunday)  # HEXA 스탯(조각 시세가 있을 때)
    shares, source = (snap.own_shares, "내 연무장 기록") if snap.own_shares else (
        (job_shares(snap.character_class) or {}).get("shares") or {}, "직업 기준값(연무장 상위 기록 중앙값)")
    out += core_paths(snap, shares, events.fragment_price, boss.defense, source)  # HEXA 스킬 코어
    for obs in observed or []:
        if not obs.get("price") or not obs.get("total"):
            continue
        slots = [s for s in SLOTS_BY_CATEGORY.get(obs["category"], (obs["category"],)) if s in pl.raw
                 and not (_part(s) == "보조무기" and snap.character_class in UNTRADEABLE_SECONDARY_JOBS)]  # 그 직업은 보조무기를 살 수 없다
        # 보조무기는 그 직업이 낄 수 있는 종류로 확인된 매물만(engine/market/secondary.py)
        slots = [s for s in slots if _part(s) != "보조무기" or secondary_fits(
            pl.raw[s].part, job_profile(snap.character_class).branches, obs.get("equip_type"), obs.get("job_groups")) is True]
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
                cube = expected_cost(kind, level, grade, t["grade"], t["reach_probability"], miracle=events.miracle)
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
