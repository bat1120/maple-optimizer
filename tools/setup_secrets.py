"""관리자 AI 기능용 비밀값을 .env에 넣는다. 입력은 화면에 표시되지 않고, 값은 출력하지 않는다.

사용: uv run python tools/setup_secrets.py
- OPENAI_API_KEY      : 붙여넣기 (platform.openai.com → API keys)
- ADMIN_PASSWORD_HASH : 관리자 비밀번호를 두 번 입력하면 해시만 저장(원문은 저장하지 않음)
- SESSION_SECRET      : 자동 생성(48자)
이미 값이 있는 항목은 Enter로 건너뛰면 그대로 둔다. 다른 줄(NEXON_API_KEY 등)은 건드리지 않는다.
"""
import getpass
import pathlib
import secrets
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from server.admin import make_password_hash  # noqa: E402

ENV = pathlib.Path(__file__).resolve().parent.parent / ".env"


def update_env(text: str, values: dict[str, str]) -> str:
    """KEY=VALUE 줄을 바꾸거나 끝에 붙인다. 나머지 줄은 그대로."""
    lines = text.splitlines()
    done = set()
    for i, line in enumerate(lines):
        key = line.split("=", 1)[0].strip()
        if key in values:
            lines[i] = f"{key}={values[key]}"
            done.add(key)
    lines += [f"{k}={v}" for k, v in values.items() if k not in done]
    return "\n".join(lines) + "\n"


def _has(text: str, key: str) -> bool:
    return any(l.startswith(f"{key}=") and l.split("=", 1)[1].strip() for l in text.splitlines())


def main() -> int:
    text = ENV.read_text(encoding="utf-8") if ENV.exists() else ""
    values: dict[str, str] = {}

    key = getpass.getpass("OPENAI_API_KEY 붙여넣기 (입력은 안 보여요, 건너뛰려면 Enter): ").strip()
    if key:
        values["OPENAI_API_KEY"] = key
    elif not _has(text, "OPENAI_API_KEY"):
        print("  ! OPENAI_API_KEY가 없으면 AI 기능은 꺼진 채로 뜹니다.")

    pw = getpass.getpass("관리자 비밀번호 (건너뛰려면 Enter): ")
    if pw:
        if pw != getpass.getpass("한 번 더: "):
            print("비밀번호가 서로 달라요. 다시 실행해 주세요.")
            return 1
        if len(pw) < 8:
            print("비밀번호는 8자 이상으로 해 주세요.")
            return 1
        values["ADMIN_PASSWORD_HASH"] = make_password_hash(pw)

    if not _has(text, "SESSION_SECRET"):
        values["SESSION_SECRET"] = secrets.token_urlsafe(36)

    if not values:
        print("바뀐 값이 없어요.")
        return 0
    ENV.write_text(update_env(text, values), encoding="utf-8")
    print("저장했어요:", ", ".join(values), "→", ENV)
    print("서버를 다시 시작하면 적용돼요: powershell -ExecutionPolicy Bypass -File scripts/run-local.ps1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
