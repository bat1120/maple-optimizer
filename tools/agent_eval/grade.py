"""AI 상담 평가 채점: run_agent가 낸 이벤트 목록을 경우(case)의 기준으로 판정한다. 모델을 부르지 않는 순수 함수."""
import re

_MISSING = object()


def _dig(value, path: str):
    for part in path.split("."):
        if isinstance(value, dict) and part in value:
            value = value[part]
        elif isinstance(value, list) and part.isdigit() and int(part) < len(value):
            value = value[int(part)]
        else:
            return _MISSING
    return value


def summarize(events: list[dict]) -> dict:
    calls = [{"name": e["name"], "input": e.get("input", {})} for e in events if e["type"] == "tool_call"]
    done = [e for e in events if e["type"] == "done"]
    return {
        "calls": calls,
        "answer": "\n".join(e["text"] for e in events if e["type"] == "text"),
        "errors": [e["message"] for e in events if e["type"] == "error"],
        "tool_errors": [f"{e['name']}: {e['result']['error']}" for e in events
                        if e["type"] == "tool_result" and isinstance(e.get("result"), dict) and "error" in e["result"]],
        "unverified_numbers": done[-1].get("unverified_numbers", []) if done else [],
        "finished": bool(done),
    }


def grade(case: dict, events: list[dict]) -> list[dict]:
    """[{what, ok, detail}] — 하나라도 ok가 False면 그 경우는 실패."""
    run = summarize(events)
    called = [c["name"] for c in run["calls"]]
    checks = [
        {"what": "오류 없이 끝났다", "ok": run["finished"] and not run["errors"], "detail": "; ".join(run["errors"])},
        {"what": "답변이 있다", "ok": bool(run["answer"].strip()), "detail": ""},
    ]
    if not case.get("allow_unverified"):
        bad = run["unverified_numbers"]
        checks.append({"what": "답변 숫자가 전부 도구 결과·질문에 있다", "ok": not bad, "detail": ", ".join(bad)})

    for want in case.get("must_call", []):
        options = want if isinstance(want, list) else [want]
        checks.append({"what": f"도구를 불렀다: {' 또는 '.join(options)}", "ok": any(o in called for o in options),
                       "detail": f"부른 도구: {', '.join(called) or '없음'}"})
    for name in case.get("must_not_call", []):
        checks.append({"what": f"도구를 부르지 않았다: {name}", "ok": name not in called, "detail": ""})

    for rule in case.get("args", []):
        inputs = [c["input"] for c in run["calls"] if c["name"] == rule["tool"]]
        values = [_dig(i, rule["path"]) for i in inputs]
        if rule.get("absent"):
            ok = all(v is _MISSING or v is None for v in values)
            what = f"{rule['tool']}에 {rule['path']}를 넣지 않았다"
        elif "absent_or_equals" in rule:
            ok = all(v is _MISSING or v is None or v == rule["absent_or_equals"] for v in values)
            what = f"{rule['tool']}의 {rule['path']}는 없거나 {rule['absent_or_equals']}"
        else:
            ok = any(v is not _MISSING and v == rule["equals"] for v in values)
            what = f"{rule['tool']}의 {rule['path']} = {rule['equals']}"
        shown = ", ".join("없음" if v is _MISSING else repr(v) for v in values) or "호출 없음"
        checks.append({"what": what, "ok": ok, "detail": f"실제: {shown}"})

    for pattern in case.get("answer_matches", []):
        checks.append({"what": f"답변에 있다: /{pattern}/", "ok": bool(re.search(pattern, run["answer"])), "detail": ""})
    for pattern in case.get("answer_not_matches", []):
        found = re.search(pattern, run["answer"])
        checks.append({"what": f"답변에 없다: /{pattern}/", "ok": not found, "detail": found[0] if found else ""})
    return checks
