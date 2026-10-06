"""배포 이미지: 서버가 import하는 이 저장소의 패키지는 전부 Dockerfile이 복사해야 한다.
2026-10-07 발견: agent/(AI 상담)를 복사하지 않아 클라우드에서 상담 요청이 import 오류로 실패할 상태였다."""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
LOCAL = {p.name for p in ROOT.iterdir() if p.is_dir() and (p / "__init__.py").exists()}


def _imported_packages() -> set[str]:
    found = set()
    for py in (ROOT / "server").rglob("*.py"):
        for m in re.finditer(r"^\s*(?:from|import)\s+([a-z_]+)", py.read_text(encoding="utf-8"), re.M):
            if m.group(1) in LOCAL:
                found.add(m.group(1))
    return found


def test_dockerfile_copies_every_local_package_the_server_imports():
    docker = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    copied = set(re.findall(r"^COPY\s+([a-z_]+)/\s", docker, re.M))
    missing = _imported_packages() - copied
    assert not missing, f"Dockerfile에 COPY가 빠진 패키지: {sorted(missing)}"
