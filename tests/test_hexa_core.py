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


def test_enhance_core_lines_apply_to_their_own_targets():
    """체인 커맨드 강화(2026-10-08): 효과 문장 줄마다 대상이 다르다.
    '오버로드 스킬의 최종 데미지 증가량' → 이름에 '오버로드'가 든 스킬 모두, '맹약 완성의 최종 데미지' → 체인 커맨드,
    '맹약 실체화 중 데미지 증가량' → 켜져 있는 시간(측정값 없음)을 몰라 빼고 skipped에 적는다."""
    import dataclasses
    snap = snapshot(bundle("레테"))
    sk = dict(snap.hexa_skills)
    cc = dict(sk["체인 커맨드 강화"])
    cc["next"] = cc["next"].replace("오버로드 스킬의 최종 데미지 증가량 16%로", "오버로드 스킬의 최종 데미지 증가량 17%로")
    sk["체인 커맨드 강화"] = cc
    snap = dataclasses.replace(snap, hexa_skills=sk)
    shares = job_shares("레테")["shares"]
    p = {x["name"]: x for x in core_paths(snap, shares, 7_000_000, 300.0, "직업 기준값")}["체인 커맨드 1→2레벨"]
    overload = [n for n in shares if "오버로드" in n]
    assert set(overload) == {"오버로드 : 이터널 게이즈", "오버로드 : 템플러 온슬로트", "인보크/오버로드 : 아즈라스",
                             "오버로드 : 바르가르 트라이던트"}
    want = sum(shares[n] for n in overload) * (117 / 116 - 1) + shares["체인 커맨드"] * (112 / 111 - 1)
    assert p["delta_pct"] == pytest.approx(want)
    assert {s["skill"] for s in p["skills"]} == set(overload) | {"체인 커맨드"}
    assert p["skipped"] == ["맹약 실체화 중 데미지 증가량 11%로 증가"]
