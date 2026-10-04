"""G9 판정 — 웹 패널 4개 vitest. 테스트 이름을 고정해 해당 패널 테스트가 실제로 돌고 통과했는지 본다."""
import json
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]
REPORT = ROOT / "goals" / "results" / "G9-vitest.json"
PANELS = ("starforce panel", "cube panel", "craft panel", "optimize panel")


def test_g9_four_panels_pass_and_total_at_least_20():
    subprocess.run(["npm", "--prefix", "web", "test", "--", "--reporter=json", f"--outputFile={REPORT}"],
                   cwd=ROOT, capture_output=True, shell=True)
    data = json.loads(REPORT.read_text(encoding="utf-8"))
    results = [a for f in data["testResults"] for a in f["assertionResults"]]
    passed = {r["fullName"] for r in results if r["status"] == "passed"}
    for panel in PANELS:
        assert any(panel in name for name in passed), f"{panel} 테스트가 없거나 실패"
    assert data["numPassedTests"] >= 20 and data["numFailedTests"] == 0
    (ROOT / "goals" / "results" / "G9.json").write_text(json.dumps(
        {"vitest_passed": data["numPassedTests"], "panels": list(PANELS)}, ensure_ascii=False, indent=1), encoding="utf-8")
