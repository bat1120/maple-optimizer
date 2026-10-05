"""화면 판독 채점: 읽은 툴팁 한 개를 정답과 항목별로 비교한다.

- 자동 테스트셋(tools/eval_frames.py): 정답 = 툴팁만 따로 읽은 검증 라벨
- 장비창 훑기(POST /api/vision/score): 정답 = 넥슨 API의 내 착용 템 — 사람이 정답을 적지 않아도 된다
"""
import difflib

from engine.stats.snapshot import CharacterSnapshot, Item

TOTAL_KEYS = ("STR", "DEX", "INT", "LUK", "HP", "ATK", "MATK", "ALL%", "BOSS", "IED", "DMG")


def compare(label: dict, read: dict) -> tuple[int, int, list[str]]:
    """(맞은 항목 수, 항목 수, 틀린 항목 설명). 스타포스는 정답이 별을 센 값일 때만 채점한다."""
    ok = n = 0
    miss = []

    def chk(name, a, b):
        nonlocal ok, n
        n += 1
        if a == b:
            ok += 1
        else:
            miss.append(f"{name}: 정답 {a} / 읽음 {b}")

    chk("이름", label.get("name"), read.get("name"))
    chk("레벨", label.get("level"), read.get("level"))
    if label.get("starforce_source") == "별 세기":
        chk("스타포스", label.get("starforce"), read.get("starforce"))
    lt, rt = label.get("total") or {}, read.get("total") or {}
    for k in TOTAL_KEYS:
        if k in lt or k in rt:
            chk(f"총옵션 {k}", lt.get(k), rt.get(k))
    chk("윗잠 등급", label.get("potential_grade"), read.get("potential_grade"))
    lp, rp = label.get("potential_lines") or [], read.get("potential_lines") or []
    for i in range(len(lp)):
        chk(f"윗잠 {i + 1}", lp[i], rp[i] if i < len(rp) else None)
    chk("에디 등급", label.get("additional_grade"), read.get("additional_grade"))
    la, ra = label.get("additional") or [], read.get("additional") or []
    for i in range(len(la)):
        chk(f"에디 {i + 1}", la[i], ra[i] if i < len(ra) else None)
    return ok, n, miss


def expected_from_item(it: Item) -> dict:
    """넥슨 API 착용 템 → 툴팁에 보여야 할 값(총 옵션 = 잠재를 뺀 합계, 0인 줄은 툴팁에 안 나온다)."""
    c = it.core
    total = {k: c.flat[k] for k in ("STR", "DEX", "INT", "LUK", "HP", "ATK", "MATK") if c.flat.get(k)}
    four = {c.pct.get(s, 0) for s in ("STR", "DEX", "INT", "LUK")}
    if len(four) == 1 and next(iter(four)):
        total["ALL%"] = next(iter(four))
    for key, v in (("BOSS", c.boss), ("DMG", c.dmg), ("IED", sum(c.ied))):
        if v:
            total[key] = v
    return {"name": it.name, "level": it.level, "starforce": it.starforce, "starforce_source": "별 세기",
            "total": total, "potential_grade": it.potential_grade, "potential_lines": list(it.potentials),
            "additional_grade": it.additional_grade, "additional": list(it.additional)}


def score_reads(snap: CharacterSnapshot, reads: list[dict]) -> dict:
    """읽은 툴팁들을 착용 템(모든 장비 프리셋)과 이름으로 맞춰 채점. 같은 템을 여러 번 읽었으면 마지막 판독만."""
    own = {}
    for preset in snap.equipment_presets.values():
        for it in preset.values():
            if it.core is not None and it.potentials:
                own.setdefault(it.name, it)
    latest = {}
    unmatched = []
    for x in reads:
        name = x.get("name") or ""
        m = difflib.get_close_matches(name, list(own), n=1, cutoff=0.8)
        if m:
            latest[m[0]] = x
        else:
            unmatched.append(name)
    items, ok, n = [], 0, 0
    for nm, x in latest.items():
        o, k, miss = compare(expected_from_item(own[nm]), x)
        ok, n = ok + o, n + k
        items.append({"name": nm, "ok": o, "n": k, "miss": miss})
    return {"matched": len(items), "unmatched": unmatched, "fields_ok": ok, "fields": n,
            "accuracy": round(ok / n, 4) if n else None, "items": items,
            "note": "정답은 넥슨 API의 착용 템(약 15분 지연). 템을 최근에 바꿨다면 틀린 것처럼 나올 수 있어요."}
