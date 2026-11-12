"""픽스처(넥슨 Open API 실측 응답)의 착용 장비에서 템별 기본 옵션·추옵·주문서 칸 수를 모아 표로 만든다(2026-11-13).

'다른 템으로 갈아타기' 계산(engine/market/swaps.py)이 지금 끼지 않은 템을 가정해 실딜을 재려면 그 템의 실측 수치가 필요하다.
숫자는 추정하지 않는다 — 픽스처에 착용자가 있는 템만 표에 들어간다.

- base: item_base_option(같은 이름이면 착용자마다 같아야 한다 — 다르면 가장 많은 값, variants에 종류 수)
- level: base_equipment_level
- slots: 주문서 칸 수(scroll_upgrade + scroll_upgradeable_count)의 최빈값
- sf_stats: 스타포스 스탯이 1성부터 붙는 칸, sf_stats_16: 16성부터만 붙는 칸(직업 전용 방어구의 비직업 스탯 등) —
  착용자 item_starforce_option 값을 성별 표(engine/enhance/starforce_stats.py)와 맞춰 가른다
- branches: 착용자 직업군 — 직업 전용 방어구(메이지로브 등)를 다른 직업에게 권하지 않게
- flames: 착용자마다 item_add_option(0이 아닌 칸만) — 이 템 추옵이 실제로 어떻게 붙어 있는지의 표본
- set: engine/data/set_items.json의 세트 이름(없으면 null)

사용: uv run python tools/derive_item_bases.py
출력: engine/data/item_bases.json
"""
import collections
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from engine.enhance.starforce_stats import _stat  # noqa: E402
from engine.stats.jobs import UnsupportedJob, job_profile  # noqa: E402

SOURCES = [ROOT / "tests" / "fixtures" / "characters", ROOT / "tests" / "fixtures" / "pairs"]
OUT = ROOT / "engine" / "data" / "item_bases.json"
PRESETS = ("item_equipment", "item_equipment_preset_1", "item_equipment_preset_2", "item_equipment_preset_3")
SKIP_SLOTS = ("예비 특수 반지",)
STAT_KEYS = ("str", "dex", "int", "luk")


def _nonzero(opt: dict | None, drop=("base_equipment_level", "equipment_level_decrease", "exceptional_upgrade")) -> dict:
    out = {}
    for k, v in (opt or {}).items():
        if k in drop or v in (None, "", "0", 0):
            continue
        out[k] = int(v) if str(v).lstrip("-").isdigit() else v
    return out


def _int(v) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def _branches(cls: str) -> tuple[str, ...]:
    try:
        return job_profile(cls).branches
    except UnsupportedJob:  # 계산을 지원하지 않는 직업(데몬어벤져)도 직업군은 세트 이름으로 안다 — 모르면 비워 둔다
        return ()


def collect() -> dict:
    seen = collections.defaultdict(list)
    for src in SOURCES:
        for f in sorted(src.rglob("character_item-equipment.json")):
            d = json.loads(f.read_text(encoding="utf-8"))
            cls = d.get("character_class") or ""
            done = set()
            for key in PRESETS:
                for it in d.get(key) or []:
                    if it["item_equipment_slot"] in SKIP_SLOTS:
                        continue
                    k = (it["item_equipment_slot"], it["item_name"])
                    if k in done:
                        continue
                    done.add(k)
                    seen[it["item_name"]].append((cls, it))
    sets = json.loads((ROOT / "engine" / "data" / "set_items.json").read_text(encoding="utf-8"))
    set_of = sets.get("items", sets)
    out = {}
    for name, rows in sorted(seen.items()):
        bases = collections.Counter(json.dumps(_nonzero(it["item_base_option"]), sort_keys=True) for _, it in rows)
        levels = collections.Counter(_int((it["item_base_option"] or {}).get("base_equipment_level")) for _, it in rows)
        slots = collections.Counter(_int(it.get("scroll_upgrade")) + _int(it.get("scroll_upgradeable_count")) for _, it in rows)
        full, from16 = set(), set()
        for _, it in rows:
            star, lv = _int(it.get("starforce")), _int((it["item_base_option"] or {}).get("base_equipment_level"))
            if star <= 0 or it.get("starforce_scroll_flag") == "사용":
                continue
            whole, upto15 = _stat(lv, star), _stat(lv, min(star, 15))
            for k in STAT_KEYS:
                v = _int((it.get("item_starforce_option") or {}).get(k))
                if not v or whole is None:
                    continue
                if v == whole:
                    full.add(k.upper())
                elif star > 15 and v == whole - upto15:
                    from16.add(k.upper())
        sf_stats, sf_stats_16 = sorted(full), sorted(from16 - full)
        branches = sorted({b for cls, _ in rows for b in _branches(cls)})
        parts = collections.Counter(it["item_equipment_part"] for _, it in rows)
        out[name] = {
            "part": parts.most_common(1)[0][0],
            "level": levels.most_common(1)[0][0],
            "set": set_of.get(name) if isinstance(set_of, dict) else None,
            "base": json.loads(bases.most_common(1)[0][0]),
            "variants": len(bases),
            "slots": slots.most_common(1)[0][0],
            "sf_stats": sf_stats,
            "sf_stats_16": sf_stats_16,
            "branches": branches,
            "wearers": len(rows),
            "flames": [_nonzero(it.get("item_add_option")) for _, it in rows],
        }
    return out


def main() -> None:
    data = collect()
    OUT.write_text(json.dumps({"_source": "tests/fixtures 착용 장비(넥슨 Open API 실측) — tools/derive_item_bases.py",
                               "items": data}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(data)}개 템 → {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
