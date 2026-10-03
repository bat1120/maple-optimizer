"""세트 효과: 착용 아이템 → 세트별 개수 → StatBlock.

매핑·단계 표는 `engine/data/`의 생성 데이터(tools/derive_set_data.py)다.
무기 규칙(실측): 제네시스·데스티니 무기는 직업군 에테르넬 세트에 +1, 루타비스·앱솔랩스·아케인셰이드
직업군 세트에는 그 세트 장비가 3개 이상일 때 +1(럭키 아이템).
"""
import collections
import json
import pathlib
from collections.abc import Iterable
from dataclasses import dataclass

from engine.options import parse_option
from engine.stats.model import StatBlock
from engine.stats.snapshot import Item

DATA = pathlib.Path(__file__).resolve().parent.parent / "data"
SPECIAL_WEAPON = ("제네시스", "데스티니")
LUCKY_SETS = ("루타비스", "앱솔랩스", "아케인셰이드")
LUCKY_MIN = 3
# 장비가 아닌 출처(펫·캐시·심볼 등)의 세트. 장비 교체와 무관해 잔차가 흡수한다.
EXTERNAL_SETS = ("쁘띠", "마스터 ", "소멸의 여로", "별하늘", "크리스마스", "폼폼", "컬러링", "인형의 꿈",
                 "나이트 일루미네이션", "메이플 트레져", "퓨어 골드", "아르카나", "결속의 반지")
NOT_WORN_SLOTS = ("예비 특수 반지",)


@dataclass(frozen=True)
class SetCatalog:
    items: dict[str, str]
    tiers: dict[str, dict[int, str]]

    @classmethod
    def load(cls) -> "SetCatalog":
        items = json.loads((DATA / "set_items.json").read_text(encoding="utf-8"))["items"]
        sets = json.loads((DATA / "set_tiers.json").read_text(encoding="utf-8"))["sets"]
        return cls(items, {name: {int(k): v for k, v in t.items()} for name, t in sets.items()})


def count_sets(items: Iterable[Item], branches: tuple[str, ...], catalog: SetCatalog) -> collections.Counter:
    worn = [it for it in items if it.slot not in NOT_WORN_SLOTS]
    weapon = next((it for it in worn if it.slot == "무기"), None)
    special = weapon is not None and weapon.name.startswith(SPECIAL_WEAPON)
    counts: collections.Counter = collections.Counter()
    for it in worn:
        if special and it is weapon:
            continue
        name = catalog.items.get(it.name)
        if name:
            counts[name] += 1
    if special:
        for b in branches:
            counts[f"에테르넬 세트({b})"] += 1
            for prefix in LUCKY_SETS:
                key = f"{prefix} 세트({b})"
                if counts.get(key, 0) >= LUCKY_MIN:
                    counts[key] += 1
    return counts


def set_block(counts: dict[str, int], level: int, catalog: SetCatalog) -> tuple[StatBlock, list[str]]:
    """활성 단계(개수 이하)의 옵션을 모두 더한다. 단계 표에 없는 세트는 excluded로 돌려준다."""
    block, excluded = StatBlock(), []
    for name, n in counts.items():
        if n <= 0:
            continue
        tiers = catalog.tiers.get(name)
        if tiers is None:
            excluded.append(name)
            continue
        for need, text in tiers.items():
            if need <= n:
                for line in parse_option(text, level) or []:
                    block.add(line)
    return block, excluded
