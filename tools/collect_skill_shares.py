"""직업별 보스 딜 지분(스킬 점유율) 기준값 모으기(2026-10-07): 넥슨 Open API 연무장(battle-practice) 결과.

공식 랭킹(ranking/overall, 직업 필터) 상위 캐릭터의 최신 연무장 기록에서 스킬별 damage_percent를 모아
직업마다 스킬별 중앙값을 engine/data/skill_share.json에 쓴다. 캐릭터 이름·리플레이 ID는 저장하지 않는다(직업 집계만).
연무장 조건: 방어율 380% 허수아비, 고정 버프 — 실제 보스와 다를 수 있다(나무위키 '연무장').

사용: uv run python tools/collect_skill_shares.py 레테 [히어로 …] [--top 8]
API 호출: 직업당 랭킹 1~3회 + 캐릭터당 2회.
"""
import argparse
import datetime as dt
import json
import pathlib
import statistics
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.stats.jobs import _BRANCHES  # noqa: E402
from nexon.client import NexonClient, NexonError, load_api_key  # noqa: E402

OUT = ROOT / "engine" / "data" / "skill_share.json"


def _rank(c: NexonClient, job: str, day: str) -> list[dict]:
    for cls in [f"{b}-{job}" for b in _BRANCHES.get(job, ())] + [f"{job}-{job}", f"{job}-전체 전직"]:
        try:
            rows = (c._request("ranking/overall", {"date": day, "class": cls}) or {}).get("ranking") or []
        except NexonError:
            continue
        mine = [r for r in rows if job in (r.get("class_name"), r.get("sub_class_name"))]
        if mine:
            return mine
    return []


def collect(c: NexonClient, job: str, top: int, day: str) -> dict | None:
    samples = []
    for row in _rank(c, job, day)[: top * 8]:  # 연무장 기록이 있는 캐릭터가 드물다(2026-10-07 레테 상위 24명 중 1명)
        if len(samples) >= top:
            break
        try:
            ocid = c.get_ocid(row["character_name"])
            reps = (c._request("battle-practice/replay-id", {"ocid": ocid}) or {}).get("replay_list") or []
        except NexonError:
            continue  # 연무장 기록이 없는 캐릭터
        if not reps:
            continue
        latest = max(reps, key=lambda r: (r.get("period_no") or 0, r.get("register_date") or ""))
        res = c._request("battle-practice/result", {"replay_id": latest["replay_id"]}) or {}
        shares = {s["skill_name"]: float(s["damage_percent"]) for s in res.get("skill_statistic") or []
                  if s.get("skill_name") and s.get("damage_percent") not in (None, "")}
        if shares:
            samples.append({"period": latest.get("period_no"), "date": (latest.get("register_date") or "")[:10], "shares": shares})
    if not samples:
        return None
    names = sorted({k for s in samples for k in s["shares"]})
    med = {k: round(statistics.median(s["shares"].get(k, 0.0) for s in samples), 3) for k in names}
    return {"collected": dt.date.today().isoformat(), "samples": len(samples),
            "periods": sorted({s["period"] for s in samples}), "record_dates": sorted({s["date"] for s in samples}),
            "shares": {k: v for k, v in sorted(med.items(), key=lambda kv: -kv[1]) if v > 0}}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("jobs", nargs="+")
    ap.add_argument("--top", type=int, default=8)
    a = ap.parse_args()
    c = NexonClient(load_api_key(ROOT))
    day = (dt.date.today() - dt.timedelta(days=1)).isoformat()
    data = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {
        "_source": "넥슨 Open API 연무장(battle-practice/result skill_statistic.damage_percent), 직업 랭킹 상위 캐릭터 최신 기록의 스킬별 중앙값",
        "_note": "연무장: 방어율 380% 허수아비·고정 버프. 캐릭터 이름은 저장하지 않는다", "jobs": {}}
    for job in a.jobs:
        r = collect(c, job, a.top, day)
        print(job, "없음" if r is None else f"{r['samples']}명, 스킬 {len(r['shares'])}개")
        if r:
            data["jobs"][job] = r
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
