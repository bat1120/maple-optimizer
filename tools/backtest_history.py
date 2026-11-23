"""실딜 계산 신뢰도 측정: 과거 기록으로 맞혀 보기(2026-11-23 사용자).

같은 캐릭터의 두 날짜 A(앞)·B(뒤)를 넥슨 Open API에서 불러와,
  'A 시점만 알고(잔차 보정은 A에서) B 시점의 장비·하이퍼·어빌·심볼·유니온·링크를 넣으면 B의 스탯창이 얼마가 나올까'
를 엔진으로 예측하고, B의 실제 스탯창(넥슨 API 값)과 비교한다. 화면이 '이 템을 끼면 +N%'라고 할 때 쓰는 것과 같은 계산이다.

    uv run python tools/backtest_history.py 닉네임 [--days 14] [--points 14] [--out 경로.json]

- 호출량: 날짜 하나에 13번쯤. 서버와 같은 캐시(.cache/cache.sqlite3, 과거 날짜 30일 보관)를 써서 다시 돌리면 호출하지 않는다.
  호출량 초과(RateLimited)가 나면 그 자리에서 멈추고 모은 것까지만 계산한다. 대량·주기 수집용이 아니다.
- 키는 .env나 환경변수에서 읽고 출력하지 않는다.
- 비교 지표: 스탯공격력(스탯창 최대값), 보스 실딜 지수(방어율 300%), 주스탯, 공격력/마력.
  '안 바뀐다고 본 경우'(A의 값을 그대로 B의 예측으로)도 같이 적는다 — 엔진이 변화의 얼마를 설명하는지 보려고.
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

from engine.stats.jobs import job_profile  # noqa: E402
from engine.stats.metrics import BossProfile, boss_index, stat_attack  # noqa: E402
from engine.stats.residual import calibrate, predict, preset_items, sources_for  # noqa: E402
from engine.stats.sets import SetCatalog  # noqa: E402
from nexon.client import NexonClient, NexonError, RateLimited, load_api_key  # noqa: E402
from nexon.convert import snapshot  # noqa: E402
from server.cache import BundleCache  # noqa: E402

CATALOG, BOSS = SetCatalog.load(), BossProfile("방어율 300%", 300.0)


def pct(new: float, old: float) -> float:
    return (new / old - 1) * 100 if old else 0.0


def changed_slots(a, b) -> list[str]:
    """두 시점의 착용 장비에서 달라진 부위(이름·스타포스·스탯 중 하나라도 다르면)."""
    ia, ib = preset_items(a, a.active_equipment_preset), preset_items(b, b.active_equipment_preset)
    return sorted(s for s in set(ia) | set(ib)
                  if (ia.get(s) is None) != (ib.get(s) is None)
                  or (ia.get(s) is not None and (ia[s].name, ia[s].starforce, ia[s].stats) != (ib[s].name, ib[s].starforce, ib[s].stats)))


def compare(a, b) -> dict:
    """A에서 보정하고 B의 출처를 넣어 B의 스탯창을 예측한다."""
    job = job_profile(b.character_class)
    main = job.mains[0]
    attack = "matk" if job.attack == "MATK" else "atk"
    part = preset_items(b, b.active_equipment_preset)["무기"].part
    pred = predict(calibrate(a, CATALOG), sources_for(b, b.active_setting, CATALOG))
    # 지수는 예측·실제 모두 같은 식(크확 100%)으로 — 스탯 예측 오차가 실딜 지수에 얼마로 번지는지만 본다
    idx = lambda f: boss_index(f, job, part, BOSS)  # noqa: E731
    actual_sa, base_sa = b.final.stat_attack_max, a.final.stat_attack_max
    return {
        "from": a.date, "to": b.date, "level": [a.level, b.level], "changed_slots": changed_slots(a, b),
        "setting_changed": a.active_setting != b.active_setting,
        # 실제로 얼마나 변했나(A → B)
        "actual_change_pct": {"stat_attack": pct(actual_sa, base_sa), "boss_index": pct(idx(b.final), idx(a.final)),
                              "main_stat": pct(b.final.stats[main], a.final.stats[main])},
        # 예측 오차(예측 ÷ 실제 − 1, %)
        "error_pct": {"stat_attack": pct(stat_attack(pred, job, part), actual_sa), "boss_index": pct(idx(pred), idx(b.final)),
                      "main_stat": pct(pred.stats[main], b.final.stats[main]),
                      "attack": pct(getattr(pred, attack), getattr(b.final, attack))},
        # 식 자체의 오차: B의 실제 스탯으로 스탯공격력 식을 돌린 값 ÷ 스탯창 값 − 1
        "formula_error_pct": pct(stat_attack(b.final, job, part), actual_sa),
        "combat_power": [a.final.combat_power, b.final.combat_power],
    }


def summarize(rows: list[dict], key: str) -> dict | None:
    v = [abs(r["error_pct"][key]) for r in rows]
    if not v:
        return None
    return {"n": len(v), "mean_abs": statistics.fmean(v), "median_abs": statistics.median(v), "max_abs": max(v),
            "bias": statistics.fmean(r["error_pct"][key] for r in rows)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--days", type=int, default=14, help="날짜 간격(일)")
    ap.add_argument("--points", type=int, default=14, help="불러올 날짜 수")
    ap.add_argument("--out", default=str(ROOT / "tools" / "backtest_out" / "history.json"))
    args = ap.parse_args()

    client = NexonClient(load_api_key(ROOT))
    cache = BundleCache(str(ROOT / ".cache" / "cache.sqlite3"), time.time)
    last = dt.date.today() - dt.timedelta(days=2)  # 어제 데이터는 아직 준비 중일 수 있다
    days = [last - dt.timedelta(days=args.days * i) for i in range(args.points)][::-1]
    snaps, fetched = [], 0
    for day in days:
        body = cache.get(args.name, day)
        if body is None:
            try:
                body = client.fetch_bundle(args.name, day)
            except RateLimited:
                print(f"{day}: 호출량 초과 — 여기서 멈추고 모은 것까지만 계산해요")
                break
            except NexonError as e:
                print(f"{day}: 불러오지 못함({e.code})")
                continue
            cache.put(args.name, day, body)
            fetched += 1
        try:
            snaps.append(snapshot(body))
        except Exception as e:  # noqa: BLE001 — 그 날짜 데이터가 비어 있으면(캐릭터 생성 전 등) 건너뛴다
            print(f"{day}: 변환하지 못함({type(e).__name__})")
    print(f"날짜 {len(snaps)}개(새로 불러온 날짜 {fetched}개)")
    if len(snaps) < 2:
        return 1

    step = [compare(a, b) for a, b in zip(snaps, snaps[1:])]            # 이웃한 두 날짜(약 2주 뒤)
    far = [compare(snaps[0], b) for b in snaps[2:]]                      # 가장 옛 날짜에서 보정 → 점점 먼 뒤
    moved = [r for r in step if abs(r["actual_change_pct"]["boss_index"]) >= 0.5]  # 실제로 뭔가 바뀐 구간만
    out = {
        "name_points": len(snaps), "first": snaps[0].date, "last": snaps[-1].date, "job": snaps[-1].character_class,
        "summary": {
            "이웃 날짜 전체": {k: summarize(step, k) for k in ("stat_attack", "boss_index", "main_stat", "attack")},
            "이웃 날짜 중 실딜이 0.5% 이상 변한 구간": {k: summarize(moved, k) for k in ("stat_attack", "boss_index")},
            "가장 옛 날짜 기준(먼 뒤)": {k: summarize(far, k) for k in ("stat_attack", "boss_index")},
            "식 자체(스탯공격력)": {"mean_abs": statistics.fmean(abs(r["formula_error_pct"]) for r in step),
                              "max_abs": max(abs(r["formula_error_pct"]) for r in step)},
        },
        "step": step, "far": far,
    }
    path = pathlib.Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out["summary"], ensure_ascii=False, indent=1))
    print(f"저장: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
