"""Claude tool use 루프 (manual loop). 이벤트를 차례로 내보낸다: text, tool_call, tool_result, error, done.

- 모델 claude-opus-5-5, effort medium, 거절 시 서버 측 fallback("default")
- assistant 응답은 response.content 그대로 이어 붙인다(append-only — thinking 블록 보존)
- 실패는 반드시 error 이벤트로 알리고 done으로 끝난다(조용히 끊기지 않게)
"""
import json
from collections.abc import Callable, Iterator

from agent.numbers import unverified_numbers
from agent.tools import TOOL_DEFS, ToolBox

MODEL = "claude-opus-5-5"
SYSTEM = """당신은 메이플스토리(KMS) 장비 최적화 도우미다. 관리자 한 명이 쓴다.

숫자 규칙 — 가장 중요하다:
- 전투력·실딜 상승률·비용·확률·환산 같은 모든 수치는 도구 결과에 있는 값만 인용한다. 직접 계산하거나 추정하지 않는다.
- 필요한 수치가 도구 결과에 없으면 도구를 더 부르거나, 계산할 수 없다고 말한다.
- 도구가 error를 돌려주면 그 이유를 설명하고, 입력을 고칠 수 있으면 고쳐서 다시 부른다.

도구 사용:
- 캐릭터 관련 질문은 닉네임이 필요하다. 없으면 먼저 물어본다.
- 매물은 사용자가 붙여넣은 툴팁을 total(총 옵션)과 potentials(잠재·에디 줄)로 나눠 넣고, 어떻게 해석했는지 먼저 짧게 보여 준다.
- 가격은 메소 정수로 넣는다(45억 3000만 → 4530000000).

답변은 한국어로, 결론을 먼저, 근거 수치는 짧게."""


def run_agent(client, toolbox: ToolBox, messages: list[dict], *, max_turns: int = 8,
              on_usage: Callable[[int], None] | None = None) -> Iterator[dict]:
    msgs = list(messages)
    seen: list = []
    try:
        for _ in range(max_turns):
            resp = client.beta.messages.create(
                model=MODEL, max_tokens=16000, system=SYSTEM, tools=TOOL_DEFS, messages=msgs,
                output_config={"effort": "medium"},
                betas=["server-side-fallback-2026-07-01"], fallbacks="default",
            )
            if on_usage and getattr(resp, "usage", None):
                on_usage(int(resp.usage.input_tokens) + int(resp.usage.output_tokens))
            if resp.stop_reason == "refusal":
                yield {"type": "error", "message": "요청이 안전 정책으로 거절됐어요. 질문을 바꿔 다시 시도해 주세요."}
                break
            texts = [b.text for b in resp.content if b.type == "text"]
            for t in texts:
                yield {"type": "text", "text": t}
            if resp.stop_reason in ("tool_use", "pause_turn"):
                msgs.append({"role": "assistant", "content": resp.content})
                if resp.stop_reason == "pause_turn":
                    continue
                results = []
                for b in (x for x in resp.content if x.type == "tool_use"):
                    yield {"type": "tool_call", "name": b.name, "input": b.input}
                    out = toolbox.run(b.name, b.input)
                    seen += [b.input, out]
                    yield {"type": "tool_result", "name": b.name, "result": out}
                    results.append({"type": "tool_result", "tool_use_id": b.id,
                                    "content": json.dumps(out, ensure_ascii=False, default=str),
                                    "is_error": "error" in out})
                msgs.append({"role": "user", "content": results})
                continue
            if resp.stop_reason == "max_tokens":
                yield {"type": "error", "message": "응답이 너무 길어 중간에 잘렸어요."}
                break
            yield {"type": "done", "unverified_numbers": unverified_numbers("\n".join(texts), seen)}
            return
        else:
            yield {"type": "error", "message": f"도구 호출이 {max_turns}번을 넘어 멈췄어요."}
    except Exception as e:  # noqa: BLE001 — 어떤 실패든 사용자에게 보인다
        yield {"type": "error", "message": f"에이전트 오류: {type(e).__name__}: {e}"}
    yield {"type": "done", "unverified_numbers": []}
