"""HEXA 스킬 코어 경로(2026-10-07): 코어를 다음 1레벨 올렸을 때의 실딜과 조각 비용.

- 효과: 실딜 상승(%) ≈ Σ(연결 스킬의 보스 딜 지분 × (그 스킬 데미지 배율 − 1))
  · 배율은 넥슨 API character/skill(6차)의 지금/다음 레벨 효과 문장에서 바뀐 % 숫자들의 비의 평균
    (강화 코어는 최종 데미지라 (100+다음)/(100+지금))
  · 강화 코어 문장은 줄마다 대상이 다를 수 있다(2026-10-08, 체인 커맨드 강화): 'X 스킬의 최종 데미지' → 이름에 X가 든 스킬 모두,
    'X의 최종 데미지'(X가 지분 표의 스킬) → 그 스킬, '… 중 데미지'(켜져 있는 동안만) → 켜진 시간을 몰라 빼고 skipped에 적는다,
    그 밖 → 코어의 기본 스킬
  · 10·20·30레벨 보너스(설명의 'N레벨 : 방어율 무시/보스 데미지')는 그 스킬에만 곱한다(방무는 곱연산으로 본다 — 미확인)
- 딜 지분: 그 캐릭터의 최신 연무장 기록(battle-practice/result)이 있으면 그것, 없으면 직업 기준값(engine/data/skill_share.json)
- 비용: engine/data/hexa_core_cost.json(다음 1레벨의 조각 × 조각 시세). 솔 에르다는 개수만 보여 준다
- API는 다음 1레벨 효과만 주므로 경로도 '다음 1레벨' 단위(헥사 코어 순서 도구와 같은 방식)
"""
import json
import pathlib
import re

_DATA = pathlib.Path(__file__).resolve().parents[1] / "data"
COST = json.loads((_DATA / "hexa_core_cost.json").read_text(encoding="utf-8"))["costs"]
_SHARE = _DATA / "skill_share.json"
_PCT = re.compile(r"(\d+(?:\.\d+)?)%")
_BONUS = re.compile(r"(\d+)레벨\s*:\s*([^\n]+)")
_BONUS_ITEM = re.compile(r"(방어율 무시|보스 몬스터 공격 시 데미지)\s*(\d+(?:\.\d+)?)%")
COLUMN = {"스킬 코어": "스킬", "마스터리 코어": "마스터리", "강화 코어": "강화", "공용 코어": "공용"}


def job_shares(job: str) -> dict | None:
    if not _SHARE.exists():
        return None
    return json.loads(_SHARE.read_text(encoding="utf-8")).get("jobs", {}).get(job)


def ratio(effect: str | None, nxt: str | None, final_damage: bool = False) -> float | None:
    """지금 → 다음 레벨 효과 문장에서 바뀐 % 숫자들의 배율 평균. 문장 구조가 다르면 None."""
    if not effect or not nxt:
        return None
    a, b = _PCT.findall(effect), _PCT.findall(nxt)
    if len(a) != len(b):
        return None
    rs = []
    for x, y in zip(map(float, a), map(float, b)):
        if x == y:
            continue
        if final_damage:
            rs.append((100 + y) / (100 + x))
        elif x:
            rs.append(y / x)
    return sum(rs) / len(rs) if rs else 1.0


def _line_targets(line: str, base: str, shares: dict) -> list[str] | None:
    """강화 코어 효과 한 줄이 올리는 스킬들. None이면 계산에서 뺀다(조건부 버프)."""
    head = line.split("데미지")[0]
    if "스킬의 " in head:
        group = head.split("스킬의 ")[0].strip()
        hit = [n for n in shares if group and group in n]
        if hit:
            return hit
    for n in sorted(shares, key=len, reverse=True):
        if head.startswith(n + "의"):
            return [n]
    if head.rstrip().endswith(" 중"):
        return None
    return [base]


def enhance_parts(effect: str | None, nxt: str | None, base: str, shares: dict) -> tuple[dict, list[str]] | None:
    """강화 코어: 줄마다 (100+다음)/(100+지금) 배율을 그 줄의 대상 스킬에 곱한다. 문장 구조가 다르면 None."""
    if not effect or not nxt:
        return None
    a, b = effect.splitlines(), nxt.splitlines()
    if len(a) != len(b):
        return None
    ratios: dict[str, float] = {}
    skipped = []
    for x, y in zip(a, b):
        r = ratio(x, y, final_damage=True)
        if r is None:
            return None
        if r == 1.0:
            continue
        targets = _line_targets(y, base, shares)
        if targets is None:
            skipped.append(y.strip())
            continue
        for n in targets:
            ratios[n] = ratios.get(n, 1.0) * r
    return ratios, skipped


def bonus_factor(description: str | None, target: int, final, boss_defense: float) -> float:
    """목표 레벨이 10·20·30이면 설명의 보너스(방어율 무시·보스 데미지)를 그 스킬 배율로."""
    f = 1.0
    for lv, text in _BONUS.findall(description or ""):
        if int(lv) != target:
            continue
        for kind, x in _BONUS_ITEM.findall(text):
            x = float(x)
            if kind == "방어율 무시":
                d = boss_defense / 100
                old = 1 - d * (1 - final.ied / 100)
                new = 1 - d * (1 - final.ied / 100) * (1 - x / 100)
                f *= (new / old) if old > 0 else 1.0
            else:
                base = 100 + final.dmg + final.boss
                f *= (base + x) / base
    return f


def core_paths(snap, shares: dict, fragment_price: float, boss_defense: float, source: str) -> list[dict]:
    """shares: 스킬 이름 → 딜 지분(%). snap.hexa_skills: 6차 스킬 이름 → {level, effect, next, description}."""
    skills = snap.hexa_skills
    if not fragment_price or not snap.hexa_cores or not shares or not skills:
        return []
    out = []
    for core in snap.hexa_cores:
        col, lv = COLUMN.get(core["type"]), core["level"]
        if col is None or lv >= 30:
            continue
        erda, frag = COST[col][lv]
        target = lv + 1
        enhance = core["type"] == "강화 코어"
        names = list(core["skills"])
        if core["type"] == "공용 코어":  # 솔 헤카테 : 스틱스처럼 딸린 스킬도 같이 오른다
            names += [n for n in skills if n.startswith(core["name"] + " :") and n not in names]
        ratios: dict[str, float] = {}
        skipped: list[str] = []
        for n in names:
            sk = skills.get(n) or {}
            base = n[:-3] if enhance and n.endswith(" 강화") else n
            if enhance:
                got = enhance_parts(sk.get("effect"), sk.get("next"), base, shares)
                if got is None:
                    continue
                per, skip = got
                skipped += skip
            else:
                r = ratio(sk.get("effect"), sk.get("next"))
                if r is None:
                    continue
                per = {base: r}
            per[base] = per.get(base, 1.0) * bonus_factor(sk.get("description"), target, snap.final, boss_defense)
            for k, r in per.items():
                ratios[k] = ratios.get(k, 1.0) * r
        gain, parts = 0.0, []
        for k, r in ratios.items():
            share = shares.get(k, 0.0)
            if share and r != 1.0:
                gain += share * (r - 1)
                parts.append({"skill": k, "share": share, "ratio": round(r, 5)})
        if gain <= 0 or not frag:
            continue
        cost = frag * fragment_price
        out.append({"slot": "HEXA 코어", "path": "HEXA 코어", "name": f"{core['name']} {lv}→{target}레벨",
                    "cost": cost, "delta_pct": gain, "per_100m": gain / (cost / 1e8), "fragments": frag, "erda": erda,
                    "share_source": source, "skills": parts, "skipped": skipped, "set_change": []})
    return out
