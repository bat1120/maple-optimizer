"""FastAPI 앱. 넥슨 오류·엔진 오류를 구분된 HTTP 상태와 한국어 메시지로 돌려준다 (스펙 §12)."""
import datetime as dt
import os
import pathlib
import time
from collections.abc import Callable

import json

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from engine.market.listing import InvalidPrice, NoDamage
from engine.stats.jobs import UnsupportedJob
from engine.stats.snapshot import Setting
from engine.stats.weapons import UnknownWeapon
from nexon.client import CharacterNotFound, InvalidKey, NexonError, RateLimited, Unavailable
from nexon.convert import snapshot
from server import service
from server.cache import BundleCache
from server.ratelimit import SlidingWindow
from pydantic import BaseModel

from server import admin
from server.schemas import CraftIn, CubeIn, ListingsIn, OptimizeIn, StarforceIn

ROOT = pathlib.Path(__file__).resolve().parent.parent


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


_NEXON = [  # 하위 클래스 먼저
    (CharacterNotFound, 404, "NOT_FOUND", "캐릭터를 찾을 수 없습니다."),
    (RateLimited, 503, "NEXON_RATE_LIMIT", "넥슨 API 호출 한도를 넘었습니다. 잠시 후 다시 시도해 주세요."),
    (Unavailable, 502, "NEXON_UNAVAILABLE", "넥슨 API가 점검 중이거나 데이터를 준비 중입니다."),
    (InvalidKey, 500, "SERVER_CONFIG", "서버 설정 오류입니다(넥슨 API 키). 관리자에게 알려 주세요."),
    (NexonError, 502, "NEXON_ERROR", "넥슨 API 오류가 발생했습니다."),
]


def _err(e: ApiError) -> JSONResponse:
    return JSONResponse(status_code=e.status, content={"code": e.code, "message": e.message})


def create_app(fetcher: Callable[[str, dt.date | None], dict], db_path: str, *, rate_limit: int = 30,
               window: float = 60.0, clock: Callable[[], float] = time.time, static_dir: str | None = None,
               agent_client=None, admin_password_hash: str | None = None, session_secret: str | None = None,
               agent_daily_token_budget: int = 200_000) -> FastAPI:
    app = FastAPI(title="maple-optimizer")
    usage = admin.UsageStore(db_path, clock)
    cache = BundleCache(db_path, clock)
    limiter = SlidingWindow(rate_limit, window, clock)

    @app.middleware("http")
    async def limit(request: Request, call_next):
        if request.url.path.startswith("/api/"):
            ip = request.client.host if request.client else "unknown"
            if not limiter.allow(ip):
                return _err(ApiError(429, "RATE_LIMIT", "요청이 너무 많습니다. 1분 뒤 다시 시도해 주세요."))
        return await call_next(request)

    @app.exception_handler(ApiError)
    async def api_error(_: Request, e: ApiError):
        return _err(e)

    @app.exception_handler(UnsupportedJob)
    async def unsupported_job(_: Request, e: UnsupportedJob):
        return _err(ApiError(422, "UNSUPPORTED", f"계산 제외: {e}"))

    @app.exception_handler(UnknownWeapon)
    async def unknown_weapon(_: Request, e: UnknownWeapon):
        return _err(ApiError(422, "UNSUPPORTED", f"계산 제외: {e}"))

    def load(name: str, date: str | None):
        day = None
        if date:
            try:
                day = dt.date.fromisoformat(date)
            except ValueError:
                raise ApiError(400, "BAD_DATE", "날짜 형식은 YYYY-MM-DD 입니다.") from None
        body = cache.get(name, day)
        if body is None:
            try:
                body = fetcher(name, day)
            except ValueError as e:  # 클라이언트의 날짜 하한 검사
                raise ApiError(400, "BAD_DATE", str(e)) from None
            except NexonError as e:
                status, code, msg = next((s, c, m) for cls, s, c, m in _NEXON if isinstance(e, cls))
                raise ApiError(status, code, msg) from None
            if any(v is None for v in body.values()):
                raise ApiError(404, "NO_DATA", "해당 날짜의 데이터가 없습니다.")
            cache.put(name, day, body)
        return snapshot(body)

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/character/{name}")
    def character(name: str, date: str | None = None):
        return service.summary(load(name, date))

    @app.get("/api/character/{name}/settings")
    def settings(name: str, boss_defense: float = 300.0, date: str | None = None):
        return service.settings(load(name, date), boss_defense)

    @app.get("/api/character/{name}/recommend")
    def recommend(name: str, boss_defense: float = 300.0, top: int = 5, cooldown_main_pct: float | None = None,
                  date: str | None = None):
        return service.recommend(load(name, date), boss_defense, max(1, min(top, 20)), cooldown_main_pct)

    @app.post("/api/character/{name}/listings")
    def listings(name: str, body: ListingsIn, date: str | None = None):
        snap = load(name, date)
        setting = Setting(**body.setting.model_dump()) if body.setting else None
        try:
            return service.listings(snap, setting, body.boss_defense, body.listings)
        except InvalidPrice as e:
            raise ApiError(400, "INVALID_PRICE", str(e)) from None
        except NoDamage as e:
            raise ApiError(422, "NO_DAMAGE", str(e)) from None
        except ValueError as e:
            raise ApiError(422, "INVALID_INPUT", str(e)) from None

    @app.post("/api/enhance/starforce")
    def enhance_starforce(body: StarforceIn):
        try:
            return service.starforce(body)
        except ValueError as e:
            raise ApiError(422, "INVALID_INPUT", str(e)) from None

    @app.post("/api/enhance/cube")
    def enhance_cube(body: CubeIn):
        try:
            return service.cube(body)
        except KeyError:
            raise ApiError(404, "NO_TABLE", f"확률표가 없습니다: {body.table}") from None
        except ValueError as e:
            raise ApiError(422, "INVALID_INPUT", str(e)) from None

    @app.post("/api/craft/compare")
    def craft_compare(body: CraftIn):
        try:
            return service.craft_compare(body)
        except ValueError as e:
            raise ApiError(422, "INVALID_INPUT", str(e)) from None

    @app.post("/api/character/{name}/optimize")
    def optimize(name: str, body: OptimizeIn, date: str | None = None):
        snap = load(name, date)
        setting = Setting(**body.setting.model_dump()) if body.setting else None
        try:
            return service.optimize(snap, setting, body.boss_defense, body.budget, body.candidates)
        except ValueError as e:
            raise ApiError(422, "INVALID_INPUT", str(e)) from None

    class LoginIn(BaseModel):
        password: str

    class ChatIn(BaseModel):
        messages: list[dict]

    @app.post("/api/admin/login")
    def login(body: LoginIn):
        if not (admin_password_hash and session_secret):
            raise ApiError(503, "ADMIN_DISABLED", "관리자 기능이 설정되지 않았습니다(ADMIN_PASSWORD_HASH·SESSION_SECRET).")
        if not admin.check_password(body.password, admin_password_hash):
            raise ApiError(401, "BAD_PASSWORD", "비밀번호가 틀렸습니다.")
        r = JSONResponse({"status": "ok"})
        r.set_cookie(admin.COOKIE, admin.sign_session(session_secret, clock()), max_age=admin.SESSION_TTL,
                     httponly=True, samesite="strict")
        return r

    @app.post("/api/agent/chat")
    def agent_chat(body: ChatIn, request: Request):
        if not (session_secret and admin.valid_session(request.cookies.get(admin.COOKIE), session_secret, clock())):
            raise ApiError(401, "UNAUTHORIZED", "관리자 로그인이 필요합니다.")
        if agent_client is None:
            raise ApiError(503, "AGENT_DISABLED", "에이전트가 설정되지 않았습니다(OPENAI_API_KEY).")
        from agent.loop import run_agent
        from agent.tools import ToolBox

        def events():
            if usage.used() >= agent_daily_token_budget:
                yield {"type": "error", "message": f"오늘 에이전트 토큰 한도({agent_daily_token_budget:,})를 다 썼어요. 내일 다시 이용해 주세요."}
                yield {"type": "done", "unverified_numbers": []}
                return
            yield from run_agent(agent_client, ToolBox(lambda name, date=None: load(name, date)), body.messages,
                                 on_usage=usage.add)

        def sse():
            for e in events():
                yield "data: " + json.dumps(e, ensure_ascii=False, default=str) + "\n\n"

        return StreamingResponse(sse(), media_type="text/event-stream")

    class VisionIn(BaseModel):
        image: str
        name: str | None = None
        boss_defense: float = 300.0
        setting: dict | None = None
        seen: list[str] = []

    class VisionEvalIn(BaseModel):
        name: str
        boss_defense: float = 300.0
        listings: list[dict]

    @app.post("/api/vision/evaluate")
    def vision_evaluate(body: VisionEvalIn, request: Request):
        """이미 화면에서 읽은 매물을 다시 평가한다(캐릭터 조회 전에 읽은 줄). 비전 호출 없음."""
        if not (session_secret and admin.valid_session(request.cookies.get(admin.COOKIE), session_secret, clock())):
            raise ApiError(401, "UNAUTHORIZED", "관리자 로그인이 필요합니다.")
        return {"items": service.vision_items(load(body.name, None), None, body.boss_defense, body.listings[:50], [])}

    @app.post("/api/vision/listings")
    def vision_listings(body: VisionIn, request: Request):
        """공유된 경매장 탭 캡처 → 매물 추출·평가. 넥슨 서버에는 요청하지 않는다(화면 픽셀만 읽는다)."""
        if not (session_secret and admin.valid_session(request.cookies.get(admin.COOKIE), session_secret, clock())):
            raise ApiError(401, "UNAUTHORIZED", "관리자 로그인이 필요합니다.")
        if agent_client is None:
            raise ApiError(503, "AGENT_DISABLED", "AI 기능이 설정되지 않았습니다(OPENAI_API_KEY).")
        if usage.used() >= agent_daily_token_budget:
            raise ApiError(429, "TOKEN_BUDGET", f"오늘 AI 토큰 한도({agent_daily_token_budget:,})를 다 썼어요.")
        if not body.image.startswith("data:image/"):
            raise ApiError(422, "INVALID_INPUT", "이미지(data URL)가 필요합니다.")
        from server.vision import VisionError, extract_listings
        try:
            data = extract_listings(agent_client, body.image, on_usage=usage.add)
        except VisionError as e:
            raise ApiError(422, "VISION_PARSE", str(e)) from None
        snap = load(body.name, None) if body.name else None
        setting = Setting(**body.setting) if body.setting else None
        return {"tooltip_visible": data["tooltip_visible"],
                "items": service.vision_items(snap, setting, body.boss_defense, data["listings"], set(body.seen))}

    if static_dir and pathlib.Path(static_dir, "index.html").exists():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="web")  # API 라우트 뒤에 둔다
    return app


def default_app() -> FastAPI:
    """실서버용: .env의 넥슨 키, 저장소의 .cache/ SQLite."""
    from nexon.client import NexonClient, load_api_key
    client = NexonClient(load_api_key(ROOT))
    admin_hash, secret = _env("ADMIN_PASSWORD_HASH"), _env("SESSION_SECRET")
    agent_client = None
    if admin_hash and secret and _env("OPENAI_API_KEY"):
        import openai
        agent_client = openai.OpenAI(api_key=_env("OPENAI_API_KEY"))
        if _env("OPENAI_MODEL"):
            os.environ.setdefault("OPENAI_MODEL", _env("OPENAI_MODEL"))
    return create_app(client.fetch_bundle, str(ROOT / ".cache" / "cache.sqlite3"), static_dir=str(ROOT / "web" / "dist"),
                      agent_client=agent_client, admin_password_hash=admin_hash, session_secret=secret,
                      agent_daily_token_budget=int(_env("AGENT_DAILY_TOKEN_BUDGET") or 200_000))


def _env(key: str) -> str | None:
    """환경변수, 없으면 저장소 .env. 값은 출력하지 않는다."""
    import os
    if os.environ.get(key):
        return os.environ[key]
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith(f"{key}=") and line.split("=", 1)[1].strip():
                return line.split("=", 1)[1].strip()
    return None
