"""화면 검증(tools/verify_ui)의 전제: 기능 지도가 읽을 수 있는 모양이고, 픽스처 서버가 키 없이 뜬다."""
import importlib.util
import json
import pathlib

import pytest
from fastapi.testclient import TestClient

from helpers import classes
from nexon.client import CharacterNotFound
from server.app import create_app

VERIFY = pathlib.Path(__file__).resolve().parent.parent / "tools" / "verify_ui"
MAP = json.loads((VERIFY / "features.json").read_text(encoding="utf-8"))


def _serve_module():
    spec = importlib.util.spec_from_file_location("verify_ui_serve", VERIFY / "serve.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_feature_map_is_well_formed():
    ids = [f["id"] for f in MAP["features"]]
    assert len(ids) == len(set(ids)) and ids
    assert MAP["character"] in classes()
    for feature in MAP["features"]:
        assert feature["title"] and feature["url"].startswith("/#/") and feature["ready"], feature["id"]
        assert feature["expect"], f"{feature['id']}: 확인할 것이 하나도 없으면 찍기만 하고 통과한다"
        assert all(e["what"] and e["js"] for e in feature["expect"]), feature["id"]
        for step in feature.get("steps", []):
            assert set(step) <= {"js", "type", "press", "wait", "timeout"}, feature["id"]
        assert feature.get("requires") in (None, "ai"), feature["id"]
        assert set(feature.get("devices", [])) <= {"pc", "mobile"}, feature["id"]
    assert any(f.get("requires") == "ai" for f in MAP["features"]), "AI 상담 화면도 기능 지도에 있어야 한다"


def test_fixture_server_serves_fixture_character_without_keys(tmp_path, monkeypatch):
    for key in ("DATABASE_URL", "OPENAI_API_KEY", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"):
        monkeypatch.setenv(key, "should-be-removed")
    serve = _serve_module()
    import os
    assert not any(os.environ.get(k) for k in ("DATABASE_URL", "OPENAI_API_KEY", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"))

    client = TestClient(create_app(serve.fixture_fetcher, str(tmp_path / "v.sqlite3")))
    assert client.get(f"/api/character/{MAP['character']}").json()["character_class"] == MAP["character"]
    assert client.get("/api/character/없는캐릭터zq9").status_code == 404
    with pytest.raises(CharacterNotFound):
        serve.fixture_fetcher("없는캐릭터zq9", None)
