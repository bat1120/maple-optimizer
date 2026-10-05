"""자동 테스트셋(사람 손 없음): 검증된 툴팁을 게임 화면 + 경매장 창 위에 원래 크기로 붙여 화면 공유 프레임을 만들고,
프레임 전체를 읽은 결과가 툴팁 단독 라벨과 같은지 잰다. 화면 공유에서만 생기는 문제(툴팁 찾기·크기·목록 행)를 본다.

사용: uv run python tools/eval_frames.py --n 40
- 배경: .data/backgrounds(game_1366.png, game_1920.png, auction_window.png), 툴팁·라벨: .data/web_tooltips
- AI API 비용이 든다(프레임 1장당 이미지 2장 이상 판독). 결과는 .data/eval_frames/report.json
- 한계: 라벨도 같은 판독기가 툴팁만 보고 만든 것 — '툴팁 단독과 화면 속에서 같은가'를 재는 일관성 시험이다.
"""
import argparse
import base64
import difflib
import io
import json
import pathlib
import random
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PIL import Image  # noqa: E402

from server.score import TOTAL_KEYS, compare  # noqa: E402,F401  (채점은 장비창 훑기와 같은 코드)

def compose(bg: Image.Image, window: Image.Image, tip: Image.Image, seed: int):
    """배경 위 경매장 창, 그 옆에 툴팁(원래 크기). 서비스 캡처처럼 JPEG 85로 압축. (프레임, 툴팁 상자)"""
    rnd = random.Random(seed)
    fr = bg.convert("RGB").copy()
    W, H = fr.size
    wx, wy = int(W * rnd.uniform(0.05, 0.2)), int(H * rnd.uniform(0.05, 0.15))
    fr.paste(window.convert("RGB"), (wx, wy))
    tx = min(max(0, wx + rnd.randint(250, 450)), W - tip.width)
    ty = min(max(0, wy + rnd.randint(-40, 60)), max(0, H - tip.height))
    fr.paste(tip.convert("RGB"), (tx, ty))
    buf = io.BytesIO()
    fr.save(buf, "JPEG", quality=85)
    return Image.open(io.BytesIO(buf.getvalue())), (tx, ty, tx + tip.width, ty + tip.height)


def _samples(d: pathlib.Path):
    """검증된 라벨 + 그 툴팁만 잘라낸 이미지."""
    from server.tooltip import crop, find_tooltips
    out = []
    for lab in sorted(d.glob("*.label.json")):
        data = json.loads(lab.read_text(encoding="utf-8"))
        rows = [r for r in data["rows"] if r["verified"]]
        if not rows:
            continue
        img = Image.open(d / f"{lab.name.split('.')[0]}.png").convert("RGB")
        boxes = find_tooltips(img)
        for r in rows:
            i = r["listing"].get("tooltip")
            if len(boxes) == data.get("tooltips_found") and isinstance(i, int) and i < len(boxes):
                out.append((lab.name.split(".")[0], crop(img, boxes[i]), r["listing"]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--seed", type=int, default=20261005)
    a = ap.parse_args()
    import openai

    from server.app import _env
    from server.vision import analyze_frame
    client = openai.OpenAI(api_key=_env("OPENAI_API_KEY"))
    data_dir = ROOT / ".data"
    bgs = [Image.open(data_dir / "backgrounds" / n).convert("RGB").resize(size)
           for n, size in (("game_1366.png", (1366, 768)), ("game_1920.png", (1920, 1080)))]
    window = Image.open(data_dir / "backgrounds" / "auction_window.png")
    samples = _samples(data_dir / "web_tooltips")
    random.Random(a.seed).shuffle(samples)
    out_dir = data_dir / "eval_frames"
    out_dir.mkdir(parents=True, exist_ok=True)
    rows, tok, t0 = [], 0, time.time()
    for k, (sid, tip, label) in enumerate(samples[: a.n]):
        bg = bgs[k % 2]
        frame, _ = compose(bg, window, tip, a.seed + k)
        buf = io.BytesIO()
        frame.save(buf, "JPEG", quality=95)
        url = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
        used = []
        res = analyze_frame(client, url, on_usage=used.append)
        tok += sum(used)
        cands = res["listings"] + res.get("equipped_items", [])
        best = max(cands, key=lambda x: difflib.SequenceMatcher(None, x.get("name") or "", label.get("name") or "").ratio(),
                   default=None)
        if not best or difflib.SequenceMatcher(None, best.get("name") or "", label.get("name") or "").ratio() < 0.6:
            rows.append({"id": sid, "size": bg.size, "found": False, "ok": 0, "n": 13, "miss": ["툴팁 못 찾음"]})
            print(f"{sid} {bg.size[0]}: 툴팁 못 찾음")
            continue
        ok, n, miss = compare(label, best)
        rows.append({"id": sid, "size": bg.size, "found": True, "ok": ok, "n": n, "miss": miss})
        print(f"{sid} {bg.size[0]}: {ok}/{n}" + (f" — {'; '.join(miss)}" if miss else ""))
    ok, n = sum(r["ok"] for r in rows), sum(r["n"] for r in rows)
    summary = {"frames": len(rows), "found": sum(r["found"] for r in rows), "fields_ok": ok, "fields": n,
               "accuracy": round(ok / n, 4) if n else None, "tokens": tok, "seconds": round(time.time() - t0)}
    (out_dir / "report.json").write_text(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=1),
                                         encoding="utf-8")
    print(f"끝: {summary}")


if __name__ == "__main__":
    main()
