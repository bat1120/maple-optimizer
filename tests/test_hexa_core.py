"""HEXA 스킬 코어 경로(2026-10-07): 넥슨 API 6차 스킬 효과 문장 + 연무장 딜 지분 + 비용표(engine/data/hexa_core_cost.json)."""
import pytest

from engine.market.hexa_core_paths import COST, bonus_factor, core_paths, job_shares, ratio
from engine.stats.model import FinalStats
from helpers import bundle
from nexon.convert import snapshot


def test_cost_table_totals_match_source():
    tot = {c: [sum(e for e, _ in v), sum(f for _, f in v)] for c, v in COST.items()}
    assert tot["스킬"] == [150, 4500] and tot["마스터리"] == [83, 2252] and tot["강화"] == [123, 3383]
    assert tot["공용"] == [208, 6268]


def test_ratio_from_effect_text():
    cur = "바르가르는 최대 3명의 적을 302%의 데미지로 3번 공격\n일반 몬스터 공격 시 데미지 403%p 증가"
    nxt = "바르가르는 최대 3명의 적을 306%의 데미지로 3번 공격\n일반 몬스터 공격 시 데미지 411%p 증가"
    assert ratio(cur, nxt) == pytest.approx((306 / 302 + 411 / 403) / 2)
    assert ratio("X의 최종 데미지 11% 증가", "X의 최종 데미지 12% 증가", final_damage=True) == pytest.approx(112 / 111)
    assert ratio("a 10%", "a 10% b 5%") is None  # 문장 구조가 바뀌면 계산하지 않는다


def test_level_bonus_only_at_target_level():
    desc = "설명\n10레벨 : 몬스터 방어율 무시 20% 증가\n20레벨 : 보스 몬스터 공격 시 데미지 20% 증가"
    final = FinalStats(stats={}, ap={}, atk=0, matk=0, dmg=100.0, boss=300.0, fd=0, cd=0, cr=0, ied=90.0,
                       stat_attack_min=0, stat_attack_max=0, combat_power=0)
    assert bonus_factor(desc, 9, final, 300.0) == 1.0
    assert bonus_factor(desc, 20, final, 300.0) == pytest.approx((500 + 20) / 500)
    ied = bonus_factor(desc, 10, final, 300.0)
    assert ied == pytest.approx((1 - 3 * 0.1 * 0.8) / (1 - 3 * 0.1))


def test_lete_core_paths_use_job_reference_shares():
    snap = snapshot(bundle("레테"))
    assert snap.hexa_cores and snap.hexa_skills and not snap.own_shares  # 레테 픽스처는 연무장 기록이 없다
    ref = job_shares("레테")
    assert ref and ref["samples"] >= 1 and ref["shares"]["임프린트 VI"] > 0
    ps = core_paths(snap, ref["shares"], 7_000_000, 300.0, "직업 기준값")
    by = {p["name"]: p for p in ps}
    templar = by["인보크 : 템플러 VI/이딕트 : 템플러 아츠 VI 20→21레벨"]
    assert templar["fragments"] == COST["마스터리"][20][1] and templar["cost"] == templar["fragments"] * 7_000_000
    assert templar["delta_pct"] > 0 and {s["skill"] for s in templar["skills"]} == {"인보크 : 템플러 VI", "이딕트 : 템플러 아츠 VI"}
    assert not [p for p in ps if p["name"].startswith("솔 야누스")]  # 딜이 없는 코어는 뺀다
    assert all(p["share_source"] == "직업 기준값" for p in ps)
    assert core_paths(snap, ref["shares"], 0, 300.0, "x") == []  # 조각 시세가 없으면 만들지 않는다


def test_paths_api_includes_hexa_cores_with_fragment_price(tmp_path):
    from fastapi.testclient import TestClient
    from server.app import create_app
    c = TestClient(create_app(lambda n, d: bundle("레테"), str(tmp_path / "c.sqlite3")))
    r = c.get("/api/character/x/paths?fragment_price=7000000").json()
    kinds = {p["path"] for p in r["all"]}
    assert {"HEXA 코어", "HEXA 스탯"} <= kinds
    hx = [p for p in r["all"] if p["path"] == "HEXA 코어"]
    assert all(p["cost_text"] and p["erda"] >= 1 for p in hx)
