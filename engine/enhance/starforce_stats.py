"""스타포스 성별 스탯 상승(2026-10-07): engine/data/starforce_stats.json.

- 표: 나무위키 '메이플스토리/스타포스 강화'(2026-10-07 열람). 넥슨 Open API 실측 item_starforce_option으로 검산했다
  (tests/test_starforce_stats.py — 픽스처 전체 스타포스 템에서 스탯·방어구 공격력·무기 공격력이 모두 일치)
- 스탯: 1~15성은 레벨과 무관, 16~22성은 레벨 구간별, 23성부터는 더 오르지 않는다
- 방어구·장신구 공격력·마력: 16성부터 레벨 구간별(둘 다). 장갑은 5·7·9·11·13·14·15성에 직업 공격 종류로 +1
- 무기 공격력·마력: 1~15성은 성마다 '지금 공격력(순수+주문서+앞 성 상승분) ÷ 50 내림 + 1'(실측 일치), 16성부터 레벨 구간별 표
- 계산하지 않는 템: 제네시스(22성 고정)·놀장·슈페리얼(타일런트·노바)·보조무기·0성(어느 스탯에 붙는지 모름)·표에 '?'인 구간
"""
import json
import math
import pathlib

from engine.stats.snapshot import Item

_T = json.loads((pathlib.Path(__file__).resolve().parent.parent / "data" / "starforce_stats.json").read_text(encoding="utf-8"))
STATS = ("STR", "DEX", "INT", "LUK")
_SKIP_SLOTS = ("보조무기", "엠블렘", "뱃지", "훈장", "포켓 아이템")
_SKIP_NAMES = ("제네시스", "타일런트", "노바 ")


def _bracket(level: int) -> str | None:
    for b in (250, 200, 160, 150, 140, 130):
        if level >= b:
            return str(b)
    return None


def _kind(it: Item) -> str:
    slot = it.slot.rstrip("0123456789")
    return "무기" if slot == "무기" else "장갑" if slot == "장갑" else "방어구"


def eligible(it: Item) -> bool:
    return (it.starforce > 0 and not it.amazing and not it.name.startswith(_SKIP_NAMES)
            and it.slot.rstrip("0123456789") not in _SKIP_SLOTS and any(it.sf_option.get(k) for k in STATS))


def _stat(level: int, star: int) -> int | None:
    if star <= 15:
        return _T["stat_1_15"][star - 1] if star else 0
    arr = _T["stat_16"].get(_bracket(level) or "", [])
    i = min(star, 22) - 16
    return arr[i] if i < len(arr) else None


def _table16(name: str, level: int, star: int) -> int | None:
    if star <= 15:
        return 0
    arr = _T[name].get(_bracket(level) or "", [])
    return arr[star - 16] if star - 16 < len(arr) else None


def _glove_key(it: Item) -> str | None:
    """장갑 1~15성 추가 공격력이 붙는 쪽(직업 공격 종류) — 지금 스타포스 옵션에서 더 큰 쪽."""
    a, m = it.sf_option.get("ATK", 0), it.sf_option.get("MATK", 0)
    return "ATK" if a > m else "MATK" if m > a else None


def cumulative(it: Item, star: int) -> dict[str, float] | None:
    """0성 → star성으로 올렸을 때의 스타포스 옵션(STAT = 직업 스탯 값, ATK·MATK). 표에 없는 구간이면 None."""
    stat = _stat(it.level, star)
    if stat is None:
        return None
    out: dict[str, float] = {"STAT": stat}
    kind = _kind(it)
    if kind == "무기":
        add = _table16("weapon_attack_16", it.level, star)
        if add is None:
            return None
        for k, a in it.scroll_attack.items():
            tot = 0
            for _ in range(min(star, 15)):
                inc = math.floor(a / 50) + 1
                tot, a = tot + inc, a + inc
            out[k] = tot + add
        return out
    add = _table16("armor_attack_16", it.level, star)
    if add is None:
        return None
    out["ATK"] = out["MATK"] = add
    if kind == "장갑":
        key = _glove_key(it)
        bonus = sum(1 for s in _T["glove_bonus_stars"] if s <= star)
        if key:
            out[key] += bonus
        elif bonus:
            return None  # 어느 쪽에 붙는지 모른다
    return out


def gain(it: Item, target: int) -> dict[str, float] | None:
    """지금 성 → target성의 스탯 상승(STR DEX INT LUK ATK MATK). 계산할 수 없으면 None.
    스탯 칸마다: 지금 값이 표의 누적값과 같으면 표 차이 전부, 다르면(도전자 망토의 비직업 스탯처럼 16성부터만 오르는 칸) 16성 이후 몫만."""
    if not eligible(it) or target <= it.starforce:
        return None
    now, then = cumulative(it, it.starforce), cumulative(it, target)
    if now is None or then is None:
        return None
    out: dict[str, float] = {}
    for k in STATS:
        v = it.sf_option.get(k, 0)
        if not v:
            continue
        d = then["STAT"] - now["STAT"] if v == now["STAT"] else then["STAT"] - max(now["STAT"], _stat(it.level, 15) or 0)
        if d > 0:
            out[k] = d
    for k in ("ATK", "MATK"):
        if k in then:
            d = then[k] - now.get(k, 0)
            if d:
                out[k] = d
    return out
