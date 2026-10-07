"""보조무기 착용 가능 판정(2026-10-07): 경매장 보조무기 매물은 직업마다 종류가 달라 아무 직업이나 낄 수 없다.

- 지금 낀 보조무기의 종류(넥슨 Open API item_equipment_part: 마법깃펜·포스실드·화살깃…)와 매물 툴팁의 '장비분류'가 같아야 한다
- '방패'는 전사·마법사·도적이 같이 쓰는 종류라 툴팁의 착용 가능 직업군까지 맞아야 한다
- 못 읽었으면 None(모름) — 추정하지 않는다. 지금과 다른 종류로 바꿔 끼는 경우(예: 마도서 ↔ 방패)는 확인하지 못해 맞지 않는 것으로 본다
"""
SHARED_TYPES = ("방패",)


def _norm(s: str | None) -> str:
    return "".join(str(s or "").split())


def secondary_fits(worn_part: str | None, branches: tuple[str, ...], equip_type: str | None,
                   job_groups: list[str] | None) -> bool | None:
    if not equip_type or not worn_part:
        return None
    if _norm(equip_type) != _norm(worn_part):
        return False
    if _norm(equip_type) in SHARED_TYPES:
        if not job_groups:
            return None
        return any(b in job_groups for b in branches)
    return True
