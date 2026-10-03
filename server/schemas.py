"""API 입력 스키마."""
from pydantic import BaseModel, Field


class SettingIn(BaseModel):
    equipment: int = Field(ge=1, le=3)
    hyper: int = Field(ge=1, le=3)
    ability: int = Field(ge=1, le=3)


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
    listings: list[ListingIn]
