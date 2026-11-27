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
    assert ratio(cur, nxt) == pytest.approx(306 / 302)  # '일반 몬스터 …%p'는 보스 실딜과 무관(2026-10-11)
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


# ── 2026-10-11: 3rd 스킬 코어·직업군 공용 코어 비용 열 구분, 강화 코어의 문장별 대상 스킬 ──
from types import SimpleNamespace  # noqa: E402

from engine.market.hexa_core_paths import KIND, cost_column  # noqa: E402


def _lete():
    snap = snapshot(bundle("레테"))
    return snap, {p["name"]: p for p in core_paths(snap, job_shares("레테")["shares"], 7_000_000, 300.0, "직업 기준값")}


def test_third_skill_list_from_official_notice():
    assert KIND["third_skill"]["레테"] == ["보이드 오리진"]
    assert KIND["third_skill"]["에반"] == ["드래곤 소어", "버티컬 피니셔", "소어-돌아와!"]
    assert len(KIND["third_skill"]) == 48 and KIND["all_job_common"] == ["솔 야누스", "솔 헤카테"]


def test_cost_column_by_core_kind():
    snap = snapshot(bundle("레테"))
    col = {c["name"]: cost_column(c) for c in snap.hexa_cores}
    assert col["보이드 오리진"] == "3rd 스킬"  # API는 셋 다 '스킬 코어'라 공지 목록으로 가른다
    assert col["오버로드 : 이터널 게이즈"] == col["앱솔루트 레인"] == "스킬"
    assert col["솔 헤카테"] == col["솔 야누스"] == "공용" and col["프라이멀 퓨리 VI"] == "직업군 공용"
    assert col["체인 커맨드"] == "강화" and col["임펠 VI/팩트 매니페스트"] == "마스터리"


def test_third_skill_and_job_common_core_paths_use_their_cost_rows():
    _, by = _lete()
    assert by["보이드 오리진 3→4레벨"]["fragments"] == COST["3rd 스킬"][3][1]
    assert by["오버로드 : 이터널 게이즈 1→2레벨"]["fragments"] == COST["스킬"][1][1]
    assert by["프라이멀 퓨리 VI 1→2레벨"]["fragments"] == COST["직업군 공용"][1][1]


def test_mastery_core_sums_linked_skill_shares():
    _, by = _lete()
    p = by["인보크 : 템플러 VI/이딕트 : 템플러 아츠 VI 20→21레벨"]
    sh = job_shares("레테")["shares"]
    want = sh["인보크 : 템플러 VI"] * (157 / 155 - 1) + sh["이딕트 : 템플러 아츠 VI"] * (730 / 718 - 1)
    assert p["delta_pct"] == pytest.approx(want)


def test_enhance_core_line_targets():
    _, by = _lete()
    sh = job_shares("레테")["shares"]
    az = by["인보크/오버로드 : 아즈라스 1→2레벨"]
    assert az["delta_pct"] == pytest.approx(sh["인보크/오버로드 : 아즈라스"] * (112 / 111 - 1))
    # 체인 커맨드 강화: '맹약 완성'은 체인 커맨드의 공격(지분은 체인 커맨드), 오버로드 줄은 16→16 그대로,
    # '맹약 실체화 중 데미지 증가량'은 버프 유지율을 몰라 계산하지 않고 따로 보여 준다
    cc = by["체인 커맨드 1→2레벨"]
    assert cc["delta_pct"] == pytest.approx(sh["체인 커맨드"] * (112 / 111 - 1))
    assert [s["skill"] for s in cc["skills"]] == ["체인 커맨드"]
    assert cc["unvalued"] == ["맹약 실체화 중 데미지 증가량 10%로 증가 → 11%"]


def test_enhance_core_category_line_raises_every_matching_skill():
    """'오버로드 스킬의 최종 데미지 증가량'이 오르면 이름에 '오버로드'가 든 스킬 지분을 모두 더한다."""
    snap = SimpleNamespace(
        hexa_cores=[{"name": "체인 커맨드", "level": 5, "type": "강화 코어", "skills": ["체인 커맨드 강화"]}],
        hexa_skills={"체인 커맨드 강화": {"level": 5, "description": "",
                                     "effect": "오버로드 스킬의 최종 데미지 증가량 16%로 증가",
                                     "next": "오버로드 스킬의 최종 데미지 증가량 17%로 증가"}},
        final=None)
    shares = {"오버로드 : 템플러 온슬로트": 4.0, "인보크/오버로드 : 아즈라스": 3.0, "인보크 : 템플러 VI": 7.0, "체인 커맨드": 3.5}
    (p,) = core_paths(snap, shares, 7_000_000, 300.0, "x")
    assert p["delta_pct"] == pytest.approx(7.0 * (117 / 116 - 1))
    assert {s["skill"] for s in p["skills"]} == {"오버로드 : 템플러 온슬로트", "인보크/오버로드 : 아즈라스"}
    assert p["fragments"] == COST["강화"][5][1]


def test_levels_up_to_30_follow_the_enhance_table_and_a_constant_step_matching_the_wiki_master_values():
    """2026-11-27: 추천 조합이 30레벨까지 보려면 레벨별 값이 있어야 한다. 강화 코어는 레벨표(나무위키 HEXA 매트릭스 각주:
    1~9레벨 11~19%, 10~19레벨 25~34%, 20~29레벨 40~49%, 30레벨 60%), 그 밖은 API의 지금·다음 레벨 값으로 잰 일정한 증가량 —
    이렇게 이은 30레벨 값이 나무위키 레테(메이플스토리)/스킬의 마스터 값(2026-11-27 열람)과 같아야 한다."""
    import re

    from engine.market.hexa_core_paths import ENHANCE_FD, at_level
    assert [ENHANCE_FD[i] for i in (1, 9, 10, 19, 20, 29, 30)] == [11, 19, 25, 34, 40, 49, 60]
    snap = snapshot(bundle("레테"))
    wiki30 = {"임프린트 VI": ["350", "237"], "이딕트 : 펠 스톰 VI": ["715"], "인보크 : 바르가르 VI": ["346"], "이딕트 : 램페이지 VI": ["833"],
              "인보크 : 템플러 VI": ["175"], "이딕트 : 템플러 아츠 VI": ["838"], "팩트 매니페스트": ["221"], "오버로드 : 이터널 게이즈": ["907", "951"]}
    for name, want in wiki30.items():
        sk = snap.hexa_skills[name]
        assert re.findall(r"(\d+(?:\.\d+)?)%의 데미지", at_level(sk["effect"], sk["next"], sk["level"], 30)) == want, name
    sk = snap.hexa_skills["오버로드 : 템플러 온슬로트 강화"]                       # 강화 코어: 1레벨 11% → 30레벨 60%
    assert at_level(sk["effect"], sk["next"], 1, 30, enhance=True) == "오버로드 : 템플러 온슬로트의 최종 데미지 60% 증가"
    assert at_level(sk["effect"], sk["next"], 1, 10, enhance=True) == "오버로드 : 템플러 온슬로트의 최종 데미지 25% 증가"
    assert at_level(sk["effect"], sk["next"], 1, 2, enhance=True) == sk["next"]


def test_all_levels_paths_sum_the_costs_and_job_shares_are_scaled_to_my_core_levels():
    from engine.market.hexa_core_paths import shares_at
    snap = snapshot(bundle("레테"))
    ref = job_shares("레테")["shares"]
    one = {p["name"]: p for p in core_paths(snap, ref, 7_000_000, 300.0, "x")}
    every = {p["name"]: p for p in core_paths(snap, ref, 7_000_000, 300.0, "x", all_levels=True)}
    assert all(every[n] == p for n, p in one.items())                          # 다음 1레벨은 전과 같은 값
    core = next(c for c in snap.hexa_cores if c["name"] == "앱솔루트 레인")
    p = every["앱솔루트 레인 1→30레벨"]
    rows = COST["스킬"][core["level"]:30]
    assert p["fragments"] == sum(f for _, f in rows) and p["erda"] == sum(e for e, _ in rows) and p["cost"] == p["fragments"] * 7_000_000
    gains = [every[f"앱솔루트 레인 1→{t}레벨"]["delta_pct"] for t in range(2, 31)]
    assert all(a < b for a, b in zip(gains, gains[1:]))                         # 레벨이 높을수록 크다
    # 랭커(30레벨로 본다) 지분을 내 레벨로: 1레벨인 어센트 스킬의 지분은 줄고, 합은 그대로 100을 넘지 않는다
    mine = shares_at(snap, ref, 300.0)
    assert mine["앱솔루트 레인"] < ref["앱솔루트 레인"] and mine["오버로드 : 이터널 게이즈"] < ref["오버로드 : 이터널 게이즈"]
    assert set(mine) == set(ref) and sum(mine.values()) <= max(100.0, sum(ref.values())) + 1e-9
    maxed = snapshot(bundle("레테"))
    for c in maxed.hexa_cores:
        c["level"] = 30
    assert shares_at(maxed, ref, 300.0) == pytest.approx(ref)                  # 코어가 전부 30레벨이면 그대로
