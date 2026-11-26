"""FastAPI 앱. 넥슨 오류·엔진 오류를 구분된 HTTP 상태와 한국어 메시지로 돌려준다 (스펙 §12)."""
import dataclasses
import datetime as dt
import threading
import hashlib
import hmac
import os
import pathlib
import time
from collections.abc import Callable

import json

from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from engine.market.listing import InvalidPrice, NoDamage
from engine.stats.jobs import UnsupportedJob
from engine.stats.snapshot import Setting
from engine.stats.weapons import UnknownWeapon
from nexon.client import ENDPOINTS, CharacterNotFound, InvalidKey, NexonError, RateLimited, Unavailable
from nexon.convert import snapshot
from server import service
from server.cache import BundleCache
from server.ratelimit import SlidingWindow
from pydantic import BaseModel, Field

from server import admin
from server.schemas import CraftIn, CubeIn, ListingsIn, OptimizeIn, StarforceIn

ROOT = pathlib.Path(__file__).resolve().parent.parent
SWAP_STARS = (17, 18, 21, 22)  # 갈아타기 후보에 가정할 수 있는 스타포스


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, extra: dict | None = None):
        super().__init__(message)
        self.status, self.code, self.message, self.extra = status, code, message, extra or {}


_NEXON = [  # 하위 클래스 먼저
    (CharacterNotFound, 404, "NOT_FOUND", "캐릭터를 찾을 수 없습니다."),
    (RateLimited, 503, "NEXON_RATE_LIMIT", "넥슨 API 호출 한도를 넘었습니다. 잠시 후 다시 시도해 주세요."),
    (Unavailable, 502, "NEXON_UNAVAILABLE", "넥슨 API가 점검 중이거나 데이터를 준비 중입니다."),
    (InvalidKey, 500, "SERVER_CONFIG", "서버 설정 오류입니다(넥슨 API 키). 관리자에게 알려 주세요."),
    (NexonError, 502, "NEXON_ERROR", "넥슨 API 오류가 발생했습니다."),
]


def _err(e: ApiError) -> JSONResponse:
    return JSONResponse(status_code=e.status, content={"code": e.code, "message": e.message, **e.extra})


import logging  # noqa: E402
_log = logging.getLogger("uvicorn.error")


BASELINE_STEP = 4  # 버프 없는 기준을 보는 과거 날짜 간격(일)
BASELINE_RETRY = 600  # 기준일을 못 불러왔으면 이만큼(초) 지난 뒤에만 다시 시도한다


MEMO_TTL, MEMO_SIZE = 60, 300  # 계산 결과를 다시 쓰는 시간(초)과 개수

STALE_HOLD = 5 * 60  # 넥슨이 막혔을 때 같은 캐릭터를 다시 불러 보기까지 기다리는 시간(초)


def create_app(fetcher: Callable[[str, dt.date | None], dict], db_path: str, *, rate_limit: int = 30,
               window: float = 60.0, clock: Callable[[], float] = time.time, static_dir: str | None = None,
               agent_client=None, admin_password_hash: str | None = None, session_secret: str | None = None,
               agent_daily_token_budget: int = 200_000, auction_mcp_command=None,
               vision_dataset_dir: str | None = None, vision_public_daily: int = 20, agent_ping_seconds: float = 10.0, agent_public_daily: int = 5, agent_public_request_tokens: int = 60000, agent_tracer=None,
               vision_frames_per_min: int = 240, ocr=None, baseline_dates: int = 0, baseline_background: bool = True) -> FastAPI:
    # baseline_dates: 버프 없는 기준을 뽑으려고 같이 보는 과거 날짜 수(0 = 끔). 날짜 하나에 넥슨 호출 13번쯤.
    # baseline_background: 과거 날짜를 뒤에서 불러온다(첫 조회가 느려지지 않게). False면 조회 안에서 불러온다(테스트용)
    baseline_busy, baseline_retry, baseline_lock = set(), {}, threading.Lock()
    app = FastAPI(title="maple-optimizer", docs_url=None, redoc_url=None, openapi_url=None)  # 운영에 API 목록 노출 안 함
    usage = admin.UsageStore(db_path, clock)
    if agent_tracer is None:  # AI 상담 추적(Langfuse) — 키가 없으면 아무것도 안 한다(agent/tracing.py)
        from agent.tracing import from_env
        agent_tracer = from_env()
    cache = BundleCache(db_path, clock)
    app.state.baseline_jobs = []  # 뒤에서 도는 기준일 불러오기(테스트가 끝나기를 기다릴 수 있게)
    from server.observations import PUBLIC_SOURCE, open_log
    observations = open_log(db_path, clock)  # 지우지 않는 관측 기록 — DATABASE_URL(Neon)이면 Postgres
    prices = observations  # 지금 시세 = 관측 기록의 최근 30일(rows) — 서버가 다시 떠도 남는다(2026-10-13)
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
    # AI를 실제로 부른 판독만 IP당 하루 vision_public_daily회로 센다. 횟수는 관측 DB에 둔다(재시작해도 이어서) —
    # IP 대신 날짜별 HMAC 해시만 저장한다(2026-10-11 사용자). 비밀값은 session_secret, 없으면 프로세스마다 새로
    vision_limiter = SlidingWindow(vision_frames_per_min, 60.0, clock)
    from server.listprice import ListMemory
    list_memory = ListMemory()
    from server.vision import ScanRegistry
    scans = ScanRegistry()  # 스캔마다 인식한 툴팁·분석 중 수(AI와 상관없이, 2026-11-14)
    import secrets as _secrets
    quota_secret = (session_secret or _secrets.token_hex(32)).encode()

    def _quota_who(ip: str, kind: str = "vision") -> str:
        day = int((clock() + 9 * 3600) // 86400)  # KST 날짜 — 날이 바뀌면 같은 IP도 다른 해시
        return hmac.new(quota_secret, f"{kind}-quota|{day}|{ip}".encode(), hashlib.sha256).hexdigest()

    def _quota_take(who: str) -> int:
        """공개 한도 차감(2026-10-17): DB가 안 되면 막는다(fail-closed) — 그동안 한도가 없어지는 걸 막는다."""
        try:
            return observations.quota_take(who)
        except Exception as e:  # noqa: BLE001
            _log.warning("한도 차감 실패: %s", type(e).__name__)
            raise ApiError(503, "QUOTA_UNAVAILABLE", "잠시 사용 횟수를 확인할 수 없어요. 조금 뒤 다시 시도해 주세요.") from None

    def _quota_used(who: str) -> int:
        try:
            return observations.quota_used(who)
        except Exception as e:  # noqa: BLE001 — DB가 잠깐 안 되면 한도 없이 막지 않고 0으로(토큰 하루 한도가 따로 있다)
            _log.warning("한도 조회 실패: %s", type(e).__name__)
            return 0

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

    @app.exception_handler(NoDamage)
    async def no_damage(_: Request, e: NoDamage):
        return _err(ApiError(422, "NO_DAMAGE", str(e)))

    @app.exception_handler(UnknownWeapon)
    async def unknown_weapon(_: Request, e: UnknownWeapon):
        return _err(ApiError(422, "UNSUPPORTED", f"계산 제외: {e}"))

    fetch_locks, fetch_guard = {}, threading.Lock()
    stale_since: dict = {}  # (이름, 날짜) → 받은 시각. 넥슨이 막혀 오래된 캐시로 답하는 중인 캐릭터
    stale_hold: dict = {}   # (이름, 날짜) → 이 시각까지는 넥슨을 다시 부르지 않고 오래된 값으로 답한다

    def _fetch_lock(name: str, day):
        with fetch_guard:
            if len(fetch_locks) > 5000:                       # 이름마다 하나씩 쌓이지 않게(잠긴 것은 남긴다)
                for k in [k for k, v in fetch_locks.items() if not v.locked()]:
                    del fetch_locks[k]
            return fetch_locks.setdefault((name.casefold(), day), threading.Lock())

    def load(name: str, date: str | None):
        day = None
        if date:
            try:
                day = dt.date.fromisoformat(date)
            except ValueError:
                raise ApiError(400, "BAD_DATE", "날짜 형식은 YYYY-MM-DD 입니다.") from None
        body = cache.get(name, day)
        if body is None:
            # 같은 캐릭터를 동시에 여러 요청이 찾으면 한 번만 넥슨을 부른다. 2026-11-25 운영: 화면이 요약·세팅·계획을 한꺼번에 불러
            # 캐시가 빈 첫 조회에서 넥슨을 3번씩(각 13회) 겹쳐 불렀고, 초당 한도에 걸려 '호출 한도를 넘었습니다'가 나왔다
            with _fetch_lock(name, day):
                body = cache.get(name, day)
                key = (name.casefold(), day)
                if body is None and clock() < stale_hold.get(key, 0):    # 방금 막혔던 캐릭터 — 잠깐은 다시 두드리지 않는다
                    old = cache.stale(name, day)
                    body = old[0] if old else None
                if body is None:
                    try:
                        body = fetcher(name, day)
                    except ValueError as e:  # 클라이언트의 날짜 하한 검사
                        raise ApiError(400, "BAD_DATE", str(e)) from None
                    except NexonError as e:
                        # 넥슨이 막혔으면(하루·초당 한도, 점검) 전에 받아 둔 값으로 답한다 — 오류 화면보다 조금 오래된 결과가 낫다.
                        # 화면에는 언제 데이터인지 적는다(stale_minutes). 2026-11-25
                        old = cache.stale(name, day) if isinstance(e, (RateLimited, Unavailable)) else None
                        if old is None:
                            status, code, msg = next((s, c, m) for cls, s, c, m in _NEXON if isinstance(e, cls))
                            raise ApiError(status, code, msg) from None
                        body, stale_since[key] = old
                        stale_hold[key] = clock() + STALE_HOLD
                    else:
                        stale_since.pop(key, None)
                        stale_hold.pop(key, None)
                        # 필수 데이터만 '없음' 판정 — 연무장 기록·HEXA·6차 스킬은 비어 있어도 된다(2026-10-08 회귀: 기록 없는 캐릭터가 전부 404)
                        if any(body[ep] is None for ep in ENDPOINTS if ep in body):
                            raise ApiError(404, "NO_DATA", "해당 날짜의 데이터가 없습니다.")
                        cache.put(name, day, body)
        snap = snapshot(body)
        if "무기" not in snap.equipment_presets.get(snap.active_equipment_preset, {}):
            # 2026-11-24 직업별 측정: 무기를 뺀 채 접속을 끝낸 캐릭터는 모든 조회가 500이었다(스탯공격력 1)
            raise ApiError(422, "NO_WEAPON", "무기를 끼지 않은 상태로 저장된 캐릭터예요. 무기를 끼고 게임에 접속했다 나온 뒤 다시 조회해 주세요.")
        if day is None and baseline_dates > 0:
            snap = dataclasses.replace(snap, floors=_floors(name, snap))
        return snap

    def _anchors() -> list:
        """버프 없는 기준을 보는 과거 기준일들. 4일마다 하나로 고정해 캐시(과거 날짜 30일 보관)를 여러 날 다시 쓴다."""
        today = dt.datetime.fromtimestamp(clock(), dt.timezone(dt.timedelta(hours=9))).date()
        first = today - dt.timedelta(days=2)                      # 어제 데이터는 아직 준비 중일 수 있다
        first -= dt.timedelta(days=first.toordinal() % BASELINE_STEP)
        return [first - dt.timedelta(days=BASELINE_STEP * i) for i in range(baseline_dates)]

    def _fetch_anchors(name: str, days: list) -> None:
        """없는 기준일을 넥슨에서 불러와 캐시에 넣는다. 실패하면 멈추고 잠시 뒤에만 다시 시도한다(호출량 초과 때 계속 두드리지 않게)."""
        try:
            for day in days:
                try:
                    body = fetcher(name, day)
                except (NexonError, ValueError):
                    baseline_retry[name.casefold()] = clock() + BASELINE_RETRY
                    return
                cache.put(name, day, body)                         # 빈 날짜(캐릭터 생성 전)도 저장해 다시 부르지 않는다
        finally:
            with baseline_lock:
                baseline_busy.discard(name.casefold())

    def _floors(name: str, now) -> dict:
        """버프 없는 기준: 지금 + 과거 기준일들의 잔차 중 항목별 최저(engine/stats/residual.py clean_floors).
        넥슨 스탯창은 접속 종료 시점 값이라 그때 켜져 있던 버프가 섞인다(2026-11-23 실측: 같은 장비·세팅인데 데미지 91→209%).
        과거 날짜는 뒤에서 불러온다(2026-11-23 사용자 결정) — 첫 조회는 지금처럼 바로 답하고 pending 표시만 붙인다. 불러오는 동안·실패해도
        조회 자체는 그대로 된다."""
        from engine.stats.residual import _raw_calibrate, clean_floors
        days = _anchors()
        bodies = [cache.get(name, d) for d in days]
        missing = [d for d, body in zip(days, bodies) if body is None]
        key = name.casefold()
        if missing and clock() >= baseline_retry.get(key, 0):
            if not baseline_background:
                baseline_busy.add(key)
                _fetch_anchors(name, missing)
                bodies = [cache.get(name, d) for d in days]
                missing = [d for d, body in zip(days, bodies) if body is None]
            else:
                with baseline_lock:
                    start = key not in baseline_busy
                    baseline_busy.add(key)
                if start:
                    t = threading.Thread(target=_fetch_anchors, args=(name, missing), daemon=True)
                    app.state.baseline_jobs.append(t)
                    t.start()
        cals = [_raw_calibrate(now, service.CATALOG)]
        for body in bodies:
            if body is None:
                continue
            try:
                past = snapshot(body)
                if past.character_class == now.character_class:
                    cals.append(_raw_calibrate(past, service.CATALOG))
            except Exception:  # noqa: BLE001 — 그 날짜 데이터가 비어 있거나 모자라면 건너뛴다
                continue
        floors = clean_floors(cals) if len(cals) > 1 else {}
        return floors | ({"pending": True} if key in baseline_busy else {})

    # 계산 결과 잠깐 다시 쓰기. 2026-11-25 운영 실측: 계획 23초·갈아타기 25초·방법별 비교 17초 — 화면이 같은 계획을
    # '1순위 한 줄'과 '계획표'로 두 번 부르고, 탭을 오갈 때마다 다시 계산했다. 같은 캐릭터 데이터(받은 시각이 같다)·같은 조건이면
    # MEMO_TTL초 동안 한 번 계산한 답을 쓰고, 동시에 온 같은 요청은 먼저 온 계산을 기다린다. 시세(관측 기록)가 바뀌어도
    # MEMO_TTL초 뒤에는 새로 계산한다
    memo_vals: dict = {}
    memo_locks: dict = {}
    memo_guard = threading.Lock()

    def memo(kind: str, name: str, date: str | None, params: tuple, compute):
        try:
            stamp = cache.fetched(name, dt.date.fromisoformat(date) if date else None)
        except ValueError:
            stamp = None
        if stamp is None:
            return compute()
        key = (kind, name.casefold(), date, stamp, params)
        with memo_guard:
            for k in [k for k, (_, at) in memo_vals.items() if clock() - at >= MEMO_TTL]:
                del memo_vals[k]
            if len(memo_locks) > 2000:
                for k in [k for k, v in memo_locks.items() if not v.locked()]:
                    del memo_locks[k]
            lock = memo_locks.setdefault(key, threading.Lock())
        with lock:
            hit = memo_vals.get(key)
            if hit is not None and clock() - hit[1] < MEMO_TTL:
                return hit[0]
            out = compute()
            with memo_guard:
                memo_vals[key] = (out, clock())
                while len(memo_vals) > MEMO_SIZE:
                    memo_vals.pop(next(iter(memo_vals)))
            return out

    def pick(snap, boss_defense: float, boss: str | None = None, arcane_force: int | None = None,
             authentic_force: int | None = None):
        """(스냅샷, 보스): boss(보스 목록 id)가 있으면 그 방어율·요구 포스, 없으면 boss_defense 숫자(하위 호환)."""
        try:
            return service.choose(snap, boss_defense, boss, arcane_force, authentic_force)
        except KeyError:
            raise ApiError(400, "BAD_BOSS", f"보스 목록에 없는 보스예요: {boss}") from None

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/bosses")
    def bosses():
        """보스 목록(방어율·요구 포스·출처). engine/data/bosses.json 그대로."""
        from engine.stats.force import CHECKED, boss_list
        return {"checked": CHECKED, "bosses": boss_list()}

    @app.get("/api/character/{name}")
    def character(name: str, date: str | None = None):
        out = service.summary(load(name, date))
        since = stale_since.get((name.casefold(), dt.date.fromisoformat(date) if date else None))
        out["stale_minutes"] = None if since is None else int((clock() - since) // 60)
        return out

    @app.get("/api/character/{name}/settings")
    def settings(name: str, boss_defense: float = 300.0, date: str | None = None, boss: str | None = None, arcane_force: int | None = None, authentic_force: int | None = None):
        snap, b = pick(load(name, date), boss_defense, boss, arcane_force, authentic_force)
        return memo("settings", name, date, (boss_defense, boss, arcane_force, authentic_force), lambda: service.settings(snap, b))

    @app.get("/api/character/{name}/recommend")
    def recommend(name: str, boss_defense: float = 300.0, top: int = 5, cooldown_main_pct: float | None = None,
                  date: str | None = None, boss: str | None = None, arcane_force: int | None = None, authentic_force: int | None = None):
        snap, b = pick(load(name, date), boss_defense, boss, arcane_force, authentic_force)
        return memo("recommend", name, date, (boss_defense, boss, arcane_force, authentic_force, top, cooldown_main_pct),
                    lambda: service.recommend(snap, b, max(1, min(top, 20)), cooldown_main_pct))

    @app.get("/api/character/{name}/roadmap")
    def roadmap(name: str, boss_defense: float = 300.0, cooldown_main_pct: float | None = None, date: str | None = None,
                miracle: bool = False, boss: str | None = None, arcane_force: int | None = None, authentic_force: int | None = None):
        snap, b = pick(load(name, date), boss_defense, boss, arcane_force, authentic_force)
        return memo("roadmap", name, date, (boss_defense, boss, arcane_force, authentic_force, cooldown_main_pct, miracle),
                    lambda: service.roadmap(snap, b, cooldown_main_pct, prices.rows(), miracle=miracle))

    @app.get("/api/character/{name}/swaps")
    def swaps(name: str, boss_defense: float = 300.0, cooldown_main_pct: float | None = None, date: str | None = None,
              boss: str | None = None, arcane_force: int | None = None, authentic_force: int | None = None, per_slot: int = 3,
              starforce: int = 18):
        """다른 템으로 갈아타기: 부위마다 다른 템(세트)을 끼면 실딜이 어떻게 되는지와 손익분기(잠재·추옵)."""
        snap, b = pick(load(name, date), boss_defense, boss, arcane_force, authentic_force)
        if starforce not in SWAP_STARS:  # 고를 수 있는 성(2026-11-16 사용자: 17 18 21 22가 대표적)
            return JSONResponse({"detail": f"스타포스는 {', '.join(map(str, SWAP_STARS))}성 중에서 골라 주세요"}, status_code=422)
        return memo("swaps", name, date, (boss_defense, boss, arcane_force, authentic_force, cooldown_main_pct, per_slot, starforce),
                    lambda: service.swaps(snap, b, cooldown_main_pct, max(1, min(per_slot, 10)), starforce))

    @app.get("/api/character/{name}/armor-sets")
    def armor_sets(name: str, boss_defense: float = 300.0, cooldown_main_pct: float | None = None, date: str | None = None,
                   boss: str | None = None, arcane_force: int | None = None, authentic_force: int | None = None,
                   starforce: int = 18):
        """방어구 세트 조합: 카루타·앱솔·아케인·에테르넬을 칸마다 맞췄을 때 실딜(3카5앱 같은 조합)."""
        if starforce not in SWAP_STARS:
            return JSONResponse({"detail": f"스타포스는 {', '.join(map(str, SWAP_STARS))}성 중에서 골라 주세요"}, status_code=422)
        snap, b = pick(load(name, date), boss_defense, boss, arcane_force, authentic_force)
        return memo("armor-sets", name, date, (boss_defense, boss, arcane_force, authentic_force, cooldown_main_pct, starforce),
                    lambda: service.armor_sets(snap, b, cooldown_main_pct, starforce))

    @app.post("/api/character/{name}/listings")
    def listings(name: str, body: ListingsIn, date: str | None = None):
        snap, b = pick(load(name, date), body.boss_defense, body.boss, body.arcane_force, body.authentic_force)
        setting = Setting(**body.setting.model_dump()) if body.setting else None
        try:
            return service.listings(snap, setting, b, body.listings, body.fee_rate)
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
        snap, b = pick(load(name, date), body.boss_defense, body.boss, body.arcane_force, body.authentic_force)
        setting = Setting(**body.setting.model_dump()) if body.setting else None
        try:
            return service.optimize(snap, setting, b, body.budget, body.candidates, body.fee_rate)
        except ValueError as e:
            raise ApiError(422, "INVALID_INPUT", str(e)) from None

    class LoginIn(BaseModel):
        password: str

    # 공개 AI 상담 입력(2026-10-17 점검): 역할은 user·assistant만, 내용은 글자만, 수·길이 상한 — 시스템 지시 덮어쓰기·
    # 이미지 끼워 넣기·초대형 입력으로 키를 범용으로 쓰거나 토큰 한도를 한 번에 태우지 못하게
    from typing import Literal

    class ChatMsg(BaseModel):
        role: Literal["user", "assistant"]
        content: str = Field(min_length=1, max_length=12000)

    class ChatIn(BaseModel):
        messages: list[ChatMsg] = Field(min_length=1, max_length=20)

    @app.get("/api/admin/session")
    def admin_session(request: Request):
        """관리자 로그인 상태(쿠키) — 캐릭터 화면이 관리자에게만 AI 상담을 보인다(2026-10-12)."""
        return {"admin": bool(session_secret) and admin.valid_session(request.cookies.get(admin.COOKIE), session_secret, clock())}

    # 로그인 무차별 대입 방어(2026-10-17): IP당 15분에 5번, 사이트 전체 1시간에 30번. 잠긴 동안은 맞는 비밀번호도 막는다
    login_ip_limiter = SlidingWindow(5, 900.0, clock)
    login_all_limiter = SlidingWindow(30, 3600.0, clock)

    @app.post("/api/admin/login")
    def login(body: LoginIn, request: Request):
        if not (admin_password_hash and session_secret):
            raise ApiError(503, "ADMIN_DISABLED", "관리자 기능이 설정되지 않았습니다(ADMIN_PASSWORD_HASH·SESSION_SECRET).")
        ip = request.client.host if request.client else "unknown"
        if not (login_ip_limiter.allow(ip) and login_all_limiter.allow("all")):
            raise ApiError(429, "LOGIN_LOCKED", "로그인 시도가 너무 많아요. 15분 뒤 다시 시도해 주세요.")
        if not admin.check_password(body.password, admin_password_hash):
            _log.warning("관리자 로그인 실패")
            raise ApiError(401, "BAD_PASSWORD", "비밀번호가 틀렸습니다.")
        r = JSONResponse({"status": "ok"})
        r.set_cookie(admin.COOKIE, admin.sign_session(session_secret, clock()), max_age=admin.SESSION_TTL,
                     httponly=True, samesite="strict", secure=request.url.scheme == "https")  # 운영은 HTTPS(프록시 헤더)
        return r

    @app.post("/api/admin/logout")
    def logout():
        """관리자 쿠키를 지운다(2026-10-17). 모든 기기에서 한꺼번에 끊으려면 SESSION_SECRET을 바꾼다."""
        r = JSONResponse({"status": "ok"})
        r.delete_cookie(admin.COOKIE)
        return r

    def _is_admin(request: Request) -> bool:
        return bool(session_secret) and admin.valid_session(request.cookies.get(admin.COOKIE), session_secret, clock())

    def _agent_who(request: Request) -> str:
        return _quota_who(request.client.host if request.client else "unknown", "agent")

    @app.get("/api/agent/quota")
    def agent_quota(request: Request):
        """AI 상담 남은 횟수(2026-10-17 공개): 관리자는 제한 없음, 일반 사용자는 IP당 하루 agent_public_daily번."""
        if _is_admin(request):
            return {"admin": True, "limit": None, "remaining": None}
        return {"admin": False, "limit": agent_public_daily,
                "remaining": max(0, agent_public_daily - _quota_used(_agent_who(request)))}

    @app.post("/api/agent/chat")
    def agent_chat(body: ChatIn, request: Request):
        # 모두에게 연다(2026-10-17 사용자). 일반 사용자는 IP당 하루 질문 수 제한 + 웹 경매장 검색(refresh_market) 없음
        is_admin = _is_admin(request)
        if agent_client is None:
            raise ApiError(503, "AGENT_DISABLED", "에이전트가 설정되지 않았습니다(OPENAI_API_KEY).")
        if sum(len(m.content) for m in body.messages) > 40000:
            raise ApiError(422, "INVALID_INPUT", "대화가 너무 길어요. 새 대화로 다시 물어봐 주세요.")
        from agent.loop import run_agent
        from agent.tools import ToolBox
        who = None if is_admin else _agent_who(request)
        if who is not None and _quota_take(who) > agent_public_daily:  # 먼저 차감하고 비교(동시 요청 틈 없음), DB 오류면 막는다
            raise ApiError(429, "AGENT_QUOTA", f"오늘 AI 상담 한도({agent_public_daily}번)를 다 썼어요. 내일 다시 써 주세요.")
        messages = [m.model_dump() for m in body.messages]

        def events():
            if usage.used() >= agent_daily_token_budget:
                yield {"type": "error", "message": f"오늘 에이전트 토큰 한도({agent_daily_token_budget:,})를 다 썼어요. 내일 다시 이용해 주세요."}
                yield {"type": "done", "unverified_numbers": []}
                return
            yield from run_agent(agent_client, ToolBox(lambda name, date=None: load(name, date), market=prices.rows,
                                                      refresh=_agent_refresh if is_admin else None), messages,
                                 on_usage=usage.add, max_tokens=None if is_admin else agent_public_request_tokens,
                                 max_turns=8 if is_admin else 6, exclude_tools=() if is_admin else ("refresh_market",),
                                 tracer=agent_tracer, trace_user="admin" if is_admin else who,
                                 trace_meta={"public": not is_admin}, public_errors=not is_admin)

        def sse():
            # 도구 계산·모델 응답을 기다리는 동안 agent_ping_seconds마다 SSE 주석을 보내 연결을 살린다
            # (2026-10-12: 데모에서 31초 도구 + 모델 응답 동안 조용해 끊겨 '호출'에서 멈췄다)
            import queue
            import threading
            q: queue.Queue = queue.Queue()
            end = object()

            def work():
                try:
                    for e in events():
                        if not is_admin and e.get("type") == "tool_result":
                            e = {"type": "tool_result", "name": e.get("name")}  # 공개 사용자에게는 도구 결과 본문을 보내지 않는다
                        q.put(e)
                finally:
                    try:
                        agent_tracer.flush()  # 무료 서버는 곧 잠들 수 있다 — 대화가 끝나면 바로 보낸다
                    except Exception as e:  # noqa: BLE001
                        _log.warning("추적 전송 실패: %s", type(e).__name__)
                    q.put(end)

            threading.Thread(target=work, daemon=True).start()
            while True:
                try:
                    e = q.get(timeout=agent_ping_seconds)
                except queue.Empty:
                    yield ": ping\n\n"
                    continue
                if e is end:
                    return
                yield "data: " + json.dumps(e, ensure_ascii=False, default=str) + "\n\n"

        return StreamingResponse(sse(), media_type="text/event-stream")

    class VisionIn(BaseModel):
        image: str
        name: str | None = None
        boss_defense: float = 300.0
        boss: str | None = None
        setting: dict | None = None
        seen: list[str] = []
        tooltips_only: bool = True  # 툴팁 없는 화면은 AI에 보내지 않는다(목록 화면도 읽으려면 false)
        scan_id: str | None = Field(None, max_length=64)  # 화면 연결마다 새로(인식 개수를 연결 단위로 센다)

    @app.get("/api/character/{name}/consult")
    def consult(name: str, boss_defense: float = 300.0, cooldown_main_pct: float | None = None, date: str | None = None,
                boss: str | None = None, arcane_force: int | None = None, authentic_force: int | None = None, sf: str | None = None):
        """목표 세팅 컨설팅: 성(17·18·21·22)마다 한 번에 갈아탈 방어구·장신구 세팅과 살 템·강화 비용.
        sf: 강화 비용에 넣을 스타포스 이벤트(쉼표: shining, discount30, destroy_down30, guarantee_5_10_15, restore_discount20, protect)."""
        events = sf_events(sf)
        snap, b = pick(load(name, date), boss_defense, boss, arcane_force, authentic_force)
        return memo("consult", name, date, (boss_defense, boss, arcane_force, authentic_force, cooldown_main_pct, events),
                    lambda: service.consult(snap, b, cooldown_main_pct, events))

    def sf_events(sf: str | None):
        from engine.market.events import Events
        try:
            return Events.parse(sf)
        except ValueError as e:
            raise ApiError(400, "BAD_EVENTS", str(e)) from None

    @app.get("/api/character/{name}/consult/mix")
    def consult_mix(name: str, star: int = Query(22, ge=0, le=25), budget: float | None = Query(None, ge=0, le=1e16),
                    total: float | None = Query(None, ge=0, le=1e16), prices: float = Query(0, ge=0, le=1e16),
                    boss_defense: float = 300.0, cooldown_main_pct: float | None = None, date: str | None = None,
                    boss: str | None = None, arcane_force: int | None = None, authentic_force: int | None = None,
                    sf: str | None = None):
        """섞은 목표: 큐브에 쓸 메소(budget) 안에서 칸마다 잠재·에디 목표를 따로 고른 조합과 그 정확한 보스 실딜.
        total(가진 메소 전체)을 주면 성까지 같이 고른다 — 성마다 강화 평균과 prices(넣은 살 템 시세)를 빼고 잰다."""
        if (budget is None) == (total is None):
            raise ApiError(422, "BAD_REQUEST", "budget(큐브에 쓸 메소)과 total(가진 메소 전체) 중 하나만 주세요.")
        events = sf_events(sf)
        snap, b = pick(load(name, date), boss_defense, boss, arcane_force, authentic_force)
        if total is not None:
            total, prices = float(int(total // 1e8) * 1e8), float(int(prices // 1e8) * 1e8)
            return memo("consult_best", name, date, (total, prices, boss_defense, boss, arcane_force, authentic_force, cooldown_main_pct, events),
                        lambda: service.consult_best(snap, b, total, prices, cooldown_main_pct, events))
        budget = float(int(budget // 1e8) * 1e8)              # 1억 단위(같은 계산을 다시 쓰게)
        return memo("consult_mix", name, date, (star, budget, boss_defense, boss, arcane_force, authentic_force, cooldown_main_pct),
                    lambda: service.consult_mix(snap, b, star, budget, cooldown_main_pct))

    @app.get("/api/character/{name}/paths")
    def upgrade_paths(name: str, boss_defense: float = 300.0, cooldown_main_pct: float | None = None,
                      date: str | None = None, sf: str | None = None, miracle: bool = False,
                      spare_price: float | None = None, fragment_price: float | None = None, hexa_sunday: bool = False,
                      spare_by_slot: str | None = None, flame_prices: str | None = None, boss: str | None = None, arcane_force: int | None = None, authentic_force: int | None = None):
        """sf: 스타포스 이벤트(쉼표: shining, discount30, destroy_down30, guarantee_5_10_15, restore_discount20, protect),
        miracle: 미라클 타임, spare_price: 파괴 시 스페어 1개 값(메소), fragment_price: 솔 에르다 조각 1개 값(메소, HEXA 경로),
        hexa_sunday: HEXA 스탯 썬데이(메인 5레벨 이상 확률 ×1.2),
        flame_prices: 환생의 불꽃 1개 값 '불꽃:메소'를 쉼표로(강력·타오르는·영원·검은·심연, 추옵 경로)."""
        from engine.market.events import Events
        try:
            events = Events.parse(sf, miracle, spare_price, fragment_price, hexa_sunday, spare_by_slot, flame_prices)
        except ValueError as e:
            raise ApiError(400, "BAD_EVENTS", str(e)) from None
        snap, b = pick(load(name, date), boss_defense, boss, arcane_force, authentic_force)
        return memo("paths", name, date, (boss_defense, boss, arcane_force, authentic_force, cooldown_main_pct, sf, miracle, spare_price,
                                         fragment_price, hexa_sunday, spare_by_slot, flame_prices),
                    lambda: service.paths(snap, b, prices.rows(), cooldown_main_pct, events=events))

    @app.get("/api/character/{name}/target-roadmap")
    def target_roadmap(name: str, current_ratio: float, target_ratio: float = 50.0, boss_defense: float = 300.0,
                       date: str | None = None, sf: str | None = None, miracle: bool = False,
                       spare_price: float | None = None, fragment_price: float | None = None, hexa_sunday: bool = False,
                      spare_by_slot: str | None = None, boss: str | None = None, arcane_force: int | None = None, authentic_force: int | None = None):
        """목표 배율 로드맵: current_ratio(지금 보스 배율 %, 예: MapleScouter 효율·보스컷) → target_ratio."""
        from engine.market.events import Events
        if current_ratio <= 0 or target_ratio <= 0:
            raise ApiError(400, "BAD_RATIO", "배율은 0보다 커야 해요.")
        try:
            events = Events.parse(sf, miracle, spare_price, fragment_price, hexa_sunday, spare_by_slot)
        except ValueError as e:
            raise ApiError(400, "BAD_EVENTS", str(e)) from None
        snap, b = pick(load(name, date), boss_defense, boss, arcane_force, authentic_force)
        return service.target_roadmap(snap, b, prices.rows(), current_ratio, target_ratio, events)

    @app.get("/api/character/{name}/budget-roadmap")
    def budget_roadmap(name: str, budget: float | None = None, steps: int | None = None, boss_defense: float = 300.0,
                       date: str | None = None, boss: str | None = None,
                       arcane_force: int | None = None, authentic_force: int | None = None):
        """업그레이드 계획: 억당 효율 순 단계와 누적 실딜. budget(가진 메소)이 있으면 그 안에서, 없으면 앞의 steps개."""
        if budget is not None and not service.MIN_BUDGET <= budget <= 1e13:
            raise ApiError(400, "BAD_BUDGET", "예산은 메소로 넣어 주세요(50억 → 5000000000).")
        if steps is not None and not 1 <= steps <= 120:
            raise ApiError(400, "BAD_STEPS", "단계 수는 1~120 사이여야 해요.")
        snap, b = pick(load(name, date), boss_defense, boss, arcane_force, authentic_force)
        return memo("budget-roadmap", name, date, (boss_defense, boss, arcane_force, authentic_force, budget, steps),
                    lambda: service.budget_roadmap(snap, b, prices.rows(), budget, steps))

    class MarketRefreshIn(BaseModel):
        name: str
        slots: list[str] | None = None
        max_searches: int = Field(15, ge=1, le=30)
        boss_defense: float = 300.0
        boss: str | None = None

    def _market_refresh(name: str, slots=None, max_searches: int = 15, boss_defense: float = 300.0,
                        boss: str | None = None) -> dict:
        if not auction_mcp_command:
            raise ApiError(503, "AUCTION_DISABLED",
                           "경매장 검색 연결이 꺼져 있어요. 로컬 PC에서 AUCTION_MCP_CMD(예: npx.cmd -y maple-auction-mcp)를 "
                           ".env에 넣고, 크롬에 maple-auction-mcp 확장을 설치해 웹 경매장에 로그인해 주세요.")
        from server.auction_mcp import McpUnavailable, refresh_market
        try:
            snap, b = pick(load(name, None), boss_defense, boss)
            return refresh_market(snap, auction_mcp_command, prices, slots, max_searches, b)
        except McpUnavailable as e:
            raise ApiError(503, "AUCTION_UNAVAILABLE", str(e)) from None

    @app.post("/api/market/refresh")
    def market_refresh(body: MarketRefreshIn, request: Request):
        """로드맵 다음 단계 조건으로 웹 경매장을 검색(판매 중·판매 완료)해 관측 시세에 넣는다(관리자, 일일 검색 한도 소진)."""
        if not (session_secret and admin.valid_session(request.cookies.get(admin.COOKIE), session_secret, clock())):
            raise ApiError(401, "UNAUTHORIZED", "관리자 로그인이 필요합니다.")
        return _market_refresh(body.name, body.slots, body.max_searches, body.boss_defense, body.boss)

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
        boss: str | None = None
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
        snap, b = pick(load(body.name, None), body.boss_defense, body.boss)
        return {"items": service.vision_items(snap, None, b, body.listings[:50], [])}

    @app.post("/api/vision/listings")
    def vision_listings(body: VisionIn, request: Request):
        """공유된 경매장 탭 캡처 → 매물 추출·평가. 넥슨 서버에는 요청하지 않는다(화면 픽셀만 읽는다).
        일반 유저도 쓴다(AI 판독 IP당 하루 상한). 학습 데이터 저장·장비창 채점 기록은 관리자 화면만."""
        is_admin = bool(session_secret) and admin.valid_session(request.cookies.get(admin.COOKIE), session_secret, clock())
        if len(body.image) > 6_000_000:
            raise ApiError(413, "IMAGE_TOO_LARGE", "화면 이미지가 너무 커요(최대 약 4MB).")
        if agent_client is None:
            raise ApiError(503, "AGENT_DISABLED", "AI 기능이 설정되지 않았습니다(OPENAI_API_KEY).")
        if not body.image.startswith("data:image/"):
            raise ApiError(422, "INVALID_INPUT", "이미지(data URL)가 필요합니다.")
        from server.vision import ImageTooLarge, VisionError, VisionQuota, analyze_frame
        ip = request.client.host if request.client else "unknown"
        who = _quota_who(ip)
        # AI를 부르기 직전에만 한도를 본다. 2026-11-25 실사용: 하루 토큰 한도가 차자 화면 평가 전체가 막혔다 — AI 없이 되는 일
        # (같은 툴팁 재사용, 툴팁 없는 화면 건너뛰기, 로컬 OCR 판독)까지 막을 이유가 없다
        blocked = []

        def allow_ai() -> bool:
            if usage.used() >= agent_daily_token_budget:
                blocked.append("budget")
                return False
            return is_admin or _quota_take(who) <= vision_public_daily  # 일반 사용자는 AI 판독 횟수를 차감
        scan = f"{who}:{body.scan_id}" if body.scan_id else None  # 다른 사용자의 스캔과 섞이지 않게 IP 해시를 붙인다
        on_tip = (lambda key, done: scans.mark(scan, key, done, clock())) if scan else None
        try:
            data = analyze_frame(agent_client, body.image, on_usage=usage.add, cache=frame_cache,
                                 tooltips_only=body.tooltips_only or not is_admin, allow_ai=allow_ai, on_tip=on_tip,
                                 ocr=ocr)
        except ImageTooLarge:
            raise ApiError(413, "IMAGE_TOO_LARGE", "화면 이미지가 너무 커요(4K 해상도 이하로 공유해 주세요).") from None
        except VisionQuota as e:
            extra = {"diag": {**e.diag, "kind": "AI 한도"}}  # 한도에 막혀도 진단은 돌려준다
            if blocked:
                raise ApiError(429, "TOKEN_BUDGET", f"오늘 AI 토큰 한도({agent_daily_token_budget:,})를 다 썼어요. "
                               "이미 읽은 매물과 AI 없이 읽히는 매물은 계속 평가돼요.", extra) from None
            raise ApiError(429, "VISION_QUOTA", f"오늘 화면 평가 한도({vision_public_daily}회)를 다 썼어요. 내일 다시 써 주세요.", extra) from None
        except VisionError as e:
            raise ApiError(422, "VISION_PARSE", str(e)) from None
        snap, vb = pick(load(body.name, None) if body.name else None, body.boss_defense, body.boss)
        setting = Setting(**body.setting) if body.setting else None
        from server.vision import normalize_fee, power_of
        # 툴팁이 목록의 가격 칸을 가린다(2026-11-13) — 툴팁이 뜨기 전 목록 화면에서 읽어 둔 줄 중
        # 전투력 증가량이 같은 줄의 가격을 붙인다(목록 읽기는 AI 없이, server/listprice.py)
        list_memory.remember(who, data.get("list_rows") or [], clock())
        for x in data["listings"]:
            if not x.get("price") and (price := list_memory.lookup(who, power_of(x), clock())):
                x["price"], x["price_source"] = price, "목록"
        for x in data["listings"]:
            # 공개 사용자 판독은 공용 시세(추천에 쓰임)에 넣지 않는다 — 조작한 툴팁으로 모두의 추천을 오염시키지 않게(2026-10-17).
            # 지우지 않는 관측 기록에는 출처를 '공개화면'으로 따로 남기고, 지금 시세(rows)는 이 출처를 읽지 않는다
            try:
                observations.record(x if is_admin else {**x, "source": PUBLIC_SOURCE})  # 영구 관측 기록(IP·이미지 없음)
            except Exception as e:  # noqa: BLE001 — DB가 잠깐 안 돼도 평가는 계속한다
                _log.warning("관측 기록 실패: %s", type(e).__name__)
        if is_admin and not data.get("cached"):
            session_reads.extend(data["listings"] + data.get("equipped_items", []))
        names = [x.get("name") for x in data["listings"] + data.get("equipped_items", [])]
        kind = f"건너뜀({data['skipped']})" if data.get("skipped") else "재사용" if data.get("cached") else "OCR 판독" if data.get("ocr") else "판독"
        _log.info("화면 %s · 툴팁 %s개 · %s", kind, data.get("tooltips_found", 0), ", ".join(n or "?" for n in names) or "-")
        from server.vision import list_log, price_log
        _log.info("목록 판독 · %s", list_log(data.get("frame_size"), data.get("list_rows") or []))
        if kind.endswith("판독") and (prices_read := price_log(data["listings"])):
            _log.info("가격 판독 · %s", prices_read)  # 2026-11-13: 80억 7999만 9999를 1,931,721로 읽음 — 화면 글자를 남겨 원인을 본다
        dataset_on = dataset if is_admin else None  # 일반 유저 화면은 저장하지 않는다
        if dataset_on:
            dataset.log_frame({"kind": kind, "tooltips": data.get("tooltips_found", 0), "names": names})
        if dataset_on and data.get("skipped") == "툴팁 없음":  # '판독 중'은 툴팁 화면 — 툴팁 없는 화면 모음에 넣지 않는다
            dataset.save_skipped(body.image, {"skipped": data["skipped"]})
        # 내 PC 학습 데이터(켜졌을 때만). 캐시로 돌려준 같은 화면은 다시 저장하지 않는다
        frame_id = (dataset.save_frame(body.image, data)
                    if dataset_on and not data.get("cached") and not data.get("skipped") else None)
        items = service.vision_items(snap, setting, vb, data["listings"], set(body.seen))
        for it in items:
            it["frame_id"] = frame_id
        return {"tooltip_visible": data["tooltip_visible"], "fee_rate": normalize_fee(data.get("fee_rate")),
                "frame_id": frame_id, "items": items,
                "equipped_items": data.get("equipped_items", []),  # 착용 템 판독(장비창 채점용, 매물 아님)
                "ai_remaining": None if is_admin else max(0, vision_public_daily - _quota_used(who)),
                # 진단(2026-11-25 실사용: 매물 4개에 '인식 13개', AI 판독 17회) — 왜 새 툴팁으로 봤는지·왜 AI로 넘어갔는지. 개인 정보 없음
                "diag": {**(data.get("diag") or {}), "kind": kind},
                **dict(zip(("recognized", "analyzing"), scans.counts(scan, clock()) if scan else (None, None)))}

    class VisionCorrectIn(BaseModel):
        frame_id: str
        signature: str
        name: str
        boss_defense: float = 300.0
        boss: str | None = None
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
        snap, b = pick(load(body.name, None), body.boss_defense, body.boss)
        item = service.vision_items(snap, None, b, [read], [])[0]
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
    from server import ocr as _ocr
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
                      agent_public_daily=int(_env("AGENT_PUBLIC_DAILY") or 5),
                      vision_frames_per_min=int(_env("VISION_FRAMES_PER_MIN") or 240),
                      baseline_dates=int(_env("BASELINE_DATES") or 0),  # 2026-11-24 사용자 결정: 끈다 — 3개 날짜로는 기준 없을 때보다 더 흔들리는 캐릭터가 있었다(7개면 3% 안). 켜려면 BASELINE_DATES
                      ocr=_ocr.lazy_reader())


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
