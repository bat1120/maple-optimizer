# 1a단계: 수집·파싱·스탯공격력 검증 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 넥슨 Open API 응답을 받아 엔진 도메인 모델(최종 스탯, 프리셋별 장비·하이퍼·어빌리티 StatBlock)로 바꾸고, 엔진이 계산한 `최대 스탯공격력`이 표본 46명 전원에서 API 값과 일치함을 회귀 테스트로 고정한다.

**Architecture:** `engine/`은 표준 라이브러리만 쓰는 순수 Python 도메인 계층(옵션 문자열 파서, StatBlock, 직업·무기 테이블, 스탯공격력 공식). `nexon/`은 HTTP 클라이언트와 "넥슨 JSON → 엔진 타입" 변환만 담당한다. 테스트는 익명화한 실제 응답 fixture(46명, 2026-10-02~03 수집)로 돈다.

**Tech Stack:** Python 3.12, uv, httpx, pytest.

**Spec:** `docs/superpowers/specs/2026-10-03-maple-optimizer-design.md` (특히 §2 결정 표, §4 1a행, §5.1, §5.5, §9 넥슨 키 규칙)

## Global Constraints

- Python `>=3.12`, 패키지 관리 `uv`. 실행은 항상 `uv run ...`.
- `engine/`은 표준 라이브러리와 `engine` 자신만 import한다. httpx·넥슨 JSON 키 이름은 `engine/`에 등장하지 않는다.
- 넥슨 JSON 형태(키 이름)는 `nexon/` 안에서만 다룬다.
- API 키: 환경변수 `NEXON_API_KEY`, 없으면 저장소 루트 `.env`의 `NEXON_API_KEY=` 줄. 키 값을 출력·로그·예외 메시지에 넣지 않는다.
- 넥슨 API 베이스 URL `https://open.api.nexon.com/maplestory/v1/`, 인증 헤더 `x-nxopen-api-key`. 개발 단계 키 한도 5건/초, 1,000건/일.
- `date` 파라미터 형식 `YYYY-MM-DD`(KST), 최소 `2023-12-21`. 생략하면 현재 데이터(평균 15분 지연).
- 테스트 fixture는 익명화한다: `character_name`, `character_guild_name`, `character_image`, `*_icon`, `item_description` 키 제거. 원본(`.raw/`)은 git에 넣지 않는다(이미 `.gitignore`).
- 넥슨 약관: 크롤링한 데이터는 30일 이내 갱신 의무가 있다. fixture는 테스트용 익명 데이터로만 쓰고 서비스 데이터로 쓰지 않는다.
- 스탯공격력 일치 기준: 상대 오차 `< 1e-4` (0.01%).
- 지원하지 않는 직업(데몬어벤져)·모르는 무기는 숫자를 추정하지 않고 예외로 알린다.
- 주석·docstring·커밋 메시지는 한국어. 커밋 메시지 끝에 `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.

## Review Focus

1. **구 표기 잠재 문자열**(`"STR : +12%"`, `"보스 몬스터 공격 시 데미지 : +40%"`, `"캐릭터 기준 10레벨 당 STR : +2"`) — 과거 `date` 조회 시 나온다. 신 표기와 같은 StatLine으로 해석돼야 한다. → Task 3에 테스트.
2. **데이터 없는 날짜**(캐릭터 생성 전 등) — 본문에 `date`만 있고 나머지가 null/빈 값이다. 예외가 아니라 `None`을 돌려줘야 한다. → Task 2에 테스트.
3. **지원 안 되는 직업·무기**(데몬어벤져, 표에 없는 무기 종류, 처음 보는 직업명) — 틀린 숫자 대신 `UnsupportedJob`/`UnknownWeapon`. → Task 4에 테스트.
4. **숫자 필드의 str/int 혼재와 음수**(`"129"`와 `129`, `"AP 배분 HP": "-633"`, `"116.00"`) — 변환이 깨지지 않아야 한다. → Task 5에 테스트.
5. **닉네임 없음·호출량 초과** — 닉네임 오류는 `OPENAPI00004`로 오고 `CharacterNotFound`로, 429는 `RateLimited`로 구분되며 재시도 폭주가 없어야 한다. → Task 2에 테스트.

---

## File Structure

```
maple-optimizer/
├── pyproject.toml
├── engine/
│   ├── __init__.py
│   ├── options.py            옵션 문자열 → StatLine (잠재 신·구 표기, 하이퍼, 어빌리티, 세트)
│   └── stats/
│       ├── __init__.py
│       ├── model.py          StatBlock, FinalStats
│       ├── jobs.py           JobProfile, 직업 테이블, UnsupportedJob
│       ├── weapons.py        무기 상수 테이블, UnknownWeapon
│       ├── formula.py        stat_value, stat_attack_max
│       └── snapshot.py       Item, CharacterSnapshot
├── nexon/
│   ├── __init__.py
│   ├── client.py             NexonClient, 예외, load_api_key
│   └── convert.py            넥슨 JSON → FinalStats / Item / CharacterSnapshot
├── tools/
│   ├── build_fixtures.py     .raw → tests/fixtures 익명화 복사
│   └── check_character.py    실캐릭터 스모크: 엔진 vs API 스탯공격력
└── tests/
    ├── helpers.py            fixture 로더
    ├── fixtures/characters/<직업>/*.json
    ├── test_fixtures.py
    ├── test_client.py
    ├── test_options.py
    ├── test_stats_core.py
    ├── test_stat_attack_fixtures.py
    └── test_snapshot.py
```

---

### Task 1: 프로젝트 골격과 익명화 fixture

**Files:**
- Create: `pyproject.toml`, `engine/__init__.py`, `engine/stats/__init__.py`, `nexon/__init__.py`
- Create: `tools/build_fixtures.py`
- Create: `tests/helpers.py`, `tests/test_fixtures.py`
- Create (생성물): `tests/fixtures/characters/<직업>/*.json`

**Interfaces:**
- Consumes: `.raw/<캐릭터명>/<endpoint>.json` (이미 수집됨, 46개 디렉터리 + 루트에 `ranking.json`, `boss_now.json` 파일)
- Produces: `tests/helpers.py`의 `ENDPOINTS: tuple[str, ...]`, `classes() -> list[str]`, `load(cls: str, endpoint: str) -> dict`, `bundle(cls: str) -> dict[str, dict]`

- [ ] **Step 1: pyproject와 빈 패키지 만들기**

`pyproject.toml`:
```toml
[project]
name = "maple-optimizer"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["httpx>=0.27"]

[dependency-groups]
dev = ["pytest>=8"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["engine", "nexon"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

`engine/__init__.py`, `engine/stats/__init__.py`, `nexon/__init__.py`: 각각 한 줄 docstring.
```python
"""메이플 장비 최적화 계산 엔진 (표준 라이브러리만 사용)."""
```
```python
"""스탯 모델과 공식."""
```
```python
"""넥슨 Open API 클라이언트와 응답 변환."""
```

Run: `uv sync`
Expected: `.venv` 생성, httpx·pytest 설치.

- [ ] **Step 2: fixture 테스트 작성 (실패 확인용)**

`tests/helpers.py`:
```python
"""테스트용 fixture 로더. 익명화된 실제 넥슨 응답을 직업명 디렉터리에서 읽는다."""
import json
import pathlib

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "characters"
ENDPOINTS = (
    "character/basic",
    "character/stat",
    "character/item-equipment",
    "character/set-effect",
    "character/hyper-stat",
    "character/ability",
    "character/symbol-equipment",
    "user/union-raider",
)


def classes() -> list[str]:
    return sorted(p.name for p in FIXTURES.iterdir() if p.is_dir())


def load(cls: str, endpoint: str) -> dict:
    path = FIXTURES / cls / (endpoint.replace("/", "_") + ".json")
    return json.loads(path.read_text(encoding="utf-8"))


def bundle(cls: str) -> dict[str, dict]:
    return {ep: load(cls, ep) for ep in ENDPOINTS}
```

`tests/test_fixtures.py`:
```python
import json

from helpers import ENDPOINTS, FIXTURES, classes, load

FORBIDDEN = {"character_name", "character_guild_name", "character_image", "item_description"}


def _keys(o):
    if isinstance(o, dict):
        for k, v in o.items():
            yield k
            yield from _keys(v)
    elif isinstance(o, list):
        for x in o:
            yield from _keys(x)


def test_46_classes_with_all_endpoints():
    cs = classes()
    assert len(cs) == 46
    assert "레테" in cs and "제논" in cs and "데몬어벤져" in cs
    for c in cs:
        for ep in ENDPOINTS:
            assert (FIXTURES / c / (ep.replace("/", "_") + ".json")).exists(), (c, ep)


def test_fixtures_are_anonymized():
    for c in classes():
        for ep in ENDPOINTS:
            keys = set(_keys(load(c, ep)))
            assert not keys & FORBIDDEN, (c, ep, keys & FORBIDDEN)
            assert not any(k.endswith("_icon") for k in keys), (c, ep)


def test_directory_name_matches_character_class():
    for c in classes():
        assert load(c, "character/basic")["character_class"] == c
```

Run: `uv run pytest tests/test_fixtures.py -v`
Expected: FAIL (`FileNotFoundError` — `tests/fixtures/characters` 없음)

- [ ] **Step 3: 익명화 복사 스크립트 작성**

`tools/build_fixtures.py`:
```python
"""`.raw/<캐릭터명>/*.json`(수집 원본)을 익명화해 `tests/fixtures/characters/<직업>/`로 복사한다.

직업명이 겹치면 멈춘다(fixture는 직업당 1명). `.raw/` 바로 아래의 파일(ranking.json 등)은 건너뛴다.
"""
import json
import pathlib
import shutil

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / ".raw"
OUT = ROOT / "tests" / "fixtures" / "characters"
DROP_KEYS = {"character_name", "character_guild_name", "character_image", "item_description"}


def scrub(o):
    if isinstance(o, dict):
        return {k: scrub(v) for k, v in o.items() if k not in DROP_KEYS and not k.endswith("_icon")}
    if isinstance(o, list):
        return [scrub(x) for x in o]
    return o


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    for d in sorted(p for p in RAW.iterdir() if p.is_dir()):
        basic = json.loads((d / "character_basic.json").read_text(encoding="utf-8"))
        dst = OUT / basic["character_class"]
        if dst.exists():
            raise SystemExit(f"직업 중복: {basic['character_class']}")
        dst.mkdir(parents=True)
        for f in sorted(d.glob("*.json")):
            data = scrub(json.loads(f.read_text(encoding="utf-8")))
            (dst / f.name).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        print(dst.name)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 스크립트 실행 후 테스트 통과 확인**

Run: `uv run python tools/build_fixtures.py`
Expected: 직업명 46줄 출력.

Run: `uv run pytest tests/test_fixtures.py -v`
Expected: 3 passed

- [ ] **Step 5: 커밋**

```bash
git add pyproject.toml uv.lock engine nexon tools/build_fixtures.py tests
git commit -m "프로젝트 골격과 익명화 fixture 46명 추가

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: 넥슨 API 클라이언트

**Files:**
- Create: `nexon/client.py`
- Test: `tests/test_client.py`

**Interfaces:**
- Consumes: 없음
- Produces:
  - `ENDPOINTS: tuple[str, ...]` (Task 1 `tests/helpers.py`와 같은 8개, 같은 순서)
  - `EARLIEST: datetime.date = date(2023, 12, 21)`
  - 예외: `NexonError(code: str | None, message: str, status: int)`와 하위 `CharacterNotFound`, `RateLimited`, `Unavailable`, `InvalidKey`
  - `NexonClient(api_key: str, *, transport: httpx.BaseTransport | None = None, min_interval: float = 0.25)`
    - `.get_ocid(name: str) -> str`
    - `.get(endpoint: str, ocid: str, day: date | None = None) -> dict | None` (데이터 없는 날 → `None`)
    - `.fetch_bundle(name: str, day: date | None = None) -> dict[str, dict | None]`
  - `load_api_key(root: pathlib.Path) -> str`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_client.py`:
```python
import datetime as dt
import json

import httpx
import pytest

from nexon.client import (
    ENDPOINTS, CharacterNotFound, InvalidKey, NexonClient, NexonError, RateLimited, Unavailable, load_api_key,
)


def make_client(handler):
    return NexonClient("test-key", transport=httpx.MockTransport(handler), min_interval=0)


def err(status, code, msg="x"):
    return httpx.Response(status, json={"error": {"name": code, "message": msg}})


def test_sends_key_header_and_returns_ocid():
    seen = {}

    def handler(req):
        seen["key"] = req.headers["x-nxopen-api-key"]
        seen["url"] = str(req.url)
        return httpx.Response(200, json={"ocid": "abc"})

    assert make_client(handler).get_ocid("내신부레테") == "abc"
    assert seen["key"] == "test-key"
    assert seen["url"].startswith("https://open.api.nexon.com/maplestory/v1/id?character_name=")


def test_unknown_name_raises_character_not_found():
    c = make_client(lambda req: err(400, "OPENAPI00004", "Please input valid parameter"))
    with pytest.raises(CharacterNotFound):
        c.get_ocid("없는캐릭터")


def test_rate_limit_raises_without_retry():
    calls = []

    def handler(req):
        calls.append(1)
        return err(429, "OPENAPI00007")

    with pytest.raises(RateLimited):
        make_client(handler).get("character/stat", "abc")
    assert len(calls) == 1


@pytest.mark.parametrize("status,code,exc", [
    (400, "OPENAPI00009", Unavailable),
    (400, "OPENAPI00010", Unavailable),
    (503, "OPENAPI00011", Unavailable),
    (400, "OPENAPI00005", InvalidKey),
    (403, "OPENAPI00002", InvalidKey),
    (500, "OPENAPI00001", NexonError),
])
def test_error_codes_map_to_exceptions(status, code, exc):
    with pytest.raises(exc) as info:
        make_client(lambda req: err(status, code)).get("character/stat", "abc")
    assert info.value.code == code
    assert info.value.status == status


def test_error_message_never_contains_key():
    with pytest.raises(NexonError) as info:
        make_client(lambda req: err(400, "OPENAPI00005")).get("character/stat", "abc")
    assert "test-key" not in str(info.value)


def test_date_param_and_lower_bound():
    seen = {}

    def handler(req):
        seen["date"] = req.url.params.get("date")
        return httpx.Response(200, json={"date": "2026-10-01T00:00+09:00", "character_class": "레테", "final_stat": [{"stat_name": "STR", "stat_value": "1"}]})

    c = make_client(handler)
    c.get("character/stat", "abc", dt.date(2026, 10, 1))
    assert seen["date"] == "2026-10-01"
    with pytest.raises(ValueError):
        c.get("character/stat", "abc", dt.date(2023, 12, 20))


def test_empty_day_returns_none():
    body = {"date": "2026-07-01T00:00+09:00", "character_class": None, "final_stat": [], "remain_ap": None}
    assert make_client(lambda req: httpx.Response(200, json=body)).get("character/stat", "abc", dt.date(2026, 7, 1)) is None


def test_zero_values_are_not_empty():
    body = {"date": None, "character_class": "레테", "remain_ap": 0, "final_stat": [{"stat_name": "STR", "stat_value": "0"}]}
    assert make_client(lambda req: httpx.Response(200, json=body)).get("character/stat", "abc") == body


def test_fetch_bundle_calls_all_endpoints():
    paths = []

    def handler(req):
        paths.append(req.url.path)
        if req.url.path.endswith("/id"):
            return httpx.Response(200, json={"ocid": "abc"})
        return httpx.Response(200, json={"date": None, "x": 1})

    b = make_client(handler).fetch_bundle("내신부레테")
    assert list(b) == list(ENDPOINTS)
    assert len(paths) == 1 + len(ENDPOINTS)


def test_load_api_key_prefers_env(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("NEXON_API_KEY=from-file\n", encoding="utf-8")
    monkeypatch.setenv("NEXON_API_KEY", "from-env")
    assert load_api_key(tmp_path) == "from-env"
    monkeypatch.delenv("NEXON_API_KEY")
    assert load_api_key(tmp_path) == "from-file"


def test_load_api_key_missing_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("NEXON_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        load_api_key(tmp_path)
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_client.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'nexon.client'`)

- [ ] **Step 3: 구현**

`nexon/client.py`:
```python
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
```

- [ ] **Step 4: 통과 확인**

Run: `uv run pytest tests/test_client.py -v`
Expected: 모두 PASS (16 passed — 파라미터화 6개 포함)

- [ ] **Step 5: 커밋**

```bash
git add nexon/client.py tests/test_client.py
git commit -m "넥슨 API 클라이언트: 오류 코드별 예외, 빈 날짜 None, 키 로딩

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: 옵션 문자열 파서

**Files:**
- Create: `engine/options.py`
- Test: `tests/test_options.py`

**Interfaces:**
- Consumes: Task 1 fixture (`helpers.classes`, `helpers.load`) — fixture 전수 테스트에만
- Produces:
  - `StatLine(key: str, value: float, percent: bool)` (frozen dataclass). `key` ∈ `STR DEX INT LUK HP ATK MATK DMG BOSS IED CD CR FD`
  - `parse_option(text: str, level: int) -> list[StatLine] | None`
    - 인식했고 딜과 관련된 옵션 → StatLine 리스트(올스탯·공격력과 마력처럼 여러 개일 수 있음)
    - 인식했지만 딜과 무관(드롭률, 메소, 스킬 사용 가능 등) → `[]`
    - 인식 못 함 → `None` (호출자가 "계산 제외"로 기록)

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_options.py`:
```python
import re

import pytest

from engine.options import StatLine, parse_option
from helpers import classes, load

L = 287


@pytest.mark.parametrize("text,expected", [
    # 신 표기 잠재
    ("STR +12%", [StatLine("STR", 12, True)]),
    ("INT +6", [StatLine("INT", 6, False)]),
    ("올스탯 +9%", [StatLine(k, 9, True) for k in ("STR", "DEX", "INT", "LUK")]),
    ("공격력 +12%", [StatLine("ATK", 12, True)]),
    ("마력 +14", [StatLine("MATK", 14, False)]),
    ("데미지 +12%", [StatLine("DMG", 12, True)]),
    ("보스 몬스터 데미지 +40%", [StatLine("BOSS", 40, True)]),
    ("몬스터 방어율 무시 +35%", [StatLine("IED", 35, True)]),
    ("크리티컬 데미지 +8%", [StatLine("CD", 8, True)]),
    ("크리티컬 확률 +9%", [StatLine("CR", 9, True)]),
    ("최대 HP +12%", [StatLine("HP", 12, True)]),
    ("최대 HP +300", [StatLine("HP", 300, False)]),
    ("캐릭터 기준 9레벨 당 INT +2", [StatLine("INT", 62, False)]),  # 287 // 9 = 31, ×2
    # 구 표기 잠재 (Review Focus 1)
    ("STR : +12%", [StatLine("STR", 12, True)]),
    ("보스 몬스터 공격 시 데미지 : +40%", [StatLine("BOSS", 40, True)]),
    ("몬스터 방어율 무시 : +15%", [StatLine("IED", 15, True)]),
    ("캐릭터 기준 10레벨 당 STR : +2", [StatLine("STR", 56, False)]),  # 287 // 10 = 28, ×2
    # 하이퍼스탯
    ("지력 180 증가", [StatLine("INT", 180, False)]),
    ("공격력과 마력 18 증가", [StatLine("ATK", 18, False), StatLine("MATK", 18, False)]),
    ("보스 몬스터 공격 시 데미지 47% 증가", [StatLine("BOSS", 47, True)]),
    ("방어율 무시 36% 증가", [StatLine("IED", 36, True)]),
    # 어빌리티
    ("모든 능력치 15 증가", [StatLine(k, 15, False) for k in ("STR", "DEX", "INT", "LUK")]),
    ("INT 30 증가, STR 15 증가", [StatLine("INT", 30, False), StatLine("STR", 15, False)]),
    # 세트 효과 (이중 공백)
    ("공격력  +30, 마력  +30, 보스 몬스터 데미지 +10%",
     [StatLine("ATK", 30, False), StatLine("MATK", 30, False), StatLine("BOSS", 10, True)]),
    # 세트 효과에 딜 무관 항목이 섞인 경우
    ("공격력  +4, 마력  +4, 파티퀘스트 경험치 3% 추가", [StatLine("ATK", 4, False), StatLine("MATK", 4, False)]),
    ("공격력  +7, 마력  +7, [수호령 라이딩] 스킬 사용 가능", [StatLine("ATK", 7, False), StatLine("MATK", 7, False)]),
])
def test_relevant_options(text, expected):
    assert parse_option(text, L) == expected


@pytest.mark.parametrize("text", [
    "아이템 드롭률 +20%",
    "메소 획득량 +20%",
    "스킬 재사용 대기시간 -2초",
    "HP 회복 아이템 및 회복 스킬 효율 +30%",
    "<쓸만한 샤프 아이즈> 스킬 사용 가능",
    "[피의 갈망 Lv.1] 스킬 사용 가능",
    "공격 시 15% 확률로 95의 HP 회복",
    "피격 시 5% 확률로 데미지의 40% 무시",
    "스킬 사용 시 19% 확률로 재사용 대기시간이 미적용",
    "상태 이상에 걸린 대상 공격 시 데미지 8% 증가",
    "일반 몬스터 공격 시 데미지 14% 증가",
    "최대 MP +195",
    "방어력 +125",
    "모든 스킬의 재사용 대기시간 : -2초(10초 이하는 10%감소, 5초 미만으로 감소 불가)",
    "파티퀘스트 경험치 10% 추가",
])
def test_irrelevant_options_are_empty(text):
    assert parse_option(text, L) == []


@pytest.mark.parametrize("text", [
    "AP를 직접 투자한 LUK의 15% 만큼 DEX 증가",
    "패시브 스킬 레벨이 1 증가 (액티브 혼합형, 5차, 6차 스킬 적용안됨)",
    "완전히 새로운 옵션 +10%",
])
def test_unknown_options_are_none(text):
    assert parse_option(text, L) is None


# fixture 46명에서 나온 모든 옵션 문자열 중 None이 허용되는 것은 이 두 종류뿐이다.
ALLOWED_UNKNOWN = (re.compile(r"^AP를 직접 투자한 "), re.compile(r"^패시브 스킬 레벨이 "))


def _all_option_strings():
    for c in classes():
        eq = load(c, "character/item-equipment")
        for key in ("item_equipment", "item_equipment_preset_1", "item_equipment_preset_2", "item_equipment_preset_3"):
            for item in eq.get(key) or []:
                for n in (1, 2, 3):
                    for prefix in ("potential_option_", "additional_potential_option_"):
                        if item.get(f"{prefix}{n}"):
                            yield item[f"{prefix}{n}"]
        hy = load(c, "character/hyper-stat")
        for n in (1, 2, 3):
            for s in hy.get(f"hyper_stat_preset_{n}") or []:
                if s.get("stat_increase"):
                    yield s["stat_increase"]
        ab = load(c, "character/ability")
        for n in (1, 2, 3):
            for a in (ab.get(f"ability_preset_{n}") or {}).get("ability_info", []):
                yield a["ability_value"]
        for se in load(c, "character/set-effect").get("set_effect") or []:
            for tier in se.get("set_option_full") or []:
                yield tier["set_option"]


def test_every_fixture_option_is_recognized():
    unknown = sorted({t for t in _all_option_strings()
                      if parse_option(t, L) is None and not any(p.match(t) for p in ALLOWED_UNKNOWN)})
    assert unknown == []
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_options.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'engine.options'`)

- [ ] **Step 3: 구현**

`engine/options.py`:
```python
"""메이플 옵션 문자열 → StatLine.

다루는 표기:
- 잠재 신 표기 "STR +12%", 구 표기 "STR : +12%"
- 레벨당 옵션 "캐릭터 기준 9레벨 당 INT +2" (구 표기는 "... STR : +2")
- 하이퍼스탯·어빌리티 "지력 180 증가", "보스 몬스터 공격 시 데미지 47% 증가"
- 세트 효과 "공격력  +30, 마력  +30, 보스 몬스터 데미지 +10%" (쉼표로 여러 개)

반환: 딜 관련 → StatLine 리스트, 딜 무관 → [], 모르는 표기 → None.
"""
import re
from dataclasses import dataclass

_FOUR = ("STR", "DEX", "INT", "LUK")


@dataclass(frozen=True)
class StatLine:
    key: str  # STR DEX INT LUK HP ATK MATK DMG BOSS IED CD CR FD
    value: float
    percent: bool


_NAMES: dict[str, tuple[str, ...]] = {
    "STR": ("STR",), "힘": ("STR",),
    "DEX": ("DEX",), "민첩성": ("DEX",),
    "INT": ("INT",), "지력": ("INT",),
    "LUK": ("LUK",), "운": ("LUK",),
    "올스탯": _FOUR, "모든 능력치": _FOUR,
    "최대 HP": ("HP",),
    "공격력": ("ATK",), "마력": ("MATK",),
    "공격력과 마력": ("ATK", "MATK"), "공격력/마력": ("ATK", "MATK"),
    "데미지": ("DMG",),
    "보스 몬스터 데미지": ("BOSS",), "보스 몬스터 공격 시 데미지": ("BOSS",),
    "몬스터 방어율 무시": ("IED",), "방어율 무시": ("IED",),
    "크리티컬 데미지": ("CD",), "크리티컬 확률": ("CR",),
    "최종 데미지": ("FD",),
}

_IRRELEVANT_NAMES = {
    "최대 MP", "아이템 드롭률", "메소 획득량", "획득 경험치", "방어력", "이동속도", "점프력",
    "일반 몬스터 공격 시 데미지", "일반 몬스터 데미지", "상태 이상 내성", "아케인포스",
    "HP 회복 아이템 및 회복 스킬 효율", "모든 스킬의 MP 소모", "버프 스킬의 지속 시간",
    "스킬 재사용 대기시간", "최대 데몬 포스/타임 포스", "상태 이상에 걸린 대상 공격 시 데미지",
}

_IRRELEVANT_PREFIXES = (
    "공격 시 ", "피격 시 ", "<", "[", "스킬 사용 시 ", "다수 공격 스킬", "방어력의 ",
    "모든 스킬의 재사용 대기시간", "파티퀘스트",
)

_PER_LEVEL = re.compile(r"^캐릭터 기준\s*(\d+)레벨 당\s*(\S+)\s*:?\s*\+(\d+)$")
_PLUS = re.compile(r"^(?P<name>.+?)\s*:?\s*(?P<sign>[+-])\s*(?P<num>\d+(?:\.\d+)?)\s*(?P<unit>%|초)?$")
_INCREASE = re.compile(r"^(?P<name>.+?)\s+(?P<num>\d+(?:\.\d+)?)(?P<unit>%)?\s*증가$")


def parse_option(text: str, level: int) -> list[StatLine] | None:
    text = text.strip()
    if text.startswith(_IRRELEVANT_PREFIXES):
        return []
    parts = [text] if "(" in text else [p.strip() for p in text.split(",")]
    out: list[StatLine] = []
    for part in parts:
        lines = _parse_one(part, level)
        if lines is None:
            return None
        out.extend(lines)
    return out


def _parse_one(part: str, level: int) -> list[StatLine] | None:
    if part.startswith(_IRRELEVANT_PREFIXES):  # 세트 효과처럼 쉼표로 섞인 경우
        return []
    m = _PER_LEVEL.match(part)
    if m:
        keys = _NAMES.get(m[2])
        if keys is None:
            return None
        value = (level // int(m[1])) * int(m[3])
        return [StatLine(k, value, False) for k in keys]
    m = _PLUS.match(part) or _INCREASE.match(part)
    if not m:
        return None
    name = m["name"].strip()
    if name in _IRRELEVANT_NAMES:
        return []
    keys = _NAMES.get(name)
    if keys is None:
        return None
    value = float(m["num"])
    if m.groupdict().get("sign") == "-":
        value = -value
    return [StatLine(k, value, m["unit"] == "%") for k in keys]
```

- [ ] **Step 4: 통과 확인**

Run: `uv run pytest tests/test_options.py -v`
Expected: 모두 PASS. `test_every_fixture_option_is_recognized`가 실패하면 출력된 `unknown` 문자열을 보고 `_NAMES`/`_IRRELEVANT_NAMES`/`_IRRELEVANT_PREFIXES` 중 맞는 곳에 넣는다. 딜에 영향을 주는데 해석할 수 없는 옵션이라면 `ALLOWED_UNKNOWN`에 추가하고, 그 이유를 테스트 주석에 적는다.

- [ ] **Step 5: 커밋**

```bash
git add engine/options.py tests/test_options.py
git commit -m "옵션 문자열 파서: 잠재 신·구 표기, 하이퍼, 어빌리티, 세트 효과

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: 스탯 모델, 직업·무기 테이블, 스탯공격력 공식

**Files:**
- Create: `engine/stats/model.py`, `engine/stats/jobs.py`, `engine/stats/weapons.py`, `engine/stats/formula.py`
- Test: `tests/test_stats_core.py`

**Interfaces:**
- Consumes: `engine.options.StatLine`
- Produces:
  - `StatBlock` (dataclass): `flat: dict[str, float]`, `pct: dict[str, float]` (키 `STR DEX INT LUK HP ATK MATK`), `dmg`, `boss`, `cd`, `cr`, `fd: float`, `ied: list[float]`. 메서드 `add(line: StatLine) -> None`, `__add__(other) -> StatBlock`, `ied_total() -> float`
  - `FinalStats` (frozen dataclass): `stats: dict[str, int]` (STR DEX INT LUK HP), `ap: dict[str, int]`, `atk: int`, `matk: int`, `dmg`, `boss`, `fd`, `cd`, `cr`, `ied: float`(모두 퍼센트 포인트), `stat_attack_min: int`, `stat_attack_max: int`, `combat_power: int`
  - `JobProfile(name: str, mains: tuple[str, ...], subs: tuple[str, ...], attack: str)` (`attack` ∈ `"ATK"`, `"MATK"`), `job_profile(character_class: str) -> JobProfile`, `UnsupportedJob(Exception)`
  - `weapon_constant(part: str) -> float`, `UnknownWeapon(Exception)`
  - `stat_value(final: FinalStats, job: JobProfile) -> float`, `stat_attack_max(final: FinalStats, job: JobProfile, weapon_part: str) -> float`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_stats_core.py`:
```python
import pytest

from engine.options import StatLine
from engine.stats.formula import stat_attack_max, stat_value
from engine.stats.jobs import UnsupportedJob, job_profile
from engine.stats.model import FinalStats, StatBlock
from engine.stats.weapons import UnknownWeapon, weapon_constant


def final(**kw):
    base = dict(
        stats={"STR": 0, "DEX": 0, "INT": 0, "LUK": 0, "HP": 0}, ap={}, atk=0, matk=0,
        dmg=0.0, boss=0.0, fd=0.0, cd=0.0, cr=0.0, ied=0.0,
        stat_attack_min=0, stat_attack_max=0, combat_power=0,
    )
    base.update(kw)
    return FinalStats(**base)


def test_statblock_add_and_sum():
    a = StatBlock()
    a.add(StatLine("INT", 12, True))
    a.add(StatLine("INT", 6, False))
    a.add(StatLine("BOSS", 40, True))
    a.add(StatLine("IED", 20, True))
    b = StatBlock()
    b.add(StatLine("INT", 9, True))
    b.add(StatLine("IED", 35, True))
    c = a + b
    assert c.pct["INT"] == 21 and c.flat["INT"] == 6 and c.boss == 40
    assert c.ied == [20, 35]
    assert c.ied_total() == pytest.approx(100 * (1 - 0.8 * 0.65))
    assert a.ied == [20]  # __add__는 원본을 바꾸지 않는다


def test_job_profiles():
    lete = job_profile("레테")
    assert (lete.mains, lete.subs, lete.attack) == (("INT",), ("LUK",), "MATK")
    assert job_profile("렌").mains == ("STR",)
    assert job_profile("섀도어").subs == ("DEX", "STR")
    assert job_profile("제논").mains == ("STR", "DEX", "LUK") and job_profile("제논").subs == ()


def test_unsupported_and_unknown_jobs_raise():  # Review Focus 3
    with pytest.raises(UnsupportedJob):
        job_profile("데몬어벤져")
    with pytest.raises(UnsupportedJob):
        job_profile("처음보는직업")


def test_weapon_constants():
    assert weapon_constant("카르타") == 1.2
    assert weapon_constant("아대") == 1.75
    assert weapon_constant("에너지소드") == 1.3125
    with pytest.raises(UnknownWeapon):  # Review Focus 3
        weapon_constant("처음보는무기")


def test_stat_attack_matches_ingame_screenshots():
    """2026-10-03 인게임 스탯창(레테, 카르타) 두 장."""
    lete = job_profile("레테")
    hunting = final(stats={"STR": 3413, "DEX": 3059, "INT": 51896, "LUK": 5960, "HP": 64856},
                    matk=4852, dmg=84.0, fd=186.70)
    boss = final(stats={"STR": 3540, "DEX": 3397, "INT": 56012, "LUK": 6768, "HP": 66150},
                 matk=5008, dmg=91.0, fd=186.70)
    assert stat_value(hunting, lete) == pytest.approx((51896 * 4 + 5960) / 100)
    assert stat_attack_max(hunting, lete, "카르타") == pytest.approx(65_590_276, rel=1e-4)
    assert stat_attack_max(boss, lete, "카르타") == pytest.approx(75_958_618, rel=1e-4)
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_stats_core.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'engine.stats.formula'`)

- [ ] **Step 3: 구현**

`engine/stats/model.py`:
```python
"""스탯 묶음과 최종 스탯 타입. 값은 모두 퍼센트 포인트(84.0 = 84%)."""
import copy
from dataclasses import dataclass, field

from engine.options import StatLine

_SCALAR = {"DMG": "dmg", "BOSS": "boss", "CD": "cd", "CR": "cr", "FD": "fd"}


@dataclass
class StatBlock:
    """출처 하나(아이템, 프리셋, 세트 등)가 주는 스탯."""
    flat: dict[str, float] = field(default_factory=dict)  # STR DEX INT LUK HP ATK MATK
    pct: dict[str, float] = field(default_factory=dict)
    dmg: float = 0.0
    boss: float = 0.0
    cd: float = 0.0
    cr: float = 0.0
    fd: float = 0.0
    ied: list[float] = field(default_factory=list)  # 방무는 곱연산이라 출처별로 보관

    def add(self, line: StatLine) -> None:
        if line.key in _SCALAR:
            attr = _SCALAR[line.key]
            setattr(self, attr, getattr(self, attr) + line.value)
        elif line.key == "IED":
            self.ied.append(line.value)
        else:
            d = self.pct if line.percent else self.flat
            d[line.key] = d.get(line.key, 0.0) + line.value

    def __add__(self, other: "StatBlock") -> "StatBlock":
        out = copy.deepcopy(self)
        for k, v in other.flat.items():
            out.flat[k] = out.flat.get(k, 0.0) + v
        for k, v in other.pct.items():
            out.pct[k] = out.pct.get(k, 0.0) + v
        for attr in _SCALAR.values():
            setattr(out, attr, getattr(out, attr) + getattr(other, attr))
        out.ied = out.ied + other.ied
        return out

    def ied_total(self) -> float:
        remain = 1.0
        for x in self.ied:
            remain *= 1 - x / 100
        return 100 * (1 - remain)


@dataclass(frozen=True)
class FinalStats:
    """API 스탯창 최종값 한 세트."""
    stats: dict[str, int]  # STR DEX INT LUK HP
    ap: dict[str, int]     # AP 배분 STR ...
    atk: int
    matk: int
    dmg: float
    boss: float
    fd: float
    cd: float
    cr: float
    ied: float
    stat_attack_min: int
    stat_attack_max: int
    combat_power: int      # 참고용. 계산에 쓰지 않는다 (스펙 §5.1)
```

`engine/stats/jobs.py`:
```python
"""직업별 주스탯·부스탯·공격 스탯. 근거: 2026-10-02 fixture 46명에서 무기 상수가 깨끗이 떨어지는 조합(스펙 §5.1)."""
from dataclasses import dataclass


class UnsupportedJob(Exception):
    """계산할 수 없는 직업. 숫자를 추정하지 않는다."""


@dataclass(frozen=True)
class JobProfile:
    name: str
    mains: tuple[str, ...]
    subs: tuple[str, ...]
    attack: str  # "ATK" | "MATK"


_GROUPS = [
    (("STR",), ("DEX",), "ATK",
     "히어로 팔라딘 다크나이트 소울마스터 미하일 블래스터 데몬슬레이어 아란 카이저 아델 제로 바이퍼 캐논마스터 스트라이커 은월 아크 렌"),
    (("DEX",), ("STR",), "ATK",
     "보우마스터 신궁 패스파인더 윈드브레이커 와일드헌터 메르세데스 카인 메카닉 캡틴 엔젤릭버스터"),
    (("INT",), ("LUK",), "MATK",
     "아크메이지(불,독) 아크메이지(썬,콜) 비숍 플레임위자드 배틀메이지 에반 루미너스 일리움 라라 키네시스 레테"),
    (("LUK",), ("DEX",), "ATK", "나이트로드 나이트워커 팬텀 칼리 호영"),
    (("LUK",), ("DEX", "STR"), "ATK", "섀도어 듀얼블레이더 카데나"),
    (("STR", "DEX", "LUK"), (), "ATK", "제논"),
]
_TABLE = {name: JobProfile(name, mains, subs, atk) for mains, subs, atk, names in _GROUPS for name in names.split()}
_UNSUPPORTED = {"데몬어벤져": "API가 HP를 표시 상한(500,000)으로만 줘서 순수/추가 HP를 나눌 수 없음"}


def job_profile(character_class: str) -> JobProfile:
    if character_class in _UNSUPPORTED:
        raise UnsupportedJob(f"{character_class}: {_UNSUPPORTED[character_class]}")
    try:
        return _TABLE[character_class]
    except KeyError:
        raise UnsupportedJob(f"직업 테이블에 없는 직업: {character_class}") from None
```

`engine/stats/weapons.py`:
```python
"""무기 상수. 근거: 2026-10-02 fixture 46명에서 스탯공격력 공식으로 역산한 실측값(스펙 §5.1)."""


class UnknownWeapon(Exception):
    """상수를 모르는 무기. 숫자를 추정하지 않는다."""


_GROUPS: dict[float, tuple[str, ...]] = {
    1.2: ("스태프", "완드", "카르타", "샤이닝 로드", "ESP 리미터", "매직 건틀렛", "한손둔기"),
    1.3: ("활", "듀얼 보우건", "에인션트 보우", "브레스 슈터", "단검", "장검", "차크람", "체인", "부채", "케인", "튜너"),
    1.3125: ("에너지소드",),
    1.34: ("두손검",),
    1.35: ("석궁",),
    1.44: ("두손도끼",),
    1.49: ("창", "폴암", "태도"),
    1.5: ("건", "핸드캐논"),
    1.7: ("너클", "소울슈터"),
    1.75: ("아대",),
}
WEAPON_CONSTANTS: dict[str, float] = {name: k for k, names in _GROUPS.items() for name in names}


def weapon_constant(part: str) -> float:
    try:
        return WEAPON_CONSTANTS[part]
    except KeyError:
        raise UnknownWeapon(f"무기 상수 테이블에 없는 무기: {part}") from None
```

`engine/stats/formula.py`:
```python
"""스탯공격력 공식 (스펙 §5.1, 실측 검증됨).

최대 스탯공격력 = (주스탯×4 + 부스탯)/100 × 공(마) × (1+데미지%) × (1+최종 데미지%) × 무기 상수
"""
from engine.stats.jobs import JobProfile
from engine.stats.model import FinalStats
from engine.stats.weapons import weapon_constant


def stat_value(final: FinalStats, job: JobProfile) -> float:
    return (4 * sum(final.stats[m] for m in job.mains) + sum(final.stats[s] for s in job.subs)) / 100


def stat_attack_max(final: FinalStats, job: JobProfile, weapon_part: str) -> float:
    attack = final.matk if job.attack == "MATK" else final.atk
    return (stat_value(final, job) * attack * (1 + final.dmg / 100) * (1 + final.fd / 100)
            * weapon_constant(weapon_part))
```

- [ ] **Step 4: 통과 확인**

Run: `uv run pytest tests/test_stats_core.py -v`
Expected: 5 passed

- [ ] **Step 5: 커밋**

```bash
git add engine/stats tests/test_stats_core.py
git commit -m "스탯 모델, 직업·무기 상수 테이블, 스탯공격력 공식

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: 최종 스탯 변환과 46명 회귀 테스트

**Files:**
- Create: `nexon/convert.py`
- Test: `tests/test_stat_attack_fixtures.py`

**Interfaces:**
- Consumes: `FinalStats`, `job_profile`, `UnsupportedJob`, `stat_attack_max` (Task 4), `helpers.classes/load` (Task 1)
- Produces:
  - `num(v) -> float` — `"129"`, `129`, `"116.00"`, `"-633"`, `None`, `""` 모두 처리(None·빈 문자열 → 0.0)
  - `final_stats(stat_json: dict) -> FinalStats`
  - `weapon_part(equipment_json: dict, preset: int | None = None) -> str` — `preset=None`이면 `item_equipment`(현재 착용), 숫자면 `item_equipment_preset_{n}`에서 `item_equipment_slot == "무기"`인 아이템의 `item_equipment_part`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_stat_attack_fixtures.py`:
```python
import pytest

from engine.stats.formula import stat_attack_max
from engine.stats.jobs import UnsupportedJob, job_profile
from helpers import classes, load
from nexon.convert import final_stats, num, weapon_part

SUPPORTED = [c for c in classes() if c != "데몬어벤져"]


@pytest.mark.parametrize("v,expected", [
    ("129", 129.0), (129, 129.0), ("116.00", 116.0), ("-633", -633.0), (None, 0.0), ("", 0.0),
])
def test_num_is_tolerant(v, expected):  # Review Focus 4
    assert num(v) == expected


def test_final_stats_parses_lete():
    f = final_stats(load("레테", "character/stat"))
    assert f.stats["INT"] == 51968 and f.stats["LUK"] == 5960
    assert f.matk == 4973 and f.dmg == 84.0 and f.boss == 294.0 and f.fd == 188.93
    assert f.ied == 84.04 and f.stat_attack_max == 67838474 and f.combat_power == 72267618
    assert f.ap["INT"] == 1453


def test_weapon_part_lete():
    eq = load("레테", "character/item-equipment")
    assert weapon_part(eq) == "카르타"
    assert weapon_part(eq, preset=2) == "카르타"


@pytest.mark.parametrize("cls", SUPPORTED)
def test_engine_stat_attack_equals_api(cls):
    f = final_stats(load(cls, "character/stat"))
    got = stat_attack_max(f, job_profile(cls), weapon_part(load(cls, "character/item-equipment")))
    assert got == pytest.approx(f.stat_attack_max, rel=1e-4), cls


def test_demon_avenger_is_explicitly_unsupported():
    with pytest.raises(UnsupportedJob):
        job_profile(load("데몬어벤져", "character/stat")["character_class"])
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_stat_attack_fixtures.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'nexon.convert'`)

- [ ] **Step 3: 구현**

`nexon/convert.py`:
```python
"""넥슨 응답 JSON → 엔진 타입. 넥슨 키 이름은 이 파일 밖으로 나가지 않는다."""
from engine.stats.model import FinalStats

_FOUR = ("STR", "DEX", "INT", "LUK")


def num(v) -> float:
    """숫자 필드는 문자열("129", "116.00", "-633")이거나 정수로 온다."""
    if v is None or v == "":
        return 0.0
    return float(str(v).replace(",", ""))


def final_stats(stat_json: dict) -> FinalStats:
    s = {x["stat_name"]: x["stat_value"] for x in stat_json["final_stat"]}

    def i(name: str) -> int:
        return int(num(s.get(name)))

    def f(name: str) -> float:
        return num(s.get(name))

    return FinalStats(
        stats={k: i(k) for k in (*_FOUR, "HP")},
        ap={k: i(f"AP 배분 {k}") for k in (*_FOUR, "HP", "MP")},
        atk=i("공격력"),
        matk=i("마력"),
        dmg=f("데미지"),
        boss=f("보스 몬스터 데미지"),
        fd=f("최종 데미지"),
        cd=f("크리티컬 데미지"),
        cr=f("크리티컬 확률"),
        ied=f("방어율 무시"),
        stat_attack_min=i("최소 스탯공격력"),
        stat_attack_max=i("최대 스탯공격력"),
        combat_power=i("전투력"),
    )


def weapon_part(equipment_json: dict, preset: int | None = None) -> str:
    key = "item_equipment" if preset is None else f"item_equipment_preset_{preset}"
    for item in equipment_json.get(key) or []:
        if item["item_equipment_slot"] == "무기":
            return item["item_equipment_part"]
    raise ValueError(f"무기를 찾을 수 없습니다 ({key})")
```

- [ ] **Step 4: 통과 확인**

Run: `uv run pytest tests/test_stat_attack_fixtures.py -v`
Expected: 모두 PASS (num 6개 + 레테 2개 + 직업 45개 + 데몬어벤져 1개). 어떤 직업이 실패하면 상대 오차를 출력해 보고, 무기 상수 오타인지 직업 주/부스탯 분류 오류인지 가른다. 허용 오차를 늘려서 통과시키지 않는다.

- [ ] **Step 5: 커밋**

```bash
git add nexon/convert.py tests/test_stat_attack_fixtures.py
git commit -m "최종 스탯 변환, 45개 직업 스탯공격력 회귀 테스트

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: 스냅샷 변환 (프리셋별 장비·하이퍼·어빌리티)과 실캐릭터 스모크

**Files:**
- Create: `engine/stats/snapshot.py`
- Modify: `nexon/convert.py` (함수 추가)
- Create: `tools/check_character.py`
- Test: `tests/test_snapshot.py`

**Interfaces:**
- Consumes: `parse_option`, `StatLine` (Task 3), `StatBlock`, `FinalStats` (Task 4), `num`, `final_stats` (Task 5), `NexonClient`, `load_api_key` (Task 2)
- Produces:
  - `Item(slot: str, part: str, name: str, starforce: int, stats: StatBlock, excluded: list[str])`
  - `CharacterSnapshot(character_class: str, level: int, date: str | None, final: FinalStats, equipment_presets: dict[int, dict[str, Item]], active_equipment_preset: int, hyper_presets: dict[int, StatBlock], active_hyper_preset: int, ability_presets: dict[int, StatBlock], active_ability_preset: int, excluded: list[str])`
  - `nexon.convert.item(item_json: dict, level: int) -> Item`
  - `nexon.convert.snapshot(bundle: dict[str, dict]) -> CharacterSnapshot` — bundle 키는 `ENDPOINTS`의 엔드포인트 문자열

1b단계에서 이 타입 위에 잔차 분해, 세트 효과, 유니온·심볼·칭호를 얹는다. 1a에서는 출처별 StatBlock까지만 만든다(% 적용 여부 판단은 1b).

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_snapshot.py`:
```python
from helpers import bundle, classes
from nexon.convert import snapshot


def test_lete_presets_and_active_flags():
    s = snapshot(bundle("레테"))
    assert (s.character_class, s.level) == ("레테", 287)
    assert (s.active_equipment_preset, s.active_hyper_preset, s.active_ability_preset) == (1, 1, 1)
    assert set(s.equipment_presets) == {1, 2, 3}
    assert s.final.stat_attack_max == 67838474


def test_lete_weapon_item_stats():
    w = snapshot(bundle("레테")).equipment_presets[1]["무기"]
    assert (w.name, w.part, w.starforce) == ("제네시스 카르타", "카르타", 22)
    st = w.stats
    assert st.flat["MATK"] == 992 and st.flat["INT"] == 387 and st.flat["LUK"] == 295
    assert st.pct["MATK"] == 21          # 잠재 마력 +9% + 에디 마력 +12%
    assert st.boss == 100                 # 기본 30 + 잠재 40 + 30
    assert st.ied == [20]
    assert st.dmg == 12
    assert st.pct["INT"] == 4             # 추옵 올스탯 4%
    assert st.pct["STR"] == 13            # 에디 STR +9% + 추옵 올스탯 4%
    assert w.excluded == []


def test_lete_boss_preset_ring():
    r = snapshot(bundle("레테")).equipment_presets[2]["반지4"]
    assert r.name == "어센던트 펄스 링"
    assert r.stats.flat["INT"] == 65      # 기본 59 + 에디 6
    assert r.stats.flat["MATK"] == 26     # 기본 16 + 에디 10
    assert r.stats.pct["INT"] == 21 and r.stats.pct["LUK"] == 9


def test_lete_hyper_and_ability_presets():
    s = snapshot(bundle("레테"))
    h2 = s.hyper_presets[2]
    assert h2.flat["INT"] == 180 and h2.flat["LUK"] == 120 and h2.flat["MATK"] == 18
    assert h2.boss == 47 and h2.dmg == 33 and h2.cd == 10 and h2.ied == [36]
    assert s.ability_presets[2].boss == 7
    assert s.ability_presets[1].flat.get("ATK") == 9


def test_all_fixtures_convert_and_unknowns_are_reported():
    for c in classes():
        s = snapshot(bundle(c))
        assert s.equipment_presets[s.active_equipment_preset], c
        for text in s.excluded:
            assert text.startswith(("AP를 직접 투자한 ", "패시브 스킬 레벨이 ")), (c, text)
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_snapshot.py -v`
Expected: FAIL (`ImportError: cannot import name 'snapshot' from 'nexon.convert'`)

- [ ] **Step 3: 도메인 타입 구현**

`engine/stats/snapshot.py`:
```python
"""한 시점의 캐릭터: API 최종 스탯 + 프리셋별 출처 StatBlock."""
from dataclasses import dataclass, field

from engine.stats.model import FinalStats, StatBlock


@dataclass
class Item:
    slot: str
    part: str
    name: str
    starforce: int
    stats: StatBlock
    excluded: list[str] = field(default_factory=list)  # 해석 못 한 옵션 원문 (계산 제외)


@dataclass
class CharacterSnapshot:
    character_class: str
    level: int
    date: str | None
    final: FinalStats
    equipment_presets: dict[int, dict[str, Item]]  # 프리셋 번호 → 슬롯 → 아이템
    active_equipment_preset: int
    hyper_presets: dict[int, StatBlock]
    active_hyper_preset: int
    ability_presets: dict[int, StatBlock]
    active_ability_preset: int
    excluded: list[str] = field(default_factory=list)
```

- [ ] **Step 4: 변환 함수 추가**

`nexon/convert.py` 맨 위 import에 추가:
```python
from engine.options import StatLine, parse_option
from engine.stats.model import FinalStats, StatBlock
from engine.stats.snapshot import CharacterSnapshot, Item
```
(기존 `from engine.stats.model import FinalStats` 줄은 위 줄로 바꾼다.)

파일 끝에 추가:
```python
_OPTION_FLAT = {"str": "STR", "dex": "DEX", "int": "INT", "luk": "LUK", "max_hp": "HP",
                "attack_power": "ATK", "magic_power": "MATK"}


def _total_option_block(opt: dict) -> StatBlock:
    """item_total_option(기본+추옵+주문서+스타포스+익셉셔널 합) → StatBlock."""
    b = StatBlock()
    for k, key in _OPTION_FLAT.items():
        if num(opt.get(k)):
            b.add(StatLine(key, num(opt.get(k)), False))
    if num(opt.get("all_stat")):
        for key in _FOUR:
            b.add(StatLine(key, num(opt["all_stat"]), True))
    if num(opt.get("max_hp_rate")):
        b.add(StatLine("HP", num(opt["max_hp_rate"]), True))
    if num(opt.get("boss_damage")):
        b.add(StatLine("BOSS", num(opt["boss_damage"]), True))
    if num(opt.get("damage")):
        b.add(StatLine("DMG", num(opt["damage"]), True))
    if num(opt.get("ignore_monster_armor")):
        b.add(StatLine("IED", num(opt["ignore_monster_armor"]), True))
    return b


def _add_texts(block: StatBlock, texts, level: int, excluded: list[str]) -> None:
    for t in texts:
        if not t:
            continue
        lines = parse_option(t, level)
        if lines is None:
            excluded.append(t)
            continue
        for line in lines:
            block.add(line)


def item(item_json: dict, level: int) -> Item:
    stats = _total_option_block(item_json.get("item_total_option") or {})
    excluded: list[str] = []
    texts = [item_json.get(f"{p}{n}") for p in ("potential_option_", "additional_potential_option_") for n in (1, 2, 3)]
    _add_texts(stats, texts, level, excluded)
    return Item(
        slot=item_json["item_equipment_slot"],
        part=item_json["item_equipment_part"],
        name=item_json["item_name"],
        starforce=int(num(item_json.get("starforce"))),
        stats=stats,
        excluded=excluded,
    )


def snapshot(bundle: dict[str, dict]) -> CharacterSnapshot:
    basic = bundle["character/basic"]
    level = int(num(basic["character_level"]))
    eq = bundle["character/item-equipment"]
    hy = bundle["character/hyper-stat"]
    ab = bundle["character/ability"]
    excluded: list[str] = []

    equipment: dict[int, dict[str, Item]] = {}
    for n in (1, 2, 3):
        items = [item(x, level) for x in eq.get(f"item_equipment_preset_{n}") or []]
        equipment[n] = {it.slot: it for it in items}
        for it in items:
            excluded.extend(it.excluded)
    # 프리셋을 쓰지 않는 캐릭터는 preset_no가 비거나 프리셋 목록이 null이다 → 현재 착용을 그 프리셋으로 본다.
    active_eq = int(num(eq.get("preset_no"))) or 1
    if not equipment.get(active_eq):
        current = [item(x, level) for x in eq.get("item_equipment") or []]
        equipment[active_eq] = {it.slot: it for it in current}
        for it in current:
            excluded.extend(it.excluded)

    hyper: dict[int, StatBlock] = {}
    for n in (1, 2, 3):
        b = StatBlock()
        _add_texts(b, [s.get("stat_increase") for s in hy.get(f"hyper_stat_preset_{n}") or []], level, excluded)
        hyper[n] = b

    ability: dict[int, StatBlock] = {}
    for n in (1, 2, 3):
        b = StatBlock()
        info = (ab.get(f"ability_preset_{n}") or {}).get("ability_info", [])
        _add_texts(b, [a.get("ability_value") for a in info], level, excluded)
        ability[n] = b

    return CharacterSnapshot(
        character_class=basic["character_class"],
        level=level,
        date=bundle["character/stat"].get("date"),
        final=final_stats(bundle["character/stat"]),
        equipment_presets=equipment,
        active_equipment_preset=active_eq,
        hyper_presets=hyper,
        active_hyper_preset=int(num(hy.get("use_preset_no"))) or 1,
        ability_presets=ability,
        active_ability_preset=int(num(ab.get("preset_no"))) or 1,
        excluded=excluded,
    )
```

- [ ] **Step 5: 통과 확인**

Run: `uv run pytest tests/test_snapshot.py -v`
Expected: 5 passed. `test_lete_weapon_item_stats`의 `pct["INT"] == 4`가 실패하면 `item_total_option.all_stat`이 퍼센트인지(추옵 올스탯%) fixture 원문으로 다시 확인한다 — 레테 무기 `item_add_option.all_stat`이 `"4"`이고 `item_total_option.all_stat`도 `"4"`다.

- [ ] **Step 6: 전체 테스트**

Run: `uv run pytest -v`
Expected: 전부 PASS

- [ ] **Step 7: 실캐릭터 스모크 도구**

`tools/check_character.py`:
```python
"""실제 API로 캐릭터를 불러와 엔진 스탯공격력과 API 값을 비교한다.

사용: uv run python tools/check_character.py <닉네임> [YYYY-MM-DD]
"""
import datetime as dt
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from engine.stats.formula import stat_attack_max  # noqa: E402
from engine.stats.jobs import UnsupportedJob, job_profile  # noqa: E402
from engine.stats.weapons import UnknownWeapon  # noqa: E402
from nexon.client import NexonClient, NexonError, load_api_key  # noqa: E402
from nexon.convert import snapshot  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    day = dt.date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else None
    client = NexonClient(load_api_key(ROOT))
    try:
        bundle = client.fetch_bundle(sys.argv[1], day)
    except NexonError as e:
        print(f"넥슨 API 오류: {e}")
        return 1
    if any(v is None for v in bundle.values()):
        print("해당 날짜 데이터가 없습니다:", [k for k, v in bundle.items() if v is None])
        return 1
    s = snapshot(bundle)
    weapon = s.equipment_presets[s.active_equipment_preset]["무기"].part
    print(f"{s.character_class} Lv.{s.level}  기준: {s.date or '현재'}")
    print(f"프리셋 — 장비 {s.active_equipment_preset}, 하이퍼 {s.active_hyper_preset}, 어빌리티 {s.active_ability_preset}")
    try:
        got = stat_attack_max(s.final, job_profile(s.character_class), weapon)
    except (UnsupportedJob, UnknownWeapon) as e:
        print("계산 제외:", e)
        return 1
    api = s.final.stat_attack_max
    print(f"스탯공격력  엔진 {got:,.0f}  API {api:,}  오차 {abs(got - api) / api:.5%}")
    print(f"전투력(참고, API 기록값) {s.final.combat_power:,}")
    if s.excluded:
        print("계산 제외 옵션:", sorted(set(s.excluded)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Run: `uv run python tools/check_character.py 내신부레테`
Expected: `레테 Lv.287`, 프리셋 줄, 스탯공격력 오차 `0.01%` 미만 출력. (`.env`에 키가 있어야 한다. 네트워크 호출 9회.)

- [ ] **Step 8: 커밋**

```bash
git add engine/stats/snapshot.py nexon/convert.py tools/check_character.py tests/test_snapshot.py
git commit -m "스냅샷 변환(프리셋별 장비·하이퍼·어빌리티)과 실캐릭터 스모크 도구

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

## 1a 완료 기준 (스펙 §4)

- `uv run pytest` 전부 통과. 그중 `test_engine_stat_attack_equals_api`가 45개 직업 전부에서 상대 오차 0.01% 이내.
- `tools/check_character.py 내신부레테`가 실제 API로 같은 결과를 낸다.

## 다음 계획 (1b, 별도 문서)

잔차 분해(% 적용/미적용 구분, 하이퍼·심볼·유니온·칭호 출처), 아이템 교체, 세트 효과(아이템→세트 매핑 데이터), 27개 프리셋 조합 평가, 보스 실딜 지수. 완료 기준은 사냥→보스 세팅 전환 예측과 실제 보스 세팅 스냅샷의 오차 1% 이내다. 이를 위해 사용자 캐릭터가 보스 세팅으로 API에 반영된 스냅샷이 필요하다.
