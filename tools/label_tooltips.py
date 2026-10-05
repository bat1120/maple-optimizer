"""모은 툴팁 자동 라벨링: 지금 화면 분석(analyze_frame)으로 읽고, 코드 검사를 모두 통과한 것만 '검증됨'으로 남긴다.

사용: uv run python tools/label_tooltips.py --max 30
- AI API 비용이 든다(툴팁 1장 = 이미지 2장 판독). --max로 한 번에 처리할 수를 정한다. 이미 라벨이 있으면 건너뛴다.
- 검사: 괄호 합 검산, 공식 큐브 옵션표, 잠재 줄 존재, 스타포스는 별 세기 값. AI 판독을 그대로 정답으로 쓰지 않는다.
"""
import argparse
import base64
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server.vision import checksum_failures, unverified_lines  # noqa: E402


def verify(x: dict) -> tuple[bool, list[str]]:
    why = []
    lines = list(x.get("potential_lines") or []) + list(x.get("additional") or [])
    if not lines:
        why.append("잠재·에디 줄 없음(장비 툴팁이 아님)")
    why += [f"검산: {c}" for c in checksum_failures(x)]
    why += [f"옵션표에 없음: {u}" for u in unverified_lines(lines)]
    if not x.get("total"):
        why.append("총 옵션 없음")
    return (not why), why


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=30)
    ap.add_argument("--dir", default=str(ROOT / ".data" / "web_tooltips"))
    a = ap.parse_args()
    import openai

    from server.app import _env
    from server.vision import analyze_frame
    client = openai.OpenAI(api_key=_env("OPENAI_API_KEY"))
    d = pathlib.Path(a.dir)
    todo = [p for p in sorted(d.glob("*.png")) if not (d / f"{p.stem}.label.json").exists()][: a.max]
    tokens, passed = 0, 0
    for p in todo:
        used = []
        url = "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode()
        data = analyze_frame(client, url, on_usage=used.append)
        tokens += sum(used)
        rows = []
        for x in data["listings"]:
            ok, why = verify(x)
            rows.append({"verified": ok, "problems": why, "listing": x})
        passed += any(r["verified"] for r in rows)
        (d / f"{p.stem}.label.json").write_text(json.dumps({"tooltips_found": data.get("tooltips_found"), "rows": rows,
                                                            "tokens": sum(used)}, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{p.name}: 매물 {len(rows)}개, 검증 통과 {sum(r['verified'] for r in rows)}개")
    print(f"끝: {len(todo)}장 처리, 검증 통과한 툴팁 {passed}장, 토큰 {tokens}")


if __name__ == "__main__":
    main()
