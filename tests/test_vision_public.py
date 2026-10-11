"""일반 유저에게 경매장 화면 분석을 연다(2026-10-07 사용자: 공개 + 한도).
- 로그인 없이 판독. AI를 실제로 부른 판독만 IP당 하루 상한(vision_public_daily)으로 센다
- 툴팁 없는 화면 건너뛰기·같은 툴팁 재사용은 AI 비용 0 → 상한과 무관, 0.5초마다 와도 분당 30회 일반 제한에 걸리지 않는다
- 일반 유저 화면은 학습 데이터·장비창 채점 기록에 넣지 않는다(관리자 기록과 섞이지 않게)"""
import base64
import io
import json
from types import SimpleNamespace as NS

from fastapi.testclient import TestClient
from PIL import Image

from helpers import bundle
from server.admin import make_password_hash
from server.app import create_app

PLAIN = None


def _plain_frame():
    buf = io.BytesIO()
    Image.new("RGB", (320, 200), (120, 170, 210)).save(buf, "JPEG")
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


class Fake:
    def __init__(self):
        self.calls = 0
        self.responses = NS(create=self._create)

    def _create(self, **kw):
        self.calls += 1
        out = {"tooltip_visible": True, "fee_rate": None, "listings": []}
        return NS(output=[], output_text=json.dumps(out), status="completed", usage=NS(input_tokens=1, output_tokens=1))


def _app(tmp_path, fake, **kw):
    return TestClient(create_app(lambda n, d: bundle("레테"), str(tmp_path / "c.sqlite3"), agent_client=fake,
                                 admin_password_hash=make_password_hash("pw", 1000), session_secret="s" * 32,
                                 vision_dataset_dir=str(tmp_path / "ds"), **kw))


AI_FRAME = "data:image/jpeg;base64,AAAA"  # 열 수 없는 이미지 → 툴팁 자르기 없이 AI로 간다


def test_public_user_can_read_and_sees_remaining(tmp_path):
    fake = Fake()
    c = _app(tmp_path, fake, vision_public_daily=3)
    r = c.post("/api/vision/listings", json={"image": AI_FRAME})
    assert r.status_code == 200 and fake.calls == 1
    assert r.json()["ai_remaining"] == 2


def test_public_daily_ai_quota_per_ip_but_free_frames_still_pass(tmp_path):
    fake = Fake()
    c = _app(tmp_path, fake, vision_public_daily=2)
    for _ in range(2):
        assert c.post("/api/vision/listings", json={"image": AI_FRAME}).status_code == 200
    r = c.post("/api/vision/listings", json={"image": AI_FRAME})
    assert r.status_code == 429 and r.json()["code"] == "VISION_QUOTA" and fake.calls == 2
    skip = c.post("/api/vision/listings", json={"image": _plain_frame()})   # 툴팁 없는 화면: AI 안 부름
    assert skip.status_code == 200 and fake.calls == 2


def test_public_frames_are_not_blocked_by_general_rate_limit(tmp_path):
    fake = Fake()
    c = _app(tmp_path, fake, rate_limit=30)
    frame = _plain_frame()
    codes = [c.post("/api/vision/listings", json={"image": frame}).status_code for _ in range(45)]
    assert codes.count(200) == 45


def test_public_frames_have_their_own_per_minute_cap(tmp_path):
    c = _app(tmp_path, Fake(), vision_frames_per_min=10)
    frame = _plain_frame()
    codes = [c.post("/api/vision/listings", json={"image": frame}).status_code for _ in range(12)]
    assert codes.count(200) == 10 and codes[-1] == 429


def test_public_reads_are_not_saved_or_scored(tmp_path):
    fake = Fake()
    c = _app(tmp_path, fake)
    c.post("/api/vision/listings", json={"image": AI_FRAME})
    assert not (tmp_path / "ds").exists() or not [p for p in (tmp_path / "ds").iterdir() if p.is_dir() and p.name != "skipped"]
    c.post("/api/admin/login", json={"password": "pw"})
    assert c.post("/api/vision/score", json={"name": "내신부레테", "reads": []}).json()["matched"] == 0


def test_too_large_image_is_rejected(tmp_path):
    c = _app(tmp_path, Fake())
    r = c.post("/api/vision/listings", json={"image": "data:image/jpeg;base64," + "A" * 6_000_001})
    assert r.status_code == 413


def test_public_evaluate_needs_no_login(tmp_path):
    c = _app(tmp_path, Fake())
    r = c.post("/api/vision/evaluate", json={"name": "내신부레테", "listings": []})
    assert r.status_code == 200 and r.json() == {"items": []}


def test_admin_has_no_public_quota(tmp_path):
    fake = Fake()
    c = _app(tmp_path, fake, vision_public_daily=1)
    c.post("/api/admin/login", json={"password": "pw"})
    for _ in range(3):
        assert c.post("/api/vision/listings", json={"image": AI_FRAME}).status_code == 200
    assert fake.calls == 3


def test_daily_quota_survives_restart_and_stores_no_raw_ip(tmp_path):
    """한도는 DB에 남는다(2026-10-11 사용자: 해시만 DB에) — 서버가 다시 떠도 이어서 센다. IP 원문은 저장하지 않는다."""
    import sqlite3
    fake = Fake()
    c = _app(tmp_path, fake, vision_public_daily=2)
    assert c.post("/api/vision/listings", json={"image": AI_FRAME}).status_code == 200
    c2 = _app(tmp_path, fake, vision_public_daily=2)  # 재시작
    r = c2.post("/api/vision/listings", json={"image": AI_FRAME})
    assert r.status_code == 200 and r.json()["ai_remaining"] == 0
    assert c2.post("/api/vision/listings", json={"image": AI_FRAME}).json()["code"] == "VISION_QUOTA"
    db = sqlite3.connect(tmp_path / "c.sqlite3")
    rows = db.execute("SELECT * FROM vision_quota").fetchall()
    assert len(rows) == 1 and not any("testclient" in str(v) for v in rows[0])


def test_old_quota_days_are_deleted(tmp_path):
    import sqlite3
    now = [1_800_000_000.0]
    fake = Fake()
    c = _app(tmp_path, fake, vision_public_daily=5, clock=lambda: now[0])
    c.post("/api/vision/listings", json={"image": AI_FRAME})
    now[0] += 86400 * 2  # 같은 앱으로 이틀 뒤 — 지난 날짜 줄은 지운다
    c.post("/api/vision/listings", json={"image": AI_FRAME + "B"})
    db = sqlite3.connect(tmp_path / "c.sqlite3")
    assert db.execute("SELECT COUNT(*) FROM vision_quota").fetchone()[0] == 1
