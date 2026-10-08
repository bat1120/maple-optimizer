"""강화 이벤트·파괴 비용 조건(2026-10-07): 경로 비교·로드맵이 같은 조건으로 비용을 계산한다.

- 스타포스: 30% 할인 / 21성 이하 파괴 30% 감소 / 5·10·15성 100% / 흔적 복구 메소 20% 할인(넷 다 = 샤이닝 스타포스), 파괴 방지(15~17성)
- 큐브: 미라클 타임(잠재·에디 등급 상승 확률 2배)
- 파괴 비용: 흔적 복구 메소는 항상 넣고, 스페어 값(spare_price, 메소)을 주면 '스페어 개수 × 값'도 넣는다.
  부위마다 값이 다르면 spare_slots(부위 → 메소)가 그 부위만 덮어쓴다(2026-10-08)
"""
from dataclasses import dataclass, field

from engine.enhance.starforce import StarforceConditions

SF_FLAGS = ("discount30", "destroy_down30", "guarantee_5_10_15", "restore_discount20", "protect")


@dataclass(frozen=True)
class Events:
    discount30: bool = False
    destroy_down30: bool = False
    guarantee_5_10_15: bool = False
    restore_discount20: bool = False
    protect: bool = False
    miracle: bool = False
    spare_price: float = 0.0
    fragment_price: float = 0.0  # 솔 에르다 조각 1개 시세(메소) — 있어야 HEXA 경로를 억당으로 비교한다
    hexa_sunday: bool = False    # HEXA 스탯: 메인 5레벨 이상일 때 메인 강화 확률 ×1.2
    spare_slots: dict = field(default_factory=dict)  # 부위 → 스페어 1개 값(메소). 없는 부위는 spare_price

    def spare_for(self, slot: str) -> float:
        return self.spare_slots.get(slot, self.spare_price)

    @classmethod
    def parse(cls, sf: str | None = None, miracle: bool = False, spare_price: float | None = None,
              fragment_price: float | None = None, hexa_sunday: bool = False, spare_slots: str | None = None) -> "Events":
        """sf: 쉼표로 이은 스타포스 조건(SF_FLAGS 이름, 'shining' = 앞의 넷).
        spare_slots: '부위:메소'를 쉼표로 이은 것(예: '벨트:300000000,장갑:5e8')."""
        names = {n.strip() for n in (sf or "").split(",") if n.strip()}
        if "shining" in names:
            names |= {"discount30", "destroy_down30", "guarantee_5_10_15", "restore_discount20"}
        unknown = names - set(SF_FLAGS) - {"shining"}
        if unknown:
            raise ValueError(f"알 수 없는 스타포스 조건: {', '.join(sorted(unknown))}")
        return cls(**{n: True for n in names if n in SF_FLAGS}, miracle=miracle, spare_price=max(0.0, spare_price or 0.0),
                   fragment_price=max(0.0, fragment_price or 0.0), hexa_sunday=hexa_sunday,
                   spare_slots=_parse_spare_slots(spare_slots))

    def starforce(self) -> StarforceConditions:
        return StarforceConditions(discount30=self.discount30, destroy_down30=self.destroy_down30,
                                   guarantee_5_10_15=self.guarantee_5_10_15, protect=self.protect,
                                   restore_discount20=self.restore_discount20)

    def label(self) -> str:
        on = [t for f, t in (("discount30", "스타포스 30% 할인"), ("destroy_down30", "파괴 30% 감소"),
                             ("guarantee_5_10_15", "5·10·15성 100%"), ("restore_discount20", "복구 메소 20% 할인"),
                             ("protect", "파괴 방지"), ("miracle", "미라클 타임"),
                             ("hexa_sunday", "HEXA 스탯 확률 ×1.2")) if getattr(self, f)]
        return " · ".join(on) if on else "이벤트 없음"


def _parse_spare_slots(text: str | None) -> dict:
    out = {}
    for part in (p.strip() for p in (text or "").split(",")):
        if not part:
            continue
        slot, sep, value = part.rpartition(":")
        try:
            meso = float(value)
        except ValueError:
            meso = -1.0
        if not sep or not slot.strip() or not meso >= 0:
            raise ValueError(f"부위별 스페어 값은 '부위:메소' 형식이에요: {part}")
        out[slot.strip()] = meso
    return out
