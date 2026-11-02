"""계산 기준 고지(2026-10-17 점검): 실딜은 넥슨 스탯창(버프·도핑 없음) 기준이라 방무·크뎀 가치가 버프 기준(MapleScouter)보다
크게 나올 수 있다 — 추천 화면마다 알린다. 스탯창 방무가 낮아 방어율 계수가 아주 작으면(0.5 미만) 방무 줄 가치가 부풀어
(나이트로드 픽스처: 방무 큐브 한 단계 +64.8%) 따로 경고한다."""
from helpers import bundle
from engine.stats.metrics import BossProfile
from nexon.convert import snapshot
from server import service

BOSS = BossProfile("기준", 300.0)


def test_recommendation_notes_state_the_unbuffed_basis():
    snap = snapshot(bundle("레테"))
    for r in (service.recommend(snap, BOSS, 3), service.roadmap(snap, BOSS)):
        assert "스탯창" in r["note"] and "버프" in r["note"]
        assert r.get("basis_warning") is None


def test_low_armor_factor_is_flagged():
    snap = snapshot(bundle("나이트로드"))
    r = service.recommend(snap, BOSS, 3)
    assert r["basis_warning"] and "방어율 무시" in r["basis_warning"]


def test_paths_say_hexa_core_is_skipped_without_share_data(monkeypatch):
    """딜 지분 자료가 레테·렌뿐 — 다른 직업은 HEXA 코어 경로가 조용히 사라졌다(2026-10-17 점검). 빠졌다고 알린다.
    HEXA 코어가 있는 픽스처는 레테뿐이라, 레테의 직업 기준값을 없앤 상태로 본다."""
    import engine.market.hexa_core_paths as hcp
    monkeypatch.setattr(hcp, "job_shares", lambda job: None)
    snap = snapshot(bundle("레테"))
    assert snap.hexa_cores and not snap.own_shares
    r = service.paths(snap, BOSS)
    assert "HEXA 코어" in r["note"] and "자료가 없" in r["note"]


def test_target_roadmap_note_lists_what_is_not_included():
    snap = snapshot(bundle("레테"))
    r = service.target_roadmap(snap, BOSS, [], 34.52, 36.0)
    assert "스페어" in r["note"] and "추옵" in r["note"]
