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
from pydantic import BaseModel, Field

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


import logging
_log = logging.getLogger("uvicorn.error")


def create_app(fetcher: Callable[[str, dt.date | None], dict], db_path: str, *, rate_limit: int = 30,
               window: float = 60.0, clock: Callable[[], float] = time.time, static_dir: str | None = None,
               agent_client=None, admin_password_hash: str | None = None, session_secret: str | None = None,
               agent_daily_token_budget: int = 200_000, auction_mcp_command=None,
               vision_dataset_dir: str | None = None, vision_public_daily: int = 20,
               vision_frames_per_min: int = 240) -> FastAPI:
    app = FastAPI(title="maple-optimizer")
    usage = admin.UsageStore(db_path, clock)
    cache = BundleCache(db_path, clock)
    from server.observations import open_log
    observations = open_log(db_path, clock)  # 지우지 않는 관측 기록 — DATABASE_URL(Neon)이면 Postgres
    prices = observations  # 지금 시세 = 관측 기록의 최근 30일(rows) — 재시작해도 남는다(2026-10-08)
    from server.dataset import DatasetStore
    dataset = DatasetStore(vision_dataset_dir, clock) if vision_dataset_dir else None
    from server.vision import FrameCache
    frame_cache = FrameCache()  # 같은 툴팁·같은 화면은 AI를 다시 부르지 않는다
    import collections
    session_reads = collections.deque(maxlen=500)  # 장비창 채점용: 서버가 읽은 툴팁(매물·착용 템)을 기억한다

    def _require_admin(request: Request) -> None:
        if not (session_secret and admin.valid_session(request.cookies.get(admin.COOKIE), session_secret, clock())):
            raise ApiError(401, "UNAUTHORIZED", "관리자 로그인이 필요합니다.")
    limiter = SlidingWindow(rate_limit, window, clock)
    # 일반 유저 화면 분석(2026-10-07 공개): 화면은 0.5초마다 오니 분당 상한을 따로 두고(툴팁 찾기는 AI 비용 0),
    # AI를 실제로 부른 판독만 IP당 하루(KST) vision_public_daily회로 센다 — 관측 기록과 같은 DB(재시작해도 유지)
    vision_limiter = SlidingWindow(vision_frames_per_min, 60.0, clock)
    import hashlib
    import hmac as _hmac
    quota_salt = (session_secret or db_path).encode()

    def _quota_who(ip: str) -> str:  # IP를 그대로 저장하지 않는다
        return _hmac.new(quota_salt, ip.encode(), hashlib.sha256).hexdigest()[:32]

    @app.middleware("http")
    async def limit(request: Request, call_next):
        path = request.url.path
        # 관리자 화면 분석은 0.5초마다 들어온다 — IP당 제한 대신 하루 토큰 한도로 묶는다(2026-10-05: 23번 중 5번 거절)
        admin_vision = path.startswith("/api/vision/") and bool(session_secret) and admin.valid_session(
            request.cookies.get(admin.COOKIE), session_secret, clock())
        ip = request.client.host if request.client else "unknown"
        if path == "/api/vision/listings" and not admin_vision:
            if not vision_limiter.allow(ip):
                return _err(ApiError(429, "RATE_LIMIT", "화면이 너무 자주 들어와요. 잠시 뒤 다시 시도해 주세요."))
        elif path.startswith("/api/") and not admin_vision:
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

    @app.get("/api/character/{name}/roadmap")
    def roadmap(name: str, boss_defense: float = 300.0, cooldown_main_pct: float | None = None, date: str | None = None,
                miracle: bool = False):
        return service.roadmap(load(name, date), boss_defense, cooldown_main_pct, prices.rows(), miracle=miracle)

    @app.post("/api/character/{name}/listings")
    def listings(name: str, body: ListingsIn, date: str | None = None):
        snap = load(name, date)
        setting = Setting(**body.setting.model_dump()) if body.setting else None
        try:
            return service.listings(snap, setting, body.boss_defense, body.listings, body.fee_rate)
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
            return service.optimize(snap, setting, body.boss_defense, body.budget, body.candidates, body.fee_rate)
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
            yield from run_agent(agent_client, ToolBox(lambda name, date=None: load(name, date), market=prices.rows,
                                                      refresh=_agent_refresh), body.messages,
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
        tooltips_only: bool = True  # 툴팁 없는 화면은 AI에 보내지 않는다(목록 화면도 읽으려면 false)

    @app.get("/api/character/{name}/paths")
    def upgrade_paths(name: str, boss_defense: float = 300.0, cooldown_main_pct: float | None = None,
                      date: str | None = None, sf: str | None = None, miracle: bool = False,
                      spare_price: float | None = None, fragment_price: float | None = None, hexa_sunday: bool = False,
                      spare_slots: str | None = None, flame_price: float | None = None):
        """sf: 스타포스 이벤트(쉼표: shining, discount30, destroy_down30, guarantee_5_10_15, restore_discount20, protect),
        miracle: 미라클 타임, spare_price: 파괴 시 스페어 1개 값(메소), fragment_price: 솔 에르다 조각 1개 값(메소, HEXA 경로),
        hexa_sunday: HEXA 스탯 썬데이(메인 5레벨 이상 확률 ×1.2), spare_slots: 부위별 스페어 값('벨트:300000000,장갑:5e8'),
        flame_price: 추옵 메소 재설정 1회 값(메소, 추옵 경로)."""
        from engine.market.events import Events
        try:
            events = Events.parse(sf, miracle, spare_price, fragment_price, hexa_sunday, spare_slots, flame_price)
        except ValueError as e:
            raise ApiError(400, "BAD_EVENTS", str(e))
        return service.paths(load(name, date), boss_defense, prices.rows(), cooldown_main_pct, events=events)

    class MarketRefreshIn(BaseModel):
        name: str
        slots: list[str] | None = None
        max_searches: int = Field(15, ge=1, le=30)
        boss_defense: float = 300.0

    def _market_refresh(name: str, slots=None, max_searches: int = 15, boss_defense: float = 300.0) -> dict:
        if not auction_mcp_command:
            raise ApiError(503, "AUCTION_DISABLED",
                           "경매장 검색 연결이 꺼져 있어요. 로컬 PC에서 AUCTION_MCP_CMD(예: npx.cmd -y maple-auction-mcp)를 "
                           ".env에 넣고, 크롬에 maple-auction-mcp 확장을 설치해 웹 경매장에 로그인해 주세요.")
        from server.auction_mcp import McpUnavailable, refresh_market
        try:
            return refresh_market(load(name, None), auction_mcp_command, prices, slots, max_searches, boss_defense)
        except McpUnavailable as e:
            raise ApiError(503, "AUCTION_UNAVAILABLE", str(e)) from None

    @app.post("/api/market/refresh")
    def market_refresh(body: MarketRefreshIn, request: Request):
        """로드맵 다음 단계 조건으로 웹 경매장을 검색(판매 중·판매 완료)해 관측 시세에 넣는다(관리자, 일일 검색 한도 소진)."""
        if not (session_secret and admin.valid_session(request.cookies.get(admin.COOKIE), session_secret, clock())):
            raise ApiError(401, "UNAUTHORIZED", "관리자 로그인이 필요합니다.")
        return _market_refresh(body.name, body.slots, body.max_searches, body.boss_defense)

    def _agent_refresh(name, slots=None, max_searches=10):
        try:
            return _market_refresh(name, slots, min(int(max_searches), 15))
        except ApiError as e:
            return {"error": e.message}

    @app.get("/api/market/observed")
    def market_observed(request: Request):
        """화면 분석으로 쌓인 관측 시세(관리자 전용)."""
        if not (session_secret and admin.valid_session(request.cookies.get(admin.COOKIE), session_secret, clock())):
            raise ApiError(401, "UNAUTHORIZED", "관리자 로그인이 필요합니다.")
        rows = prices.rows()
        return {"count": len(rows), "rows": rows[-200:]}

    class VisionEvalIn(BaseModel):
        name: str
        boss_defense: float = 300.0
        listings: list[dict]

    @app.get("/api/market/stats")
    def market_stats():
        """쌓인 경매장 관측 기록 수(부위별, 첫·마지막 날짜). 공개."""
        return observations.stats()

    @app.get("/api/market/export.csv")
    def market_export(request: Request):
        """관측 기록 전체 CSV(관리자)."""
        _require_admin(request)
        from fastapi.responses import Response
        return Response(observations.export_csv(), media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": "attachment; filename=observations.csv"})

    @app.post("/api/vision/evaluate")
    def vision_evaluate(body: VisionEvalIn, request: Request):
        """이미 화면에서 읽은 매물을 다시 평가한다(캐릭터 조회 전에 읽은 줄). 비전 호출 없음 — 일반 유저도 쓴다."""
        return {"items": service.vision_items(load(body.name, None), None, body.boss_defense, body.listings[:50], [])}

    @app.post("/api/vision/listings")
    def vision_listings(body: VisionIn, request: Request):
        """공유된 경매장 탭 캡처 → 매물 추출·평가. 넥슨 서버에는 요청하지 않는다(화면 픽셀만 읽는다).
        일반 유저도 쓴다(AI 판독 IP당 하루 상한). 학습 데이터 저장·장비창 채점 기록은 관리자 화면만."""
        is_admin = bool(session_secret) and admin.valid_session(request.cookies.get(admin.COOKIE), session_secret, clock())
        if len(body.image) > 6_000_000:
            raise ApiError(413, "IMAGE_TOO_LARGE", "화면 이미지가 너무 커요(최대 약 4MB).")
        if agent_client is None:
            raise ApiError(503, "AGENT_DISABLED", "AI 기능이 설정되지 않았습니다(OPENAI_API_KEY).")
        if usage.used() >= agent_daily_token_budget:
            raise ApiError(429, "TOKEN_BUDGET", f"오늘 AI 토큰 한도({agent_daily_token_budget:,})를 다 썼어요.")
        if not body.image.startswith("data:image/"):
            raise ApiError(422, "INVALID_INPUT", "이미지(data URL)가 필요합니다.")
        from server.vision import VisionError, VisionQuota, analyze_frame
        ip = request.client.host if request.client else "unknown"
        who = _quota_who(ip)
        try:
            used = 0 if is_admin else observations.quota_used(who)
        except Exception as e:  # DB가 잠깐 안 돼도 판독은 된다 — 비용은 하루 토큰 한도가 막는다
            _log.warning("화면 한도 조회 실패: %s", type(e).__name__)
            used = 0
        allow_ai = None if is_admin else (lambda: used < vision_public_daily)
        try:
            data = analyze_frame(agent_client, body.image, on_usage=usage.add, cache=frame_cache,
                                 tooltips_only=body.tooltips_only or not is_admin, allow_ai=allow_ai)
        except VisionQuota:
            raise ApiError(429, "VISION_QUOTA", f"오늘 화면 분석 한도({vision_public_daily}회)를 다 썼어요. 내일 다시 써 주세요.") from None
        except VisionError as e:
            raise ApiError(422, "VISION_PARSE", str(e)) from None
        if not is_admin and not data.get("cached") and not data.get("skipped"):
            try:
                used = observations.quota_add(who)
            except Exception as e:
                _log.warning("화면 한도 기록 실패: %s", type(e).__name__)
                used += 1
        snap = load(body.name, None) if body.name else None
        setting = Setting(**body.setting) if body.setting else None
        from server.vision import normalize_fee
        for x in data["listings"]:
            try:
                observations.record(x)  # 영구 관측 기록(IP·이미지 없음) — 지금 시세도 여기서 최근 30일을 읽는다
            except Exception as e:  # DB가 잠깐 안 돼도 평가는 계속한다
                _log.warning("관측 기록 실패: %s", type(e).__name__)
        if is_admin and not data.get("cached"):
            session_reads.extend(data["listings"] + data.get("equipped_items", []))
        names = [x.get("name") for x in data["listings"] + data.get("equipped_items", [])]
        kind = "건너뜀(툴팁 없음)" if data.get("skipped") else "재사용" if data.get("cached") else "판독"
        _log.info("화면 %s · 툴팁 %s개 · %s", kind, data.get("tooltips_found", 0), ", ".join(n or "?" for n in names) or "-")
        dataset_on = dataset if is_admin else None  # 일반 유저 화면은 저장하지 않는다
        if dataset_on:
            dataset.log_frame({"kind": kind, "tooltips": data.get("tooltips_found", 0), "names": names})
        if dataset_on and data.get("skipped"):
            dataset.save_skipped(body.image, {"skipped": data["skipped"]})
        # 내 PC 학습 데이터(켜졌을 때만). 캐시로 돌려준 같은 화면은 다시 저장하지 않는다
        frame_id = (dataset.save_frame(body.image, data)
                    if dataset_on and not data.get("cached") and not data.get("skipped") else None)
        items = service.vision_items(snap, setting, body.boss_defense, data["listings"], set(body.seen))
        for it in items:
            it["frame_id"] = frame_id
        return {"tooltip_visible": data["tooltip_visible"], "fee_rate": normalize_fee(data.get("fee_rate")),
                "frame_id": frame_id, "items": items,
                "equipped_items": data.get("equipped_items", []),  # 착용 템 판독(장비창 채점용, 매물 아님)
                "ai_remaining": None if is_admin else max(0, vision_public_daily - used)}

    class VisionCorrectIn(BaseModel):
        frame_id: str
        signature: str
        name: str
        boss_defense: float = 300.0
        fields: dict

    _EDITABLE = ("name", "starforce", "level", "potentials", "additional", "price", "total")

    @app.post("/api/vision/correct")
    def vision_correct(body: VisionCorrectIn, request: Request):
        """화면에서 잘못 읽은 값을 고친다: 정답으로 저장하고, 고친 값으로 다시 평가한다."""
        _require_admin(request)
        if dataset is None:
            raise ApiError(503, "DATASET_DISABLED", "학습 데이터 저장이 꺼져 있어요(VISION_DATASET_DIR).")
        from server.vision import signature
        try:
            reading = dataset.reading(body.frame_id)
        except KeyError:
            raise ApiError(404, "FRAME_NOT_FOUND", "그 화면 기록을 찾지 못했어요.") from None
        read = next((x for x in reading.get("listings") or [] if signature(x) == body.signature), None)
        if read is None:
            raise ApiError(404, "LISTING_NOT_FOUND", "그 매물을 찾지 못했어요.")
        fields = {k: v for k, v in body.fields.items() if k in _EDITABLE}
        dataset.save_correction(body.frame_id, body.signature, fields)
        read = {**read, **fields, "corrected": True}
        if "potentials" in fields or "additional" in fields:
            read["potential_lines"] = list(fields.get("potentials", read.get("potential_lines") or []))
            read["additional"] = list(fields.get("additional", read.get("additional") or []))
            read["potentials"] = read["potential_lines"] + read["additional"]
        if "starforce" in fields:
            read["starforce_source"] = "사용자 수정"
        item = service.vision_items(load(body.name, None), None, body.boss_defense, [read], [])[0]
        item["frame_id"] = body.frame_id
        return {"item": item}

    class VisionScoreIn(BaseModel):
        name: str
        reads: list[dict]

    @app.post("/api/vision/score")
    def vision_score(body: VisionScoreIn, request: Request):
        """장비창 훑기 채점: 화면에서 읽은 툴팁을 넥슨 API의 착용 템(정답)과 항목별로 비교한다."""
        _require_admin(request)
        from server.score import score_reads
        # 화면 쪽에서 판독이 빠져도(2026-10-05 실측) 서버가 기억한 판독을 함께 채점한다
        return score_reads(load(body.name, None), list(session_reads) + body.reads[:100])

    @app.post("/api/vision/score/reset")
    def vision_score_reset(request: Request):
        _require_admin(request)
        session_reads.clear()
        return {"cleared": True}

    @app.get("/api/vision/dataset")
    def vision_dataset(request: Request):
        _require_admin(request)
        return {"enabled": dataset is not None, **(dataset.stats() if dataset else {"frames": 0, "corrected": 0})}

    if static_dir and pathlib.Path(static_dir, "index.html").exists():
        @app.middleware("http")
        async def _no_cache_index(request: Request, call_next):
            # 새로 빌드해도 브라우저가 옛 화면을 계속 쓰던 문제(2026-10-05): index.html은 매번 새로 확인하게 한다.
            # /assets/는 파일 이름에 해시가 붙어 있어 캐시해도 된다.
            response = await call_next(request)
            path = request.url.path
            if not path.startswith(("/api/", "/assets/")):
                response.headers["Cache-Control"] = "no-cache"
            return response

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
                      agent_daily_token_budget=int(_env("AGENT_DAILY_TOKEN_BUDGET") or 200_000),
                      auction_mcp_command=_env("AUCTION_MCP_CMD"),
                      vision_dataset_dir=_env("VISION_DATASET_DIR"),
                      vision_public_daily=int(_env("VISION_PUBLIC_DAILY") or 20),
                      vision_frames_per_min=int(_env("VISION_FRAMES_PER_MIN") or 240))


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
