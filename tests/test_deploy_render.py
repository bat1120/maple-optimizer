"""데모 배포(Render 무료, 2026-10-07): render.yaml 한 번 연결로 Dockerfile 빌드·배포.
비밀값은 저장소에 두지 않고 Render 화면에서 넣는다(sync: false). 포트는 Render가 주는 PORT를 따른다."""
import pathlib
import re

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _service():
    data = yaml.safe_load((ROOT / "render.yaml").read_text(encoding="utf-8"))
    return data["services"][0]


def test_render_blueprint_builds_dockerfile_with_health_check():
    s = _service()
    assert s["type"] == "web" and s["runtime"] == "docker" and s["plan"] == "free"
    assert s["healthCheckPath"] == "/api/health"


def test_render_secrets_are_entered_in_dashboard_not_committed():
    env = {e["key"]: e for e in _service()["envVars"]}
    for key in ("NEXON_API_KEY", "OPENAI_API_KEY", "ADMIN_PASSWORD_HASH"):
        assert env[key].get("sync") is False and "value" not in env[key]
    assert env["SESSION_SECRET"].get("generateValue") is True


def test_container_listens_on_platform_port():
    cmd = re.search(r"^CMD (.+)$", (ROOT / "Dockerfile").read_text(encoding="utf-8"), re.M).group(1)
    assert "${PORT:-8000}" in cmd
