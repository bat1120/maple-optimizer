"""스탯 묶음과 최종 스탯 타입. 값은 모두 퍼센트 포인트(84.0 = 84%)."""
from dataclasses import dataclass, field

from engine.options import StatLine

_SCALAR = {"DMG": "dmg", "BOSS": "boss", "CD": "cd", "CR": "cr", "FD": "fd"}


@dataclass
class StatBlock:
    """출처 하나(아이템, 프리셋, 세트 등)가 주는 스탯."""
    flat: dict[str, float] = field(default_factory=dict)  # STR DEX INT LUK HP ATK MATK
    pct: dict[str, float] = field(default_factory=dict)
    dmg: float = 0.0
    boss: float = 0.0
    cd: float = 0.0
    cr: float = 0.0
    fd: float = 0.0
    ied: list[float] = field(default_factory=list)  # 방무는 곱연산이라 출처별로 보관

    def add(self, line: StatLine) -> None:
        if line.key in _SCALAR:
            attr = _SCALAR[line.key]
            setattr(self, attr, getattr(self, attr) + line.value)
        elif line.key == "IED":
            self.ied.append(line.value)
        else:
            d = self.pct if line.percent else self.flat
            d[line.key] = d.get(line.key, 0.0) + line.value

    def __add__(self, other: "StatBlock") -> "StatBlock":
        # 값이 전부 숫자라 사전·목록만 새로 만들면 된다. 전에는 copy.deepcopy였는데 계획 한 번에 10만 번 넘게 불려
        # 계산 시간의 70%를 썼다(2026-11-25 실측). 결과는 같다 — tests/test_stats_core.py
        out = StatBlock(dict(self.flat), dict(self.pct), self.dmg, self.boss, self.cd, self.cr, self.fd, list(self.ied))
        for k, v in other.flat.items():
            out.flat[k] = out.flat.get(k, 0.0) + v
        for k, v in other.pct.items():
            out.pct[k] = out.pct.get(k, 0.0) + v
        for attr in _SCALAR.values():
            setattr(out, attr, getattr(out, attr) + getattr(other, attr))
        out.ied = out.ied + other.ied
        return out

    def ied_total(self) -> float:
        remain = 1.0
        for x in self.ied:
            remain *= 1 - x / 100
        return 100 * (1 - remain)


@dataclass(frozen=True)
class FinalStats:
    """API 스탯창 최종값 한 세트."""
    stats: dict[str, int]  # STR DEX INT LUK HP
    ap: dict[str, int]     # AP 배분 STR ...
    atk: int
    matk: int
    dmg: float
    boss: float
    fd: float
    cd: float
    cr: float
    ied: float
    stat_attack_min: int
    stat_attack_max: int
    combat_power: int      # 참고용. 계산에 쓰지 않는다 (스펙 §5.1)
