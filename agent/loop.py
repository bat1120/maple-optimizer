"""OpenAI Responses API 함수 호출 루프 (manual loop). 이벤트를 차례로 내보낸다: text, tool_call, tool_result, error, done.

- 모델 기본값 gpt-6-luna (환경변수 OPENAI_MODEL로 변경), reasoning effort medium
- store=False(상태 비저장): 매 턴 응답 output 항목(reasoning·function_call)을 그대로 다시 넣는다 — 공식 가이드의
  "reasoning items ... must also be passed back with tool call outputs"
- 실패는 반드시 error 이벤트로 알리고 done으로 끝난다(조용히 끊기지 않게)
"""
import json
import logging
import os
import re
from collections.abc import Callable, Iterator

from agent.numbers import unverified_numbers
from agent.tools import ToolBox, openai_tools
from agent.tracing import NoopTracer, safe

_log = logging.getLogger("uvicorn.error")
DEFAULT_MODEL = "gpt-6-luna"  # 2026-10-04 사용자 결정 (실호출 스모크 통과, Sol 대비 비용 약 1/10)
# 2026-11-23 사용자 지시로 처음부터 다시 썼다: 프롬프트는 금지 목록이 아니라 답의 방향만 정한다.
# 도구를 언제 쓰는지는 도구 설명(agent/tools.py)에, 결과를 읽는 법은 도구 결과의 note·reason에,
# 입력·숫자 규칙은 코드(도구 가드, invented_argument, 숫자 출처 재작성 턴)에 있다. 여기에 규칙을 다시 쌓지 않는다.
SYSTEM = """메이플스토리(KMS) 장비 최적화 사이트의 상담 도우미다. 사용자가 자기 템을 객관적으로 진단하고, 가진 재화에 맞춰 스펙을 어디까지 올리는 게 적당한지 판단하도록 돕는다.

- 근거는 도구다. 답에 쓰는 수치·옵션 문장·아이템 이름·가격은 도구 결과와 사용자가 준 값을 그대로 옮긴다(금액은 *_text 표기). 결과에 딸린 note·reason은 그 값을 읽는 법이니 함께 전한다.
- 필요한 값이 없으면 "측정값 없음"이라고 말하고, 무엇을 하면 측정되는지 알려 준다.
- 먼저 추천한다. 캐릭터가 정해져 있으면 도구로 지금 상태를 읽고 바로 답한다. 기준은 억당 실딜 효율이고, 다음 한 단계씩 권한다.
- 예산을 알면 그 안에서 어디까지 오르는지 보여 준다. 예산을 모르면 효율 순서로 답하고, 쓸 수 있는 메소를 알려 주면 거기에 맞춰 끊어 주겠다고 덧붙인다.
- 흐름은 추천 → 그 조건으로 경매장 검색 → 화면 공유로 읽은 매물을 실제 실딜로 평가다. 지금 사용자가 어느 단계인지 보고 다음 단계로 이끈다.
- 장비 이야기는 보스 세팅 기준이다. 도구가 보스 실딜 최적 세팅으로 계산하며, 지금 낀 세팅이 사냥용인 것은 흔한 일이다.
- 한국어로, 결론 먼저, 근거 수치는 짧게(여러 항목은 표, %는 소수 둘째 자리까지)."""

_LOOKED_UP = re.compile(r"\[조회한 캐릭터: ([^\]\n]+)\]")


def context(messages: list[dict]) -> str:
    """질문마다 달라지는 사실은 프롬프트가 아니라 여기서 만든다: 화면이 붙여 보낸 조회 캐릭터."""
    names = [m for msg in messages if msg.get("role") == "user" and isinstance(msg.get("content"), str)
             for m in _LOOKED_UP.findall(msg["content"])]
    if names:
        return f"조회한 캐릭터: {names[-1].strip()} — 캐릭터 도구의 name에 이 이름을 쓴다."
    return "조회한 캐릭터: 없음 — 캐릭터 도구는 닉네임이 필요하다. 사용자가 닉네임을 말하지 않았으면 먼저 닉네임을 받는다."


CHARS_PER_TOKEN = 2  # 도구 결과(한글 섞인 JSON)의 다음 턴 입력 토큰 어림 — 마무리 턴을 정하는 데만 쓴다
USER_ONLY_ARGS = ("cooldown_main_pct",)  # 사용자가 정하는 값 — 모델이 대신 정해 넣지 못하게 코드로 막는다


def invented_argument(args: dict, user_texts: list[str]) -> dict | None:
    """사용자만 정할 수 있는 인자(닉네임, 쿨감 환산값)에 사용자가 말한 적 없는 값이 들어 있으면 도구를 돌리지 않고 오류를 돌려준다."""
    said = {float(n) for text in user_texts for n in re.findall(r"\d+(?:\.\d+)?", text)}
    for key in USER_ONLY_ARGS:
        value = args.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool) and float(value) not in said:
            return {"error": f"{key}={value}는 사용자가 말한 값이 아니다. 이 값은 사용자가 정한다 — 이 인자를 빼고 다시 부르고, "
                             "필요하면 사용자에게 값을 물어본다."}
    name = args.get("name")
    squeeze = lambda t: re.sub(r"\s+", "", t).casefold()  # noqa: E731
    # 매물 이름이 아니라 캐릭터 닉네임일 때만: 캐릭터 도구는 최상위 name, 매물 이름은 listings[].name
    if isinstance(name, str) and name.strip() and not any(squeeze(name) in squeeze(t) for t in user_texts):
        return {"error": f"'{name}'은 사용자가 말한 닉네임이 아니다. 사용자에게 닉네임을 물어본다."}
    return None


def rewrite_request(bad: list[str]) -> str:
    """출처 없는 숫자가 든 답을 사용자에게 보내기 전에 모델에게 한 번 되돌려 보낸다(프롬프트의 '직접 계산 금지'를 대신한다)."""
    return ("방금 답의 다음 숫자는 도구 결과와 사용자 입력에서 찾을 수 없다: " + ", ".join(bad)
            + ". 도구 결과에 있는 값(금액은 *_text)으로 바꾸고, 결과에 없는 값은 빼거나 측정값 없음이라고 써서 답 전체를 다시 쓴다.")


def _refusal(output) -> str | None:
    for item in output:
        if getattr(item, "type", None) == "message":
            for c in getattr(item, "content", None) or []:
                if getattr(c, "type", None) == "refusal":
                    return getattr(c, "refusal", "") or "요청이 거절됐어요."
    return None


def _brief(items: list, cap: int = 4000) -> list:
    """추적에 보낼 입력 요약: 메시지·도구 결과 문자열은 cap 글자까지, SDK 객체는 종류·이름만."""
    out = []
    for it in items:
        if isinstance(it, dict):
            out.append({k: (v[:cap] if isinstance(v, str) else v) for k, v in it.items()})
        else:
            out.append({"type": getattr(it, "type", type(it).__name__), "name": getattr(it, "name", None)})
    return out


def run_agent(client, toolbox: ToolBox, messages: list[dict], *, max_turns: int = 8,
              on_usage: Callable[[int], None] | None = None, model: str | None = None,
              exclude_tools: tuple = (), tracer=None, trace_user: str | None = None,
              trace_meta: dict | None = None, max_tokens: int | None = None,
              public_errors: bool = False) -> Iterator[dict]:
    """tracer: agent/tracing.py(Langfuse 또는 Noop). 추적이 실패해도 답변 흐름은 그대로다."""
    tracer = tracer or NoopTracer()
    question = messages[-1].get("content") if messages else None
    answer = []
    with safe(lambda: tracer.conversation(user_id=trace_user, metadata=trace_meta, input=question)) as root:
        for ev in _run(client, toolbox, messages, max_turns, on_usage, model, exclude_tools, tracer, max_tokens,
                       public_errors):
            if ev["type"] == "text":
                answer.append(ev["text"])
            elif ev["type"] == "error":
                root.update(level="ERROR", status_message=ev["message"])
            yield ev
        root.update(output="\n".join(answer))


def _run(client, toolbox, messages, max_turns, on_usage, model, exclude_tools, tracer, max_tokens=None,
         public_errors=False) -> Iterator[dict]:
    model = model or os.environ.get("OPENAI_MODEL") or DEFAULT_MODEL
    items: list = [{"role": m["role"], "content": m["content"]} for m in messages]
    # 출처: 도구 입력·결과 + 사용자가 쓴 글(예산 "200억", 첨부 매물의 잠재 수치를 되풀이하는 건 지어낸 숫자가 아니다)
    seen: list = [m["content"] for m in messages if m.get("role") == "user" and isinstance(m.get("content"), str)]
    user_texts = list(seen)
    spent = 0
    # 요청당 한도가 한 턴 분량밖에 안 남으면 도구를 더 부르지 못하게 하고 지금까지의 결과로 답하게 한다.
    # 2026-11-22 평가: 도구를 5개 부른 질문이 한도를 넘어, 6만 토큰을 쓰고도 답 없이 오류만 나갔다
    wrap_up = False
    rewritten = False
    instructions = SYSTEM + "\n\n" + context(messages)
    try:
        for turn in range(max_turns):
            with safe(lambda: tracer.observe("model", as_type="generation", model=model, input=_brief(items))) as gen:  # noqa: B023
                resp = client.responses.create(
                    model=model, instructions=instructions, tools=openai_tools(exclude_tools), input=items,
                    reasoning={"effort": "medium"}, max_output_tokens=32000, store=False,
                    **({"tool_choice": "none"} if wrap_up else {}),
                )
                usage = getattr(resp, "usage", None)
                gen.update(output=getattr(resp, "output_text", "") or [getattr(it, "name", None) for it in resp.output
                                                                       if getattr(it, "type", None) == "function_call"],
                           usage_details={"input": int(usage.input_tokens), "output": int(usage.output_tokens)} if usage else None)
            if on_usage and getattr(resp, "usage", None):
                on_usage(int(resp.usage.input_tokens) + int(resp.usage.output_tokens))
            if getattr(resp, "usage", None):
                spent += int(resp.usage.input_tokens) + int(resp.usage.output_tokens)
            text = getattr(resp, "output_text", "") or ""
            # 질문 한 번이 하루 한도를 다 쓰지 못하게(공개 사용자, 2026-10-17). 마무리 턴에서 나온 답은 조금 넘어도 보여 준다
            if max_tokens and spent > max_tokens and not (wrap_up and text):
                yield {"type": "error", "message": "질문 한 번에 쓸 수 있는 AI 양을 넘었어요. 질문을 더 짧게 나눠 물어봐 주세요."}
                break
            refusal = _refusal(resp.output)
            if refusal:
                yield {"type": "error", "message": f"요청이 거절됐어요: {refusal}"}
                break
            if getattr(resp, "status", "completed") == "incomplete":
                yield {"type": "error", "message": "응답이 길이 한도에 걸려 중간에 잘렸어요."}
                break
            calls = [it for it in resp.output if getattr(it, "type", None) == "function_call"]
            final = not calls or (wrap_up and text)
            bad = unverified_numbers(text, seen) if final else []
            # 출처 없는 숫자가 있으면 보여 주기 전에 한 번 다시 쓰게 한다 — 한 턴 더 돌 여유(턴 수·토큰)가 있을 때만
            if bad and not rewritten and not wrap_up and turn + 1 < max_turns and getattr(resp, "usage", None) and (
                    not max_tokens or spent + int(resp.usage.input_tokens) + int(resp.usage.output_tokens) <= max_tokens):
                rewritten = wrap_up = True
                items += resp.output
                items.append({"role": "developer", "content": rewrite_request(bad)})
                continue
            if text:
                yield {"type": "text", "text": text}
            if final:
                yield {"type": "done", "unverified_numbers": bad}
                return
            items += resp.output
            added = 0
            for call in calls:
                try:
                    args = json.loads(call.arguments or "{}")
                except json.JSONDecodeError:
                    out = {"error": "도구 인자가 올바른 JSON이 아닙니다. 다시 시도해 주세요."}
                    args = {}
                else:
                    yield {"type": "tool_call", "name": call.name, "input": args}
                    with safe(lambda: tracer.observe(call.name, as_type="tool", input=args)) as t:  # noqa: B023
                        out = invented_argument(args, user_texts) or toolbox.run(call.name, args)
                        failed = isinstance(out, dict) and "error" in out
                        t.update(output=out, **({"level": "ERROR", "status_message": str(out["error"])} if failed else {}))
                seen += [args, out]
                yield {"type": "tool_result", "name": call.name, "result": out}
                payload = json.dumps(out, ensure_ascii=False, default=str)
                added += len(payload) // CHARS_PER_TOKEN
                items.append({"type": "function_call_output", "call_id": call.call_id, "output": payload})
            if max_tokens and getattr(resp, "usage", None):
                next_turn = int(resp.usage.input_tokens) + int(resp.usage.output_tokens) + added
                wrap_up = spent + 2 * next_turn > max_tokens  # 두 턴은 못 돈다 → 다음 턴이 마지막
        else:
            yield {"type": "error", "message": f"도구 호출이 {max_turns}번을 넘어 멈췄어요."}
    except Exception as e:  # noqa: BLE001 — 어떤 실패든 사용자에게 보인다
        _log.warning("에이전트 오류: %s: %s", type(e).__name__, e)
        # 공개 사용자에게는 내부 오류 문구(경로·라이브러리 메시지)를 보이지 않는다(2026-10-17) — 자세한 내용은 서버 로그에만
        msg = "AI 상담 중 오류가 났어요. 잠시 뒤 다시 시도해 주세요." if public_errors else f"에이전트 오류: {type(e).__name__}: {e}"
        yield {"type": "error", "message": msg}
    yield {"type": "done", "unverified_numbers": []}
