"""강화 이벤트·파괴 비용 조건(2026-10-07): 경로 비교·로드맵이 같은 조건으로 비용을 계산한다.

- 스타포스: 30% 할인 / 21성 이하 파괴 30% 감소 / 5·10·15성 100% / 흔적 복구 메소 20% 할인(넷 다 = 샤이닝 스타포스), 파괴 방지(15~17성)
- 큐브: 미라클 타임(잠재·에디 등급 상승 확률 2배)
- 파괴 비용: 흔적 복구 메소는 항상 넣고, 스페어 값(spare_price, 메소)을 주면 '스페어 개수 × 값'도 넣는다
- 추옵: 환생의 불꽃 1개 값(flame_prices, 메소) — 공식 메소 가격이 없어 사용자가 넣은 불꽃만 경로에 넣는다
  (메소 추가옵션 재설정은 공식 1회 3,000,000 메소라 항상 들어간다, engine/enhance/flame.py)
"""
from dataclasses import dataclass

from engine.enhance.flame import KINDS as FLAME_KINDS
from engine.enhance.flame import MESO_RESET
from engine.enhance.starforce import StarforceConditions

SF_FLAGS = ("discount30", "destroy_down30", "guarantee_5_10_15", "restore_discount20", "protect")
# 불꽃 가격 입력의 줄임 이름 → 아이템 이름
FLAME_SHORT = {"강력": "강력한 환생의 불꽃", "타오르는": "타오르는 환생의 불꽃", "영원": "영원한 환생의 불꽃",
               "검은": "검은 환생의 불꽃", "심연": "심연의 환생의 불꽃"}


@dataclass(frozen=True)
class Events:
    discount30: bool = False
    destroy_down30: bool = False
    guarantee_5_10_15: bool = False
    restore_discount20: bool = False
    protect: bool = False
    miracle: bool = False
    spare_price: float = 0.0
    spare_by_slot: tuple = ()    # ((부위, 메소), …) — 넣은 부위만 spare_price 대신(2026-10-11)
    fragment_price: float = 0.0  # 솔 에르다 조각 1개 시세(메소) — 있어야 HEXA 경로를 억당으로 비교한다
    hexa_sunday: bool = False    # HEXA 스탯: 메인 5레벨 이상일 때 메인 강화 확률 ×1.2
    flame_prices: tuple = ()     # ((불꽃 이름, 1개 메소), …) — 넣은 불꽃만 추옵 경로에 넣는다(2026-10-11)

    @classmethod
    def parse(cls, sf: str | None = None, miracle: bool = False, spare_price: float | None = None,
              fragment_price: float | None = None, hexa_sunday: bool = False, spare_by_slot: str | None = None,
              flame_prices: str | None = None) -> "Events":
        """sf: 쉼표로 이은 스타포스 조건(SF_FLAGS 이름, 'shining' = 앞의 넷).
        flame_prices: '불꽃:메소'를 쉼표로(불꽃 = 강력·타오르는·영원·검은·심연 또는 아이템 이름)."""
        names = {n.strip() for n in (sf or "").split(",") if n.strip()}
        if "shining" in names:
            names |= {"discount30", "destroy_down30", "guarantee_5_10_15", "restore_discount20"}
        unknown = names - set(SF_FLAGS) - {"shining"}
        if unknown:
            raise ValueError(f"알 수 없는 스타포스 조건: {', '.join(sorted(unknown))}")
        by_slot = []
        for part in (spare_by_slot or "").split(","):
            if not part.strip():
                continue
            slot, sep, val = part.partition(":")
            try:
                by_slot.append((slot.strip(), max(0.0, float(val))))
            except ValueError:
                raise ValueError(f"부위별 스페어 값은 '부위:메소' 형식이에요: {part.strip()}") from None
            if not sep or not slot.strip():
                raise ValueError(f"부위별 스페어 값은 '부위:메소' 형식이에요: {part.strip()}")
        return cls(**{n: True for n in names if n in SF_FLAGS}, miracle=miracle, spare_price=max(0.0, spare_price or 0.0),
                   spare_by_slot=tuple(by_slot), flame_prices=_flame_prices(flame_prices),
                   fragment_price=max(0.0, fragment_price or 0.0), hexa_sunday=hexa_sunday)

    def spare_for(self, slot: str) -> float:
        """그 부위 스페어 1개 값(메소): 부위별 값이 있으면 그것, 없으면 공통 값."""
        return next((v for s, v in self.spare_by_slot if s == slot), self.spare_price)

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


def _flame_prices(text: str | None) -> tuple:
    out = []
    for part in (text or "").split(","):
        if not part.strip():
            continue
        name, sep, val = part.partition(":")
        name = FLAME_SHORT.get(name.strip(), name.strip())
        if not sep or name not in FLAME_KINDS or name == MESO_RESET:
            raise ValueError(f"불꽃 가격은 '불꽃:메소' 형식이에요(불꽃: {', '.join(FLAME_SHORT)}): {part.strip()}")
        try:
            price = float(val)
        except ValueError:
            raise ValueError(f"불꽃 가격은 '불꽃:메소' 형식이에요: {part.strip()}") from None
        if price > 0:
            out.append((name, price))
    return tuple(out)
