"""G10 판정 — 배포 준비물. Docker 데몬이 없으면 ②는 실패(skip은 통과가 아니다)."""
import json
import os
import pathlib
import re
import subprocess
import time
import urllib.request

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
RESULTS = ROOT / "goals" / "results" / "G10.json"
_m: dict = {}


def _record(k, v):
    _m[k] = v
    RESULTS.write_text(json.dumps(_m, ensure_ascii=False, indent=1), encoding="utf-8")


def _run(*args, **kw):
    return subprocess.run(list(args), cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)


def test_criterion1_compose_config_is_valid():
    env = {**os.environ, "DOMAIN": "example.com"}
    r = _run("docker", "compose", "-f", "docker-compose.yml", "config", "--quiet", env=env)
    _record("criterion1_compose_config_exit", r.returncode)
    assert r.returncode == 0, r.stderr[-1000:]
    cfg = yaml.safe_load(_run("docker", "compose", "-f", "docker-compose.yml", "config", env=env).stdout)
    assert set(cfg["services"]) == {"api", "caddy"}


def test_criterion2_image_builds_and_serves_health():
    b = _run("docker", "build", "-t", "maple-optimizer:g10", ".", timeout=1800)
    _record("criterion2_build_exit", b.returncode)
    assert b.returncode == 0, (b.stderr or b.stdout)[-1500:]
    _run("docker", "rm", "-f", "maple-g10")
    r = _run("docker", "run", "-d", "--name", "maple-g10", "-p", "18000:8000", "-e", "NEXON_API_KEY=dummy", "maple-optimizer:g10")
    assert r.returncode == 0, r.stderr
    try:
        status = None
        for _ in range(60):
            try:
                status = urllib.request.urlopen("http://127.0.0.1:18000/api/health", timeout=2).status
                break
            except Exception:
                time.sleep(1)
        root = urllib.request.urlopen("http://127.0.0.1:18000/", timeout=5).read().decode()
        _record("criterion2_health_status", status)
        assert status == 200 and '<div id="root">' in root
    finally:
        _run("docker", "rm", "-f", "maple-g10")


def test_criterion3_workflow_parses_and_secrets_documented():
    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "deploy.yml").read_text(encoding="utf-8"))
    assert wf["jobs"]
    used = set(re.findall(r"secrets\.([A-Z_][A-Z0-9_]*)", (ROOT / ".github" / "workflows" / "deploy.yml").read_text(encoding="utf-8")))
    used.discard("GITHUB_TOKEN")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    missing = sorted(s for s in used if f"`{s}`" not in readme)
    _record("criterion3_secrets", sorted(used))
    assert used and not missing, missing
