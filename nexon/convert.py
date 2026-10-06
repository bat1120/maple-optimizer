"""넥슨 응답 JSON → 엔진 타입. 넥슨 키 이름은 이 파일 밖으로 나가지 않는다."""
import copy
import re

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
    core = (_total_option_block(item_json.get("item_total_option") or {})
            + _total_option_block(item_json.get("item_exceptional_option") or {}))
    excluded: list[str] = []
    pots = [t for t in (item_json.get(f"potential_option_{n}") for n in (1, 2, 3)) if t]
    additional = [t for t in (item_json.get(f"additional_potential_option_{n}") for n in (1, 2, 3)) if t]
    after = additional + [item_json.get(f"soul_potential_option_{n}") for n in (1, 2, 3)]
    # 소울: soul_active가 비어 있어도 soul_option이 오는 경우가 있다(나이트로드). soul_pad/soul_mad는 의미 미확인 → 1b에서 판단.
    after = [t for t in after + [item_json.get("soul_option")] if t]
    stats = copy.deepcopy(core)
    _add_texts(stats, pots + after, level, excluded)
    return Item(
        slot=item_json["item_equipment_slot"],
        part=item_json["item_equipment_part"],
        name=item_json["item_name"],
        starforce=int(num(item_json.get("starforce"))),
        stats=stats,
        potentials=pots,
        core=core,
        after=after,
        additional=additional,
        potential_grade=item_json.get("potential_option_grade"),
        additional_grade=item_json.get("additional_potential_option_grade"),
        level=int(num((item_json.get("item_base_option") or {}).get("base_equipment_level"))),
        special_ring_level=int(num(item_json.get("special_ring_level"))),
        icon=item_json.get("item_icon") or None,
        excluded=excluded,
    )


_PLUS_NUMBER = re.compile(r"[+-]\s*\d")


def _title_block(title: dict | None, level: int, excluded: list[str]) -> StatBlock:
    """칭호 설명문에서 "올스탯 +10", "공격력/마력+10" 같은 줄만 읽는다. 숫자 없는 줄은 설명문이다.
    옵션 적용 기간이 끝난 칭호(date_option_expire == "expired")는 효과가 없다."""
    b = StatBlock()
    if (title or {}).get("date_option_expire") == "expired":
        return b
    for raw in ((title or {}).get("title_description") or "").splitlines():
        line = raw.strip().lstrip("-").strip().replace("최대 HP/최대 MP", "최대 HP").replace("최대 HP/MP", "최대 HP")
        if not line or not _PLUS_NUMBER.search(line) or line.startswith("옵션 적용 기간"):
            continue
        _add_texts(b, [line], level, excluded)
    return b


_UNION_MULTI = re.compile(r"^((?:STR|DEX|INT|LUK)(?:, (?:STR|DEX|INT|LUK))+) (\d+) 증가$")


def _union_texts(text: str) -> list[str]:
    """유니온 공격대 문자열 정규화: "ALLSTAT 50, 최대 HP 2500 증가", "STR, DEX, LUK 40 증가"."""
    t = text.replace("ALLSTAT", "올스탯")
    m = _UNION_MULTI.match(t)
    if m:
        return [f"{s} {m[2]} 증가" for s in m[1].split(", ")]
    if "," in t and t.endswith("증가") and not t.startswith("이동속도"):
        return [p if p.endswith("증가") else f"{p} 증가" for p in (x.strip() for x in t.split(","))]
    return [t]


def _symbol_block(symbol_json: dict | None) -> StatBlock:
    b = StatBlock()
    for s in (symbol_json or {}).get("symbol") or []:
        for k, key in (("symbol_str", "STR"), ("symbol_dex", "DEX"), ("symbol_int", "INT"),
                       ("symbol_luk", "LUK"), ("symbol_hp", "HP")):
            if num(s.get(k)):
                b.add(StatLine(key, num(s[k]), False))
    return b


# 조건부 효과를 나타내는 표현. 이런 줄은 스탯창 상시 수치가 아니다 (예: "중첩 당 데미지 3%, 방어율 무시 3% 증가").
_LINK_CONDITIONAL = ("중첩", "동안", "발동", "처치", "돌입", "적용시키면")


def _link_block(skills: list[dict] | None, level: int) -> StatBlock:
    """링크 스킬 효과 중 조건 없는 것만. "10초 동안", "전투 상태 돌입 시" 같은 조건부 문장은 해석되지 않아 빠진다."""
    b = StatBlock()
    for sk in skills or []:
        for line in (sk.get("skill_effect") or "").splitlines():
            if any(m in line for m in _LINK_CONDITIONAL):
                continue
            for part in line.split(","):
                part = part.strip().strip("[]")
                if not part:
                    continue
                for stat in parse_option(part, level) or []:
                    b.add(stat)
    return b


def _link_presets(link_json: dict | None, level: int) -> tuple[dict[int, StatBlock], int]:
    if not link_json:
        return {}, 0
    presets, names = {}, {}
    for n in (1, 2, 3):
        skills = link_json.get(f"character_link_skill_preset_{n}") or []
        if skills:
            presets[n] = _link_block(skills, level)
            names[n] = sorted(s["skill_name"] for s in skills)
    current = sorted(s["skill_name"] for s in link_json.get("character_link_skill") or [])
    active = next((n for n, v in names.items() if v == current), 0)
    if not active and current:  # 프리셋과 맞는 게 없으면 현재 목록을 0번으로
        presets[0] = _link_block(link_json.get("character_link_skill"), level)
    return presets, active


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

    titles = {n: _title_block(eq.get(f"title_preset{n}"), level, excluded) for n in (1, 2, 3)}
    if not titles[active_eq].flat and eq.get("title"):
        titles[active_eq] = _title_block(eq.get("title"), level, excluded)
    ur = bundle.get("user/union-raider") or {}
    union = StatBlock()
    for text in ur.get("union_raider_stat") or []:
        _add_texts(union, _union_texts(text), level, excluded)
    # 유니온 프리셋별 효과. 프리셋 목록이 없으면 현재 효과(union_state_stat)를 적용 중인 프리셋으로 본다.
    active_union = int(num(ur.get("use_preset_no"))) or 1
    union_states: dict[int, StatBlock] = {}
    for p in ur.get("union_state_stat_preset") or []:
        b = StatBlock()
        for text in p.get("union_state_stat") or []:
            _add_texts(b, _union_texts(text), level, excluded)
        if p.get("union_state_stat"):
            union_states[int(num(p.get("preset_no")))] = b
    if active_union not in union_states and ur.get("union_state_stat"):
        b = StatBlock()
        for text in ur["union_state_stat"]:
            _add_texts(b, _union_texts(text), level, excluded)
        union_states[active_union] = b

    link_presets, active_link = _link_presets(bundle.get("character/link-skill"), level)

    profile = {"name": basic.get("character_name"), "world": basic.get("world_name"),
               "guild": basic.get("character_guild_name"), "image": basic.get("character_image") or None,
               "class_level": basic.get("character_class_level"), "date_create": basic.get("character_date_create")}
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
        titles=titles,
        symbols=_symbol_block(bundle.get("character/symbol-equipment")),
        union=union,
        union_states=union_states,
        active_union_preset=active_union if union_states else 0,
        link_presets=link_presets,
        active_link_preset=active_link,
        profile=profile,
    )


def cube_attempts(potential_rows: list[dict], cube_rows: list[dict]) -> list:
    """확률 정보 조회(history/potential, history/cube) 기록 → CubeAttempt 목록 (시간순)."""
    from engine.enhance.history import CubeAttempt

    out = []
    for r in potential_rows:
        out.append(CubeAttempt(r["potential_type"], r["target_item"], r["item_equipment_part"], int(num(r["item_level"])),
                               r["potential_option_grade"], [x["value"] for x in r.get("after_potential_option") or []],
                               r["date_create"]))
    for r in cube_rows:
        out.append(CubeAttempt(r["cube_type"], r["target_item"], r["item_equipment_part"], int(num(r["item_level"])),
                               r["potential_option_grade"], [x["value"] for x in r.get("after_potential_option") or []],
                               r["date_create"]))
    return sorted(out, key=lambda a: a.date)
