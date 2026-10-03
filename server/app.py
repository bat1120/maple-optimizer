"""FastAPI 앱. 넥슨 오류·엔진 오류를 구분된 HTTP 상태와 한국어 메시지로 돌려준다 (스펙 §12)."""
import datetime as dt
import pathlib
import time
from collections.abc import Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
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
               window: float = 60.0, clock: Callable[[], float] = time.time, static_dir: str | None = None) -> FastAPI:
    app = FastAPI(title="maple-optimizer")
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

    if static_dir and pathlib.Path(static_dir, "index.html").exists():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="web")  # API 라우트 뒤에 둔다
    return app


def default_app() -> FastAPI:
    """실서버용: .env의 넥슨 키, 저장소의 .cache/ SQLite."""
    from nexon.client import NexonClient, load_api_key
    client = NexonClient(load_api_key(ROOT))
    return create_app(client.fetch_bundle, str(ROOT / ".cache" / "cache.sqlite3"), static_dir=str(ROOT / "web" / "dist"))
