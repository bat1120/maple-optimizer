"""경매장 목록 글자 모양 표(engine/data/list_glyphs.json)를 만든다.

입력: tests/fixtures/auction_list/*.png(실제 경매장 캡처에서 목록 부분만 자른 것) + labels.json(화면 글자 정답).
    uv run python tools/derive_list_glyphs.py
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image  # noqa: E402

from server.listprice import TABLE, build_table, learn  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "auction_list"


def collect() -> dict:
    labels = json.loads((FIXTURES / "labels.json").read_text(encoding="utf-8"))
    samples = []
    for name, want in sorted((k, v) for k, v in labels.items() if not k.startswith("_")):
        samples += learn(Image.open(FIXTURES / name), want["prices"], want["powers"])
    return {"_source": "tools/derive_list_glyphs.py — tests/fixtures/auction_list 캡처와 화면 글자 정답", **build_table(samples)}


if __name__ == "__main__":
    data = collect()
    TABLE.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{TABLE.name}: 견본 {len(data['glyphs'])}개, 글자 {''.join(data['classes'])}, 허용 거리 {data['max_dist']}")
