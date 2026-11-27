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
from nexon.client import NexonClient, NexonError, RateLimited, load_api_key  # noqa: E402

OUT = ROOT / "engine" / "data" / "skill_share.json"


# 랭킹 API의 class 값은 '직업군-전직'인데 시그너스·레지스탕스·데몬은 직업군 이름이 전사·마법사가 아니다.
# 2026-11-27 수집에서 소울마스터·미하일·플레임위자드·블래스터·데몬슬레이어·데몬어벤져가 '없음'이라 후보로 넣었다 —
# 아래 이름은 넥슨 문서로 확인하지 못한 후보다(틀리면 다음 후보로 넘어가고, 호출 1번이 더 든다)
_RANK_GROUPS = {"기사단": "소울마스터 미하일 플레임위자드 윈드브레이커 나이트워커 스트라이커",
                "레지스탕스": "블래스터 배틀메이지 와일드헌터 메카닉", "데몬": "데몬슬레이어 데몬어벤져"}


def rank_classes(job: str) -> list[str]:
    extra = [f"{g}-{job}" for g, names in _RANK_GROUPS.items() if job in names.split()]
    return extra + [f"{b}-{job}" for b in _BRANCHES.get(job, ())] + [f"{job}-{job}", f"{job}-전체 전직"]


def _rank(c: NexonClient, job: str, day: str) -> list[dict]:
    for cls in rank_classes(job):
        try:
            rows = (c._request("ranking/overall", {"date": day, "class": cls}) or {}).get("ranking") or []
        except RateLimited:
            raise                                       # 호출 한도는 '기록 없음'이 아니다 — 바로 멈춘다(2026-11-27: 삼키고 끝까지 불렀다)
        except NexonError:
            continue
        mine = [r for r in rows if job in (r.get("class_name"), r.get("sub_class_name"))]
        if mine:
            return mine
    return []


def collect(c: NexonClient, job: str, top: int, day: str) -> dict | None:
    samples = []
    rows = _rank(c, job, day)
    if not rows:
        print(f"  {job}: 랭킹에서 이 직업을 찾지 못했어요(class 이름 후보 {rank_classes(job)})")
    for row in rows[: top * 8]:  # 연무장 기록이 있는 캐릭터가 드물다(2026-10-07 레테 상위 24명 중 1명)
        if len(samples) >= top:
            break
        try:
            ocid = c.get_ocid(row["character_name"])
            reps = (c._request("battle-practice/replay-id", {"ocid": ocid}) or {}).get("replay_list") or []
        except RateLimited:
            raise
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


def merge_job(data: dict, job: str, r: dict) -> bool:
    """표본이 기존보다 적은 결과로 덮어쓰지 않는다(2026-11-02: 렌 6명 → 1명으로 덮일 뻔). 바꿨으면 True."""
    old = data["jobs"].get(job)
    if old and r["samples"] < old.get("samples", 0):
        return False
    data["jobs"][job] = r
    return True


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
        try:
            r = collect(c, job, a.top, day)
        except RateLimited:
            print(f"{job}: 넥슨 API 호출 한도에 걸려 여기서 멈춰요(운영과 같은 키) — 이 직업부터 다음에 다시")
            break
        print(job, "없음" if r is None else f"{r['samples']}명, 스킬 {len(r['shares'])}개")
        if r and not merge_job(data, job, r):
            print(f"  {job}: 기존 {data['jobs'][job]['samples']}명보다 적어 유지")
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
