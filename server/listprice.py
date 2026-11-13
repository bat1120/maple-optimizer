"""경매장 목록 행의 가격·전투력 증가량을 AI 없이 읽는다(2026-11-13).

왜: 매물에 마우스를 올리면 툴팁이 목록의 가격 칸을 가려서, 툴팁 화면만으로는 가격을 알 수 없다
(실사용 캡처: AI가 툴팁의 '전투력 증가량 -193만 1721'을 가격으로 읽음). 툴팁이 뜨기 전 목록 화면에서
줄마다 (전투력 증가량, 가격)을 읽어 두고, 툴팁 매물의 전투력 증가량(AI 판독)과 같은 줄의 가격을 붙인다.

어떻게: 가격 바로 왼쪽의 동전 아이콘으로 줄을 찾고, 가격 줄(동전 높이)과 전투력 줄(동전 아래)을 글자 단위로 나눠
글자 모양 표(engine/data/list_glyphs.json — tools/derive_list_glyphs.py가 실제 캡처와 화면 글자 정답으로 만든다)와 대조한다.
붙어 있는 글자('64억'의 4와 억, '20'의 2와 0)는 표와 가장 잘 맞게 나눈다.
'81억 0000만 0000'·'-193만 1721' 형식에 맞을 때만 값으로 인정한다 — 애매하면 읽지 않은 것으로 둔다.
"""
import functools
import json
import pathlib
import re

import numpy as np

GLYPH_W, GLYPH_H = 8, 12   # 글자를 이 크기로 맞춰 비교한다
TH = 140                   # 글자 밝기 문턱(가격 흰 글자·전투력 회색 글자 모두)
SPACE = 5                  # 이만큼 비면 띄어쓰기
TABLE = pathlib.Path(__file__).resolve().parents[1] / "engine" / "data" / "list_glyphs.json"
PRICE_RE = re.compile(r"(?:(\d+)억)?(?:(\d{1,4})만)?(\d{1,4})?")
POWER_RE = re.compile(r"[-+](?:(\d+)만)?(\d{1,4})")


def _components(m: np.ndarray) -> list[tuple[int, int, int, int, int]]:
    """True 칸의 8방향 연결 덩어리 (y0, x0, y1, x1, 칸 수)."""
    h, w = m.shape
    seen = np.zeros_like(m, dtype=bool)
    out = []
    for y, x in zip(*np.nonzero(m)):
        if seen[y, x]:
            continue
        stack, seen[y, x], pts = [(y, x)], True, []
        while stack:
            cy, cx = stack.pop()
            pts.append((cy, cx))
            for ny in (cy - 1, cy, cy + 1):
                for nx in (cx - 1, cx, cx + 1):
                    if 0 <= ny < h and 0 <= nx < w and m[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
        ys, xs = [p[0] for p in pts], [p[1] for p in pts]
        out.append((min(ys), min(xs), max(ys), max(xs), len(pts)))
    return out


def find_coins(rgb: np.ndarray) -> list[tuple[int, int]]:
    """목록 줄의 동전 아이콘 중심 (x, y), 위에서부터. 같은 세로줄에 2개 이상 늘어선 동전만(보유 메소 동전 등은 뺀다)."""
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    mask = (r > 190) & (g > 130) & (g < 230) & (b < 110)
    if mask.sum() > 60000:  # 노란 영역이 넓으면 목록 화면이 아니다(덩어리 찾기도 느려진다)
        return []
    coins = []
    for y0, x0, y1, x1, n in _components(mask):
        hh, ww = y1 - y0 + 1, x1 - x0 + 1
        if 11 <= hh <= 16 and 11 <= ww <= 16 and abs(hh - ww) <= 2 and n > 0.5 * hh * ww:
            coins.append((round((x0 + x1) / 2), round((y0 + y1) / 2)))
    return sorted((c for c in coins if sum(abs(c[0] - d[0]) <= 3 for d in coins) >= 2), key=lambda c: c[1])


def _bands(gray: np.ndarray, cx: int, cy: int) -> tuple[np.ndarray, np.ndarray]:
    """동전 기준 가격 칸(동전 오른쪽, 같은 높이)과 전투력 칸(동전 왼쪽 아래 줄)."""
    h, w = gray.shape
    price = gray[max(cy - 8, 0):min(cy + 9, h), min(cx + 8, w):min(cx + 150, w)]
    power = gray[max(cy + 3, 0):min(cy + 20, h), max(cx - 215, 0):max(cx - 20, 0)]
    return price, power


def _runs(crop: np.ndarray) -> list[tuple[int, int]]:
    """글자가 있는 세로줄 구간 [a, b)."""
    on = list((crop > TH).any(axis=0)) + [False]
    out, start = [], None
    for x, v in enumerate(on):
        if v and start is None:
            start = x
        elif not v and start is not None:
            out.append((start, x))
            start = None
    return out


def _feature(crop: np.ndarray, a: int, b: int) -> np.ndarray | None:
    """crop[:, a:b]의 글자를 꼭 맞게 잘라 GLYPH_H×GLYPH_W 밝기 + (폭, 높이)."""
    from PIL import Image
    part = crop[:, a:b]
    mask = part > TH
    rows, cols = np.nonzero(mask.any(axis=1))[0], np.nonzero(mask.any(axis=0))[0]
    if not len(rows):
        return None
    part = part[rows[0]:rows[-1] + 1, cols[0]:cols[-1] + 1]
    lo, hi = float(part.min()), float(part.max())
    norm = (part - lo) / (hi - lo) if hi > lo else np.zeros_like(part, dtype=float)
    img = Image.fromarray((norm * 255).astype(np.uint8)).resize((GLYPH_W, GLYPH_H), Image.BILINEAR)
    # 늘이면 비슷해지는 글자('-'·'1'·'만')는 폭·높이로 가른다
    return np.concatenate([np.asarray(img, dtype=float).ravel() / 255.0, [part.shape[1] / 4.0, part.shape[0] / 4.0]])


def _is_minus(crop: np.ndarray, a: int, b: int) -> bool:
    rows = np.nonzero((crop[:, a:b] > TH).any(axis=1))[0]
    return len(rows) > 0 and rows[-1] - rows[0] <= 2 and 3 <= b - a <= 6


def _plus_width(crop: np.ndarray, a: int, b: int) -> int | None:
    """덩어리 왼쪽이 '+'(왼쪽 끝에서 시작하는 가로 줄 + 그 가운데를 지나는 세로 줄뿐)면 그 폭.
    실제 프레임에서 '+'는 뒤 숫자와 붙어 찍힌다(2026-11-13)."""
    m = crop[:, a:min(b, a + 10)] > TH
    if not m.any():
        return None
    r = int(np.argmax(m.sum(axis=1)))
    k = int(np.argmin(m[r])) if not m[r].all() else m.shape[1]  # 가로 줄 길이(왼쪽 끝부터 이어진 칸)
    if k < 5 or k > 9:
        return None
    p = m[:, :k]
    col = p.sum(axis=0)
    c = int(np.argmax(col))
    ys = np.nonzero(p[:, c])[0]
    if (abs(c - (k - 1) / 2) <= 1 and col[c] >= 5 and r - ys[0] >= 2 and ys[-1] - r >= 2
            and p.sum() <= col[c] + k):  # 십자 말고 다른 칸이 거의 없다
        return k
    return None


def make_table(glyphs, max_dist: float) -> dict:
    return {"chars": [c for c, _ in glyphs], "vecs": np.asarray([v for _, v in glyphs], dtype=float), "max_dist": max_dist}


@functools.lru_cache(maxsize=1)
def load_table() -> dict:
    """가격 줄(흰 글자)과 전투력 줄(회색 글자)은 같은 글꼴 — 견본을 한 표에 모은다(밝기는 글자마다 맞춘다).
    따로 두면 가격 줄에 따로 떨어져 찍힌 적 없는 숫자(64억의 6·4 등)를 못 읽는다(2026-11-13 측정)."""
    data = json.loads(TABLE.read_text(encoding="utf-8"))
    return make_table(data["glyphs"], data["max_dist"])


def _nearest(f: np.ndarray, table: dict) -> tuple[str, float]:
    d = np.linalg.norm(table["vecs"] - f, axis=1)
    i = int(d.argmin())
    return table["chars"][i], float(d[i])


def _split(crop: np.ndarray, a: int, b: int, table: dict) -> list[str] | None:
    """붙은 글자 덩어리 [a, b)를 표와 가장 잘 맞게 나눈다(조각 폭 3~12). 어느 조각이든 표와 멀면 None."""
    best: dict[int, tuple[float, list[str]]] = {a: (0.0, [])}
    for end in range(a + 3, b + 1):
        cands = []
        for start in range(max(a, end - 12), end - 2):
            if start not in best:
                continue
            f = _feature(crop, start, end)
            if f is None:
                continue
            ch, d = _nearest(f, table)
            if d <= table["max_dist"]:
                cands.append((best[start][0] + d + 0.5, best[start][1] + [ch]))  # 0.5: 쓸데없이 잘게 나누지 않게
        if cands:
            best[end] = min(cands, key=lambda t: t[0])
    return best[b][1] if b in best and best[b][1] else None


def _glyphs(crop: np.ndarray, a: int, b: int, table: dict) -> str:
    f = _feature(crop, a, b)
    ch, d = _nearest(f, table) if f is not None else ("?", 1e9)
    if d > table["max_dist"]:
        parts = _split(crop, a, b, table)
        ch = "".join(parts) if parts else "?"
    return ch


def _decode(crop: np.ndarray, table: dict) -> str | None:
    """글자 덩어리마다 표에서 가장 가까운 글자. 한 글자로 안 맞으면 나눠 본다. 못 읽은 글자는 '?'."""
    text, prev = [], None
    for a, b in _runs(crop):
        if prev is not None and a - prev >= SPACE:
            text.append(" ")
        prev = b
        if _is_minus(crop, a, b):  # 부호는 모양으로 본다 — 프레임에서 '-'가 3픽셀로 짧게 찍히면 견본과 안 맞는다(2026-11-13)
            text.append("-")
            continue
        if (k := _plus_width(crop, a, b)) is not None:
            text.append("+")
            rest = np.nonzero((crop[:, a + k:b] > TH).any(axis=0))[0]
            if not len(rest):
                continue
            a += k + int(rest[0])
        text.append(_glyphs(crop, a, b, table))
    return "".join(text).strip() or None


def _price_value(s: str | None) -> int | None:
    if not s or "?" in s:
        return None
    m = PRICE_RE.fullmatch(s.replace(" ", ""))
    if not m or not any(m.groups()):
        return None
    eok, man, one = m.groups()
    if (eok and man is not None and len(man) != 4) or ((eok or man) and one is not None and len(one) != 4):
        return None  # '81억 0000만 0000': 억 뒤의 만, 만 뒤의 일의 자리는 4자리로 찍힌다
    return int(eok or 0) * 100_000_000 + int(man or 0) * 10_000 + int(one or 0)


def _power_value(s: str | None) -> int | None:
    """'-193만 1721' → 1931721, '+372만 9056' → 3729056(크기). 앞의 '전투력 증가량' 글자는 마지막 부호부터 잘라 버린다."""
    if not s or ("-" not in s and "+" not in s):
        return None
    s = s[max(s.rfind("-"), s.rfind("+")):].replace(" ", "")
    if "?" in s:
        return None
    m = POWER_RE.fullmatch(s)
    if not m:
        return None
    man, one = m.groups()
    if man is not None and len(one) != 4:
        return None
    return int(man or 0) * 10_000 + int(one)


def read_rows(img, table: dict | None = None) -> list[dict]:
    """목록 화면 → 줄마다 {'y', 'price', 'power', 'price_text', 'power_text'}(위에서부터).
    형식이 안 맞으면 그 값은 None(읽었다고 하지 않는다)."""
    table = table or load_table()
    rgb = np.asarray(img.convert("RGB"), dtype=int)
    gray = rgb.mean(axis=2)
    out = []
    for cx, cy in find_coins(rgb):
        price_crop, power_crop = _bands(gray, cx, cy)
        pt, wt = _decode(price_crop, table), _decode(power_crop, table)
        out.append({"y": cy, "price_text": pt, "price": _price_value(pt), "power_text": wt, "power": _power_value(wt)})
    return out


def _aligned(crop: np.ndarray, want: str, power: bool) -> list[tuple[str, np.ndarray]]:
    """정답 글자와 덩어리를 맞춰 (글자, 모양). 붙은 덩어리(정답보다 덩어리가 적은 만큼)는 건너뛴다.
    전투력 줄은 '-' 덩어리부터 맞춘다(앞의 '전투력 증가량' 글자는 뺀다)."""
    runs = _runs(crop)
    if power:
        k = max((i for i, (a, b) in enumerate(runs) if _is_minus(crop, a, b)), default=None)
        if k is None:
            return []
        runs = runs[k:]
    chars = want.replace(" ", "")
    extra = len(chars) - len(runs)
    if extra < 0:
        return []
    widths = [b - a for a, b in runs]
    if extra == 0:
        pairs = list(zip(chars, runs))
    else:  # 가장 넓은 덩어리 하나가 extra+1글자를 품었다고 보고 그 앞뒤만 쓴다
        i = int(np.argmax(widths))
        pairs = list(zip(chars[:i], runs[:i])) + list(zip(chars[i + extra + 1:], runs[i + 1:]))
    out = []
    for ch, (a, b) in pairs:
        f = _feature(crop, a, b)
        if f is not None:
            out.append((ch, f))
    return out


def learn(img, prices: list[str], powers: list[str]) -> list[tuple[str, np.ndarray]]:
    """정답 글자를 아는 목록 캡처에서 글자 모양 견본을 뜬다(tools/derive_list_glyphs.py)."""
    rgb = np.asarray(img.convert("RGB"), dtype=int)
    gray = rgb.mean(axis=2)
    coins = find_coins(rgb)
    if len(coins) != len(prices):
        raise ValueError(f"동전 {len(coins)}개, 정답 {len(prices)}줄")
    out = []
    for (cx, cy), price, power in zip(coins, prices, powers):
        price_crop, power_crop = _bands(gray, cx, cy)
        out += _aligned(price_crop, price, False) + _aligned(power_crop, power, True)
    return out


def build_table(samples: list[tuple[str, np.ndarray]]) -> dict:
    """글자 모양 표: 견본을 모두 두고 가장 가까운 견본의 글자를 쓴다(평균하면 흰·회색 글자가 섞여 흐려진다).
    허용 거리 = 견본마다 '자기 말고 가장 가까운 같은 글자 견본'까지 거리의 최댓값 × 1.5 — 그보다 먼 덩어리는 못 읽은 글자.
    측정(2026-11-13, 목록 16줄): 원본·JPEG 85(화면 공유 프레임 품질)에서 가격 16/16, 틀리게 읽은 값 0."""
    vecs = np.asarray([f for _, f in samples], dtype=float)
    chars = [c for c, _ in samples]
    same = []
    for i, (c, f) in enumerate(samples):
        d = np.linalg.norm(vecs - f, axis=1)
        mine = [d[j] for j in range(len(samples)) if chars[j] == c and j != i]
        if mine:
            same.append(min(mine))
    within = float(max(same))
    return {"glyphs": [(c, np.asarray(f).round(4).tolist()) for c, f in samples], "max_dist": round(within * 1.5, 4),
            "classes": sorted(set(chars))}


class ListMemory:
    """사용자(IP 해시)마다 최근 본 목록 줄 {전투력 증가량: 가격}. 툴팁 매물의 전투력 증가량으로 가격을 찾는다.
    - ttl초가 지난 줄은 버린다(다른 검색으로 넘어갔을 수 있다)
    - 같은 전투력에 다른 가격을 본 적이 있으면 어느 줄인지 모르므로 답하지 않는다"""

    def __init__(self, ttl: float = 900, max_users: int = 2000, max_rows: int = 400):
        self.ttl, self.max_users, self.max_rows = ttl, max_users, max_rows
        self._rows: dict[str, dict[int, tuple[int | None, float]]] = {}

    def remember(self, who: str, rows: list[dict], now: float) -> None:
        good = [(r["power"], r["price"]) for r in rows if r.get("power") and r.get("price")]
        if not good:
            return
        mine = self._rows.pop(who, {})
        mine = {p: v for p, v in mine.items() if now - v[1] <= self.ttl}
        for power, price in good:
            old = mine.get(power)
            mine[power] = (None if old and old[0] not in (None, price) else price, now) if old else (price, now)
        if len(mine) > self.max_rows:
            mine = dict(sorted(mine.items(), key=lambda kv: kv[1][1])[-self.max_rows:])
        self._rows[who] = mine  # 다시 넣어 '최근 쓴 사용자'를 뒤로
        while len(self._rows) > self.max_users:
            self._rows.pop(next(iter(self._rows)))

    def lookup(self, who: str, power: int | None, now: float) -> int | None:
        hit = self._rows.get(who, {}).get(power) if power else None
        if not hit or now - hit[1] > self.ttl:
            return None
        return hit[0]
