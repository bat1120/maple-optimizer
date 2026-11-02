"""OpenAI Responses API 함수 호출 루프 (manual loop). 이벤트를 차례로 내보낸다: text, tool_call, tool_result, error, done.

- 모델 기본값 gpt-6-luna (환경변수 OPENAI_MODEL로 변경), reasoning effort medium
- store=False(상태 비저장): 매 턴 응답 output 항목(reasoning·function_call)을 그대로 다시 넣는다 — 공식 가이드의
  "reasoning items ... must also be passed back with tool call outputs"
- 실패는 반드시 error 이벤트로 알리고 done으로 끝난다(조용히 끊기지 않게)
"""
import json
import logging
import os
from collections.abc import Callable, Iterator

from agent.numbers import unverified_numbers
from agent.tools import ToolBox, openai_tools
from agent.tracing import NoopTracer, safe

_log = logging.getLogger("uvicorn.error")
DEFAULT_MODEL = "gpt-6-luna"  # 2026-10-04 사용자 결정 (실호출 스모크 통과, Sol 대비 비용 약 1/10)
SYSTEM = """당신은 메이플스토리(KMS) 장비 최적화 도우미다. 사이트 사용자 누구나 쓴다(2026-10-17 공개, 일반 사용자는 하루 질문 수 제한).

실측값 원칙 — 어떤 규칙보다 먼저다:
- 답변에 쓰는 사실(수치·옵션 문장·아이템 이름·시세·확률·게임 규칙)은 실제로 측정·관측된 것만 쓴다:
  도구 결과, 화면에서 읽은 매물, 사용자가 직접 말한 값. 기억이나 일반 지식으로 채우지 않는다.
- 옵션 문장·아이템 이름·가격은 도구 결과의 문자열을 글자 그대로 옮긴다. 줄이거나 다듬거나 바꿔 쓰지 않는다.
- 필요한 값이 없으면 "측정값 없음"이라고 쓰고, 무엇을 하면 측정되는지(어떤 도구, 어떤 화면을 연결)를 안내한다.
  비슷한 값으로 대신하거나 "보통 ~정도"라고 짐작하지 않는다.
- 측정값이 아닌 계산값은 성격을 밝힌다: cube_cost는 평균 기대값, reach_probability는 근사, market은 관측 매물 count건 기준.
- 도구 결과에 unverified_lines(공식 옵션표에 없는 줄)나 held가 있으면 그 매물 판단을 보류하고 화면을 다시 확인해 달라고 한다.
- 게임 업데이트·확률·정책을 도구 결과 없이 단정하지 않는다. 모르면 모른다고 말한다.

숫자 규칙:
- 실딜 상승률·비용·확률·환산 같은 모든 수치는 도구 결과에 있는 값만 인용한다. 직접 계산하거나 추정하지 않는다.
- 필요한 수치가 도구 결과에 없으면 도구를 더 부르거나, 계산할 수 없다고 말한다.
- 잠재 줄을 더하거나(12%+9%+9%=30%) 차이를 빼는 것도 직접 계산이다. 잠재는 줄 그대로("INT +12% / +9% / +9%") 쓴다.
- 도구가 error를 돌려주면 그 이유를 설명하고, 입력을 고칠 수 있으면 고쳐서 다시 부른다.

도구 사용:
- 캐릭터 관련 질문은 닉네임이 필요하다. 없으면 먼저 물어본다.
- 매물은 사용자가 붙여넣은 툴팁을 total(총 옵션)과 potentials(잠재·에디 줄)로 나눠 넣고, 어떻게 해석했는지 먼저 짧게 보여 준다.
- 가격은 메소 정수로 넣는다(45억 3000만 → 4530000000).
- "전체 부위 어떻게 바꿔야 해" 같은 질문에는 upgrade_roadmap을 쓰고, 부위마다 next 단계와 그다음 단계를 표로 정리한다. route가 '큐브'인 부위(제네시스 무기 등)는 경매장 구매가 아니라 큐브 재설정으로 안내한다.
- "가격 대비", "가성비" 질문에는 upgrade_roadmap의 value_ranking(억당 실딜 순)을 쓰고 비용은 cube_cost_text를 그대로 인용한다. 이 비용은 메소 재설정 평균이며, 경매장에서 그 단계 템이 더 싸면 경매장이 낫다고 덧붙인다(화면 매물 evaluate_listings로 비교).
- 단계에 market(관측 시세)이 있으면 큐브 평균 비용과 시세를 나란히 비교해 더 싼 경로를 권한다. 시세 건수(count)가 적으면 참고용이라고 밝힌다. market이 없으면 시세를 지어내지 말고, 그 조건으로 경매장을 검색해 화면을 연결해 달라고 한다.
- 무엇을 할지(구매·직작·큐브) 추천할 때는 upgrade_paths를 먼저 쓴다. 전투력(실딜) 상승만 보지 말고 억당(per_100m)과 비용(cost_text), 세트 효과 변화(set_change: 세트가 깨지거나 맞춰짐)를 함께 설명한다. 같은 부위에서 구매·직작·큐브 중 억당이 높은 쪽을 권하고, sold=false(호가)와 sold=true(체결 시세)를 구분해 말한다.
- upgrade_paths에 구매·직작 경로가 없거나 관측 시세가 오래됐으면 refresh_market으로 한 번 갱신한 뒤 다시 본다. 같은 대화에서 refresh_market을 두 번 넘게 부르지 않는다(일일 검색 한도).
- 스펙업은 단계적으로 권한다. recommend_searches의 각 카드는 그 부위의 '다음 한 단계'다. 고점 잠재(레전 3줄 이탈 등)로 한 번에 바꾸라고 권하지 않는다. 예산이 있으면 싼 단계부터 여러 부위를 올리는 순서를 제안하고, 실제 가격은 화면 매물로 확인한다.
- 쿨감(스킬 재사용 대기시간) 줄은 실딜 계산에 들어가지 않는다(도구 결과 cooldown_s_not_valued, kept). 쿨감 템을 쿨감 없는 템으로 바꾸라고 권하지 말고, 사용자가 '쿨감 1초 = 주스탯 N%'를 정하면 cooldown_main_pct로 다시 계산한다. N을 대신 정하지 않는다.
- "뭘 사야 해", "경매장에서 뭘 검색해" 같은 질문에는 recommend_searches를 쓰고, 각 카드의 search 문자열을 게임 경매장 검색 조건으로 그대로 안내한다(부위·잠재·에디·최소 스타포스를 한 번에). 사용자가 그 조건으로 검색한 화면을 연결하면 화면 매물을 평가한다.
- 질문에 "[조회한 캐릭터: 이름]"이 붙어 있으면 그 이름으로 도구를 부른다. 닉네임을 다시 묻지 않는다.
- 추천은 먼저 한다: 캐릭터 질문이면 lookup_character·upgrade_paths·recommend_searches로 지금 템 상태를 읽고 질문에 맞게 바로 추천한다.
- "경매장에서 ○○ 찾아줘/보여줘", 실제 매물로 확인이 필요한 추천이면 request_auction_screen을 불러 검색 조건을 넘긴다
  (화면 연결 카드가 뜬다). 부른 뒤에는 그 조건으로 경매장을 검색해 매물에 마우스를 대고 [AI에게 보내기]를 눌러 달라고 짧게 안내하고 멈춘다.
- 첨부 매물의 price가 null이고 list_prices(같은 이름 목록 행 가격 후보)가 있으면, 후보 가격마다 evaluate_listings로 억당을 계산해 보여 주고 툴팁이 어느 행인지 확인을 부탁한다.
- 경매장 판매 수수료(기본 5%, MVP 실버 이상·PC방 3%)는 사는 가격엔 붙지 않고 지금 템 판매 대금에서 빠진다. 도구가 net_resale·net_cost로 반영한다. 사용자가 MVP 실버 이상·PC방이라고 하면 fee_rate 0.03을 넣는다.
- special_ring_note가 붙은 매물(특수 반지)은 스킬 효과가 실딜 계산에 없다. 실딜 수치로 사라/말라 하지 말고, 반지 레벨(special_ring_level)과 가격으로 지금 낀 반지와 비교해 말한다.
- 매물 결과에 resale_note가 있으면(지금 낀 템이 PC방 템이라 팔 수 없음) 판매 대금 0으로 계산됐다고 그대로 전한다.
- 가격은 도구 결과의 price_text를 글자 그대로 옮긴다. 메소 숫자를 직접 억·만으로 바꾸지 않는다(자릿수 실수 방지).
- 도구가 held로 돌려준 매물은 평가 숫자를 만들지 말고 reason을 그대로 전한다.
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
    spent = 0
    try:
        for _ in range(max_turns):
            with safe(lambda: tracer.observe("model", as_type="generation", model=model, input=_brief(items))) as gen:
                resp = client.responses.create(
                    model=model, instructions=SYSTEM, tools=openai_tools(exclude_tools), input=items,
                    reasoning={"effort": "medium"}, max_output_tokens=32000, store=False,
                )
                usage = getattr(resp, "usage", None)
                gen.update(output=getattr(resp, "output_text", "") or [getattr(it, "name", None) for it in resp.output
                                                                       if getattr(it, "type", None) == "function_call"],
                           usage_details={"input": int(usage.input_tokens), "output": int(usage.output_tokens)} if usage else None)
            if on_usage and getattr(resp, "usage", None):
                on_usage(int(resp.usage.input_tokens) + int(resp.usage.output_tokens))
            if getattr(resp, "usage", None):
                spent += int(resp.usage.input_tokens) + int(resp.usage.output_tokens)
            if max_tokens and spent > max_tokens:  # 질문 한 번이 하루 한도를 다 쓰지 못하게(공개 사용자, 2026-10-17)
                yield {"type": "error", "message": "질문 한 번에 쓸 수 있는 AI 양을 넘었어요. 질문을 더 짧게 나눠 물어봐 주세요."}
                break
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
                    with safe(lambda: tracer.observe(call.name, as_type="tool", input=args)) as t:
                        out = toolbox.run(call.name, args)
                        failed = isinstance(out, dict) and "error" in out
                        t.update(output=out, **({"level": "ERROR", "status_message": str(out["error"])} if failed else {}))
                seen += [args, out]
                yield {"type": "tool_result", "name": call.name, "result": out}
                items.append({"type": "function_call_output", "call_id": call.call_id,
                              "output": json.dumps(out, ensure_ascii=False, default=str)})
        else:
            yield {"type": "error", "message": f"도구 호출이 {max_turns}번을 넘어 멈췄어요."}
    except Exception as e:  # noqa: BLE001 — 어떤 실패든 사용자에게 보인다
        _log.warning("에이전트 오류: %s: %s", type(e).__name__, e)
        # 공개 사용자에게는 내부 오류 문구(경로·라이브러리 메시지)를 보이지 않는다(2026-10-17) — 자세한 내용은 서버 로그에만
        msg = "AI 상담 중 오류가 났어요. 잠시 뒤 다시 시도해 주세요." if public_errors else f"에이전트 오류: {type(e).__name__}: {e}"
        yield {"type": "error", "message": msg}
    yield {"type": "done", "unverified_numbers": []}
