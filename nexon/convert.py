"""넥슨 응답 JSON → 엔진 타입. 넥슨 키 이름은 이 파일 밖으로 나가지 않는다."""
from engine.options import StatLine, parse_option
from engine.stats.model import FinalStats, StatBlock
from engine.stats.snapshot import CharacterSnapshot, Item

_FOUR = ("STR", "DEX", "INT", "LUK")


def num(v) -> float:
    """숫자 필드는 문자열("129", "116.00", "-633")이거나 정수로 온다."""
    if v is None or v == "":
        return 0.0
    return float(str(v).replace(",", ""))


# 공식·평가에 쓰는 스탯. 빠지면 0으로 메우지 않고 멈춘다 (스펙: 추정하지 않는다).
_REQUIRED = {*_FOUR, "HP", "공격력", "마력", "데미지", "보스 몬스터 데미지", "최종 데미지",
             "크리티컬 데미지", "방어율 무시", "최대 스탯공격력"}


def final_stats(stat_json: dict) -> FinalStats:
    s = {x["stat_name"]: x["stat_value"] for x in stat_json["final_stat"]}
    missing = sorted(_REQUIRED - s.keys())
    if missing:
        raise ValueError(f"스탯 응답에 필수 항목이 없습니다: {', '.join(missing)}")

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


_OPTION_FLAT = {"str": "STR", "dex": "DEX", "int": "INT", "luk": "LUK", "max_hp": "HP",
                "attack_power": "ATK", "magic_power": "MATK"}


def _total_option_block(opt: dict) -> StatBlock:
    """옵션 블록 → StatBlock. item_total_option은 기본+추옵+주문서+스타포스 합이고 익셉셔널은 들어 있지 않다
    (fixture 66건 실측) — 익셉셔널 블록은 따로 넘겨 더한다."""
    b = StatBlock()
    for k, key in _OPTION_FLAT.items():
        if num(opt.get(k)):
            b.add(StatLine(key, num(opt.get(k)), False))
    if num(opt.get("all_stat")):
        for key in _FOUR:
            b.add(StatLine(key, num(opt["all_stat"]), True))
    if num(opt.get("max_hp_rate")):
        b.add(StatLine("HP", num(opt["max_hp_rate"]), True))
    if num(opt.get("boss_damage")):
        b.add(StatLine("BOSS", num(opt["boss_damage"]), True))
    if num(opt.get("damage")):
        b.add(StatLine("DMG", num(opt["damage"]), True))
    if num(opt.get("ignore_monster_armor")):
        b.add(StatLine("IED", num(opt["ignore_monster_armor"]), True))
    return b


def _add_texts(block: StatBlock, texts, level: int, excluded: list[str]) -> None:
    for t in texts:
        if not t:
            continue
        lines = parse_option(t, level)
        if lines is None:
            excluded.append(t)
            continue
        for line in lines:
            block.add(line)


def item(item_json: dict, level: int) -> Item:
    stats = (_total_option_block(item_json.get("item_total_option") or {})
             + _total_option_block(item_json.get("item_exceptional_option") or {}))
    excluded: list[str] = []
    prefixes = ("potential_option_", "additional_potential_option_", "soul_potential_option_")
    texts = [item_json.get(f"{p}{n}") for p in prefixes for n in (1, 2, 3)]
    # 소울: soul_active가 비어 있어도 soul_option이 오는 경우가 있다(나이트로드). soul_pad/soul_mad는 의미 미확인 → 1b에서 판단.
    texts.append(item_json.get("soul_option"))
    _add_texts(stats, texts, level, excluded)
    return Item(
        slot=item_json["item_equipment_slot"],
        part=item_json["item_equipment_part"],
        name=item_json["item_name"],
        starforce=int(num(item_json.get("starforce"))),
        stats=stats,
        excluded=excluded,
    )


def snapshot(bundle: dict[str, dict]) -> CharacterSnapshot:
    basic = bundle["character/basic"]
    level = int(num(basic["character_level"]))
    eq = bundle["character/item-equipment"]
    hy = bundle["character/hyper-stat"]
    ab = bundle["character/ability"]
    excluded: list[str] = []

    equipment: dict[int, dict[str, Item]] = {}
    for n in (1, 2, 3):
        items = [item(x, level) for x in eq.get(f"item_equipment_preset_{n}") or []]
        equipment[n] = {it.slot: it for it in items}
        for it in items:
            excluded.extend(it.excluded)
    # 프리셋을 쓰지 않는 캐릭터는 preset_no가 비거나 프리셋 목록이 null이다 → 현재 착용을 그 프리셋으로 본다.
    active_eq = int(num(eq.get("preset_no"))) or 1
    if not equipment.get(active_eq):
        current = [item(x, level) for x in eq.get("item_equipment") or []]
        equipment[active_eq] = {it.slot: it for it in current}
        for it in current:
            excluded.extend(it.excluded)

    hyper: dict[int, StatBlock] = {}
    for n in (1, 2, 3):
        b = StatBlock()
        _add_texts(b, [s.get("stat_increase") for s in hy.get(f"hyper_stat_preset_{n}") or []], level, excluded)
        hyper[n] = b

    ability: dict[int, StatBlock] = {}
    for n in (1, 2, 3):
        b = StatBlock()
        info = (ab.get(f"ability_preset_{n}") or {}).get("ability_info", [])
        _add_texts(b, [a.get("ability_value") for a in info], level, excluded)
        ability[n] = b

    return CharacterSnapshot(
        character_class=basic["character_class"],
        level=level,
        date=bundle["character/stat"].get("date"),
        final=final_stats(bundle["character/stat"]),
        equipment_presets=equipment,
        active_equipment_preset=active_eq,
        hyper_presets=hyper,
        active_hyper_preset=int(num(hy.get("use_preset_no"))) or 1,
        ability_presets=ability,
        active_ability_preset=int(num(ab.get("preset_no"))) or 1,
        excluded=excluded,
    )
