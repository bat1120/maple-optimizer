"""직업별 쿨감 효율(2026-10-07 사용자: 인터넷 정보로 반영). 출처에 숫자가 있는 직업만, 표에 있는 초수만.
- 직접 입력(cooldown_main_pct)이 있으면 그 값 × 초(예전 그대로)
- 없으면 직업 표: 칼리 1초 9%·2초 13%, 제논 2초 20%·…(올스탯 → 주스탯 셋 모두), 표에 없는 초수·직업은 반영 안 함"""
import json
import pathlib

from engine.market.recommend import cooldown_valuer

DATA = json.loads((pathlib.Path(__file__).resolve().parents[1] / "engine/data/cooldown_value.json").read_text(encoding="utf-8"))


def test_manual_value_is_linear_and_wins_over_table():
    v, src = cooldown_valuer("칼리", 5.0)
    assert v(2) == 10.0 and src["kind"] == "manual"


def test_table_value_is_stepwise_exact_seconds_only():
    v, src = cooldown_valuer("칼리", None)
    assert v(1) == 9 and v(2) == 13 and v(3) is None
    assert src["kind"] == "table" and src["source"].startswith("https://") and src["date"]


def test_job_without_sourced_numbers_is_not_valued():
    v, src = cooldown_valuer("레테", None)
    assert v(2) is None and src["kind"] == "none"
    v, src = cooldown_valuer("데몬어벤져", None)    # 엔진 계산 범위 밖 직업 — 참고만
    assert v(2) is None and src["kind"] == "reference"


# 2026-10-10 사용자: '누군가 효율 계산해 놓은 걸(최종뎀%) 주스탯%로 여기서 다시 계산'.
# 출처 숫자(최종뎀%)는 그대로 두고, 주스탯%로 바꾸는 건 그 캐릭터 스펙으로 엔진이 한다(짐작 없음).
def test_final_damage_table_needs_a_converter():
    v, src = cooldown_valuer("카인", None)          # 변환기가 없으면 반영하지 않는다
    assert v(2) is None and src["kind"] == "table_fd" and "최종" in src["unit"]
    v, src = cooldown_valuer("카인", None, fd_to_main=lambda fd: fd * 10)
    assert v(2) == 12.0 and v(4) == 24.5 and v(3) is None   # 표에 있는 초수만(계단식)
    v, src = cooldown_valuer("아크메이지(불,독)", None, fd_to_main=lambda fd: fd * 10)
    assert v(2) == 25.0 and src["per_sec"] == 1.25          # 원문 '1초 1.25~1.3%' — 범위의 낮은 값


def test_every_final_damage_entry_has_source_date_and_quote():
    for job, e in DATA["jobs_final_damage"].items():
        assert e["source"].startswith("https://") and e["date"] and e["basis"] and e["quote"], job
        assert e.get("cumulative") or e.get("per_sec"), job


def test_converted_main_pct_reproduces_the_source_final_damage():
    """주스탯 p%를 더하면 실딜이 원문 최종뎀%만큼 오른다(이 캐릭터 스펙 기준 검산)."""
    from helpers import bundle
    from nexon.convert import snapshot
    from engine.market.recommend import _Planner, _with_main_pct
    from engine.stats.metrics import BossProfile
    from server.service import CATALOG, rank_settings
    snap = snapshot(bundle("카인"))
    b = BossProfile("방어율 300%", 300.0)
    setting = rank_settings(snap, b, CATALOG)[0][0]
    pl = _Planner(snap, setting, b, CATALOG, None)
    p = pl.per_sec(2)
    assert p and 3 < p < 40                                      # 주스탯% 범위(상식선)
    base = pl.ev.index(pl.raw)
    up = pl.ev.index(_with_main_pct(pl.raw, pl.mains, p))
    assert abs((up / base - 1) * 100 - 1.2) < 0.01               # 원문: '0초 --> 2초 1.2퍼'
    assert pl.cooldown_source["converted"][2] == round(p, 2)


def test_every_table_entry_has_source_date_and_basis():
    for job, e in DATA["jobs"].items():
        assert e["source"].startswith("https://") and e["date"] and e["basis"] and e["cumulative"], job


def test_xenon_all_stat_goes_to_all_three_mains():
    from helpers import bundle
    from nexon.convert import snapshot
    from engine.market.recommend import _valued
    from engine.stats.jobs import job_profile
    snap = snapshot(bundle("제논"))
    hat = next(it for p in snap.equipment_presets.values() for it in p.values() if it.slot == "모자")
    hat = type(hat)(**{**hat.__dict__, "potentials": ["스킬 재사용 대기시간 -2초"], "after": []})
    v, _ = cooldown_valuer("제논", None)
    out = _valued(hat, job_profile("제논").mains, v)
    added = [l for l in out.stats.lines if l not in hat.stats.lines] if hasattr(out.stats, "lines") else None
    for m in ("STR", "DEX", "LUK"):
        assert out.stats.pct.get(m, 0) - hat.stats.pct.get(m, 0) == 20


def test_service_reports_how_cooldown_was_valued():
    from helpers import bundle
    from nexon.convert import snapshot
    from server import service
    kali = service.roadmap(snapshot(bundle("칼리")), 300)
    assert kali["cooldown"]["kind"] == "table" and "fmkorea" in kali["cooldown"]["source"]
    assert "1초 9%" in kali["note"] and "2초 13%" in kali["note"]
    kain = service.roadmap(snapshot(bundle("카인")), 300)
    assert kain["cooldown"]["kind"] == "table_fd" and "2초 최종뎀 1.2%" in kain["note"] and "주스탯" in kain["note"]
    other = service.recommend(snapshot(bundle("레테")), 300)
    assert other["cooldown"]["kind"] == "none" and "직접" in other["note"]
    manual = service.recommend(snapshot(bundle("레테")), 300, cooldown_main_pct=6)
    assert manual["cooldown"]["kind"] == "manual" and "6%" in manual["note"]
