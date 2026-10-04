"""OpenAI Responses API 함수 호출 루프 (manual loop). 이벤트를 차례로 내보낸다: text, tool_call, tool_result, error, done.

- 모델 기본값 gpt-6-luna (환경변수 OPENAI_MODEL로 변경), reasoning effort medium
- store=False(상태 비저장): 매 턴 응답 output 항목(reasoning·function_call)을 그대로 다시 넣는다 — 공식 가이드의
  "reasoning items ... must also be passed back with tool call outputs"
- 실패는 반드시 error 이벤트로 알리고 done으로 끝난다(조용히 끊기지 않게)
"""
import json
import os
from collections.abc import Callable, Iterator

from agent.numbers import unverified_numbers
from agent.tools import ToolBox, openai_tools

DEFAULT_MODEL = "gpt-6-luna"  # 2026-10-04 사용자 결정 (실호출 스모크 통과, Sol 대비 비용 약 1/10)
SYSTEM = """당신은 메이플스토리(KMS) 장비 최적화 도우미다. 관리자 한 명이 쓴다.

숫자 규칙 — 가장 중요하다:
- 실딜 상승률·비용·확률·환산 같은 모든 수치는 도구 결과에 있는 값만 인용한다. 직접 계산하거나 추정하지 않는다.
- 필요한 수치가 도구 결과에 없으면 도구를 더 부르거나, 계산할 수 없다고 말한다.
- 잠재 줄을 더하거나(12%+9%+9%=30%) 차이를 빼는 것도 직접 계산이다. 잠재는 줄 그대로("INT +12% / +9% / +9%") 쓴다.
- 도구가 error를 돌려주면 그 이유를 설명하고, 입력을 고칠 수 있으면 고쳐서 다시 부른다.

도구 사용:
- 캐릭터 관련 질문은 닉네임이 필요하다. 없으면 먼저 물어본다.
- 매물은 사용자가 붙여넣은 툴팁을 total(총 옵션)과 potentials(잠재·에디 줄)로 나눠 넣고, 어떻게 해석했는지 먼저 짧게 보여 준다.
- 가격은 메소 정수로 넣는다(45억 3000만 → 4530000000).
- "뭘 사야 해", "경매장에서 뭘 검색해" 같은 질문에는 recommend_searches를 쓰고, 각 카드의 search 문자열을 게임 경매장 검색 조건으로 그대로 안내한다(부위·잠재·최소 스타포스). 사용자가 그 조건으로 검색한 화면을 연결하면 화면 매물을 평가한다.
- 질문에 "[경매장 화면에서 읽은 매물]" JSON이 붙어 있으면 그 매물을 evaluate_listings로 평가한 뒤, 억당 효율이 높은 순으로 살지 말지 판단한다. price가 null인 매물은 가격을 물어본다.
- 매물 평가·예산 최적화는 setting을 넣지 않는다(생략하면 보스 실딜 최적 세팅 기준). 사용자가 특정 세팅을 요청할 때만 넣는다.
- 사용자는 사냥 중일 때가 많다. 현재 적용 세팅(active_setting)이 사냥 세팅인 것은 정상이며, 사용자는 보스전에 보스 세팅으로 바꿔 낀다. "프리셋을 바꾸라"는 조언은 하지 않는다. 장비·매물 판단은 언제나 보스 세팅(evaluation_setting) 기준으로 한다. 세팅 자체를 물을 때만 rank_settings를 쓴다.

답변은 한국어로, 결론을 먼저, 근거 수치는 짧게.
- 수치 표기: 실딜 상승률은 소수 둘째 자리 %(예: +1.70%), 억당 효율은 "억당 +0.04%"처럼 셋째 자리, 메소는 "45억 3000만"처럼, 환산 주스탯은 정수. 도구 결과를 그대로 길게 붙이지 않는다."""


def _refusal(output) -> str | None:
    for item in output:
        if getattr(item, "type", None) == "message":
            for c in getattr(item, "content", None) or []:
                if getattr(c, "type", None) == "refusal":
                    return getattr(c, "refusal", "") or "요청이 거절됐어요."
    return None


def run_agent(client, toolbox: ToolBox, messages: list[dict], *, max_turns: int = 8,
              on_usage: Callable[[int], None] | None = None, model: str | None = None) -> Iterator[dict]:
    model = model or os.environ.get("OPENAI_MODEL") or DEFAULT_MODEL
    items: list = [{"role": m["role"], "content": m["content"]} for m in messages]
    seen: list = []
    try:
        for _ in range(max_turns):
            resp = client.responses.create(
                model=model, instructions=SYSTEM, tools=openai_tools(), input=items,
                reasoning={"effort": "medium"}, max_output_tokens=32000, store=False,
            )
            if on_usage and getattr(resp, "usage", None):
                on_usage(int(resp.usage.input_tokens) + int(resp.usage.output_tokens))
            refusal = _refusal(resp.output)
            if refusal:
                yield {"type": "error", "message": f"요청이 거절됐어요: {refusal}"}
                break
            if getattr(resp, "status", "completed") == "incomplete":
                yield {"type": "error", "message": "응답이 길이 한도에 걸려 중간에 잘렸어요."}
                break
            text = getattr(resp, "output_text", "") or ""
            if text:
                yield {"type": "text", "text": text}
            calls = [it for it in resp.output if getattr(it, "type", None) == "function_call"]
            if not calls:
                yield {"type": "done", "unverified_numbers": unverified_numbers(text, seen)}
                return
            items += resp.output
            for call in calls:
                try:
                    args = json.loads(call.arguments or "{}")
                except json.JSONDecodeError:
                    out = {"error": "도구 인자가 올바른 JSON이 아닙니다. 다시 시도해 주세요."}
                    args = {}
                else:
                    yield {"type": "tool_call", "name": call.name, "input": args}
                    out = toolbox.run(call.name, args)
                seen += [args, out]
                yield {"type": "tool_result", "name": call.name, "result": out}
                items.append({"type": "function_call_output", "call_id": call.call_id,
                              "output": json.dumps(out, ensure_ascii=False, default=str)})
        else:
            yield {"type": "error", "message": f"도구 호출이 {max_turns}번을 넘어 멈췄어요."}
    except Exception as e:  # noqa: BLE001 — 어떤 실패든 사용자에게 보인다
        yield {"type": "error", "message": f"에이전트 오류: {type(e).__name__}: {e}"}
    yield {"type": "done", "unverified_numbers": []}
