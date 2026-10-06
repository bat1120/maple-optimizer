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
SINGLE_MAX_W = 460       # 이보다 넓으면 툴팁 두 개가 붙은 것으로 본다(실측 툴팁 폭 250~450)
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
    if cuts:
        c = x0 + cuts[len(cuts) // 2]
        return [(x0, y0, c, y1), (c + 1, y0, x1, y1)]
    if x1 - x0 > SINGLE_MAX_W:
        # 테두리 없이 딱 붙은 두 툴팁: 가운데쯤에서 '어두운 바탕' 비율이 가장 낮은 열(두 툴팁의 경계)에서 나눈다
        dark = _dark_mask(a[y0:y1, x0:x1]).mean(axis=0)
        lo, hi = int((x1 - x0) * 0.3), int((x1 - x0) * 0.7)
        c = x0 + lo + int(np.argmin(dark[lo:hi]))
        return [(x0, y0, c, y1), (c + 1, y0, x1, y1)]
    return [box]


def _column_runs(grid: np.ndarray, max_gap: int = 0) -> list[tuple[int, int, int]]:
    """열마다 가장 긴 세로 어두운 구간 (열, 시작 행, 끝 행). max_gap칸 이하로 끊긴 곳은 이어진 것으로 본다 —
    훈장처럼 짧은 툴팁은 주황 이름표·아이콘 칸에 끊겨 기준 길이에 못 미친다(2026-10-06 실측: 168px 두 토막)."""
    out = []
    for x in range(grid.shape[1]):
        best, start, last = (0, 0, 0), None, None
        for y, v in enumerate(grid[:, x]):
            if not v:
                continue
            if start is None or y - last - 1 > max_gap:
                start = y
            last = y
            if y - start + 1 > best[0]:
                best = (y - start + 1, start, y)
        out.append((x, best[1], best[2]) if best[0] else (x, 0, -1))
    return out


def find_tooltips(img: Image.Image) -> list[tuple[int, int, int, int]]:
    """툴팁 상자 [(x0, y0, x1, y1)] 왼쪽부터. 기본 방식 결과는 그대로 두고, 짧게 끊긴 열을 잇는 방식(훈장처럼 짧은 툴팁)으로
    찾은 상자 중 기존 상자와 겹치지 않는 것만 보탠다 — 바로 바꾸면 실제 화면 25/88장·수집본 74/174장의 상자가 달라졌다(2026-10-06)."""
    base = _find(img, max_gap=0, widen=False)
    a = np.asarray(img.convert("RGB")).astype(np.int16)
    extra = [b for b in _find(img, max_gap=3, widen=True)
             if not any(_overlap(b, o) for o in base) and _looks_like_text(a, b)]
    return sorted(set(base + extra))


def _looks_like_text(a: np.ndarray, box) -> bool:
    """보충 상자는 글자 줄이 있어야 툴팁으로 본다 — 깃발·어두운 배경 같은 가짜를 AI에 보내지 않으려고.
    실측(2026-10-06): 훈장 툴팁 글자 줄 12·밝은 글자 5%, 기존 방식이 찾은 툴팁 최소 6줄, 게임 속 가짜(깃발) 0줄."""
    x0, y0, x1, y1 = box
    sub = a[y0:y1, x0:x1]
    luma = 0.299 * sub[..., 0] + 0.587 * sub[..., 1] + 0.114 * sub[..., 2]
    bright = luma > 170
    rows = bright.mean(axis=1) > 0.02
    lines = int(rows[0]) + int(np.count_nonzero(rows[1:] & ~rows[:-1]))
    return lines >= 8 and 0.03 <= bright.mean() <= 0.20


def _overlap(a, b) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _find(img: Image.Image, max_gap: int, widen: bool) -> list[tuple[int, int, int, int]]:
    """툴팁 상자 [(x0, y0, x1, y1)] 왼쪽부터.
    툴팁은 경매장 창 위에 겹쳐 뜨고 창 테두리도 같은 남회색이라, 어두운 덩어리로는 둘이 붙는다(2026-10-04 실측).
    그래서 '위에서 아래로 길게 이어지는 어두운 열'을 모아 툴팁 폭을 잡는다 — 경매장 창 본문은 흰색이라 끊긴다."""
    a = np.asarray(img.convert("RGB")).astype(np.int16)
    dark = _dark_mask(a)
    h, w = dark.shape
    gh, gw = h // CELL, w // CELL
    grid = _close(dark[: gh * CELL, : gw * CELL].reshape(gh, CELL, gw, CELL).mean(axis=(1, 3)) > 0.45)
    need = MIN_H // CELL
    runs = _column_runs(grid, max_gap)
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
        gx0, gx1 = g[0][0], g[-1][0]
        # 아이콘 칸처럼 밝은 것에 막혀 짧아진 가장자리 열: 같은 높이에서 절반 이상 어두우면 툴팁에 넣는다(훈장 아이콘)
        rows = slice(y0 // CELL, y1 // CELL)
        while widen and gx0 > 0 and grid[rows, gx0 - 1].mean() >= 0.5:
            gx0 -= 1
        while widen and gx1 < gw - 1 and grid[rows, gx1 + 1].mean() >= 0.5:
            gx1 += 1
        box = (gx0 * CELL, y0, (gx1 + 1) * CELL, y1)
        for part in _split_columns(a, box):
            px0, py0, px1, py1 = _refine(dark, part)
            if MIN_W <= px1 - px0 <= MAX_W and py1 - py0 >= MIN_H:
                boxes.append((px0, py0, px1, py1))
    return sorted(boxes)


def crop(img: Image.Image, box: tuple[int, int, int, int], margin: int = 4) -> Image.Image:
    x0, y0, x1, y1 = box
    return img.crop((max(0, x0 - margin), max(0, y0 - margin), min(img.width, x1 + margin), min(img.height, y1 + margin)))


def stars_near(img: Image.Image, box: tuple[int, int, int, int]) -> int | None:
    """툴팁 상자 위쪽 띠까지 포함해 별을 센다 — 첫 별 줄이 어두운 패널 위(배경)에 걸치면 상자가 그 아래에서 시작한다
    (2026-10-05 자동 프레임 40장 실측: 22성을 7성으로 셈)."""
    x0, y0, x1, _ = box
    region = img.crop((max(0, x0 - 4), max(0, y0 - 40), min(img.width, x1 + 4), min(img.height, y0 + STAR_BAND)))
    return count_stars(region, band=region.height)


def count_stars(tip: Image.Image, band: int = STAR_BAND) -> int | None:
    """툴팁 맨 위 별 줄에서 노란(채워진) 별 개수. 노란 별이 하나도 없으면 None(0성인지 잘린 건지 모른다)."""
    a = np.asarray(tip.convert("RGB")).astype(np.int16)[:band]
    # 채워진 별: 노랑~주황(빨강 높고 파랑 낮음). 화면에 따라 주황으로 보인다(2026-10-05 실측: 19성을 못 셈)
    yellow = (a[..., 0] > 200) & (a[..., 1] > 120) & (a[..., 2] < 110) & (a[..., 0] - a[..., 2] > 120)
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
        if bw >= 4 and bh >= 4 and 0.6 <= bw / bh <= 1.7:   # 별은 정사각형에 가깝다(가는 선 제외, 경계에 잘린 별은 납작할 수 있다)
            areas.append((n, (x0 + x1) / 2, (y0 + y1) / 2, bw))
    big = [b for b in areas if b[0] >= 6]
    if not big:
        return None
    ref = float(np.percentile([b[0] for b in big], 75))
    blobs = sorted((b for b in big if b[0] >= 0.45 * ref), key=lambda b: b[2])  # 반짝이(작은 점) 제외
    return _count_star_rows(blobs)


def _count_star_rows(blobs) -> int | None:
    """별 줄은 툴팁 맨 위에 있고, 같은 크기의 별이 같은 간격(5개마다 조금 넓게)으로 늘어선다.
    글자(주황 '교환 불가' 등)는 크기·간격이 들쭉날쭉하다 — 맨 위에서부터 '고른 줄'만 센다(2026-10-05 실측)."""
    if not blobs:
        return None
    rows, cur = [], [blobs[0]]
    for b in blobs[1:]:
        if abs(b[2] - np.mean([c[2] for c in cur])) <= max(3, 0.5 * b[3]):
            cur.append(b)
        else:
            rows.append(cur)
            cur = [b]
    rows.append(cur)
    total, step, started = 0, None, False
    for row in rows:
        row = sorted(row, key=lambda b: b[1])
        sizes = [b[0] for b in row]
        xs = [b[1] for b in row]
        diffs = np.diff(xs)
        regular = max(sizes) <= 1.7 * min(sizes)
        if regular and len(diffs):
            base = float(diffs.min()) if step is None else step
            regular = base > 0 and all(0.7 * base <= d <= 2.3 * base for d in diffs)
        elif regular:
            # 덩어리 하나뿐인 줄: 이미 센 별 줄 바로 다음(16성 등)일 때만 별로 본다
            regular = started and step is not None and abs(sizes[0] - ref_size) <= 0.6 * ref_size
        if not regular:
            if started:
                break
            continue  # 별 줄 위쪽 배경(노을 등)의 들쭉날쭉한 덩어리는 건너뛴다(2026-10-05 실측)
        if not started:
            started, ref_size = True, float(np.median(sizes))
            step = step or (float(diffs.min()) if len(diffs) else None)
        total += len(row)
        if len(row) < 15:  # 덜 찬 줄 다음에는 채워진 별이 없다
            break
    return total or None


def _distance(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def correct_name(name: str | None, names) -> tuple[str | None, bool]:
    """한 글자 틀린 이름만 알려진 이름으로 바로잡는다("에테르널"→"에테르넬"). 그 밖에는 그대로."""
    if not name or name in names:
        return name, False
    m = difflib.get_close_matches(name, list(names), n=1, cutoff=0.8)
    if m and _distance(name, m[0]) <= 1:  # 두 글자 차이는 다른 템일 수 있다(나이트↔메이지, 2026-10-05 실측)
        return m[0], True
    return name, False
