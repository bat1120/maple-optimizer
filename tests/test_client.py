import datetime as dt
import json

import httpx
import pytest

from nexon.client import (
    ENDPOINTS, OPTIONAL_ENDPOINTS, CharacterNotFound, InvalidKey, NexonClient, NexonError, RateLimited, Unavailable, load_api_key,
)


def make_client(handler):
    return NexonClient("test-key", transport=httpx.MockTransport(handler), min_interval=0)


def err(status, code, msg="x"):
    return httpx.Response(status, json={"error": {"name": code, "message": msg}})


def test_sends_key_header_and_returns_ocid():
    seen = {}

    def handler(req):
        seen["key"] = req.headers["x-nxopen-api-key"]
        seen["url"] = str(req.url)
        return httpx.Response(200, json={"ocid": "abc"})

    assert make_client(handler).get_ocid("내신부레테") == "abc"
    assert seen["key"] == "test-key"
    assert seen["url"].startswith("https://open.api.nexon.com/maplestory/v1/id?character_name=")


def test_unknown_name_raises_character_not_found():
    c = make_client(lambda req: err(400, "OPENAPI00004", "Please input valid parameter"))
    with pytest.raises(CharacterNotFound):
        c.get_ocid("없는캐릭터")


def test_rate_limit_raises_without_retry():
    calls = []

    def handler(req):
        calls.append(1)
        return err(429, "OPENAPI00007")

    with pytest.raises(RateLimited):
        make_client(handler).get("character/stat", "abc")
    assert len(calls) == 1


@pytest.mark.parametrize("status,code,exc", [
    (400, "OPENAPI00009", Unavailable),
    (400, "OPENAPI00010", Unavailable),
    (503, "OPENAPI00011", Unavailable),
    (400, "OPENAPI00005", InvalidKey),
    (403, "OPENAPI00002", InvalidKey),
    (500, "OPENAPI00001", NexonError),
])
def test_error_codes_map_to_exceptions(status, code, exc):
    with pytest.raises(exc) as info:
        make_client(lambda req: err(status, code)).get("character/stat", "abc")
    assert info.value.code == code
    assert info.value.status == status


def test_error_message_never_contains_key():
    with pytest.raises(NexonError) as info:
        make_client(lambda req: err(400, "OPENAPI00005")).get("character/stat", "abc")
    assert "test-key" not in str(info.value)


def test_date_param_and_lower_bound():
    seen = {}

    def handler(req):
        seen["date"] = req.url.params.get("date")
        return httpx.Response(200, json={"date": "2026-10-01T00:00+09:00", "character_class": "레테", "final_stat": [{"stat_name": "STR", "stat_value": "1"}]})

    c = make_client(handler)
    c.get("character/stat", "abc", dt.date(2026, 10, 1))
    assert seen["date"] == "2026-10-01"
    with pytest.raises(ValueError):
        c.get("character/stat", "abc", dt.date(2023, 12, 20))


def test_empty_day_returns_none():
    body = {"date": "2026-07-01T00:00+09:00", "character_class": None, "final_stat": [], "remain_ap": None}
    assert make_client(lambda req: httpx.Response(200, json=body)).get("character/stat", "abc", dt.date(2026, 7, 1)) is None


def test_zero_values_are_not_empty():
    body = {"date": None, "character_class": "레테", "remain_ap": 0, "final_stat": [{"stat_name": "STR", "stat_value": "0"}]}
    assert make_client(lambda req: httpx.Response(200, json=body)).get("character/stat", "abc") == body


def test_fetch_bundle_calls_all_endpoints():
    paths = []

    def handler(req):
        paths.append(req.url.path)
        if req.url.path.endswith("/id"):
            return httpx.Response(200, json={"ocid": "abc"})
        return httpx.Response(200, json={"date": None, "x": 1})

    b = make_client(handler).fetch_bundle("내신부레테")
    # 기본 + 선택(HEXA 스탯·코어) + 6차 스킬 + 연무장(기록이 없으면 결과는 None) — 2026-10-07 HEXA 경로
    assert list(b) == list(ENDPOINTS) + list(OPTIONAL_ENDPOINTS) + ["character/skill_6", "battle-practice/result"]
    assert b["battle-practice/result"] is None
    assert len(paths) == 1 + len(ENDPOINTS) + len(OPTIONAL_ENDPOINTS) + 2  # 6차 스킬 + 연무장 리플레이 목록


def test_load_api_key_prefers_env(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("NEXON_API_KEY=from-file\n", encoding="utf-8")
    monkeypatch.setenv("NEXON_API_KEY", "from-env")
    assert load_api_key(tmp_path) == "from-env"
    monkeypatch.delenv("NEXON_API_KEY")
    assert load_api_key(tmp_path) == "from-file"


def test_load_api_key_missing_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("NEXON_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        load_api_key(tmp_path)
