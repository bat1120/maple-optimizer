"""넥슨 응답 JSON → 엔진 타입. 넥슨 키 이름은 이 파일 밖으로 나가지 않는다."""
from engine.stats.model import FinalStats

_FOUR = ("STR", "DEX", "INT", "LUK")


def num(v) -> float:
    """숫자 필드는 문자열("129", "116.00", "-633")이거나 정수로 온다."""
    if v is None or v == "":
        return 0.0
    return float(str(v).replace(",", ""))


def final_stats(stat_json: dict) -> FinalStats:
    s = {x["stat_name"]: x["stat_value"] for x in stat_json["final_stat"]}

    def i(name: str) -> int:
        return int(num(s.get(name)))

    def f(name: str) -> float:
        return num(s.get(name))

    return FinalStats(
        stats={k: i(k) for k in (*_FOUR, "HP")},
        ap={k: i(f"AP 배분 {k}") for k in (*_FOUR, "HP", "MP")},
        atk=i("공격력"),
        matk=i("마력"),
        dmg=f("데미지"),
        boss=f("보스 몬스터 데미지"),
        fd=f("최종 데미지"),
        cd=f("크리티컬 데미지"),
        cr=f("크리티컬 확률"),
        ied=f("방어율 무시"),
        stat_attack_min=i("최소 스탯공격력"),
        stat_attack_max=i("최대 스탯공격력"),
        combat_power=i("전투력"),
    )


def weapon_part(equipment_json: dict, preset: int | None = None) -> str:
    key = "item_equipment" if preset is None else f"item_equipment_preset_{preset}"
    for item in equipment_json.get(key) or []:
        if item["item_equipment_slot"] == "무기":
            return item["item_equipment_part"]
    raise ValueError(f"무기를 찾을 수 없습니다 ({key})")
