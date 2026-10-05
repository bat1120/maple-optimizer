"""공식 큐브 확률표(메이플스토리 홈페이지 > 확률형 아이템 > 큐브)를 받아 engine/data/cube_tables.json에 저장한다.

사용: uv run python tools/fetch_cube_tables.py
- 윗잠: 블랙 큐브(5062010), 에디: 에디셔널 큐브(5062500)
- 등급: 에픽·유니크·레전드리, 부위: 아래 PARTS, 레벨 구간: 200 이하 / 201 이상 (2026-10-04 실측: 201레벨부터 수치 +1)
- 공개 안내 페이지를 0.4초 간격으로 조회한다(게임 서버·경매장과 무관).
"""
import datetime as dt
import html
import json
import pathlib
import re
import time
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar

BASE = "https://maplestory.nexon.com/Guide/OtherProbability/cube"
CUBES = {"잠재": "5062010", "에디": "5062500"}
GRADES = {"레어": 1, "에픽": 2, "유니크": 3, "레전드리": 4}
PARTS = {"무기": 1, "엠블렘": 2, "보조무기": 3, "모자": 6, "상의": 7, "하의": 9, "신발": 10, "장갑": 11, "망토": 12,
         "벨트": 13, "어깨장식": 14, "얼굴장식": 15, "눈장식": 16, "귀고리": 17, "반지": 18, "펜던트": 19}
BANDS = {"200": 200, "250": 250}  # 키는 구간의 대표 레벨(200 이하 / 201 이상) — 단계 계산용
# 옵션 문장 검사용(--all): 낮은 레벨 구간·레어 등급까지 받아 '공식표에 있는 문장' 목록을 넓힌다(2026-10-05: 점프력 +4·마력 +3 헛경보)
ALL_BANDS = {str(v): v for v in (10, 30, 50, 70, 90, 110, 130, 150, 160, 200, 250)}
OUT = pathlib.Path(__file__).resolve().parents[1] / "engine" / "data" / "cube_tables.json"
ROOT_DATA = pathlib.Path(__file__).resolve().parents[1] / ".data"

_ROW = re.compile(r"<td>([^<]+)</td>\s*<td>([\d.]+)%</td>")


def parse(page: str) -> list[dict[str, float]] | None:
    """'첫/두/세 번째 옵션' 표 세 개 → [{옵션: 확률%}] × 3."""
    parts = re.split(r"<th>(?:첫|두|세) 번째 옵션</th>", page)[1:]
    if not parts:
        return None  # 그 레벨 구간에 없는 부위(예: 201레벨 이상 엠블렘)
    out = []
    for p in parts:
        out.append({html.unescape(o).strip(): float(v) for o, v in _ROW.findall(p)})
    if len(out) != 3 or not all(out):
        raise ValueError(f"확률표 형식이 예상과 달라요 (표 {len(out)}개, 줄 수 {[len(x) for x in out]})")
    return out


def main():
    import sys
    all_mode = "--all" in sys.argv
    bands = ALL_BANDS if all_mode else BANDS
    out = ROOT_DATA / "cube_options_all.json" if all_mode else OUT  # 전체 표는 크다(2.6MB) — .data에 두고 문장 목록만 저장소에
    jar = CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    opener.open(f"{BASE}/addi", timeout=20).read()
    tables: dict = {}
    for kind, cube in CUBES.items():
        for grade, g in GRADES.items():
            for part, code in PARTS.items():
                for band, lv in bands.items():
                    body = urllib.parse.urlencode({"nCubeItemID": cube, "nGrade": g, "nPartsType": code, "nReqLev": lv}).encode()
                    req = urllib.request.Request(f"{BASE}/GetSearchProbList", data=body, headers={
                        "X-Requested-With": "XMLHttpRequest", "Referer": f"{BASE}/addi",
                        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"})
                    page = opener.open(req, timeout=20).read().decode("utf-8")
                    try:
                        parsed = parse(page)
                        if parsed is not None:
                            tables.setdefault(kind, {}).setdefault(grade, {}).setdefault(part, {})[band] = parsed
                    except ValueError as e:
                        raise ValueError(f"{kind} {grade} {part} {band}: {e}") from None
                    time.sleep(0.4)
            print(kind, grade, "ok")
    out.write_text(json.dumps({"_source": f"{BASE}/GetSearchProbList (블랙 5062010, 에디셔널 5062500)",
                               "_as_of": dt.date.today().isoformat(),
                               "_bands": "200 = 장비 레벨 200 이하, 250 = 201 이상",
                               "tables": tables}, ensure_ascii=False, indent=0), encoding="utf-8")
    print("saved", out)
    if all_mode:  # 화면 판독 검사용 옵션 문장 목록
        opts = sorted({o for k in tables.values() for g in k.values() for p in g.values() for b in p.values() for ln in b for o in ln})
        OUT.with_name("cube_options.json").write_text(json.dumps(
            {"_source": f"{BASE}/GetSearchProbList", "_as_of": dt.date.today().isoformat(),
             "_note": "잠재·에디 옵션 문장 목록(레어~레전드리, 장비 레벨 10~250 구간 합집합). 화면 판독 줄 검사용",
             "options": opts}, ensure_ascii=False, indent=0), encoding="utf-8")


if __name__ == "__main__":
    main()
