"""AI 상담 평가 실행(이 PC 전용): 평가 세트(cases.json)의 질문을 실제 모델에 보내고 규칙을 지켰는지 채점한다.

    uv run python tools/agent_eval/run.py [--only what-first,starforce-cost] [--label 기준선] [--if-changed]

- .env의 OPENAI_API_KEY를 쓰고 비용이 든다(값은 출력하지 않는다). CI·클라우드에서는 돌리지 않는다.
- 캐릭터는 픽스처(넥슨 API 없음), 관측 시세는 비어 있고, 추적(Langfuse)·웹 경매장 검색은 끈다 — 공개 사용자와 같은 조건.
- 모델 답변은 돌릴 때마다 조금씩 다르다. 실패한 경우는 두 번 더 돌려 3번 중 2번 통과해야 통과로 본다(섞인 실패는 결과 페이지에 남는다).
- --if-changed: AI 상담에 닿는 파일(agent/·서버 계산·평가 세트)이 마지막 통과 뒤로 바뀌지 않았으면 모델을 부르지 않고 0으로 끝난다.
  게이트(scripts/validate.ps1)가 이렇게 부른다. 키가 없으면 2(건너뜀).
- 결과: tools/agent_eval/out/<커밋>-<시각>[-라벨]/report.html(사람용)·result.json. 종료 코드: 모두 통과 0, 아니면 1.
"""
import argparse
import datetime as dt
import hashlib
import html
import json
import os
import pathlib
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests"), str(HERE)]

from grade import grade, summarize  # noqa: E402
from helpers import bundle, classes  # noqa: E402

from agent.loop import DEFAULT_MODEL, run_agent  # noqa: E402
from agent.tools import ToolBox  # noqa: E402
from agent.tracing import NoopTracer  # noqa: E402
from nexon.client import CharacterNotFound  # noqa: E402
from nexon.convert import snapshot  # noqa: E402
from server.app import _env  # noqa: E402

PUBLIC_MAX_TURNS, PUBLIC_REQUEST_TOKENS = 6, 60_000
LAST_PASS = HERE / "out" / "last_pass.json"
WATCHED = ("agent", "engine", "server/service.py", "server/schemas.py", "tools/agent_eval/cases.json", "tools/agent_eval/grade.py")


def fingerprint() -> str:
    """AI 상담의 답을 바꿀 수 있는 파일 내용의 해시(줄바꿈 차이는 무시)."""
    digest = hashlib.sha256()
    for rel in WATCHED:
        target = ROOT / rel
        files = sorted(p for p in target.rglob("*") if p.suffix in (".py", ".json")) if target.is_dir() else [target]
        for path in files:
            digest.update(path.relative_to(ROOT).as_posix().encode())
            digest.update(path.read_bytes().replace(b"\r\n", b"\n"))
    return digest.hexdigest()


def _load(name, _date=None):
    if name not in classes():
        raise CharacterNotFound("OPENAPI00004", f"캐릭터를 찾을 수 없습니다: {name}", 400)
    return snapshot(bundle(name))


def _attempt(client, model: str, case: dict, character: str) -> dict:
    question = case["question"].replace("{character}", character)
    tokens = []
    events = list(run_agent(client, ToolBox(_load, market=lambda: []), [{"role": "user", "content": question}],
                            max_turns=PUBLIC_MAX_TURNS, max_tokens=PUBLIC_REQUEST_TOKENS, model=model,
                            exclude_tools=("refresh_market",), tracer=NoopTracer(), on_usage=tokens.append))
    checks = grade(case, events)
    return {"id": case["id"], "why": case["why"], "question": question, "ok": all(c["ok"] for c in checks),
            "checks": checks, "tokens": sum(tokens), **summarize(events)}


def run_case(client, model: str, case: dict, character: str, attempt=_attempt) -> dict:
    """모델 답은 매번 다르다: 한 번 실패하면 두 번 더 돌려 3번 중 2번 통과해야 통과로 본다.
    실패가 섞인 경우는 flaky로 표시해 결과 페이지에 보인다 — 숨기지 않는다."""
    tries = [attempt(client, model, case, character)]
    if not tries[0]["ok"]:
        tries += [attempt(client, model, case, character) for _ in range(2)]
    passed = [t for t in tries if t["ok"]]
    ok = len(passed) * 2 > len(tries)
    shown = passed[-1] if ok else next(t for t in tries if not t["ok"])
    return shown | {"ok": ok, "tokens": sum(t["tokens"] for t in tries), "attempts": [t["ok"] for t in tries],
                    "flaky": 0 < len(passed) < len(tries),
                    "failed_checks": sorted({c["what"] + (f" ({c['detail']})" if c["detail"] else "")
                                             for t in tries for c in t["checks"] if not c["ok"]})}


def report(result: dict) -> str:
    def esc(s):
        return html.escape(str(s))

    failed = [c for c in result["cases"] if not c["ok"]]
    cards = []
    for c in result["cases"]:
        checks = "".join(f'<li class="{"ok" if k["ok"] else "no"}">{esc(k["what"])}'
                         f'{" — " + esc(k["detail"]) if k["detail"] and not k["ok"] else ""}</li>' for k in c["checks"])
        calls = "".join(f"<li><code>{esc(x['name'])}</code> {esc(json.dumps(x['input'], ensure_ascii=False))}</li>" for x in c["calls"])
        cards.append(f'''<section class="card {"pass" if c["ok"] else "fail"}" id="{esc(c["id"])}">
<h2><span class="badge">{"통과" if c["ok"] else "실패"}</span> {esc(c["id"])}{f' <small>· {len(c["attempts"])}번 중 {sum(c["attempts"])}번 통과</small>' if len(c["attempts"]) > 1 else ""}</h2>
{"".join(f'<p class="flaky">다른 시도에서 실패: {esc(x)}</p>' for x in c["failed_checks"]) if c["flaky"] and c["ok"] else ""}
<p class="why">{esc(c["why"])}</p><p class="q">{esc(c["question"])}</p><ul class="checks">{checks}</ul>
<details><summary>부른 도구 {len(c["calls"])}개 · 답변 · {c["tokens"]:,} 토큰</summary><ol>{calls}</ol><pre>{esc(c["answer"])}</pre></details></section>''')
    verdict = f"실패 {len(failed)}개 / 전체 {len(result['cases'])}개" if failed else f"전체 {len(result['cases'])}개 통과"
    return f'''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI 상담 평가 {esc(result["commit"])}</title><style>
:root{{--bg:#f4f5f7;--card:#fff;--ink:#1c2330;--muted:#5d6878;--line:#dfe3ea;--ok:#12733f;--okbg:#e3f5ea;--no:#b3261e;--nobg:#fde8e6}}
@media (prefers-color-scheme:dark){{:root{{--bg:#12151b;--card:#1b2029;--ink:#e8ecf2;--muted:#9aa5b5;--line:#2d3440;--ok:#6fd49b;--okbg:#153324;--no:#ff9a92;--nobg:#3c1b19}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 system-ui,"Malgun Gothic",sans-serif}}
main{{max-width:920px;margin:0 auto;padding:24px 16px 64px}}h1{{font-size:22px;margin:0 0 4px}}.meta{{color:var(--muted);margin:0 0 16px}}
.verdict{{display:inline-block;padding:6px 14px;border-radius:999px;font-weight:700;margin-bottom:16px}}
.verdict.pass,.pass .badge{{background:var(--okbg);color:var(--ok)}}.verdict.fail,.fail .badge{{background:var(--nobg);color:var(--no)}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;margin-bottom:14px}}.card.fail{{border-color:var(--no)}}
h2{{font-size:16px;margin:0 0 4px}}.badge{{font-size:12px;padding:2px 8px;border-radius:999px;margin-right:6px}}
.why{{color:var(--muted);margin:0 0 6px}}.q{{margin:0 0 8px;padding:8px 10px;background:var(--bg);border-radius:8px}}
ul.checks{{margin:0 0 8px;padding-left:22px}}li.ok::marker{{content:"✓  ";color:var(--ok)}}li.no{{color:var(--no);font-weight:600}}li.no::marker{{content:"✗  "}}
.flaky{{color:var(--no);margin:2px 0;font-size:13px}}small{{color:var(--muted);font-weight:400}}summary{{cursor:pointer;color:var(--muted);font-size:13px}}pre{{white-space:pre-wrap;word-break:break-word;background:var(--bg);padding:10px;border-radius:8px;font:13px/1.5 inherit}}
ol{{font-size:13px;word-break:break-all}}code{{font-family:ui-monospace,Consolas,monospace}}
</style><main><h1>AI 상담 평가 — {esc(result["commit"])}{" · " + esc(result["label"]) if result["label"] else ""}</h1>
<p class="meta">{esc(result["time"])} · 모델 {esc(result["model"])} · 픽스처 캐릭터 「{esc(result["character"])}」 · 합계 {result["tokens"]:,} 토큰</p>
<div class="verdict {"fail" if failed else "pass"}">{verdict}</div>{"".join(cards)}</main></html>'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", default="")
    parser.add_argument("--label", default="")
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--if-changed", action="store_true")
    args = parser.parse_args()

    mark = fingerprint()
    if args.if_changed and LAST_PASS.exists() and json.loads(LAST_PASS.read_text(encoding="utf-8")).get("fingerprint") == mark:
        print("AI 상담 평가: 마지막 통과 뒤로 바뀐 것이 없어 건너뜀")
        return 0

    key = _env("OPENAI_API_KEY")
    if not key:
        print("OPENAI_API_KEY가 없어요(.env) — 이 평가는 실제 모델을 부른다.")
        return 2
    import openai
    client = openai.OpenAI(api_key=key)
    model = _env("OPENAI_MODEL") or DEFAULT_MODEL
    for name in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "DATABASE_URL"):
        os.environ.pop(name, None)

    spec = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))
    cases = [c for c in spec["cases"] if not args.only or c["id"] in args.only.split(",")]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        done = list(pool.map(lambda c: run_case(client, model, c, spec["character"]), cases))

    dirty = "-dirty" if subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout.strip() else ""
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip() + dirty
    now = dt.datetime.now()
    result = {"commit": commit, "label": args.label, "time": now.isoformat(timespec="seconds"), "model": model,
              "character": spec["character"], "tokens": sum(c["tokens"] for c in done),
              "ok": bool(done) and all(c["ok"] for c in done), "cases": done}
    out = HERE / "out" / "-".join(x for x in (commit, now.strftime("%Y%m%d-%H%M%S"), args.label) if x)
    out.mkdir(parents=True, exist_ok=True)
    (out / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "report.html").write_text(report(result), encoding="utf-8")
    if result["ok"] and not args.only:  # 일부만 돌린 통과는 '전체 통과'로 기록하지 않는다
        LAST_PASS.write_text(json.dumps({"fingerprint": mark, "commit": commit, "time": result["time"],
                                         "report": str(out / "report.html")}, ensure_ascii=False), encoding="utf-8")
    for c in done:
        tried = f" ({len(c['attempts'])}번 중 {sum(c['attempts'])}번 통과)" if len(c["attempts"]) > 1 else ""
        print(f"{'통과' if c['ok'] else '실패'} {c['id']}{tried}{' — ' + '; '.join(c['failed_checks']) if c['failed_checks'] else ''}")
    print(f"{'평가 통과' if result['ok'] else '평가 실패'} · {result['tokens']:,} 토큰 · {out / 'report.html'}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
