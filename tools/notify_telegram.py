"""결과 보고서를 텔레그램으로 보낸다(문서 파일 + 짧은 요약).

    uv run python tools/notify_telegram.py 보고서.html --caption "한 줄 요약"
    uv run python tools/notify_telegram.py --check            # 설정이 됐는지만 확인(값은 출력하지 않는다)
    uv run python tools/notify_telegram.py --read             # 사용자가 봇에게 보낸 새 답장을 읽는다(읽은 것은 다시 안 나온다)
    uv run python tools/notify_telegram.py --read --wait 1500 # 새 답장이 올 때까지 최대 1500초 기다린다
    uv run python tools/notify_telegram.py --say "한 줄"       # 글만 보낸다

답장은 설정한 채팅(TELEGRAM_CHAT_ID)에서 온 것만 읽는다 — 다른 사람이 봇에게 보낸 글은 버린다.

설정: 저장소의 .env(커밋되지 않는다) 또는 환경 변수에 TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID.
토큰·채팅 ID는 어디에도 출력하지 않는다 — 오류가 나도 텔레그램이 준 설명만 보여 준다.
"""
from __future__ import annotations

import argparse
import os
import pathlib
import sys

import httpx

ROOT = pathlib.Path(__file__).resolve().parents[1]
KEYS = ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")
CAPTION_MAX = 1024  # 텔레그램 문서 설명 길이 한도


def settings() -> dict[str, str]:
    out = {k: os.environ.get(k, "") for k in KEYS}
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            key, sep, value = line.partition("=")
            if sep and key.strip() in KEYS and not out[key.strip()]:
                out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def send_document(path: pathlib.Path, caption: str, *, transport: httpx.BaseTransport | None = None) -> None:
    s = settings()
    missing = [k for k in KEYS if not s[k]]
    if missing:
        raise SystemExit(f"텔레그램 설정이 없습니다: {', '.join(missing)} (.env에 넣어 주세요)")
    with httpx.Client(timeout=30.0, transport=transport) as http, path.open("rb") as f:
        r = http.post(f"https://api.telegram.org/bot{s['TELEGRAM_BOT_TOKEN']}/sendDocument",
                      data={"chat_id": s["TELEGRAM_CHAT_ID"], "caption": caption[:CAPTION_MAX]},
                      files={"document": (path.name, f)})
    try:
        body = r.json()
    except ValueError:
        body = {}
    if not body.get("ok"):
        raise SystemExit(f"텔레그램 전송 실패({r.status_code}): {body.get('description', '응답을 읽지 못함')}")


OFFSET_FILE = ROOT / ".cache" / "telegram_offset.txt"  # 어디까지 읽었는지(.cache는 커밋되지 않는다)


def _call(method: str, payload: dict, *, transport: httpx.BaseTransport | None = None, timeout: float = 30.0) -> dict:
    s = settings()
    missing = [k for k in KEYS if not s[k]]
    if missing:
        raise SystemExit(f"텔레그램 설정이 없습니다: {', '.join(missing)} (.env에 넣어 주세요)")
    with httpx.Client(timeout=timeout, transport=transport) as http:
        r = http.post(f"https://api.telegram.org/bot{s['TELEGRAM_BOT_TOKEN']}/{method}", json=payload)
    try:
        body = r.json()
    except ValueError:
        body = {}
    if not body.get("ok"):
        raise SystemExit(f"텔레그램 요청 실패({r.status_code}): {body.get('description', '응답을 읽지 못함')}")
    return body


def send_text(text: str, *, transport: httpx.BaseTransport | None = None) -> None:
    _call("sendMessage", {"chat_id": settings()["TELEGRAM_CHAT_ID"], "text": text[:4000]}, transport=transport)


def read_replies(wait: int = 0, *, transport: httpx.BaseTransport | None = None, offset_file: pathlib.Path = OFFSET_FILE) -> list[str]:
    """설정한 채팅에서 온 새 글만(시간순). 읽은 자리는 파일에 적어 다음에 다시 나오지 않게 한다.
    wait > 0이면 새 글이 올 때까지 그만큼(초) 기다린다(텔레그램 long polling, 한 번에 최대 50초)."""
    import time
    chat = settings()["TELEGRAM_CHAT_ID"]
    offset = int(offset_file.read_text().strip() or 0) if offset_file.exists() else 0
    deadline = time.monotonic() + wait
    while True:
        hold = max(0, min(50, int(deadline - time.monotonic())))
        body = _call("getUpdates", {"offset": offset, "timeout": hold, "allowed_updates": ["message"]}, transport=transport, timeout=hold + 20)
        out = []
        for u in body.get("result", []):
            offset = max(offset, u["update_id"] + 1)
            m = u.get("message") or {}
            if str((m.get("chat") or {}).get("id")) == str(chat) and m.get("text"):
                out.append(m["text"])
        offset_file.parent.mkdir(parents=True, exist_ok=True)
        offset_file.write_text(str(offset))
        if out or time.monotonic() >= deadline:
            return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("file", nargs="?")
    ap.add_argument("--caption", default="")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--read", action="store_true")
    ap.add_argument("--wait", type=int, default=0)
    ap.add_argument("--say")
    args = ap.parse_args()
    if args.check:
        s = settings()
        print({k: "있음" if s[k] else "없음" for k in KEYS})
        return
    if args.read:
        got = read_replies(args.wait)
        print("\n---\n".join(got) if got else "(새 답장 없음)")
        return
    if args.say:
        send_text(args.say)
        print("보냈습니다")
        return
    if not args.file:
        ap.error("보낼 파일을 적어 주세요")
    send_document(pathlib.Path(args.file), args.caption)
    print("보냈습니다")


if __name__ == "__main__":
    sys.exit(main())
