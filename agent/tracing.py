"""AI 상담 추적(2026-10-17 사용자: Langfuse).

- LANGFUSE_PUBLIC_KEY·LANGFUSE_SECRET_KEY가 있으면 Langfuse(v5)로 보낸다. 지역은 LANGFUSE_BASE_URL(기본 EU cloud.langfuse.com)
- 키가 없으면 NoopTracer — 아무것도 보내지 않는다(로컬·테스트)
- 대화 하나 = 추적 하나(agent), 모델 호출마다 generation(모델·토큰), 도구 호출마다 tool(입력·결과·오류)
- 추적이 실패해도 답변은 나간다: 모든 호출을 safe()로 감싼다
- 사용자는 user_id로만 구분한다 — 관리자는 'admin', 일반 사용자는 날짜별 HMAC 해시(IP 원문을 보내지 않는다)
"""
import contextlib
import logging
import os

_log = logging.getLogger("uvicorn.error")


class _NoopObs:
    def update(self, **kw):
        pass


class NoopTracer:
    @contextlib.contextmanager
    def conversation(self, **kw):
        yield _NoopObs()

    @contextlib.contextmanager
    def observe(self, name, as_type="span", **kw):
        yield _NoopObs()

    def flush(self):
        pass


class LangfuseTracer:
    def __init__(self, client):
        self._c = client

    @contextlib.contextmanager
    def conversation(self, user_id=None, session_id=None, metadata=None, input=None):
        from langfuse import propagate_attributes
        with propagate_attributes(user_id=user_id, session_id=session_id, metadata=metadata, trace_name="agent_chat"):
            with self._c.start_as_current_observation(name="agent_chat", as_type="agent", input=input) as root:
                yield root

    def observe(self, name, as_type="span", **kw):
        return self._c.start_as_current_observation(name=name, as_type=as_type, **kw)

    def flush(self):
        self._c.flush()


def from_env():
    if not (os.environ.get("LANGFUSE_PUBLIC_KEY") and os.environ.get("LANGFUSE_SECRET_KEY")):
        return NoopTracer()
    try:
        from langfuse import Langfuse
        return LangfuseTracer(Langfuse())  # 키·주소는 환경변수에서
    except Exception as e:  # noqa: BLE001 — 추적을 못 켜도 서버는 뜬다
        _log.warning("Langfuse 초기화 실패: %s", type(e).__name__)
        return NoopTracer()


class _SafeObs:
    def __init__(self, obs):
        self._o = obs

    def update(self, **kw):
        try:
            self._o.update(**kw)
        except Exception as e:  # noqa: BLE001
            _log.warning("추적 기록 실패: %s", type(e).__name__)


@contextlib.contextmanager
def safe(cm_factory):
    """추적 컨텍스트를 연다. 열기·닫기에 실패해도 안쪽 코드는 그대로 돈다."""
    try:
        cm = cm_factory()
        obs = cm.__enter__()
    except Exception as e:  # noqa: BLE001
        _log.warning("추적 시작 실패: %s", type(e).__name__)
        yield _NoopObs()
        return
    try:
        yield _SafeObs(obs)
    finally:
        try:
            cm.__exit__(None, None, None)
        except Exception as e:  # noqa: BLE001
            _log.warning("추적 종료 실패: %s", type(e).__name__)
