"""화면 공유 프레임에서 메이플 툴팁을 찾아 원래 크기로 자르고, 별(스타포스)을 세고, 아이템 이름 오타를 바로잡는다.

2026-10-04 측정(로컬 골든셋): 화면 전체를 줄여 보내면 AI가 숫자를 잘못 읽고(255→2550), 스타포스를 자주 틀린다(18→25).
툴팁만 원래 크기로 잘라 함께 보내고, 별은 코드가 센다. AI 판독값을 그대로 믿지 않는다(실측값 원칙).
"""
import difflib

import numpy as np
from PIL import Image

CELL = 8                 # 툴팁 찾기 격자(픽셀)
MIN_W, MIN_H = 160, 180  # 툴팁 최소 크기(픽셀)
MAX_W = 600              # 툴팁 최대 폭(나란히 붙은 두 개는 나눈 뒤 잰다)
STAR_BAND = 48           # 툴팁 맨 위에서 별 줄이 있는 높이(픽셀)


def _dark_mask(a: np.ndarray) -> np.ndarray:
    """툴팁 바탕: 어둡고 채도가 낮은 남회색(반투명이라 배경이 살짝 비친다)."""
    luma = 0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]
    sat = a.max(axis=2) - a.min(axis=2)
    # 실측(툴팁 4장): 중앙값 RGB (47~55, 53~61, 61~70), 채도 중앙값 13~15 — 남회색(파랑 ≥ 빨강)
    return (luma > 35) & (luma < 82) & (sat < 30) & (a[..., 2] >= a[..., 0])


def _open(g: np.ndarray, n: int = 2) -> np.ndarray:
    """격자 열기(침식 후 팽창): 툴팁과 주변 어두운 창을 잇는 가는 다리를 끊는다."""
    e = g.copy()
    for _ in range(n):
        f = e.copy()
        f[1:] &= e[:-1]; f[:-1] &= e[1:]; f[:, 1:] &= e[:, :-1]; f[:, :-1] &= e[:, 1:]
        e = f
    for _ in range(n):
        f = e.copy()
        f[1:] |= e[:-1]; f[:-1] |= e[1:]; f[:, 1:] |= e[:, :-1]; f[:, :-1] |= e[:, 1:]
        e = f
    return e & g | e


def _close(g: np.ndarray) -> np.ndarray:
    """격자 닫기(팽창 후 침식): 글자 줄 때문에 끊긴 칸을 메운다."""
    d = g.copy()
    d[1:] |= g[:-1]; d[:-1] |= g[1:]; d[:, 1:] |= g[:, :-1]; d[:, :-1] |= g[:, 1:]
    e = d.copy()
    e[1:] &= d[:-1]; e[:-1] &= d[1:]; e[:, 1:] &= d[:, :-1]; e[:, :-1] &= d[:, 1:]
    return e


def _components(g: np.ndarray) -> list[tuple[int, int, int, int, int]]:
    seen = np.zeros_like(g, dtype=bool)
    out = []
    for y, x in zip(*np.nonzero(g)):
        if seen[y, x]:
            continue
        stack, cells = [(y, x)], 0
        y0 = y1 = y
        x0 = x1 = x
        seen[y, x] = True
        while stack:
            cy, cx = stack.pop()
            cells += 1
            y0, y1, x0, x1 = min(y0, cy), max(y1, cy), min(x0, cx), max(x1, cx)
            for ny, nx in ((cy + 1, cx), (cy - 1, cx), (cy, cx + 1), (cy, cx - 1)):
                if 0 <= ny < g.shape[0] and 0 <= nx < g.shape[1] and g[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    stack.append((ny, nx))
        out.append((x0, y0, x1, y1, cells))
    return out


def _refine(dark: np.ndarray, box: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    """격자 단위 상자를 픽셀 단위로: 어두운 비율이 절반 넘는 첫·마지막 행·열."""
    x0, y0, x1, y1 = box
    sub = dark[y0:y1, x0:x1]
    cols = np.nonzero(sub.mean(axis=0) > 0.5)[0]
    rows = np.nonzero(sub.mean(axis=1) > 0.5)[0]
    if len(cols) == 0 or len(rows) == 0:
        return box
    return x0 + int(cols[0]), y0 + int(rows[0]), x0 + int(cols[-1]) + 1, y0 + int(rows[-1]) + 1


def _split_columns(a: np.ndarray, box: tuple[int, int, int, int]) -> list[tuple[int, int, int, int]]:
    """나란히 붙은 두 툴팁(마우스를 올린 매물 + '현재 장착 중인 장비' 비교)을 밝은 세로 테두리에서 나눈다."""
    x0, y0, x1, y1 = box
    luma = 0.299 * a[y0:y1, x0:x1, 0] + 0.587 * a[y0:y1, x0:x1, 1] + 0.114 * a[y0:y1, x0:x1, 2]
    light = (luma > 110).mean(axis=0)
    cuts = [i for i in range(MIN_W, (x1 - x0) - MIN_W) if light[i] > 0.7]
    if not cuts:
        return [box]
    c = x0 + cuts[len(cuts) // 2]
    return [(x0, y0, c, y1), (c + 1, y0, x1, y1)]


def _column_runs(grid: np.ndarray) -> list[tuple[int, int, int]]:
    """열마다 가장 긴 세로 어두운 구간 (열, 시작 행, 끝 행)."""
    out = []
    for x in range(grid.shape[1]):
        best, start, cur = (0, 0, 0), None, 0
        for y, v in enumerate(grid[:, x]):
            if v:
                start = y if start is None else start
                cur = y - start + 1
                if cur > best[0]:
                    best = (cur, start, y)
            else:
                start = None
        out.append((x, best[1], best[2]) if best[0] else (x, 0, -1))
    return out


def find_tooltips(img: Image.Image) -> list[tuple[int, int, int, int]]:
    """툴팁 상자 [(x0, y0, x1, y1)] 왼쪽부터.
    툴팁은 경매장 창 위에 겹쳐 뜨고 창 테두리도 같은 남회색이라, 어두운 덩어리로는 둘이 붙는다(2026-10-04 실측).
    그래서 '위에서 아래로 길게 이어지는 어두운 열'을 모아 툴팁 폭을 잡는다 — 경매장 창 본문은 흰색이라 끊긴다."""
    a = np.asarray(img.convert("RGB")).astype(np.int16)
    dark = _dark_mask(a)
    h, w = dark.shape
    gh, gw = h // CELL, w // CELL
    grid = _close(dark[: gh * CELL, : gw * CELL].reshape(gh, CELL, gw, CELL).mean(axis=(1, 3)) > 0.45)
    need = MIN_H // CELL
    runs = _column_runs(grid)
    groups, cur = [], []
    for x, y0, y1 in runs:
        if y1 - y0 + 1 >= need:
            cur.append((x, y0, y1))
        elif cur:
            groups.append(cur)
            cur = []
    if cur:
        groups.append(cur)
    boxes = []
    for g in groups:
        if len(g) * CELL < MIN_W:
            continue
        y0 = int(np.median([r[1] for r in g])) * CELL
        y1 = (int(np.median([r[2] for r in g])) + 1) * CELL
        box = (g[0][0] * CELL, y0, (g[-1][0] + 1) * CELL, y1)
        for part in _split_columns(a, box):
            px0, py0, px1, py1 = _refine(dark, part)
            if MIN_W <= px1 - px0 <= MAX_W and py1 - py0 >= MIN_H:
                boxes.append((px0, py0, px1, py1))
    return sorted(boxes)


def crop(img: Image.Image, box: tuple[int, int, int, int], margin: int = 4) -> Image.Image:
    x0, y0, x1, y1 = box
    return img.crop((max(0, x0 - margin), max(0, y0 - margin), min(img.width, x1 + margin), min(img.height, y1 + margin)))


def count_stars(tip: Image.Image) -> int | None:
    """툴팁 맨 위 별 줄에서 노란(채워진) 별 개수. 노란 별이 하나도 없으면 None(0성인지 잘린 건지 모른다)."""
    a = np.asarray(tip.convert("RGB")).astype(np.int16)[:STAR_BAND]
    yellow = (a[..., 0] > 200) & (a[..., 1] > 165) & (a[..., 2] < 110)
    if yellow.sum() < 8:
        return None
    seen = np.zeros_like(yellow)
    areas = []
    for y, x in zip(*np.nonzero(yellow)):
        if seen[y, x]:
            continue
        stack, n = [(y, x)], 0
        seen[y, x] = True
        y0 = y1 = y
        x0 = x1 = x
        while stack:
            cy, cx = stack.pop()
            n += 1
            y0, y1, x0, x1 = min(y0, cy), max(y1, cy), min(x0, cx), max(x1, cx)
            for ny, nx in ((cy + 1, cx), (cy - 1, cx), (cy, cx + 1), (cy, cx - 1)):
                if 0 <= ny < yellow.shape[0] and 0 <= nx < yellow.shape[1] and yellow[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    stack.append((ny, nx))
        bw, bh = x1 - x0 + 1, y1 - y0 + 1
        if bw >= 4 and bh >= 4 and 0.5 <= bw / bh <= 2:   # 별은 거의 정사각형(배경의 가는 노란 선 제외, 2026-10-04 실측)
            areas.append(n)
    big = [s for s in areas if s >= 6]
    if not big:
        return None
    ref = float(np.percentile(big, 75))
    n = sum(1 for s in big if s >= 0.45 * ref)   # 반짝이 효과(작은 노란 점)는 별보다 훨씬 작다
    return n or None


def _distance(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def correct_name(name: str | None, names) -> tuple[str | None, bool]:
    """한두 글자 틀린 이름만 알려진 이름으로 바로잡는다("에테르널"→"에테르넬"). 그 밖에는 그대로."""
    if not name or name in names:
        return name, False
    m = difflib.get_close_matches(name, list(names), n=1, cutoff=0.8)
    if m and _distance(name, m[0]) <= 2:
        return m[0], True
    return name, False
