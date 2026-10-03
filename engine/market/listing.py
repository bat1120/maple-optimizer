"""매물 평가: 현재 세팅의 같은 부위와 교체했을 때 보스 실딜 상승률과 억당 효율."""
from dataclasses import dataclass

from engine.options import StatLine, parse_option
from engine.stats.evaluate import evaluate_setting, swap_item
from engine.stats.metrics import BossProfile
from engine.stats.model import StatBlock
from engine.stats.sets import SetCatalog
from engine.stats.snapshot import CharacterSnapshot, Item, Setting

HUNDRED_MILLION = 100_000_000
_FOUR = ("STR", "DEX", "INT", "LUK")
_TOTAL_KEYS = {"STR", "DEX", "INT", "LUK", "HP", "ATK", "MATK", "ALL%", "BOSS", "IED", "DMG"}


class InvalidPrice(ValueError):
    """가격 − 판매 예상가 ≤ 0. 효율이 정의되지 않는다."""


class NoDamage(ValueError):
    """현재 세팅의 보스 실딜 지수가 0 (방무 부족). 상승률을 정의할 수 없다."""


@dataclass(frozen=True)
class Listing:
    slot: str
    item: Item
    price: int        # 메소
    resale: int = 0   # 지금 그 부위 템의 판매 예상가 (메소)


@dataclass(frozen=True)
class ListingEval:
    listing: Listing
    base: float       # 현재 실딜 지수
    new: float        # 교체 후 실딜 지수
    delta_pct: float  # (new/base − 1) × 100
    per_100m: float   # delta_pct ÷ ((가격 − 판매가)/1억)


def item_from_input(slot: str, part: str, name: str, total: dict[str, float], potentials: list[str],
                    level: int, starforce: int = 0) -> Item:
    """경매장 툴팁의 총 옵션 수치 + 잠재·에디 문자열 → Item. 모르는 옵션은 excluded로 남긴다."""
    unknown = set(total) - _TOTAL_KEYS
    if unknown:
        raise ValueError(f"알 수 없는 총 옵션 키: {sorted(unknown)}")
    stats = StatBlock()
    for key, value in total.items():
        if not value:
            continue
        if key == "ALL%":
            for s in _FOUR:
                stats.add(StatLine(s, value, True))
        elif key in ("BOSS", "IED", "DMG"):
            stats.add(StatLine(key, value, True))
        else:
            stats.add(StatLine(key, value, False))
    excluded = []
    for text in potentials:
        lines = parse_option(text, level)
        if lines is None:
            excluded.append(text)
            continue
        for line in lines:
            stats.add(line)
    return Item(slot=slot, part=part, name=name, starforce=starforce, stats=stats, excluded=excluded)


def evaluate_listing(snap: CharacterSnapshot, setting: Setting, listing: Listing, boss: BossProfile,
                     catalog: SetCatalog) -> ListingEval:
    cost = listing.price - listing.resale
    if cost <= 0:
        raise InvalidPrice(f"가격({listing.price:,})이 판매 예상가({listing.resale:,}) 이하입니다")
    base = evaluate_setting(snap, setting, boss, catalog)
    if base <= 0:
        raise NoDamage(f"{boss.name}: 방어율 무시가 부족해 현재 데미지가 0입니다 (방무 {snap.final.ied:.2f}%)")
    new = swap_item(snap, setting, listing.slot, listing.item, boss, catalog)
    delta = (new / base - 1) * 100
    return ListingEval(listing, base, new, delta, delta / (cost / HUNDRED_MILLION))


def rank_listings(snap: CharacterSnapshot, setting: Setting, listings: list[Listing], boss: BossProfile,
                  catalog: SetCatalog) -> list[ListingEval]:
    evals = [evaluate_listing(snap, setting, x, boss, catalog) for x in listings]
    return sorted(evals, key=lambda e: e.per_100m, reverse=True)
