"""패키지 경계: 계산 엔진은 서버·AI·네트워크를 모른다.
에이전트는 코드베이스에 이미 있는 import를 따라 쓴다 — 경계를 넘는 import가 하나 생기면 다음 작업이 그걸 본보기로 삼는다.
그래서 규칙을 글이 아니라 테스트로 둔다. 지금 있는 예외는 아래 표에 적어 두고, 새로 늘지 않게 막는다(줄이는 건 언제든 좋다)."""
import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
PACKAGES = ("engine", "nexon", "server", "agent")

FORBIDDEN = {
    "engine": {"server", "agent", "nexon"},
    "nexon": {"server", "agent"},
    "agent": {"server"},
}

KNOWN_EXCEPTIONS = {
    ("engine/market/armor_sets.py", "nexon"),
    ("engine/market/swaps.py", "nexon"),
    ("agent/tools.py", "server"),
}

ENGINE_FORBIDDEN_LIBRARIES = {"fastapi", "httpx", "openai", "psycopg", "uvicorn", "langfuse", "requests", "urllib"}


def _imports(path: pathlib.Path) -> set[str]:
    found = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.add(node.module.split(".")[0])
    return found


def _crossings() -> set[tuple[str, str]]:
    seen = set()
    for package, forbidden in FORBIDDEN.items():
        for path in sorted((ROOT / package).rglob("*.py")):
            rel = path.relative_to(ROOT).as_posix()
            seen.update((rel, target) for target in _imports(path) & forbidden)
    return seen


def test_no_new_imports_across_package_boundaries():
    new = sorted(_crossings() - KNOWN_EXCEPTIONS)
    assert not new, (
        f"패키지 경계를 넘는 import가 새로 생겼다: {new}. "
        "engine은 nexon·server·agent를, nexon은 server·agent를, agent는 server를 import하지 않는다. "
        "필요한 값은 호출하는 쪽(server)에서 인자로 넘긴다."
    )


def test_known_exceptions_still_exist():
    gone = sorted(KNOWN_EXCEPTIONS - _crossings())
    assert not gone, f"이 예외는 이제 없다 — KNOWN_EXCEPTIONS에서 지운다: {gone}"


def test_engine_does_not_touch_network_or_server_libraries():
    hits = sorted(
        (path.relative_to(ROOT).as_posix(), lib)
        for path in (ROOT / "engine").rglob("*.py")
        for lib in _imports(path) & ENGINE_FORBIDDEN_LIBRARIES
    )
    assert not hits, f"engine은 순수 계산이다 — 네트워크·서버 라이브러리를 import하지 않는다: {hits}"
