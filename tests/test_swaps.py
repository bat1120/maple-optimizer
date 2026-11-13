"""다른 템으로 갈아타기(2026-11-13 사용자: 커맨더 포스 이어링처럼 다른 템으로 바꾸면 세트 효과도 바뀌며 이득일 수 있다 —
세트·장비 옵션·추옵·잠재를 계산해 '어느 수준 이상이면 그 템이 낫다'까지 추천).

가정한 템의 수치는 실측만: 기본 옵션·주문서 칸·추옵 표본은 픽스처 착용 장비(engine/data/item_bases.json), 스타포스는 성별 표,
세트는 세트 표. 합성한 템이 실제 착용 템의 총 옵션을 그대로 재현하는지 픽스처 전체로 검산한다."""
import json
import pathlib

import pytest

from engine.market.swaps import BASES, swap_candidates, synth_json
from engine.stats.evaluate import rank_settings
from engine.stats.metrics import BossProfile
from engine.stats.sets import SetCatalog
from helpers import bundle
from nexon.convert import snapshot

ROOT = pathlib.Path(__file__).resolve().parent.parent
CAT, BOSS = SetCatalog.load(), BossProfile("기준", 300.0)
# 최대 HP는 뺀다: 스타포스 HP는 성별 표에 없고, HP는 지원하는 직업의 실딜에 쓰이지 않는다(HP 직업 데몬어벤져는 미지원)
TOTAL_KEYS = ("str", "dex", "int", "luk", "attack_power", "magic_power", "all_stat", "boss_damage",
              "ignore_monster_armor", "damage")


def test_item_bases_table_is_regenerated_from_fixtures():
    """표는 도구로 다시 만들면 똑같아야 한다(손으로 고친 숫자 없음)."""
    import sys
    sys.path.insert(0, str(ROOT / "tools"))
    from derive_item_bases import collect
    assert collect() == BASES


def test_commander_force_earring_is_measured():
    cfe = BASES["커맨더 포스 이어링"]
    assert (cfe["part"], cfe["level"], cfe["set"], cfe["slots"]) == ("귀고리", 200, "칠흑의 보스 세트", 7)
    assert (cfe["base"]["int"], cfe["base"]["magic_power"], cfe["variants"]) == (7, 5, 1)
    assert cfe["wearers"] >= 30 and len(cfe["flames"]) == cfe["wearers"]


def _worn():
    for f in sorted((ROOT / "tests" / "fixtures").rglob("character_item-equipment.json")):
        for it in json.loads(f.read_text(encoding="utf-8")).get("item_equipment") or []:
            yield f.parent.name, it


def test_synthesized_item_reproduces_every_worn_total():
    """기본 + 추옵 + 주문서 + 스타포스(성별 표)로 합성한 총 옵션 = 넥슨 API item_total_option.
    무기·보조무기·엠블렘(갈아타기 대상 아님), 놀장, 표로 못 재는 템은 건너뛴다."""
    checked, skipped = 0, 0
    for who, it in _worn():
        if it["item_equipment_slot"] in ("무기", "보조무기", "엠블렘", "예비 특수 반지") or it.get("starforce_scroll_flag") == "사용":
            continue
        got = synth_json(it["item_name"], it["item_equipment_slot"], int(it.get("starforce") or 0),
                         it.get("item_add_option") or {}, it.get("item_etc_option") or {})
        if got is None:
            skipped += 1
            continue
        want = it["item_total_option"]
        diff = {k: (got["item_total_option"].get(k, 0), int(want.get(k) or 0)) for k in TOTAL_KEYS
                if int(got["item_total_option"].get(k, 0)) != int(want.get(k) or 0)}
        assert not diff, f"{who} {it['item_name']} {it.get('starforce')}성: {diff}"
        checked += 1
    assert checked >= 500 and skipped < checked / 5


@pytest.fixture(scope="module")
def lete():
    snap = snapshot(bundle("레테"))
    setting = rank_settings(snap, BOSS, CAT)[0][0]
    return snap, setting, swap_candidates(snap, setting, BOSS, CAT, per_slot=50)


def test_same_item_swap_changes_nothing(lete):
    """지금 템을 같은 조건으로 '갈아타면' 실딜 변화 0 — 합성·세트 재계산 경로 검산."""
    from engine.market.swaps import _Swapper
    snap, setting, _ = lete
    sw = _Swapper(snap, setting, BOSS, CAT)
    slot, cur = next((s, it) for s, it in sw.pl.slots() if it.name in BASES and s == "귀고리")
    d, change = sw.delta(slot, sw.like_current(slot, cur.name))
    assert d == pytest.approx(0, abs=1e-6) and change == []


def test_earring_candidates_include_other_boss_sets_with_set_change(lete):
    snap, _, out = lete
    ear = [c for c in out if c["slot"] == "귀고리"]
    names = {c["name"] for c in ear}
    assert ear[0]["current"]["name"] == "에스텔라 이어링"   # 레테 보스 세팅의 귀고리(여명의 보스 세트)
    assert "커맨더 포스 이어링" in names and "에스텔라 이어링" not in names  # 지금 템은 후보가 아니다
    cfe = next(c for c in ear if c["name"] == "커맨더 포스 이어링")
    cur_set = BASES[cfe["current"]["name"]]["set"]
    sets = {x["set"]: (x["before"], x["after"]) for x in cfe["set_change"]}
    assert sets["칠흑의 보스 세트"][1] == sets["칠흑의 보스 세트"][0] + 1
    assert sets[cur_set][1] == sets[cur_set][0] - 1
    f = cfe["flame"]
    assert f["samples"] == BASES["커맨더 포스 이어링"]["wearers"]
    assert f["min"] <= f["median"] <= f["max"] and 0 <= f["better_share"] <= 1


def test_candidates_respect_job_and_level(lete):
    """직업 전용 방어구는 그 직업군 착용자가 있는 템만, 캐릭터 레벨보다 높은 템은 빼고, 경매장에서 못 사는 템도 뺀다."""
    snap, _, out = lete
    for c in out:
        b = BASES[c["name"]]
        assert "마법사" in b["branches"] and b["level"] <= snap.level
        assert not c["name"].startswith(("제네시스", "데스티니", "아스트라", "미트라의 분노"))
        assert c["slot"] not in ("무기", "보조무기", "엠블렘")


def test_potential_break_even_is_the_first_tier_that_wins(lete):
    """잠재 손익분기: 그 템에 그 단계(이상)를 띄우면 지금보다 실딜이 오른다. 앞 단계들은 못 미친다."""
    _, _, out = lete
    some = [c for c in out if c["potential"]["break_even"]]
    assert some
    for c in some:
        be, tiers = c["potential"]["break_even"], c["potential"]["tiers"]
        i = next(i for i, t in enumerate(tiers) if t["target"] == be["target"] and t["grade"] == be["grade"])
        assert be["delta_pct"] > 0 and all(t["delta_pct"] <= 0 for t in tiers[:i])


def test_swaps_route(tmp_path):
    from fastapi.testclient import TestClient
    from server.app import create_app
    c = TestClient(create_app(lambda n, d: bundle("레테"), str(tmp_path / "c.sqlite3")))
    r = c.get("/api/character/x/swaps").json()
    assert r["swaps"] and {"slot", "name", "set_change", "same", "flame", "potential"} <= set(r["swaps"][0])
    assert "실측" in r["note"]


def test_no_flame_items_are_not_shown_as_a_distribution(lete):
    """반지처럼 추옵이 안 붙는 템(착용자 추옵 표본이 전부 비어 있음)은 분포 대신 '없음'."""
    _, _, out = lete
    rings = [c for c in out if not any(BASES[c["name"]]["flames"])]
    assert rings
    assert all(c["flame"] == {"samples": 0, "none": True} for c in rings)


def test_potential_none_and_ladder_skips(lete):
    """잠재를 비운 실딜(none)은 지금 잠재를 옮긴 실딜(same)보다 클 수 없다. 사다리가 안 쓰는 지금 잠재 줄은 따로 알린다."""
    _, _, out = lete
    for c in out:
        p = c["potential"]
        assert p["none"] is not None and p["none"] <= c["same"] + 1e-9
        assert set(p["ladder_skips"]) <= set(c["current"]["potentials"])


def test_market_break_even_assumes_a_typical_listing(lete):
    """보통 매물 기준(2026-11-13 실사용: 18성 레전드리 INT 3줄 커맨더 포스 이어링이 추옵이 STR·LUK 쪽이고 에디가 없어
    +0.08%뿐 — 지금 추옵·에디를 옮긴다는 가정의 손익분기 '에픽 2줄'과 크게 달랐다):
    추옵은 착용자 실측 표본 중 실딜이 가운데인 표본 하나(추정값 아님), 에디는 없음. 그 상태의 잠재 손익분기를 따로 준다."""
    _, _, out = lete
    for c in out:
        m = c["market"]
        assert m["additional"] == []
        flames = BASES[c["name"]]["flames"]
        assert m["flame"] in flames if any(flames) else m["flame"] == {}
        be, tiers = m["break_even"], m["tiers"]
        first = next((t for t in tiers if t["delta_pct"] > 0), None)
        assert be == first
        assert m["none"] is not None


def test_market_flame_is_the_middle_sample(lete):
    """보통 추옵 = 착용자 추옵을 실딜 순으로 놓았을 때 가운데(짝수면 아래쪽) 표본."""
    from engine.market.swaps import _Swapper
    snap, setting, out = lete
    sw = _Swapper(snap, setting, BOSS, CAT)
    c = next(c for c in out if c["name"] == "커맨더 포스 이어링")
    ds = sorted((sw.delta(c["slot"], sw.like_current(c["slot"], c["name"], add=a))[0], i)
                for i, a in enumerate(BASES[c["name"]]["flames"]))
    assert c["market"]["flame"] == BASES[c["name"]]["flames"][ds[(len(ds) - 1) // 2][1]]
