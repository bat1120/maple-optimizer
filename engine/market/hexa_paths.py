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


def _spread(subs: tuple, rest: float, cap: float = 10) -> tuple:
    """남은 레벨을 부가 스탯에 반씩 나누되 한 줄 상한(10레벨, 나무위키 레벨표)을 넘긴 몫은 다른 줄로(2026-10-11)."""
    out = list(subs)
    while rest > 1e-9:
        open_ = [i for i, v in enumerate(out) if v < cap]
        if not open_:
            break
        share = rest / len(open_)
        for i in open_:
            add = min(share, cap - out[i])
            out[i] += add
            rest -= add
    return tuple(out)


def stat_options(snap, fragment_price: float, sunday: bool = False) -> list[dict]:
    """코어마다 고를 수 있는 선택지 — '강화 계속'(20등급 미만)과 '초기화 → 메인 L레벨 이상'. 실딜은 재지 않고
    outcomes [(확률, 지금 대비 스탯 변화 extra)]만 준다 — 어떤 세팅에서 잴지는 부르는 쪽이 정한다(경로 비교: 지금 템, 추천 조합: 갈아탄 뒤)."""
    if not fragment_price or not snap.hexa_stat:
        return []
    job = job_profile(snap.character_class)
    out = []
    for core in snap.hexa_stat:
        cur = _block(core["lines"], job)
        if cur["unknown"]:
            continue
        main_now = next(lv for _, lv, m in core["lines"] if m)
        main_name = next(n for n, _, m in core["lines"] if m)

        def extra(main_level, subs, core=core, cur=cur):
            return H.delta(_block(_lines(core, main_level, subs), job), cur)

        label = f"코어 {'I' * core['core']} 메인 {main_name.replace(' 증가', '')}"
        if core["grade"] < H.MAX_G:  # 강화 계속: 최종 메인 레벨 분포
            dist, frag = H.main_distribution(core["grade"], main_now, sunday)
            subs_now = [lv for _, lv, m in core["lines"] if not m]
            outcomes = [(q, extra(m, _spread(tuple(subs_now), (H.MAX_G - core["grade"]) - (m - main_now)))) for m, q in dist.items()]
            out.append({"core": core["core"], "name": f"{label} 강화 계속 {core['grade']}→20등급", "cost": frag * fragment_price,
                        "fragments": frag, "reset_meso": 0.0, "outcomes": outcomes})
        reset_meso = RESET_MESO[str(core["core"])]
        for target in range(main_now + 1, H.MAX_L + 1):
            r = H.reach_cost(target, reset_meso / fragment_price, sunday)
            sub = (H.MAX_G - target) / 2
            out.append({"core": core["core"], "name": f"{label} 초기화 → {target}레벨 이상", "target_level": target,
                        "cost": (r["fragments"] * fragment_price) + reset_meso,  # 지금 상태에서 첫 초기화 1회 포함
                        "fragments": r["fragments"], "reset_meso": reset_meso, "outcomes": [(1.0, extra(target, (sub, sub)))]})
    return out


def expected_index(ev, items, outcomes, extra: dict | None = None) -> float:
    """선택지 하나를 한 세팅(items, 이미 들어간 장비 밖 변화 extra)에서 잰 보스 지수의 평균."""
    from engine.stats.model import StatBlock
    total = 0.0
    for q, e in outcomes:
        merged = dict(extra or {})
        merged["pct"] = merged.get("pct", StatBlock()) + e["pct"]
        merged["nopct"] = merged.get("nopct", StatBlock()) + e["nopct"]
        total += q * ev.index(items, merged)
    return total


def hexa_stat_paths(pl, fragment_price: float, sunday: bool = False) -> list[dict]:
    out = []
    for o in stat_options(pl.snap, fragment_price, sunday):
        d = 0.0
        for q, e in o["outcomes"]:
            d += q * (pl.ev.index(pl.items, e) / pl.base - 1) * 100
        if d > 0 and o["cost"] > 0:
            out.append({"slot": "HEXA 스탯", "path": "HEXA 스탯", "name": o["name"], "cost": o["cost"], "delta_pct": d,
                        "per_100m": d / (o["cost"] / 1e8), "fragments": o["fragments"], "core": o["core"],
                        **({"target_level": o["target_level"]} if "target_level" in o else {}), "set_change": []})
    return out
