"""넥슨 Open API(메이플스토리 KMS) 동기 클라이언트.

오류 판정은 HTTP 상태가 아니라 본문의 `error` 키로 한다. 재시도하지 않는다 — 호출량 초과는 호출자에게 그대로 알린다.
"""
import datetime as dt
import os
import pathlib
import time

import httpx

BASE_URL = "https://open.api.nexon.com/maplestory/v1/"
EARLIEST = dt.date(2023, 12, 21)
ENDPOINTS = (
    "character/basic",
    "character/stat",
    "character/item-equipment",
    "character/set-effect",
    "character/hyper-stat",
    "character/ability",
    "character/symbol-equipment",
    "user/union-raider",
    "character/link-skill",
)


class NexonError(Exception):
    def __init__(self, code: str | None, message: str, status: int):
        super().__init__(f"[{code}] {message} (HTTP {status})")
        self.code = code
        self.message = message
        self.status = status


class CharacterNotFound(NexonError):
    """닉네임에 해당하는 캐릭터가 없다 (OPENAPI00004 on /id)."""


class RateLimited(NexonError):
    """API 호출량 초과 (OPENAPI00007)."""


class Unavailable(NexonError):
    """데이터 준비 중·게임 점검·API 점검 (OPENAPI00009/00010/00011)."""


class InvalidKey(NexonError):
    """키가 없거나 권한이 없다 (OPENAPI00002/00005)."""


_BY_CODE = {
    "OPENAPI00002": InvalidKey,
    "OPENAPI00005": InvalidKey,
    "OPENAPI00007": RateLimited,
    "OPENAPI00009": Unavailable,
    "OPENAPI00010": Unavailable,
    "OPENAPI00011": Unavailable,
}


def _is_empty(body: dict) -> bool:
    return all(v is None or v == [] or v == {} or v == "" for k, v in body.items() if k != "date")


class NexonClient:
    def __init__(self, api_key: str, *, transport: httpx.BaseTransport | None = None, min_interval: float = 0.25):
        self._http = httpx.Client(
            base_url=BASE_URL, headers={"x-nxopen-api-key": api_key}, transport=transport, timeout=10.0,
        )
        self._min_interval = min_interval
        self._last = 0.0

    def _request(self, path: str, params: dict) -> dict:
        wait = self._min_interval - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()
        r = self._http.get(path, params=params)
        try:
            body = r.json()
        except ValueError:
            body = {}
        err = body.get("error") if isinstance(body, dict) else None
        if err:
            code = err.get("name")
            raise _BY_CODE.get(code, NexonError)(code, err.get("message", ""), r.status_code)
        if r.status_code >= 400:
            raise NexonError(None, "알 수 없는 오류 응답", r.status_code)
        return body

    def get_ocid(self, name: str) -> str:
        try:
            return self._request("id", {"character_name": name})["ocid"]
        except NexonError as e:
            if e.code == "OPENAPI00004":
                raise CharacterNotFound(e.code, f"캐릭터를 찾을 수 없습니다: {name}", e.status) from e
            raise

    def get(self, endpoint: str, ocid: str, day: dt.date | None = None) -> dict | None:
        params = {"ocid": ocid}
        if day is not None:
            if day < EARLIEST:
                raise ValueError(f"{EARLIEST.isoformat()} 이후 날짜만 조회할 수 있습니다: {day.isoformat()}")
            params["date"] = day.isoformat()
        body = self._request(endpoint, params)
        return None if _is_empty(body) else body

    def fetch_bundle(self, name: str, day: dt.date | None = None) -> dict[str, dict | None]:
        ocid = self.get_ocid(name)
        return {ep: self.get(ep, ocid, day) for ep in ENDPOINTS}


def load_api_key(root: pathlib.Path) -> str:
    """환경변수 NEXON_API_KEY, 없으면 root/.env 에서 읽는다. 값은 출력하지 않는다."""
    if os.environ.get("NEXON_API_KEY"):
        return os.environ["NEXON_API_KEY"]
    env = root / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("NEXON_API_KEY=") and line.split("=", 1)[1].strip():
                return line.split("=", 1)[1].strip()
    raise RuntimeError("NEXON_API_KEY가 없습니다. 환경변수나 .env에 넣어 주세요.")
