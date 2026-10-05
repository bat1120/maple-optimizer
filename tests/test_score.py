"""장비창 훑기 자동 채점: 화면에서 읽은 툴팁을 넥슨 API의 내 착용 템(정답)과 이름으로 맞춰 항목마다 채점한다."""
from fastapi.testclient import TestClient

from helpers import bundle
from nexon.convert import snapshot
from server.admin import make_password_hash
from server.app import create_app
from server.score import expected_from_item, score_reads
from engine.stats.residual import preset_items


def _glove():
    snap = snapshot(bundle("레테"))
    return snap, preset_items(snap, snap.active_equipment_preset)["장갑"]


def test_expected_answer_comes_from_api_item():
    snap, it = _glove()
    e = expected_from_item(it)
    assert e["name"] == it.name and e["starforce"] == it.starforce and e["level"] == it.level
    assert e["potential_lines"] == it.potentials and e["additional"] == it.additional
    assert e["potential_grade"] == it.potential_grade and e["starforce_source"] == "별 세기"
    assert e["total"]["INT"] == it.core.flat["INT"]


def test_reads_are_matched_by_name_and_scored():
    snap, it = _glove()
    right = expected_from_item(it)
    wrong = {**right, "starforce": right["starforce"] - 3, "potential_lines": right["potential_lines"][:2]}
    r = score_reads(snap, [right])
    assert r["matched"] == 1 and r["accuracy"] == 1.0
    r2 = score_reads(snap, [wrong, {"name": "없는 템"}])
    assert r2["matched"] == 1 and r2["unmatched"] == ["없는 템"]
    assert r2["accuracy"] < 1.0 and any("스타포스" in m for m in r2["items"][0]["miss"])


def test_score_route(tmp_path):
    snap, it = _glove()
    c = TestClient(create_app(lambda n, d: bundle("레테"), str(tmp_path / "c.sqlite3"),
                              admin_password_hash=make_password_hash("pw", 1000), session_secret="s" * 32))
    assert c.post("/api/vision/score", json={"name": "x", "reads": []}).status_code == 401
    c.post("/api/admin/login", json={"password": "pw"})
    r = c.post("/api/vision/score", json={"name": "내신부레테", "reads": [expected_from_item(it)]}).json()
    assert r["matched"] == 1 and r["accuracy"] == 1.0


def test_score_uses_reads_remembered_by_server(tmp_path):
    """화면 쪽에서 판독이 빠져도(2026-10-05: 9개 읽고 3개만 채점) 서버가 기억한 판독으로 채점한다."""
    import json
    from types import SimpleNamespace as NS
    snap, it = _glove()
    read = {**expected_from_item(it), "category": "장갑", "part": "장갑", "price": None, "equipped": True, "tooltip": None,
            "breakdown": {}, "potentials": it.potentials + it.additional}
    payload = {"tooltip_visible": True, "fee_rate": None, "listings": [read]}
    fake = NS(responses=NS(create=lambda **kw: NS(output=[], output_text=json.dumps(payload, ensure_ascii=False),
                                                   status="completed", usage=NS(input_tokens=1, output_tokens=1))))
    c = TestClient(create_app(lambda n, d: bundle("레테"), str(tmp_path / "c.sqlite3"), agent_client=fake,
                              admin_password_hash=make_password_hash("pw", 1000), session_secret="s" * 32))
    c.post("/api/admin/login", json={"password": "pw"})
    c.post("/api/vision/listings", json={"image": "data:image/jpeg;base64,AAA", "name": "내신부레테"})
    r = c.post("/api/vision/score", json={"name": "내신부레테", "reads": []}).json()
    assert r["matched"] == 1 and r["items"][0]["name"] == it.name
    assert c.post("/api/vision/score/reset").json() == {"cleared": True}
    assert c.post("/api/vision/score", json={"name": "내신부레테", "reads": []}).json()["matched"] == 0
