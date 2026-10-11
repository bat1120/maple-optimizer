"""추가옵션(추옵) 재설정: 환생의 불꽃·메소 재설정 확률(공식 확률 페이지)과 단계별 수치(나무위키 공식)로
목표 추옵까지 기대 비용과 실딜을 계산한다. 출처: engine/data/flame_tables.json."""
import json
import math
import pathlib

import pytest

from engine.enhance import flame
from engine.market.events import Events
from engine.market.paths import upgrade_paths
from engine.market.recommend import MIN_GAIN
from engine.stats.evaluate import rank_settings
from engine.stats.metrics import BossProfile
from engine.stats.sets import SetCatalog
from helpers import bundle
from nexon.convert import snapshot

CAT, BOSS = SetCatalog.load(), BossProfile("기준", 300.0)
DATA = json.loads((pathlib.Path(flame.__file__).resolve().parents[1] / "data" / "flame_tables.json").read_text(encoding="utf-8"))


def test_data_file_cites_official_probability_page_and_meso_cost_with_check_date():
    src = DATA["_sources"]
    assert src["probability"]["url"] == "https://maplestory.nexon.com/Guide/OtherProbability/game/gameAddOption"
    assert src["meso_reset"]["url"] == "https://maplestory.nexon.com/News/Update/799"
    assert all(s["checked"] == "2026-10-11" for s in src.values())
    assert flame.MESO_RESET_COST == 3_000_000


def test_stage_tables_are_official_and_boss_items_get_plus_two():
    for kind in ("강력", "영원", "심연"):
        assert sum(DATA["stage_probability"][kind]) == 100
    assert flame.stage_distribution("검은 환생의 불꽃", boss=True) == pytest.approx({4: .29, 5: .45, 6: .25, 7: .01})
    assert flame.stage_distribution("추가옵션 재설정", boss=True) == flame.stage_distribution("영원한 환생의 불꽃", boss=True)
    assert flame.stage_distribution("타오르는 환생의 불꽃", boss=True) == pytest.approx({3: .2, 4: .3, 5: .36, 6: .14})
    assert flame.stage_distribution("심연의 환생의 불꽃", boss=False) == pytest.approx({3: .63, 4: .34, 5: .03})
    with pytest.raises(ValueError):
        flame.stage_distribution("수상한 불꽃", boss=True)


@pytest.mark.parametrize("level,base,expected", [
    (150, 86, [11, 16, 21, 28, 36]),    # 파프니르 리스크홀더(나무위키 메이플스토리/시스템/추가옵션 표)
    (150, 125, [15, 22, 31, 40, 52]),   # 파프니르 첼리스카
    (150, 160, [20, 29, 39, 52, 66]),   # 파프니르 윈드체이서
    (200, 295, [54, 78, 108, 142, 182]),  # 아케인셰이드 투핸드소드(나무위키 추가옵션 6.1.2)
])
def test_weapon_attack_formula_reproduces_wiki_tables(level, base, expected):
    got = [flame.line_value("공격력", s, level, weapon=True, base_attack={"ATK": base})[("ATK", False)] for s in range(3, 8)]
    assert got == expected


def test_stat_formulas_reproduce_fixture_flames():
    """아케인셰이드 신발(200제): LUK 5단계 + INT+LUK 5단계 + STR+INT 3단계 + 방어력 = API item_add_option 그대로."""
    v = lambda o, s, lv=200: flame.line_value(o, s, lv, weapon=False, base_attack={})  # noqa: E731
    total: dict = {}
    for o, s in (("LUK", 5), ("INT+LUK", 5), ("STR+INT", 3)):
        for k, x in v(o, s).items():
            total[k] = total.get(k, 0) + x
    assert total == {("LUK", False): 85, ("INT", False): 48, ("STR", False): 18}
    assert v("최대 HP", 4) == {("HP", False): 2400}           # 아케인셰이드 장갑 최대 HP 2400
    assert v("STR", 5, 250) == {("STR", False): 60}            # 250제는 220으로 계산: (11+1)×5
    assert v("올스탯%", 6) == {(k, True): 6 for k in ("STR", "DEX", "INT", "LUK")}
    assert v("방어력", 7) == {} and v("점프력", 7) == {}       # 실딜 무관 옵션은 수치를 쓰지 않는다
    assert flame.line_value("보스 몬스터 데미지%", 6, 200, weapon=True, base_attack={}) == {("BOSS", True): 12}
    # 제네시스 카르타(레테 fixture): 순수 마력 400, 추옵 마력 246 = 7단계
    assert flame.line_value("마력", 7, 200, weapon=True, base_attack={"MATK": 400}) == {("MATK", False): 246}


def test_options_are_uniform_and_boss_items_always_get_four():
    one = lambda o: {s: 1.0 for s in range(1, 8)} if o == "올스탯%" else {}  # noqa: E731 — 올스탯%만 점수 1
    boss = flame.score_distribution("검은 환생의 불꽃", weapon=False, level=200, boss=True, score_of=one)
    assert sum(boss.values()) == pytest.approx(1)
    assert sum(p for s, p in boss.items() if s > 0) == pytest.approx(4 / 19)
    normal = flame.score_distribution("검은 환생의 불꽃", weapon=False, level=200, boss=False, score_of=one)
    assert sum(p for s, p in normal.items() if s > 0) == pytest.approx((.4 * 1 + .4 * 2 + .16 * 3 + .04 * 4) / 19)
    low = flame.score_distribution("검은 환생의 불꽃", weapon=False, level=65, boss=True, score_of=one)  # 70 미만: 올스탯% 없음
    assert sum(p for s, p in low.items() if s > 0) == 0
    atk = lambda o: {s: float(s) for s in range(1, 8)} if o == "공격력" else {}  # noqa: E731
    w80 = flame.score_distribution("영원한 환생의 불꽃", weapon=True, level=80, boss=True, score_of=atk)  # 보스뎀 없는 18종
    assert w80[7.0] == pytest.approx(4 / 18 * .01)


def test_boss_equipment_only_from_cited_sets():
    assert flame.is_boss_item("데아 시두스 이어링", "귀고리", CAT)          # 보스 장신구 세트
    assert flame.is_boss_item("제네시스 카르타", "카르타", CAT)
    assert not flame.is_boss_item("도전자의 모자", "모자", CAT)           # 보스 장비인지 출처가 없다
    assert not flame.is_boss_item("혼테일의 목걸이", "펜던트", CAT)
    assert not flame.is_boss_item("가디언 엔젤 링", "반지", CAT)          # 반지에는 추옵이 없다


def test_expected_tries_and_conditional_gain():
    dist = {0.0: 0.5, 1.0: 0.3, 3.0: 0.2}
    t = flame.target_stats(dist, 1.0)
    assert t["probability"] == pytest.approx(0.5)
    assert t["mean_score"] == pytest.approx((0.3 * 1 + 0.2 * 3) / 0.5)


def test_snapshot_keeps_add_option_and_pure_attack():
    snap = snapshot(bundle("레테"))
    w = snap.equipment_presets[snap.active_equipment_preset]["무기"]
    assert w.add_option[("MATK", False)] == 246 and w.add_option[("INT", False)] == 60
    assert w.add_option[("STR", True)] == 4  # 올스탯% 4
    assert w.base_attack["MATK"] == 400


def _flames(events=None):
    snap = snapshot(bundle("레테"))
    setting = rank_settings(snap, BOSS, CAT)[0][0]
    return [p for p in upgrade_paths(snap, setting, BOSS, CAT, [], events=events)["all"] if p["path"] == "추옵"]


def test_paths_include_meso_reset_flame_routes_for_boss_items():
    ps = _flames()
    assert ps, "메소 재설정(공식 300만 메소)은 가격 입력 없이도 경로가 나온다"
    assert {p["flame"] for p in ps} == {"추가옵션 재설정"}
    slots = {p["slot"] for p in ps}
    assert "무기" in slots  # 제네시스 카르타
    assert not slots & {"모자", "상의", "하의", "신발", "장갑", "망토"}  # 도전자 장비: 보스 장비라는 출처가 없다
    assert not slots & {"반지1", "반지2", "반지3", "반지4", "보조무기", "어깨장식", "훈장", "뱃지"}
    for p in ps:
        assert p["cost"] == pytest.approx(3_000_000 * p["expected_tries"])
        assert p["expected_tries"] == pytest.approx(1 / p["reach_probability"])
        assert p["delta_pct"] >= MIN_GAIN and p["target_score"] > p["current_score"]
        assert p["delta_pct"] == pytest.approx(p["mean_score"] - p["current_score"])
    per_slot = {}
    for p in ps:
        per_slot[p["slot"]] = per_slot.get(p["slot"], 0) + 1
    assert max(per_slot.values()) <= 2


def test_linear_score_matches_evaluator_when_flame_is_removed():
    """점수(키별 실딜 기울기 × 추옵 수치)는 추옵을 통째로 뺐을 때 실제 실딜 하락과 가깝다(선형 근사 검산)."""
    import copy

    from engine.market.paths import _Paths, _flame_weights
    from engine.market.recommend import _Planner
    from engine.options import StatLine
    snap = snapshot(bundle("레테"))
    setting = rank_settings(snap, BOSS, CAT)[0][0]
    pl = _Planner(snap, setting, BOSS, CAT, None)
    px = _Paths(pl, CAT)
    it = pl.raw["무기"]
    w = _flame_weights(px, "무기", it, True)
    score = sum(w.get(k, 0) * v for k, v in it.add_option.items())
    bare = copy.deepcopy(it)
    for (k, pct), v in it.add_option.items():
        bare.stats.add(StatLine(k, -v, pct))
        bare.core.add(StatLine(k, -v, pct))
    drop = -px.delta("무기", bare)[0]
    assert score == pytest.approx(drop, rel=0.1)


def test_flame_prices_add_item_routes_and_unknown_names_fail():
    ev = Events.parse(flame_prices="심연:50000000,강력:1000000")
    assert dict(ev.flame_prices) == {"심연의 환생의 불꽃": 50_000_000, "강력한 환생의 불꽃": 1_000_000}
    with pytest.raises(ValueError):
        Events.parse(flame_prices="수상한:1")
    with pytest.raises(ValueError):
        Events.parse(flame_prices="심연")
    ps = _flames(ev)
    assert {p["flame"] for p in ps} <= {"추가옵션 재설정", "심연의 환생의 불꽃", "강력한 환생의 불꽃"}
    for p in ps:
        price = {"추가옵션 재설정": 3_000_000, **dict(ev.flame_prices)}[p["flame"]]
        assert p["price_each"] == price and p["cost"] == pytest.approx(price / p["reach_probability"])
    assert math.isfinite(sum(p["cost"] for p in ps))


def test_server_paths_accepts_flame_prices(tmp_path):
    from fastapi.testclient import TestClient

    from server.app import create_app
    c = TestClient(create_app(lambda name, day: bundle("레테"), str(tmp_path / "c.sqlite3"), clock=lambda: 1_000_000.0))
    r = c.get("/api/character/내신부레테/paths", params={"flame_prices": "심연:50000000"})
    assert r.status_code == 200
    body = r.json()
    assert "추옵" in body["note"]
    assert dict(map(tuple, body["events"]["flame_prices"])) == {"심연의 환생의 불꽃": 50_000_000}
    assert c.get("/api/character/내신부레테/paths", params={"flame_prices": "수상한:1"}).status_code == 400
