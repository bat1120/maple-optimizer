"""HEXA 스탯 경로(2026-10-07): 코어마다 '강화 계속'(20등급 미만)과 '초기화해서 메인 L레벨 이상'의 실딜·조각 기대값.

- 실딜: 지금 HEXA 스탯 대신 바뀐 스탯을 넣어 보스 지수를 다시 계산(engine/stats/hexa.py, 주력 스탯은 %미적용)
- 초기화 목표: 메인 L레벨, 부가 둘은 남은 (20−L)레벨을 반씩 나눈 평균(부가 종류는 그대로)
- 비용: 조각 기대값 × 조각 시세 + 초기화 메소(최적 초기화 시점, 나무위키 기대값표 재현). 조각 시세가 없으면 경로를 만들지 않는다
"""
from engine.stats import hexa as H
from engine.stats.jobs import job_profile

RESET_MESO = H._T["reset_meso"]


def _lines(core: dict, main_level: float | None = None, sub_levels: tuple | None = None) -> list:
    out = []
    subs = iter(sub_levels or ())
    for name, lv, is_main in core["lines"]:
        if is_main:
            out.append((name, main_level if main_level is not None else lv, True))
        else:
            out.append((name, next(subs) if sub_levels else lv, False))
    return out


def _block(lines, job):
    # 부가 스탯 평균 레벨이 소수일 수 있어 단위로 직접 계산(stat_block은 정수 레벨 표를 쓴다 — 메인은 정수만 넣는다)
    whole = [(n, int(lv), m) for n, lv, m in lines]
    b = H.stat_block(whole, job.mains[0], xenon=job.name == "제논")
    for n, lv, m in lines:
        frac = lv - int(lv)
        if frac and not m:
            extra = H.stat_block([(n, 1, False)], job.mains[0], xenon=job.name == "제논")
            for part in ("pct", "nopct"):
                for k, v in extra[part].flat.items():
                    b[part].flat[k] = b[part].flat.get(k, 0.0) + v * frac
                for attr in ("dmg", "boss", "cd"):
                    setattr(b[part], attr, getattr(b[part], attr) + getattr(extra[part], attr) * frac)
                b[part].ied += [x * frac for x in extra[part].ied]
    return b


def hexa_stat_paths(pl, fragment_price: float, sunday: bool = False) -> list[dict]:
    if not fragment_price or not pl.snap.hexa_stat:
        return []
    job = job_profile(pl.snap.character_class)
    out = []
    for core in pl.snap.hexa_stat:
        cur = _block(core["lines"], job)
        if cur["unknown"]:
            continue
        main_now = next(lv for _, lv, m in core["lines"] if m)
        main_name = next(n for n, _, m in core["lines"] if m)

        def gain(main_level, subs):
            new = _block(_lines(core, main_level, subs), job)
            return (pl.ev.index(pl.items, H.delta(new, cur)) / pl.base - 1) * 100

        label = f"코어 {'I' * core['core']} 메인 {main_name.replace(' 증가', '')}"
        if core["grade"] < H.MAX_G:  # 강화 계속: 최종 메인 레벨 분포의 평균 실딜
            dist, frag = H.main_distribution(core["grade"], main_now, sunday)
            subs_now = [lv for _, lv, m in core["lines"] if not m]
            d = 0.0
            for m, q in dist.items():
                rest = (H.MAX_G - core["grade"]) - (m - main_now)
                d += q * gain(m, tuple(s + rest / len(subs_now) for s in subs_now))
            cost = frag * fragment_price
            if d > 0 and cost > 0:
                out.append({"slot": "HEXA 스탯", "path": "HEXA 스탯", "name": f"{label} 강화 계속 {core['grade']}→20등급",
                            "cost": cost, "delta_pct": d, "per_100m": d / (cost / 1e8), "fragments": frag,
                            "core": core["core"], "set_change": []})
        reset_meso = RESET_MESO[str(core["core"])]
        for target in range(main_now + 1, H.MAX_L + 1):
            r = H.reach_cost(target, reset_meso / fragment_price, sunday)
            sub = (H.MAX_G - target) / 2
            d = gain(target, (sub, sub))
            cost = (r["fragments"] * fragment_price) + reset_meso  # 지금 상태에서 첫 초기화 1회 포함
            if d > 0:
                out.append({"slot": "HEXA 스탯", "path": "HEXA 스탯", "name": f"{label} 초기화 → {target}레벨 이상",
                            "cost": cost, "delta_pct": d, "per_100m": d / (cost / 1e8), "fragments": r["fragments"],
                            "core": core["core"], "target_level": target, "set_change": []})
    return out
