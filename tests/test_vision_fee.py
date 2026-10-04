"""화면에 보이는 경매장 판매 수수료를 읽어 자동 적용한다(판매 등록 창 등)."""
import json
from types import SimpleNamespace as NS

from fastapi.testclient import TestClient

from helpers import bundle
from server.admin import make_password_hash
from server.app import create_app
from server.vision import _SCHEMA, normalize_fee

IMG = "data:image/jpeg;base64,AAA"


def test_schema_asks_for_fee_rate():
    assert "fee_rate" in _SCHEMA["required"] and _SCHEMA["properties"]["fee_rate"]["type"] == ["number", "null"]


def test_normalize_fee_accepts_fraction_or_percent_and_rejects_nonsense():
    assert normalize_fee(0.03) == 0.03 and normalize_fee(5) == 0.05 and normalize_fee(3.0) == 0.03
    assert normalize_fee(None) is None and normalize_fee(0) is None and normalize_fee(0.5) is None and normalize_fee(-1) is None


def _app(tmp_path, payload):
    fake = NS(responses=NS(create=lambda **kw: NS(output=[], output_text=json.dumps(payload), status="completed",
                                                   usage=NS(input_tokens=1, output_tokens=1))))
    c = TestClient(create_app(lambda n, d: bundle("레테"), str(tmp_path / "c.sqlite3"), agent_client=fake,
                              admin_password_hash=make_password_hash("pw", 1000), session_secret="s" * 32))
    c.post("/api/admin/login", json={"password": "pw"})
    return c


def test_vision_endpoint_returns_fee_read_from_screen(tmp_path):
    r = _app(tmp_path, {"tooltip_visible": False, "listings": [], "fee_rate": 3}).post("/api/vision/listings", json={"image": IMG})
    assert r.json()["fee_rate"] == 0.03


def test_vision_endpoint_fee_is_null_when_not_visible(tmp_path):
    r = _app(tmp_path, {"tooltip_visible": False, "listings": []}).post("/api/vision/listings", json={"image": IMG})
    assert r.json()["fee_rate"] is None
