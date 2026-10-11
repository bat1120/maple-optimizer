"""디자인 심사 종합(2026-10-11): 판사 JSON + 기계 판정 → report.md, 통과 여부(종료 코드).

    python tools/design_review/aggregate.py tools/design_review/out/<회차>

통과: (1) 기계 판정 실패 0 (가로 스크롤·넘침·두 줄 버튼·글자 대비, 휴대폰 작은 터치 영역)
      (2) 판사 3명 중 2명 이상이 모든 항목 4점 이상
      (3) 캡처가 지금 커밋 것(이름의 커밋 = git HEAD) — 낡은 사진으로 통과하지 않는다
기준은 회차 중간에 낮추지 않는다.
"""
import json
import pathlib
import subprocess
import sys
from collections import defaultdict

AXES = ["polish", "hierarchy", "consistency", "maple_fit", "readability", "task_flow", "mobile", "dark"]
PASS_SCORE, PASS_JUDGES = 4, 2
SEV = {"must": 0, "should": 1, "nice": 2}


def machine_failures(manifest: dict) -> list[str]:
    out = []
    for s in manifest["shots"]:
        c, tag = s.get("checks") or {}, f"{s['screen']}·{s['device']}·{s['theme']}"
        if not s.get("ready"):
            out.append(f"{tag}: 화면이 다 그려지지 않음(시간 초과)")
            continue
        if c.get("hscroll"):
            out.append(f"{tag}: 가로 스크롤")
        out += [f"{tag}: 화면 밖 넘침 {x}" for x in c.get("overflow", [])]
        out += [f"{tag}: 두 줄로 꺾인 버튼 '{x}'" for x in c.get("two_line_click", [])]
        out += [f"{tag}: 글자 대비 {x['ratio']} '{x['text']}'" for x in c.get("low_contrast", [])]
        if s["device"] == "mobile":
            out += [f"{tag}: 터치 영역 32px 미만 '{x}'" for x in c.get("small_targets", [])]
    return sorted(set(out))


def main(run_dir: str) -> int:
    d = pathlib.Path(run_dir)
    manifest = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    fresh = manifest["commit"].split("-")[0] == head
    judges = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(d.glob("judge_*.json"))]
    mf = machine_failures(manifest)
    ok_judges = [j["judge"] for j in judges if all(j["scores"].get(a, {}).get("score", 0) >= PASS_SCORE for a in AXES)]
    passed = fresh and not mf and len(judges) >= 3 and len(ok_judges) >= PASS_JUDGES

    lines = [f"# 디자인 심사 — {manifest['commit']} ({manifest['time']})", "",
             f"**판정: {'통과' if passed else '불통과'}** · 캡처 최신 {'예' if fresh else f'아니오(HEAD {head})'} · "
             f"기계 판정 실패 {len(mf)}건 · 4점 이상 전 항목 판사 {len(ok_judges)}/{len(judges)}", "",
             "## 점수", "", "| 항목 | " + " | ".join(j["judge"] for j in judges) + " | 평균 |", "|---|" + "---|" * (len(judges) + 1)]
    for a in AXES:
        sc = [j["scores"].get(a, {}).get("score", 0) for j in judges]
        lines.append(f"| {a} | " + " | ".join(str(x) for x in sc) + f" | {sum(sc) / max(1, len(sc)):.1f} |")
    lines += ["", "## 기계 판정 실패", ""] + ([f"- {x}" for x in mf] or ["- 없음"])
    # 지적 합치기: 같은 화면·요소를 여러 판사가 짚으면 위로
    merged = defaultdict(list)
    for j in judges:
        for it in j.get("issues", []):
            merged[(it.get("screen"), it.get("where", "")[:30])].append({**it, "judge": j["judge"]})
    ranked = sorted(merged.values(), key=lambda g: (min(SEV.get(x.get("severity"), 3) for x in g), -len(g)))
    lines += ["", "## 고칠 점 (중요도 · 짚은 판사 수 순)", ""]
    for i, g in enumerate(ranked, 1):
        x = g[0]
        who = ", ".join(sorted({y["judge"] for y in g}))
        lines.append(f"{i}. **[{x.get('severity')}] {x.get('screen')}·{x.get('device')}·{x.get('theme')} — {x.get('where')}** ({who})")
        lines.append(f"   - 문제: {x.get('problem')}")
        for y in g:
            lines.append(f"   - 고침({y['judge']}): {y.get('fix')}")
    lines += ["", "## 판사 총평", ""] + [f"- **{j['judge']}**: {j.get('verdict')} / 잘된 점: {j.get('best')}" for j in judges]
    (d / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:4]))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
