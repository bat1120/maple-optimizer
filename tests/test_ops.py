"""운영 보강(2026-10-17 점검): 되돌릴 수 있는 배포, 바깥 감시, DB 백업."""
import pathlib
import shutil
import subprocess

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
WF = ROOT / ".github" / "workflows"


def _load(name):
    return yaml.safe_load((WF / name).read_text(encoding="utf-8"))


def test_image_is_tagged_by_commit_and_deploy_rolls_back_when_unhealthy():
    wf = _load("deploy.yml")
    tags = next(s for s in wf["jobs"]["image"]["steps"] if "build-push-action" in str(s.get("uses")))["with"]["tags"]
    assert "github.sha" in tags and ":latest" in tags
    script = next(s for s in wf["jobs"]["deploy"]["steps"] if "ssh-action" in str(s.get("uses")))["with"]["script"]
    assert "healthy" in script and ".deployed-image" in script and "PREV" in script  # 새 이미지가 안 뜨면 이전 이미지로
    assert "image prune -f" not in script  # 이전 이미지를 지우면 되돌릴 수 없다


def test_uptime_workflow_checks_health_on_schedule():
    wf = _load("uptime.yml")
    on = wf.get("on") or wf.get(True)  # yaml에서 on: 은 True 키가 된다
    assert on["schedule"][0]["cron"]
    assert "/api/health" in str(wf["jobs"])


def _bash():
    """문법 검사용 bash. Windows에서는 Git bash를 먼저 쓴다 — PATH의 bash가 WSL 실행기(System32)면 경로를 못 연다."""
    git_bash = pathlib.Path(r"C:/Program Files/Git/bin/bash.exe")
    if git_bash.exists():
        return str(git_bash)
    b = shutil.which("bash")
    return b if b and "system32" not in b.lower() else None


@pytest.mark.skipif(not _bash(), reason="쓸 수 있는 bash 없음")
def test_backup_script_is_valid_and_keeps_two_weeks():
    p = ROOT / "deploy" / "backup.sh"
    body = p.read_text(encoding="utf-8")
    assert "pg_dump" in body and "-mtime +14" in body and "\r" not in body
    assert subprocess.run([_bash(), "-n", "deploy/backup.sh"], cwd=ROOT).returncode == 0
