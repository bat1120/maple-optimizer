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
    v, src = cooldown_valuer("아크메이지(불,독)", None)
    assert v(2) is None and src["kind"] == "none"
    v, src = cooldown_valuer("카인", None)          # 최종뎀 단위 — 참고만
    assert v(2) is None and src["kind"] == "reference" and "최종" in src["unit"]


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
    other = service.recommend(snapshot(bundle("레테")), 300)
    assert other["cooldown"]["kind"] == "none" and "직접" in other["note"]
    manual = service.recommend(snapshot(bundle("레테")), 300, cooldown_main_pct=6)
    assert manual["cooldown"]["kind"] == "manual" and "6%" in manual["note"]
