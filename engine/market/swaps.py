"""다른 템으로 갈아타기(2026-11-13): 부위마다 지금 템 대신 다른 템(다른 세트)을 끼면 실딜이 어떻게 되는지,
그리고 그 템이 '어느 수준 이상'이어야 지금보다 나은지를 계산한다.

가정한 템은 실측 수치로만 합성한다(숫자 추정 금지):
- 기본 옵션·주문서 칸 수·추옵 표본: engine/data/item_bases.json(픽스처 착용 장비, tools/derive_item_bases.py)
- 스타포스: 성별 스탯 표(engine/enhance/starforce_stats.py, 실측 검산) — 지금 템과 같은 성(그 템 최대 성까지)
- 세트 효과: 템 이름으로 세트 개수를 다시 센다(engine/stats/sets.py)
합성 결과가 실제 착용 템의 총 옵션을 재현하는지는 tests/test_swaps.py가 픽스처 전체로 검산한다.

보는 값:
- same: 성·잠재·에디·추옵 수치·주문서(칸 수 비율)를 지금 템 그대로 옮겼을 때
- flame: 추옵만 그 템 착용자 실측 표본으로 바꿔 가며(나머지는 same과 같음) — 중앙값과 '지금보다 나은 비율'
- potential: 그 템에 잠재 단계(에픽→레전드리, 좋은 줄 2→3)를 띄웠을 때 — 지금보다 처음 나아지는 단계(손익분기)
익셉셔널은 다른 템에 옮기지 않는다(0으로 본다). 경매장 거래 가능 여부는 확인된 구매 불가 템만 뺀다.
"""
import copy
import json
import pathlib
import statistics

from engine.enhance.starforce import max_star
from engine.enhance.starforce_stats import cumulative
from engine.market.paths import _Paths
from engine.market.recommend import UNTRADEABLE_PREFIX, _part, _Planner
from engine.stats.jobs import job_profile
from engine.stats.metrics import BossProfile
from engine.stats.model import StatBlock
from engine.stats.sets import SetCatalog
from engine.stats.snapshot import CharacterSnapshot, Item, Setting
from nexon.convert import item as convert_item

BASES: dict[str, dict] = json.loads((pathlib.Path(__file__).resolve().parents[1] / "data" / "item_bases.json")
                                    .read_text(encoding="utf-8"))["items"]
SKIP_PARTS = ("무기", "보조무기", "엠블렘")  # 직업 전용·구매 불가가 많고 무기 스타포스는 따로 — 갈아타기 대상에서 뺀다
_TIP_TO_API = {"STR": "str", "DEX": "dex", "INT": "int", "LUK": "luk", "최대 HP": "max_hp", "공격력": "attack_power",
               "마력": "magic_power", "보스 몬스터 공격 시 데미지": "boss_damage", "몬스터 방어율 무시": "ignore_monster_armor",
               "데미지": "damage", "올스탯": "all_stat"}


def _num(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _sum(*blocks: dict) -> dict:
    out: dict[str, float] = {}
    for b in blocks:
        for k, v in (b or {}).items():
            if k in ("base_equipment_level", "equipment_level_decrease", "exceptional_upgrade"):
                continue
            if _num(v):
                out[k] = out.get(k, 0) + _num(v)
    return {k: int(v) if float(v).is_integer() else v for k, v in out.items()}


def _sf_api(name: str, slot: str, star: int, glove_attack: str | None, has: dict) -> dict | None:
    """그 템 star성의 스타포스 옵션(API 형식). 표로 못 재거나 스탯이 어느 칸에 붙는지 모르면 None.
    has: 기본+주문서 스탯 — 16성부터만 오르는 칸은 기본·주문서에 그 스탯이 있을 때만 오르고 추옵만으로는 안 오른다
    (픽스처 실측: 에테르넬 시프셔츠 STR은 주문서 STR이 있는 착용자만 119, 칼리는 추옵 STR 35뿐이라 0.
    하이네스 워리어헬름 LUK은 주문서 LUK 2인 팔라딘만 77, 추옵 LUK 20뿐인 다크나이트는 0)."""
    if star <= 0:
        return {}
    b = BASES[name]
    if not b["sf_stats"]:
        return None
    prov = Item(slot=slot, part=b["part"], name=name, starforce=star, stats=StatBlock(), level=b["level"],
                sf_option={glove_attack: 1.0} if glove_attack else {})
    sf = cumulative(prov, star)
    if sf is None:
        return None
    out = {k.lower(): sf["STAT"] for k in b["sf_stats"]} if sf.get("STAT") else {}
    if star > 15 and b.get("sf_stats_16"):  # 16성부터만 오르는 칸(직업 전용 방어구의 비직업 스탯 등)
        upto15 = cumulative(prov, 15)
        if upto15 is None:
            return None
        out.update({k.lower(): sf["STAT"] - upto15["STAT"] for k in b["sf_stats_16"] if _num(has.get(k.lower()))})
    for key, api in (("ATK", "attack_power"), ("MATK", "magic_power")):
        if sf.get(key):
            out[api] = sf[key]
    return out


def synth_json(name: str, slot: str, star: int, add: dict, etc: dict, potentials=(), additional=(),
               glove_attack: str | None = None, exceptional: dict | None = None) -> dict | None:
    """실측 표의 템을 star성·추옵(add)·주문서(etc)·잠재로 꾸민 넥슨 API 형식 장비. 표에 없거나 못 재면 None."""
    b = BASES.get(name)
    if b is None or (_part(slot) == "장갑" and star > 0 and glove_attack is None):
        return None
    sf = _sf_api(name, slot, star, glove_attack, _sum(b["base"], etc))
    if sf is None:
        return None
    pots, adds = list(potentials)[:3], list(additional)[:3]
    j = {"item_equipment_slot": slot, "item_equipment_part": b["part"], "item_name": name, "starforce": str(star),
         "item_base_option": {**b["base"], "base_equipment_level": b["level"]},
         "item_add_option": dict(add or {}), "item_etc_option": dict(etc or {}), "item_starforce_option": sf,
         "item_exceptional_option": dict(exceptional or {}),
         "item_total_option": _sum(b["base"], add, etc, sf),
         "potential_option_grade": "레전드리" if pots else None, "additional_potential_option_grade": "레전드리" if adds else None}
    for n in (1, 2, 3):
        j[f"potential_option_{n}"] = pots[n - 1] if n <= len(pots) else None
        j[f"additional_potential_option_{n}"] = adds[n - 1] if n <= len(adds) else None
    return j


def _parts_of(it: Item, part: str) -> dict:
    """지금 템 툴팁 줄에서 출처별 값(add=추옵, etc=주문서, exc=익셉셔널)을 API 형식으로."""
    return {_TIP_TO_API[r["label"]]: r[part] for r in it.tip_stats if r.get(part) and r["label"] in _TIP_TO_API}


class _Swapper:
    def __init__(self, snap: CharacterSnapshot, setting: Setting, boss: BossProfile, catalog: SetCatalog,
                 cooldown_main_pct: float | None = None):
        self.snap = snap
        self.pl = _Planner(snap, setting, boss, catalog, cooldown_main_pct)
        self.px = _Paths(self.pl, catalog)
        self.job = job_profile(snap.character_class)

    def build(self, slot: str, name: str, star: int, add: dict, etc: dict, potentials, additional,
              exceptional: dict | None = None) -> Item | None:
        j = synth_json(name, slot, star, add, etc, potentials, additional, glove_attack=self.job.attack,
                       exceptional=exceptional)
        if j is None:
            return None
        it = convert_item(j, self.snap.level)
        cur = self.pl.raw[slot]
        it.potential_grade, it.additional_grade = cur.potential_grade, cur.additional_grade  # 큐브 단계 계산의 출발 등급
        return it

    def _etc_for(self, cur: Item, name: str) -> dict:
        """주문서: 지금 템 주문서 값을 칸 수 비율로(같은 주문서를 칸마다 했다고 본다)."""
        etc = _parts_of(cur, "etc")
        mine, theirs = (BASES.get(cur.name) or {}).get("slots"), BASES[name]["slots"]
        if not mine or mine == theirs:
            return etc
        return {k: round(v * theirs / mine) for k, v in etc.items()}

    def star_for(self, cur: Item, name: str) -> int:
        return min(cur.starforce, max_star(BASES[name]["level"]))

    def like_current(self, slot: str, name: str, add: dict | None = None) -> Item | None:
        """지금 템과 같은 성·잠재·에디·추옵·주문서로 name 템을 낀다고 가정(익셉셔널은 같은 템일 때만)."""
        cur = self.pl.raw[slot]
        return self.build(slot, name, self.star_for(cur, name), _parts_of(cur, "add") if add is None else add,
                          self._etc_for(cur, name), cur.potentials, cur.additional,
                          _parts_of(cur, "exc") if name == cur.name else None)

    def delta(self, slot: str, it: Item) -> tuple[float, list[dict]]:
        return self.px.delta(slot, it)

    def candidates(self, slot: str, cur: Item) -> list[str]:
        worn = {it.name for s, it in self.pl.raw.items() if s != slot}
        return [n for n, b in BASES.items()
                if b["part"] == cur.part and n != cur.name and n not in worn and b["level"] <= self.snap.level
                and set(b["branches"]) & set(self.job.branches) and not n.startswith(UNTRADEABLE_PREFIX)]

    def potential_tiers(self, slot: str, it: Item) -> list[dict]:
        """그 템을 낀 상태에서 잠재 단계별 실딜(지금 템 기준 %). _Planner.tiers를 그 템으로 바꿔 돌린다."""
        sub = copy.copy(self.pl)
        sub.raw = dict(self.pl.raw)
        sub.raw[slot] = it
        return [{"grade": t["grade"], "lines_good": t["lines_good"], "target": t["target"], "delta_pct": t["delta_pct"],
                 "probability": t["probability"]} for t in sub.tiers(slot, "잠재")]


def swap_candidates(snap: CharacterSnapshot, setting: Setting, boss: BossProfile, catalog: SetCatalog,
                    cooldown_main_pct: float | None = None, per_slot: int = 3) -> list[dict]:
    sw = _Swapper(snap, setting, boss, catalog, cooldown_main_pct)
    branch = sw.job.branches[0] if len(sw.job.branches) == 1 else "/".join(sw.job.branches)
    set_name = lambda n: n.replace("{branch}", branch) if n else n  # noqa: E731 — 도전자의 장비 세트({branch}) → (마법사)
    out = []
    for slot, cur in sw.pl.slots():
        if _part(slot) in SKIP_PARTS or cur.special_ring_level:
            continue
        rows = []
        for name in sw.candidates(slot, cur):
            same = sw.like_current(slot, name)
            if same is None:
                continue
            d_same, change = sw.delta(slot, same)
            b = BASES[name]
            # 추옵 표본이 전부 비었으면(반지처럼 추옵이 안 붙는 템) 분포가 아니다 — 없다고 표시
            has_flame = any(b["flames"])
            pairs = sorted(((sw.delta(slot, f)[0], i) for i, f in
                            ((i, sw.like_current(slot, name, add=a)) for i, a in enumerate(b["flames"])) if f is not None),
                           key=lambda t: t[0]) if has_flame else []
            flames = [d for d, _ in pairs]
            rows.append({"slot": slot, "name": name, "set": set_name(b["set"]), "level": b["level"], "starforce": sw.star_for(cur, name),
                         "wearers": b["wearers"],
                         "current": {"name": cur.name, "set": set_name((BASES.get(cur.name) or {}).get("set")), "level": cur.level,
                                     "starforce": cur.starforce, "potentials": list(cur.potentials),
                                     "additional": list(cur.additional)},
                         "set_change": change, "same": d_same, "_item": same,
                         # 보통 추옵 = 착용자 실측 표본을 실딜 순으로 놓은 가운데(짝수면 아래쪽) 표본 하나 — 평균 같은 추정값이 아니다
                         "_mid_flame": b["flames"][pairs[(len(pairs) - 1) // 2][1]] if pairs else {},
                         "flame": {"samples": len(flames), "min": min(flames), "median": statistics.median(flames),
                                   "max": max(flames), "better_share": sum(d > 0 for d in flames) / len(flames)}
                         if flames else {"samples": 0, "none": not has_flame}})
        rows.sort(key=lambda r: r["flame"].get("median", r["same"]), reverse=True)
        # 잠재 단계 사다리는 주스탯·공격·보공·방무·크뎀·뎀 줄만 쓴다 — 지금 잠재에 그 밖의 줄(크리티컬 확률 등)이 있으면
        # 사다리 어느 단계도 그 줄을 잃어 손해일 수 있다(2026-11-13 내신부레테 도미네이터 펜던트 크확 +6%)
        skipped = [t for t in cur.potentials if not sw.pl.is_useful(t)]
        for r in rows[:per_slot]:
            it = r.pop("_item")
            tiers = sw.potential_tiers(slot, it)
            bare = sw.build(slot, r["name"], r["starforce"], _parts_of(cur, "add"), sw._etc_for(cur, r["name"]), [],
                            cur.additional)
            r["potential"] = {"none": sw.delta(slot, bare)[0] if bare else None,  # 잠재를 비워도(나머지는 same과 같게)
                              "break_even": next((t for t in tiers if t["delta_pct"] > 0), None), "tiers": tiers,
                              "ladder_skips": skipped}
            # 보통 매물 기준(2026-11-13 실사용: 추옵이 STR·LUK 쪽이고 에디 없는 18성 레전드리 커포링이 +0.08%뿐):
            # 지금 템 추옵·에디를 옮길 수는 없다 — 착용자 가운데 추옵 + 에디 없음으로 다시 손익분기를 잰다
            mid = r.pop("_mid_flame")
            plain = sw.build(slot, r["name"], r["starforce"], mid, sw._etc_for(cur, r["name"]), [], [])
            m_tiers = sw.potential_tiers(slot, plain) if plain else []
            r["market"] = {"flame": mid, "additional": [], "none": sw.delta(slot, plain)[0] if plain else None,
                           "break_even": next((t for t in m_tiers if t["delta_pct"] > 0), None), "tiers": m_tiers}
            out.append(r)
    return sorted(out, key=lambda r: r["flame"].get("median", r["same"]), reverse=True)


__all__ = ["BASES", "swap_candidates", "synth_json"]
