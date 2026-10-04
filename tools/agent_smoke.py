"""에이전트 실호출 스모크 (H5): 실제 OpenAI + 실제 넥슨 데이터로 질문 하나를 끝까지 돌린다.

사용: uv run python tools/agent_smoke.py "내신부레테 보스 세팅 추천해줘"
판정: 도구 호출 ≥ 1, error 이벤트 0, 검증 안 된 숫자 0 → 종료코드 0. 키 값은 출력하지 않는다.
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import openai  # noqa: E402

from agent.loop import run_agent  # noqa: E402
from agent.tools import ToolBox  # noqa: E402
from nexon.client import NexonClient, load_api_key  # noqa: E402
from nexon.convert import snapshot  # noqa: E402
from server.app import _env  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent


def main() -> int:
    question = sys.argv[1] if len(sys.argv) > 1 else "내신부레테 보스 세팅 순위 알려줘"
    nexon = NexonClient(load_api_key(ROOT))
    cache: dict = {}

    def load(name, date=None):
        if name not in cache:
            cache[name] = snapshot(nexon.fetch_bundle(name))
        return cache[name]

    client = openai.OpenAI(api_key=_env("OPENAI_API_KEY"))
    used = {"tokens": 0}
    tools = errors = 0
    unverified: list = []
    for ev in run_agent(client, ToolBox(load), [{"role": "user", "content": question}],
                        on_usage=lambda n: used.__setitem__("tokens", used["tokens"] + n),
                        model=_env("OPENAI_MODEL")):
        if ev["type"] == "tool_call":
            tools += 1
            print(f"[도구] {ev['name']} {json.dumps(ev['input'], ensure_ascii=False)[:160]}")
        elif ev["type"] == "tool_result":
            err = ev["result"].get("error") if isinstance(ev["result"], dict) else None
            print(f"[결과] {ev['name']}: {'오류 ' + err if err else '정상'}")
        elif ev["type"] == "text":
            print("[답변]\n" + ev["text"])
        elif ev["type"] == "error":
            errors += 1
            print("[오류]", ev["message"])
        elif ev["type"] == "done":
            unverified = ev["unverified_numbers"]
    print(f"\n도구 호출 {tools}회 · 오류 {errors} · 검증 안 된 숫자 {unverified or '없음'} · 토큰 {used['tokens']:,}")
    return 0 if (tools >= 1 and errors == 0 and not unverified) else 1


if __name__ == "__main__":
    raise SystemExit(main())
