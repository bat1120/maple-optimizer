"""결과 보고서를 텔레그램으로 보낸다(문서 파일 + 짧은 요약).

    uv run python tools/notify_telegram.py 보고서.html --caption "한 줄 요약"
    uv run python tools/notify_telegram.py --check            # 설정이 됐는지만 확인(값은 출력하지 않는다)

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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("file", nargs="?")
    ap.add_argument("--caption", default="")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    if args.check:
        s = settings()
        print({k: "있음" if s[k] else "없음" for k in KEYS})
        return
    if not args.file:
        ap.error("보낼 파일을 적어 주세요")
    send_document(pathlib.Path(args.file), args.caption)
    print("보냈습니다")


if __name__ == "__main__":
    sys.exit(main())
