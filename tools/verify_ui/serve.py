"""화면 검증용 서버: 넥슨 API·AI 키 없이, 익명화한 픽스처(tests/fixtures/characters)로 실제 앱을 띄운다.

    uv run python tools/verify_ui/serve.py --port 8765 [--with-ai]

- 닉네임 = 픽스처 직업 이름(예: 레테). 그 밖의 닉네임은 실제와 같이 '캐릭터를 찾을 수 없습니다'(404)가 된다.
- 바깥으로 나가는 연결이 없다: 운영 DB(DATABASE_URL)·AI·추적 키는 이 프로세스에서 지우고, 기록은 임시 SQLite에만 쓴다.
- 결과가 매번 같아서, 사람 없이 도는 작업도 이 서버로 화면을 직접 확인할 수 있다.
- --with-ai(이 PC 전용): .env의 OPENAI_API_KEY로 AI 상담만 실제 모델에 연결한다(비용 발생). 추적·운영 DB는 여전히 끈다.
"""
import argparse
import os
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]

for key in ("DATABASE_URL", "OPENAI_API_KEY", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "AUCTION_MCP_CMD"):
    os.environ.pop(key, None)

import uvicorn  # noqa: E402

from helpers import bundle, classes  # noqa: E402
from nexon.client import CharacterNotFound  # noqa: E402
from server.app import create_app  # noqa: E402


def fixture_fetcher(name, _day):
    if name not in classes():
        raise CharacterNotFound("OPENAPI00004", f"캐릭터를 찾을 수 없습니다: {name}", 400)
    return bundle(name)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--with-ai", action="store_true")
    args = parser.parse_args()
    agent_client = None
    if args.with_ai:
        import openai

        from server.app import _env
        key = _env("OPENAI_API_KEY")
        if not key:
            sys.exit("OPENAI_API_KEY가 없어요(.env) — --with-ai는 실제 모델을 부른다")
        agent_client = openai.OpenAI(api_key=key)
        if _env("OPENAI_MODEL"):
            os.environ.setdefault("OPENAI_MODEL", _env("OPENAI_MODEL"))
    static_dir = ROOT / "web" / "dist"
    if not (static_dir / "index.html").exists():
        sys.exit("web/dist가 없어요 — 먼저 `npm --prefix web run build`")
    with tempfile.TemporaryDirectory(prefix="mo-verify-") as tmp:
        app = create_app(fixture_fetcher, str(pathlib.Path(tmp) / "verify.sqlite3"), static_dir=str(static_dir),
                         rate_limit=100_000, agent_client=agent_client)
        uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
