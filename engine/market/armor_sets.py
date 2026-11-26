"""방어구 세트 조합(2026-11-16 사용자: 카루타·앱솔랩스·아케인셰이드·에테르넬을 어떤 조합으로 맞추는 게 나은지 — 3카5앱처럼).

방어구 7칸마다 '지금 템' 또는 네 세트 템(직업 계열별)을 고른다. 전부 정확히 재면 수십만 번(한 번 ~1.4ms)이라:
1) 칸마다 템 자체의 몫(세트에 안 세지게 이름을 지운 사본으로 잰 실딜)을 한 번씩 잰다.
2) 모든 배치를 훑어 세트 구성(세트별 개수)이 같은 묶음마다 몫의 합이 가장 큰 배치를 고른다 — 같은 묶음이면 세트 효과는 같다.
3) 묶음마다 그 배치만 세트 효과(행운 아이템 무기 포함, count_sets)까지 넣어 정확히 잰다.
템 수치는 갈아타기와 같은 넥슨 API 실측 표(BASES), 잠재·에디·추옵·주문서는 지금 템 것을 옮긴다고 가정한다."""
import collections
import copy
from dataclasses import dataclass

from engine.market.recommend import UNTRADEABLE_PREFIX, _valued
from engine.market.swaps import BASES, _Swapper, synth_json
from engine.enhance.starforce import max_star
from engine.stats.metrics import BossProfile
from engine.stats.sets import SetCatalog, count_sets
from engine.stats.snapshot import CharacterSnapshot, Item, Setting

ARMOR_SLOTS = ("모자", "상의", "하의", "신발", "장갑", "망토", "어깨장식")
SETS = ("루타비스", "앱솔랩스", "아케인셰이드", "에테르넬")
SHORT = {"루타비스": "카루타", "앱솔랩스": "앱솔", "아케인셰이드": "아케인", "에테르넬": "에테르넬"}
CURRENT = "지금"


@dataclass
class Cand:
    name: str
    set: str          # 짧은 세트 이름(카루타·앱솔·아케인·에테르넬) 또는 '지금'
    branch: str | None
    item: Item        # 평가용(쿨감 환산 포함)
    starforce: int
    kept: bool = False  # 지금 낀 템 그대로


def _set_of(name: str) -> tuple[str, str] | None:
    s = (BASES.get(name) or {}).get("set") or ""
    for key in SETS:
        if s.startswith(key + " 세트(") and s.endswith(")"):
            return key, s[len(key) + 4:-1]
    return None


def _build(sw: _Swapper, slot: str, name: str) -> Item | None:
    cur = sw.pl.raw.get(slot)
    if cur is not None:
        return sw.like_current(slot, name)
    # 비어 있는 칸: 잠재·추옵·주문서 없이 고른 성으로
    from nexon.convert import item as convert
    star = min(sw.starforce or 0, max_star(BASES[name]["level"]))
    j = synth_json(name, slot, star, {}, {}, (), (), glove_attack=sw.job.attack)
    return convert(j, sw.snap.level) if j else None


def slot_candidates(sw: _Swapper, sets: tuple[str, ...] = SETS, raise_kept: bool = False) -> dict[str, list[Cand]]:
    """칸마다 후보: 지금 템(있으면) + 고른 세트들의 그 칸 템(이 직업 계열·레벨 이하·구매 가능).
    raise_kept: 지금 템도 고른 성까지 강화한다고 본다(컨설팅 — 새 템만 22성으로 가정하면 지금 템이 부당하게 밀린다)."""
    out = {}
    for slot in ARMOR_SLOTS:
        cs = []
        cur = sw.pl.raw.get(slot)
        if cur is not None:  # 지금 템도 네 세트 중 하나면 그 세트로 센다(지금 3카3앱이면 '카루타 3 · 앱솔 3')
            hit = _set_of(cur.name)
            kept_item, kept_star = sw.pl.items[slot], cur.starforce
            if raise_kept and cur.name in BASES and sw.star_for(cur, cur.name) > cur.starforce:
                up = sw.like_current(slot, cur.name)
                if up is not None:
                    kept_item, kept_star = _valued(up, sw.pl.mains, sw.pl.per_sec), up.starforce
            cs.append(Cand(cur.name, SHORT[hit[0]] if hit else CURRENT, hit[1] if hit else None, kept_item,
                           kept_star, kept=True))
        for name, b in BASES.items():
            hit = _set_of(name)
            if (hit is None or hit[0] not in sets or b["part"] != slot or b["level"] > sw.snap.level
                    or hit[1] not in sw.job.branches or name.startswith(UNTRADEABLE_PREFIX)
                    or (cur is not None and name == cur.name)):
                continue
            it = _build(sw, slot, name)
            if it is None:
                continue
            cs.append(Cand(name, SHORT[hit[0]], hit[1], _valued(it, sw.pl.mains, sw.pl.per_sec), it.starforce))
        out[slot] = cs
    return out


def _anon(it: Item) -> Item:
    """세트에 안 세지게 이름만 지운 사본 — 템 자체 스탯의 몫을 재는 데 쓴다."""
    out = copy.copy(it)
    out.name = "__몫__"
    return out


def _label(combo: list[Cand], multi_branch: bool, catalog: SetCatalog) -> str:
    n = collections.Counter((c.set, c.branch) for c in combo if c.set != CURRENT)
    parts = [f"{s}{f'({b})' if multi_branch else ''} {k}" for (s, b), k in
             sorted(n.items(), key=lambda x: (list(SHORT.values()).index(x[0][0]), x[0][1] or ""))]  # 3카4앱처럼 카·앱·아·에 순
    # 네 세트가 아닌 지금 템은 그 템 세트 이름으로(도전자의 장비 7), 세트가 없으면 '지금 템'
    rest = collections.Counter(((catalog.items.get(c.name) or "").split(" 세트")[0] or "지금 템") for c in combo if c.set == CURRENT)
    return " · ".join(parts + [f"{k} {v}" for k, v in rest.items()])


def armor_combos(snap: CharacterSnapshot, setting: Setting, boss: BossProfile, catalog: SetCatalog,
                 starforce: int = 18, sets: tuple[str, ...] = SETS, cooldown_main_pct: float | None = None,
                 top: int | None = None, raise_kept: bool = False) -> list[dict]:
    sw = _Swapper(snap, setting, boss, catalog, cooldown_main_pct, starforce)
    cands = slot_candidates(sw, sets, raise_kept)
    slots = [s for s in ARMOR_SLOTS if cands[s]]
    base, ev = sw.pl.base, sw.pl.ev
    # 1) 칸마다 템 자체 몫
    own = {}
    for s in slots:
        for i, c in enumerate(cands[s]):
            trial = dict(sw.pl.items)
            trial[s] = _anon(c.item)
            own[s, i] = ev.index(trial) / base - 1
    # 2) 세트 구성 묶음마다 몫의 합이 가장 큰 배치 — 칸을 하나씩 늘려 가며 묶음별 최선만 남긴다(전부 훑는 것과 같고 훨씬 빠름)
    keys = {(s, i): (c.set, c.branch or "") if c.set != CURRENT else (CURRENT, catalog.items.get(c.name) or "-")
            for s in slots for i, c in enumerate(cands[s])}
    best: dict[tuple, tuple[float, tuple[int, ...]]] = {(): (0.0, ())}
    for s in slots:
        nxt: dict[tuple, tuple[float, tuple[int, ...]]] = {}
        for sig, (score, idx) in best.items():
            for i in range(len(cands[s])):
                k = tuple(sorted(sig + (keys[s, i],)))
                # 한 세트를 두 계열로 섞는 건(에테르넬 도적 6 + 해적 1) 세트가 따로 세져 손해 — 묶음에서 뺀다
                if len({b for st, b in k if st == keys[s, i][0] and st != CURRENT}) > 1:
                    continue
                v = score + own[s, i]
                if k not in nxt or v > nxt[k][0]:
                    nxt[k] = (v, idx + (i,))
        best = nxt
    # 3) 묶음마다 그 배치를 세트 효과까지 정확히
    before = count_sets(sw.pl.items.values(), sw.job.branches, catalog)
    multi = len(sw.job.branches) > 1
    rows = []
    for _, idx in best.values():
        combo = [cands[s][i] for s, i in zip(slots, idx)]
        trial = dict(sw.pl.items)
        trial.update({s: c.item for s, c in zip(slots, combo)})
        after = count_sets(trial.values(), sw.job.branches, catalog)
        rows.append({
            "label": _label(combo, multi, catalog),
            "pieces": {s: {"name": c.name, "set": c.set, "branch": c.branch, "starforce": c.starforce, "kept": c.kept}
                       for s, c in zip(slots, combo)},
            "set_change": [{"set": k, "before": before.get(k, 0), "after": after.get(k, 0)}
                           for k in sorted(set(before) | set(after)) if before.get(k, 0) != after.get(k, 0)],
            "delta_pct": (ev.index(trial) / base - 1) * 100,
        })
    rows.sort(key=lambda r: r["delta_pct"], reverse=True)
    return rows[:top] if top else rows


# 대표 조합(2026-11-16 사용자: 3카5앱 같은 흔한 세팅) — 방어구 7칸 기준(무기는 지금 무기라 3카5앱 = 카루타 3 · 앱솔 4)
CLASSICS = {
    "3카 4앱": {"카루타": 3, "앱솔": 4},
    "3카 4아케인": {"카루타": 3, "아케인": 4},
    "3에테 4앱": {"에테르넬": 3, "앱솔": 4},
    "3에테 4아케인": {"에테르넬": 3, "아케인": 4},
    "4에테 3앱": {"에테르넬": 4, "앱솔": 3},
    "4에테 3아케인": {"에테르넬": 4, "아케인": 3},
    "3카 4에테": {"카루타": 3, "에테르넬": 4},
    "7에테": {"에테르넬": 7},
}


def classic_rows(rows: list[dict]) -> list[dict]:
    """대표 조합마다 그 세트 구성(계열은 아무거나)인 줄 중 실딜이 가장 높은 하나. 순위와 상관없이 준다."""
    out = []
    for name, want in CLASSICS.items():
        hits = [r for r in rows if collections.Counter(p["set"] for p in r["pieces"].values()) == want]
        if hits:
            out.append({**max(hits, key=lambda r: r["delta_pct"]), "classic": name})
    return sorted(out, key=lambda r: r["delta_pct"], reverse=True)
