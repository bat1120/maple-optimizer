"""직업별 신뢰도 측정: 48개 직업을 한 번씩(2026-11-23 사용자: "48개 직업을 다 봐야 되잖아").

API 키 주인 계정의 캐릭터 목록(공식 Open API character/list, 호출 1번)에서 직업마다 레벨이 가장 높은 캐릭터를 골라,
과거 기준일을 넓게(직업마다 1개씩) 먼저 채우고 그다음 날짜를 더한다. 하루 호출 한도에 걸리면 그 자리에서 멈추고,
다음에 다시 돌리면 캐시(.cache/cache.sqlite3, 과거 날짜 30일 보관)에서 이어 간다 — 같은 날짜를 다시 부르지 않는다.

    uv run python tools/backtest_jobs.py [--dates 3] [--names 가,나,다] [--offline]

직업마다 보는 것:
- 식 오차: 그 날 실제 스탯으로 스탯공격력 식을 돌린 값 ÷ 스탯창 값 − 1 (직업별 주스탯·무기 상수가 맞는지. 날짜 1개면 된다)
- 계획: 업그레이드 계획이 오류 없이 나오는지
- 주스탯 예측 오차: 앞 날짜에서 보정하고 뒤 날짜의 장비·세팅을 넣어 맞혀 본 값(날짜 2개부터)
- 버프 섞인 날: 잔차(데미지·보공·크뎀·크확·최종뎀)가 그 캐릭터의 최저보다 높은 날 수

호출량: 날짜 하나에 13번쯤. 대량·주기 수집용이 아니다 — 계정에 없는 직업은 공식 종합 랭킹(ranking/overall, 직업당 호출 1~2번, 한 번 찾으면 파일에 적어 둔다)에서
맨 위 캐릭터 하나만 본다(2026-11-23 사용자 결정). --no-ranking이면 '캐릭터 없음'으로만 적는다.
키는 .env나 환경변수에서 읽고 출력하지 않는다.
"""
import argparse
import datetime as dt
import json
import pathlib
import statistics
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from backtest_history import compare, pct  # noqa: E402
from engine.stats import jobs  # noqa: E402
from engine.stats.jobs import UnsupportedJob, job_profile  # noqa: E402
from engine.stats.metrics import stat_attack  # noqa: E402
from engine.stats.residual import FLOOR_KEYS, _raw_calibrate, preset_items  # noqa: E402
from nexon.client import NexonClient, NexonError, RateLimited, load_api_key  # noqa: E402
from nexon.convert import snapshot  # noqa: E402
from server import service  # noqa: E402
from server.cache import BundleCache  # noqa: E402

OUT = ROOT / "tools" / "backtest_out"
STEP = 4  # 서버의 버프 없는 기준과 같은 기준일(4일마다 하나) — 캐시를 같이 쓴다
ALL_JOBS = sorted(jobs._BRANCHES)


def anchors(n: int) -> list[dt.date]:
    first = dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date() - dt.timedelta(days=2)
    first -= dt.timedelta(days=first.toordinal() % STEP)
    return [first - dt.timedelta(days=STEP * i) for i in range(n)]


def account(client) -> list[dict]:
    """계정 캐릭터 목록. 하루에 한 번만 부른다(파일에 적어 둔다)."""
    path = OUT / "account.json"
    today = dt.date.today().isoformat()
    if path.exists():
        saved = json.loads(path.read_text(encoding="utf-8"))
        if saved.get("day") == today or client is None:
            return saved["characters"]
    if client is None:
        return []
    body = client._request("character/list", {})
    chars = [{"name": c.get("character_name"), "job": c.get("character_class"), "level": c.get("character_level") or 0}
             for a in body.get("account_list", []) for c in a.get("character_list", [])]
    OUT.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"day": today, "characters": chars}, ensure_ascii=False), encoding="utf-8")
    return chars


# 공식 랭킹(ranking/overall)의 class 값 후보. 넥슨 문서의 표기는 '계열-직업' 또는 '직업-전체 전직'인데 직업마다 어느 쪽인지는
# 응답으로 확인한다(돌려받은 캐릭터의 직업이 찾는 직업과 같을 때만 쓴다) — 틀린 후보는 빈 결과라 호출 한두 번만 더 든다.
_RANK_GROUPS = {
    "전사": ("히어로", "팔라딘", "다크나이트"), "마법사": ("아크메이지(불,독)", "아크메이지(썬,콜)", "비숍"),
    "궁수": ("보우마스터", "신궁", "패스파인더"), "도적": ("나이트로드", "섀도어", "듀얼블레이더"), "해적": ("바이퍼", "캡틴", "캐논마스터"),
    "기사단": ("소울마스터", "플레임위자드", "윈드브레이커", "나이트워커", "스트라이커", "미하일"),
    "레지스탕스": ("배틀메이지", "와일드헌터", "메카닉", "데몬슬레이어", "데몬어벤져", "제논", "블래스터"),
    "초월자": ("제로",), "프렌즈 월드": ("키네시스",),
}


def rank_classes(job: str) -> list[str]:
    out = [f"{g}-{job}" for g, js in _RANK_GROUPS.items() if job in js]
    return out + [f"{job}-전체 전직"]


def ranked(client, job: str, day: dt.date) -> str | None:
    """계정에 없는 직업(2026-11-23 사용자: "없는 직업은 랭킹에서 해봐"): 공식 종합 랭킹에서 그 직업의 맨 위 캐릭터 하나.
    직업마다 한 번만 찾고 파일에 적어 둔다. 못 찾으면 None(호출량 초과는 그대로 올린다)."""
    path = OUT / "ranking.json"
    saved = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    if job in saved or client is None:
        return saved.get(job)
    for cls in rank_classes(job):
        try:
            body = client._request("ranking/overall", {"date": day.isoformat(), "class": cls})
        except RateLimited:
            raise
        except NexonError:
            continue
        for r in body.get("ranking") or []:
            if job in (r.get("sub_class_name"), r.get("class_name")) and r.get("character_name"):
                saved[job] = r["character_name"]
                OUT.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(saved, ensure_ascii=False), encoding="utf-8")
                return saved[job]
    return None


def measure(snaps: list) -> dict:
    """한 캐릭터의 날짜들(옛 → 최근)에서 직업 한 줄."""
    last = snaps[-1]
    row = {"level": last.level, "dates": len(snaps),
           "formula_error_pct": max(abs(pct(stat_attack(s.final, job_profile(s.character_class),
                                                        preset_items(s, s.active_equipment_preset)["무기"].part), s.final.stat_attack_max))
                                    for s in snaps)}
    try:
        plan = service.budget_roadmap(last, 300.0, None)
        row["plan_steps"] = len(plan["steps"])
        row["plan_first"] = " ".join(str(plan["steps"][0].get(k)) for k in ("slot", "path") if plan["steps"]) if plan["steps"] else None
    except Exception as e:  # noqa: BLE001 — 직업별로 어디서 깨지는지가 측정 대상이다
        row["plan_error"] = f"{type(e).__name__}: {e}"[:160]
    if len(snaps) >= 2:
        steps = [compare(a, b) for a, b in zip(snaps, snaps[1:])]
        for key in ("main_stat", "attack"):
            v = [abs(r["error_pct"][key]) for r in steps]
            row[f"{key}_error_pct"] = {"mean": statistics.fmean(v), "max": max(v)}
        cals = [_raw_calibrate(s, service.CATALOG) for s in snaps]
        low = {k: min(getattr(c, k) for c in cals) for k in FLOOR_KEYS}
        row["buffed_days"] = sum(any(getattr(c, k) > low[k] + 1e-6 for k in FLOOR_KEYS) for c in cals)
    return row


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dates", type=int, default=3, help="직업마다 볼 과거 날짜 수")
    ap.add_argument("--names", default="", help="쉼표로 나눈 닉네임(계정에 없는 직업을 채울 때). 계정 목록에 더해 본다")
    ap.add_argument("--no-ranking", action="store_true", help="계정에 없는 직업을 공식 랭킹에서 채우지 않는다")
    ap.add_argument("--offline", action="store_true", help="넥슨을 부르지 않고 캐시에 있는 것만으로 표를 만든다")
    args = ap.parse_args()

    client = None if args.offline else NexonClient(load_api_key(ROOT))
    cache = BundleCache(str(ROOT / ".cache" / "cache.sqlite3"), time.time)
    days = anchors(args.dates)
    stopped = None
    try:
        chars = account(client)
    except RateLimited:
        chars, stopped = account(None), "계정 목록(호출량 초과) — 저장해 둔 목록을 썼어요"
    except NexonError as e:
        print(f"계정 목록을 불러오지 못함({e.code})")
        chars = account(None)
    extra = [n.strip() for n in args.names.split(",") if n.strip()]

    # 직업 → 후보 캐릭터(레벨 높은 순). --names로 준 이름은 직업을 모르니 따로 본다
    by_job: dict[str, list[str]] = {}
    for c in sorted(chars, key=lambda c: -c["level"]):
        if c["job"] in jobs._BRANCHES and c["level"] >= 200:
            by_job.setdefault(c["job"], []).append(c["name"])
    source = {job: "계정" for job in by_job}
    if not args.no_ranking:
        for job in ALL_JOBS:                              # 계정에 없는 직업은 공식 랭킹에서 하나
            if job in by_job or job in jobs._UNSUPPORTED:
                continue
            try:
                name = ranked(client if stopped is None else None, job, days[0])
            except RateLimited:
                stopped, name = f"랭킹 {job}(호출량 초과)", ranked(None, job, days[0])
            if name:
                by_job[job], source[job] = [name], "랭킹"
    targets = [(job, names[0]) for job, names in by_job.items()] + [(None, n) for n in extra]

    bodies: dict[str, dict] = {name: {} for _, name in targets}
    fetched = 0
    for day in days:                                   # 넓게 먼저: 모든 직업의 첫 날짜 → 그다음 날짜
        for _, name in targets:
            body = cache.get(name, day)
            if body is None and client is not None and stopped is None:
                try:
                    body = client.fetch_bundle(name, day)
                except RateLimited:
                    stopped = f"{name} {day}(호출량 초과)"
                    continue
                except NexonError as e:
                    print(f"{name} {day}: 불러오지 못함({e.code})")
                    continue
                cache.put(name, day, body)
                fetched += 1
            if body is not None:
                bodies[name][day] = body

    rows: dict[str, dict] = {}
    for job, name in targets:
        snaps = []
        for day in sorted(bodies[name]):
            try:
                snaps.append(snapshot(bodies[name][day]))
            except UnsupportedJob as e:
                rows[job or name] = {"name": name, "status": "지원 안 함", "why": str(e)[:120]}
                break
            except Exception as e:  # noqa: BLE001 — 그 날짜가 비어 있으면(생성 전·미접속) 건너뛴다
                rows.setdefault("_skipped", {}).setdefault(name, []).append(f"{day}: {type(e).__name__}")
        if not snaps:
            rows.setdefault(job or name, {"name": name, "status": "아직 못 불러옴" if name not in rows.get("_skipped", {}) else "변환 실패"})
            continue
        key = job or snaps[-1].character_class
        try:
            rows[key] = {"name": name, "status": "측정함", "source": source.get(job, "직접 지정")} | measure(snaps)
        except Exception as e:  # noqa: BLE001
            rows[key] = {"name": name, "status": "계산 실패", "why": f"{type(e).__name__}: {e}"[:160]}
    for job in ALL_JOBS:
        if job not in rows:
            rows[job] = {"status": "지원 안 함", "why": jobs._UNSUPPORTED[job]} if job in jobs._UNSUPPORTED else {"status": "캐릭터 없음"}

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "jobs.json").write_text(json.dumps({"days": [d.isoformat() for d in days], "stopped": stopped, "jobs": rows},
                                              ensure_ascii=False, indent=1), encoding="utf-8")
    done = [j for j in ALL_JOBS if rows[j]["status"] == "측정함"]
    print(f"새로 불러온 날짜 {fetched}개 · 측정한 직업 {len(done)}/{len(ALL_JOBS)}" + (f" · 멈춘 곳: {stopped}" if stopped else ""))
    for job in ALL_JOBS:
        r = rows[job]
        if r["status"] != "측정함":
            print(f"{job:14} {r['status']} {r.get('why', '')}")
            continue
        ms = r.get("main_stat_error_pct")
        print(f"{job:14} {r['source']} Lv{r['level']} 날짜 {r['dates']} · 식 {r['formula_error_pct']:.3f}% · "
              + (f"주스탯 {ms['mean']:.2f}/{ms['max']:.2f}% · 버프 {r['buffed_days']}일 · " if ms else "")
              + (f"계획 오류 {r['plan_error']}" if "plan_error" in r else f"계획 {r['plan_steps']}단계"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
