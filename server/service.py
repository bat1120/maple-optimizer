"""엔진 호출을 API 응답 형태로 묶는다. 계산은 전부 engine이 한다."""
from dataclasses import asdict

from engine.market.listing import Listing, item_from_input, rank_listings
from engine.stats.evaluate import evaluate_setting, rank_settings
from engine.stats.formula import stat_attack_max
from engine.stats.jobs import job_profile
from engine.stats.metrics import BossProfile
from engine.stats.sets import SetCatalog
from engine.stats.snapshot import CharacterSnapshot, Setting

CATALOG = SetCatalog.load()


def boss(defense: float) -> BossProfile:
    return BossProfile(f"방어율 {defense:g}%", defense)


def summary(snap: CharacterSnapshot) -> dict:
    weapon = snap.equipment_presets[snap.active_equipment_preset]["무기"].part
    engine_sa = stat_attack_max(snap.final, job_profile(snap.character_class), weapon)
    f = snap.final
    return {
        "character_class": snap.character_class,
        "level": snap.level,
        "date": snap.date,
        "active_setting": asdict(snap.active_setting),
        "stat_attack": {"engine": engine_sa, "api": f.stat_attack_max},
        "combat_power_reference": f.combat_power,
        "final": {"stats": f.stats, "atk": f.atk, "matk": f.matk, "dmg": f.dmg, "boss": f.boss,
                  "fd": f.fd, "cd": f.cd, "ied": f.ied},
        "equipment_presets": {str(n): [{"slot": it.slot, "name": it.name, "starforce": it.starforce}
                                       for it in items.values()]
                              for n, items in snap.equipment_presets.items() if items},
        "excluded": sorted(set(snap.excluded)),
    }


def settings(snap: CharacterSnapshot, defense: float) -> dict:
    b = boss(defense)
    ranked = rank_settings(snap, b, CATALOG)
    active = evaluate_setting(snap, snap.active_setting, b, CATALOG)
    return {"boss": asdict(b),
            "ranking": [{"setting": asdict(s), "index": v, "relative_to_active": v / active if active > 0 else None}
                        for s, v in ranked]}


def listings(snap: CharacterSnapshot, setting: Setting | None, defense: float, inputs: list) -> dict:
    b = boss(defense)
    chosen = setting or rank_settings(snap, b, CATALOG)[0][0]
    built = [Listing(x.slot, item_from_input(x.slot, x.part, x.name, x.total, x.potentials, snap.level, x.starforce),
                     x.price, x.resale) for x in inputs]
    ranked = rank_listings(snap, chosen, built, b, CATALOG)
    return {"setting": asdict(chosen), "boss": asdict(b),
            "ranking": [{"slot": e.listing.slot, "name": e.listing.item.name, "price": e.listing.price,
                         "resale": e.listing.resale, "delta_pct": e.delta_pct, "per_100m": e.per_100m,
                         "excluded": e.listing.item.excluded} for e in ranked]}
