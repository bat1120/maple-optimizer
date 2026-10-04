"""API 입력 스키마."""
from pydantic import BaseModel, Field


class SettingIn(BaseModel):
    equipment: int = Field(ge=1, le=3)
    hyper: int = Field(ge=1, le=3)
    ability: int = Field(ge=1, le=3)
    union: int | None = Field(None, ge=1, le=10)
    link: int | None = Field(None, ge=0, le=3)


class ListingIn(BaseModel):
    slot: str
    part: str
    name: str
    total: dict[str, float] = {}
    potentials: list[str] = []
    starforce: int = 0
    price: int
    resale: int = 0


class ListingsIn(BaseModel):
    setting: SettingIn | None = None
    boss_defense: float = 300.0
    fee_rate: float = Field(0.05, ge=0, le=0.1)  # 경매장 판매 수수료(5%, MVP 실버↑·PC방 3%)
    listings: list[ListingIn]


class StarforceConditionsIn(BaseModel):
    discount30: bool = False
    destroy_down30: bool = False
    guarantee_5_10_15: bool = False
    protect: bool = False
    restore: str = Field("full", pattern="^(full|basic)$")


class StarforceIn(BaseModel):
    level: int = Field(ge=1, le=300)
    start: int = Field(ge=0, le=29)
    target: int = Field(ge=1, le=30)
    destroy_cost: float = Field(ge=0)
    conditions: StarforceConditionsIn = StarforceConditionsIn()
    trials: int = Field(20000, ge=1000, le=200000)


class SumTarget(BaseModel):
    key: str
    percent: bool = True
    value: float


class CubeIn(BaseModel):
    table: str
    level: int = Field(ge=1, le=300)
    grade: str
    lines_at_least: dict[str, int] = {}
    sum_at_least: list[SumTarget] = []


class CraftIn(BaseModel):
    price: float = Field(gt=0)
    base_price: float = Field(ge=0)
    level: int = Field(ge=1, le=300)
    start_star: int = Field(0, ge=0, le=30)
    target_star: int = Field(0, ge=0, le=30)
    destroy_cost: float = Field(0, ge=0)
    conditions: StarforceConditionsIn = StarforceConditionsIn()
    cube_p: float = Field(0, ge=0, le=1)
    cube_cost: float = Field(0, ge=0)


class OptimizeIn(BaseModel):
    setting: SettingIn | None = None
    boss_defense: float = 300.0
    budget: float = Field(ge=0)
    fee_rate: float = Field(0.05, ge=0, le=0.1)
    candidates: list[ListingIn]
