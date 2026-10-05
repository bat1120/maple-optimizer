"""내 데이터 모으기: 화면 분석 프레임과 AI 판독을 내 PC 폴더에만 저장하고, 화면에서 고친 값을 정답으로 남긴다(VISION_DATASET_DIR, 기본 꺼짐).
나중에 파인튜닝을 검토할 때 쓸 정답지다 — 다른 사람 이미지는 쓰지 않는다."""
import base64
import io
import json
from types import SimpleNamespace as NS

from fastapi.testclient import TestClient
from PIL import Image

from helpers import bundle
from server.admin import make_password_hash
from server.app import create_app
from server.dataset import DatasetStore

KEYS = ("STR", "DEX", "INT", "LUK", "HP", "ATK", "MATK", "ALL%", "BOSS", "IED", "DMG")


def _jpeg():
    buf = io.BytesIO()
    Image.new("RGB", (64, 48), (120, 170, 210)).save(buf, "JPEG")
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


LISTING = {"name": "에테르넬 메이지햇", "category": "모자", "part": "모자", "starforce": 22, "level": 250,
           "potential_grade": "레전드리", "additional_grade": "에픽", "total": {k: None for k in KEYS} | {"INT": 150},
           "breakdown": {k: None for k in KEYS}, "potentials": ["INT +13%"], "additional": ["마력 +10"],
           "price": 5_000_000_000, "equipped": False, "tooltip": None}


def test_store_saves_frames_and_corrections(tmp_path):
    store = DatasetStore(str(tmp_path / "ds"), clock=lambda: 1.0)
    fid = store.save_frame(_jpeg(), {"listings": [LISTING]})
    assert (tmp_path / "ds" / fid / "frame.jpg").exists()
    assert json.loads((tmp_path / "ds" / fid / "reading.json").read_text(encoding="utf-8"))["listings"][0]["name"] == "에테르넬 메이지햇"
    store.save_correction(fid, "sig1", {"starforce": 21})
    assert store.stats() == {"frames": 1, "corrected": 1}
    corr = json.loads((tmp_path / "ds" / fid / "corrections.json").read_text(encoding="utf-8"))
    assert corr == [{"signature": "sig1", "fields": {"starforce": 21}, "at": 1.0}]


def test_store_rejects_unknown_frame_and_path_tricks(tmp_path):
    store = DatasetStore(str(tmp_path / "ds"), clock=lambda: 1.0)
    for bad in ("nope", "../etc", ""):
        try:
            store.save_correction(bad, "s", {})
        except KeyError:
            continue
        raise AssertionError(bad)


def _client(tmp_path, dataset_dir):
    fake = NS(responses=NS(create=lambda **kw: NS(
        output=[], output_text=json.dumps({"tooltip_visible": True, "fee_rate": None, "listings": [LISTING]}, ensure_ascii=False),
        status="completed", usage=NS(input_tokens=1, output_tokens=1))))
    c = TestClient(create_app(lambda n, d: bundle("레테"), str(tmp_path / "c.sqlite3"), agent_client=fake,
                              admin_password_hash=make_password_hash("pw", 1000), session_secret="s" * 32,
                              vision_dataset_dir=dataset_dir))
    c.post("/api/admin/login", json={"password": "pw"})
    return c


def test_vision_saves_frame_and_correction_reevaluates(tmp_path):
    c = _client(tmp_path, str(tmp_path / "ds"))
    r = c.post("/api/vision/listings", json={"image": _jpeg(), "name": "내신부레테", "tooltips_only": False}).json()
    fid, item = r["frame_id"], r["items"][0]
    assert fid and item["frame_id"] == fid
    fixed = c.post("/api/vision/correct", json={"frame_id": fid, "signature": item["signature"], "name": "내신부레테",
                                                "fields": {"starforce": 21, "potentials": ["INT +12%"]}}).json()
    assert fixed["item"]["read"]["starforce"] == 21 and fixed["item"]["read"]["potential_lines"] == ["INT +12%"]
    assert fixed["item"]["read"]["corrected"] is True and fixed["item"]["evaluated"] is True
    assert c.get("/api/vision/dataset").json() == {"enabled": True, "frames": 1, "corrected": 1}


def test_dataset_is_off_by_default(tmp_path):
    c = _client(tmp_path, None)
    r = c.post("/api/vision/listings", json={"image": _jpeg(), "name": "내신부레테", "tooltips_only": False}).json()
    assert r.get("frame_id") is None and not (tmp_path / "ds").exists()
    assert c.get("/api/vision/dataset").json() == {"enabled": False, "frames": 0, "corrected": 0}
    bad = c.post("/api/vision/correct", json={"frame_id": "x", "signature": "s", "name": "내신부레테", "fields": {}})
    assert bad.status_code == 503
