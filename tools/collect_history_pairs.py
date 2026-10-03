"""과거 날짜 스냅샷에서 같은 캐릭터의 "사냥 세팅 날"과 "보스 세팅 날" 짝을 찾아 받는다 (G1 ④ 검증용).

1단계: 날짜별 character/stat만 받아(하루 1회) 아이템 드롭률·메소 획득량으로 사냥/보스를 가른다.
2단계: 드롭·메소가 가장 높은 날(사냥)과 가장 낮은 날(보스)의 전체 번들을 받는다.

사용: uv run python tools/collect_history_pairs.py <닉네임> [<닉네임> ...] --days 8 --until 2026-10-03
출력: .raw-history-pairs/<닉네임>/<YYYY-MM-DD>/<endpoint>.json  (git 제외)
"""
import argparse
import datetime as dt
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from nexon.client import ENDPOINTS, NexonClient, NexonError, load_api_key  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / ".raw-history-pairs"


def hunt_score(stat: dict) -> float:
    s = {x["stat_name"]: x["stat_value"] for x in stat.get("final_stat") or []}
    return float(s.get("아이템 드롭률") or 0) + float(s.get("메소 획득량") or 0)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="+")
    ap.add_argument("--days", type=int, default=8)
    ap.add_argument("--until", default="2026-10-03")
    a = ap.parse_args()
    client = NexonClient(load_api_key(ROOT))
    until = dt.date.fromisoformat(a.until)
    calls = 0
    for name in a.names:
        try:
            ocid = client.get_ocid(name)
        except NexonError as e:
            print(name, "ocid 실패", e)
            continue
        calls += 1
        scores = {}
        for i in range(a.days):
            day = until - dt.timedelta(days=i)
            calls += 1
            try:
                stat = client.get("character/stat", ocid, day)
            except NexonError as e:  # 데이터 준비 중(전날 데이터는 다음 날 02시 이후) 등
                print(name, day, "건너뜀:", e.code)
                continue
            if stat:
                scores[day] = hunt_score(stat)
        if len(scores) < 2 or max(scores.values()) - min(scores.values()) < 20:
            print(name, "세팅 변화 없음", sorted(set(scores.values())))
            continue
        hunt_day = max(scores, key=scores.get)
        boss_day = min(scores, key=scores.get)
        for day in (hunt_day, boss_day):
            d = OUT / name / day.isoformat()
            d.mkdir(parents=True, exist_ok=True)
            for ep in ENDPOINTS:
                body = client.get(ep, ocid, day)
                calls += 1
                (d / (ep.replace("/", "_") + ".json")).write_text(json.dumps(body, ensure_ascii=False, indent=1), encoding="utf-8")
        print(name, "짝", hunt_day, f"(드롭+메소 {scores[hunt_day]:.0f})", "↔", boss_day, f"({scores[boss_day]:.0f})")
    print("API 호출", calls)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
