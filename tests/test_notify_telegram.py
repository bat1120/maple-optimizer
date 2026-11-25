"""결과 보고서 텔레그램 전송(tools/notify_telegram.py) — 실제로 보내지 않고 요청 모양만 본다."""
import importlib.util
import pathlib

import httpx
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("notify_telegram", ROOT / "tools" / "notify_telegram.py")
notify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(notify)


def test_sends_document_with_caption(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    seen = {}

    def handler(request):
        seen["url"], seen["body"] = str(request.url), request.read()
        return httpx.Response(200, json={"ok": True})
    f = tmp_path / "보고서.html"
    f.write_text("<p>결과</p>", encoding="utf-8")
    notify.send_document(f, "요약 " * 600, transport=httpx.MockTransport(handler))
    assert seen["url"] == "https://api.telegram.org/bot123:abc/sendDocument"
    assert b'name="chat_id"\r\n\r\n42' in seen["body"] and "<p>결과</p>".encode() in seen["body"]


def test_failure_shows_reason_but_never_the_token(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:secret-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    f = tmp_path / "r.html"
    f.write_text("x", encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        notify.send_document(f, "", transport=httpx.MockTransport(lambda r: httpx.Response(403, json={"ok": False, "description": "bot was blocked"})))
    assert "bot was blocked" in str(e.value) and "secret-token" not in str(e.value)


def test_missing_settings_say_which(tmp_path, monkeypatch):
    monkeypatch.setattr(notify, "settings", lambda: {"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": "1"})
    with pytest.raises(SystemExit) as e:
        notify.send_document(tmp_path / "없음.html", "")
    assert "TELEGRAM_BOT_TOKEN" in str(e.value)


def test_reads_only_new_replies_from_my_chat(tmp_path, monkeypatch):
    """답장 읽기: 설정한 채팅의 글만, 한 번 읽은 것은 다시 안 나온다(읽은 자리를 파일에 적는다)."""
    import json
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    updates = [{"update_id": 7, "message": {"chat": {"id": 42}, "text": "4개 올렸어"}},
               {"update_id": 8, "message": {"chat": {"id": 999}, "text": "남이 보낸 글"}},
               {"update_id": 9, "message": {"chat": {"id": 42}, "text": "값은 맞아"}}]
    asked = []

    def handler(request):
        offset = json.loads(request.read())["offset"]
        asked.append(offset)
        return httpx.Response(200, json={"ok": True, "result": [u for u in updates if u["update_id"] >= offset]})
    t, f = httpx.MockTransport(handler), tmp_path / "offset.txt"
    assert notify.read_replies(transport=t, offset_file=f) == ["4개 올렸어", "값은 맞아"]
    assert notify.read_replies(transport=t, offset_file=f) == [] and asked == [0, 10]
