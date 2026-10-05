"""인터넷 메이플 툴팁 자동 수집 (내 PC 전용, .data/web_tooltips).

사용: uv run python tools/collect_tooltips.py --pages 5
- 인벤 메이플 게시판(robots.txt가 막지 않은 경로)의 글 목록 → 글 → '글 쓴 날 올라온' 본문 이미지만 받는다.
- 코드(server.tooltip.find_tooltips)가 툴팁이라고 판단한 이미지만 저장한다. 출처 URL·게시일을 함께 남긴다.
- 요청 사이 간격(--delay)을 두고, 이미 본 글·이미지는 다시 받지 않는다(이어서 실행 가능).
- 다른 사람이 올린 이미지다: 평가·연구용으로 내 PC에만 둔다. 학습에 쓸지는 따로 판단한다(goal-log 2026-10-05).
"""
import argparse
import hashlib
import io
import json
import pathlib
import re
import sys
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PIL import Image, ImageOps  # noqa: E402

from server.tooltip import find_tooltips  # noqa: E402

UA = "Mozilla/5.0 (compatible; maple-optimizer-collector; personal research)"
BOARDS = (2300, 5974, 2294, 2295, 2296, 2297, 2298)  # 질문답변·자유·직업 게시판 (robots.txt 허용)
_DATE = re.compile(r"(20\d{2})-(\d{2})-(\d{2}) \d{2}:\d{2}")


def post_date(html: str) -> str | None:
    m = _DATE.search(html)
    return f"{m[1]}-{m[2]}-{m[3]}" if m else None


def content_images(html: str, date: str) -> list[str]:
    """글 쓴 날 올라온 본문 이미지(사이드바·썸네일 제외)."""
    day = date.replace("-", "/")
    rx = re.compile(rf"https?://upload\d*\.inven\.co\.kr/upload/{day}/bbs/i\d+\.(?:png|jpg|jpeg)")
    return list(dict.fromkeys(rx.findall(html)))


def is_tooltip_image(img: Image.Image) -> bool:
    """잘라 올린 툴팁(이미지 대부분이 툴팁) 또는 툴팁이 뜬 전체 화면."""
    img = img.convert("RGB")
    pad = ImageOps.expand(img, border=30, fill=(235, 235, 235))  # 잘라 올린 툴팁도 가장자리가 생기게
    boxes = find_tooltips(pad)
    if any((x1 - x0) * (y1 - y0) >= 0.6 * img.width * img.height for x0, y0, x1, y1 in boxes):
        return True
    return img.width >= 1000 and bool(boxes)


def _get(url: str, referer: str | None = None) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, **({"Referer": referer} if referer else {})})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=3)
    ap.add_argument("--delay", type=float, default=0.5)
    ap.add_argument("--max-posts", type=int, default=600)
    ap.add_argument("--out", default=str(ROOT / ".data" / "web_tooltips"))
    a = ap.parse_args()
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    seen_posts = out / "seen_posts.txt"
    seen = set(seen_posts.read_text(encoding="utf-8").split()) if seen_posts.exists() else set()
    posts = []
    for b in BOARDS:
        for p in range(1, a.pages + 1):
            html = _get(f"https://www.inven.co.kr/board/maple/{b}?p={p}").decode("utf-8", "replace")
            posts += [x for x in dict.fromkeys(re.findall(rf"board/maple/{b}/\d+", html)) if x not in seen]
            time.sleep(a.delay)
    posts = list(dict.fromkeys(posts))[: a.max_posts]
    saved = 0
    for n, post in enumerate(posts, 1):
        url = f"https://www.inven.co.kr/{post}"
        try:
            html = _get(url).decode("utf-8", "replace")
            date = post_date(html)
            for img_url in content_images(html, date) if date else []:
                key = hashlib.sha1(img_url.encode()).hexdigest()[:16]
                if (out / f"{key}.png").exists():
                    continue
                raw = _get(img_url, referer="https://www.inven.co.kr/")
                img = Image.open(io.BytesIO(raw))
                if is_tooltip_image(img):
                    img.convert("RGB").save(out / f"{key}.png")
                    (out / f"{key}.json").write_text(json.dumps(
                        {"image_url": img_url, "post": url, "posted": date, "size": img.size,
                         "collected_at": time.strftime("%Y-%m-%d %H:%M")}, ensure_ascii=False), encoding="utf-8")
                    saved += 1
                time.sleep(a.delay / 2)
        except Exception as e:  # noqa: BLE001 — 글 하나 실패해도 계속
            print(f"건너뜀 {post}: {type(e).__name__}", file=sys.stderr)
        with seen_posts.open("a", encoding="utf-8") as f:
            f.write(post + "\n")
        if n % 50 == 0:
            print(f"글 {n}/{len(posts)} · 툴팁 {saved}장")
        time.sleep(a.delay)
    total = len(list(out.glob("*.png")))
    print(f"끝: 글 {len(posts)}개 확인, 새 툴팁 {saved}장 저장 (모은 툴팁 전체 {total}장) → {out}")


if __name__ == "__main__":
    main()
