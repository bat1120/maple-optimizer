"""HEXA 스킬 코어 경로(2026-10-07): 코어를 다음 1레벨 올렸을 때의 실딜과 조각 비용.

- 효과: 실딜 상승(%) ≈ Σ(연결 스킬의 보스 딜 지분 × (그 스킬 데미지 배율 − 1))
  · 배율은 넥슨 API character/skill(6차)의 지금/다음 레벨 효과 문장에서 바뀐 % 숫자들의 비의 평균
    (강화 코어는 최종 데미지라 (100+다음)/(100+지금))
  · 10·20·30레벨 보너스(설명의 'N레벨 : 방어율 무시/보스 데미지')는 그 스킬에만 곱한다(방무는 곱연산으로 본다 — 미확인)
- 딜 지분: 그 캐릭터의 최신 연무장 기록(battle-practice/result)이 있으면 그것, 없으면 직업 기준값(engine/data/skill_share.json)
- 비용: engine/data/hexa_core_cost.json(다음 1레벨의 조각 × 조각 시세). 솔 에르다는 개수만 보여 준다
  · (2026-10-11) API의 hexa_core_type은 오리진·어센트·3rd가 모두 '스킬 코어', 전 직업·직업군 공용이 모두 '공용 코어'라
    engine/data/hexa_core_kind.json(공식 공지 신규 HEXA 스킬 목록, 나무위키 공용 코어)의 이름으로 비용 열을 가른다
- (2026-10-11) 강화 코어는 효과 문장을 줄(쉼표 구간)마다 나눠 'X의 최종 데미지 (증가량) N%'의 X 스킬 지분에 그 줄 배율을 곱한다
  · X가 'Y 스킬'이면 이름 앞부분(' : ' 앞, '/'로 나눈 것)에 Y가 든 스킬 전부(체인 커맨드 강화의 '오버로드 스킬' — 6차 오버로드 포함 여부 미확인)
  · X가 지분 목록에 없으면 그 코어 스킬의 공격으로 본다(레테 '맹약 완성'은 체인 커맨드의 공격 — 나무위키 레테(메이플스토리)/스킬)
  · 최종 데미지가 아닌 줄(예: '맹약 실체화 중 데미지 증가량')은 버프 유지율을 몰라 계산하지 않고 unvalued로 남긴다
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
_FD = re.compile(r"^(.+?)의 최종 데미지 (?:증가량 )?\d+(?:\.\d+)?%")
COLUMN = {"스킬 코어": "스킬", "마스터리 코어": "마스터리", "강화 코어": "강화", "공용 코어": "공용"}
KIND = json.loads((_DATA / "hexa_core_kind.json").read_text(encoding="utf-8"))
_THIRD = {n for names in KIND["third_skill"].values() for n in names}


def cost_column(core: dict) -> str | None:
    """코어 → 비용표 열. 3rd 스킬 코어·직업군 공용 코어는 API 종류가 같아 이름으로 가른다."""
    col = COLUMN.get(core.get("type"))
    names = {core.get("name"), *core.get("skills", [])}
    if col == "스킬" and names & _THIRD:
        return "3rd 스킬"
    if col == "공용" and core.get("name") not in KIND["all_job_common"]:
        return "직업군 공용"
    return col


def enhance_targets(effect: str | None, nxt: str | None, base: str, shares: dict) -> tuple[dict, list] | None:
    """강화 코어 효과 문장 → ({지분 스킬: 배율}, 계산 못 한 줄). 줄·구간 구조가 다르면 None."""
    if not effect or not nxt:
        return None
    a = [seg for ln in effect.split("\n") for seg in ln.split(", ")]
    b = [seg for ln in nxt.split("\n") for seg in ln.split(", ")]
    if len(a) != len(b):
        return None
    out, unvalued = {}, []
    for x, y in zip(a, b):
        r = ratio(x, y, final_damage=True)
        if r is None:
            return None
        if r == 1.0:
            continue
        m = _FD.match(x.strip())
        if not m:
            new = [v for u, v in zip(_PCT.findall(x), _PCT.findall(y)) if u != v]
            unvalued.append(f"{x.strip()} → {', '.join(new)}%")
            continue
        target = m.group(1)
        if target.endswith(" 스킬"):
            word = target[:-3]
            names = [n for n in shares if word in [t.strip() for t in n.split(" : ")[0].split("/")]]
        else:
            names = [target if target in shares else base]
        for n in names:
            out[n] = out.get(n, 1.0) * r
    return out, unvalued


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
        col, lv = cost_column(core), core["level"]
        if col is None or lv >= 30:
            continue
        erda, frag = COST[col][lv]
        target = lv + 1
        enhance = core["type"] == "강화 코어"
        names = list(core["skills"])
        if core["type"] == "공용 코어":  # 솔 헤카테 : 스틱스처럼 딸린 스킬도 같이 오른다
            names += [n for n in skills if n.startswith(core["name"] + " :") and n not in names]
        ratios, unvalued = {}, []  # 지분 스킬 → 배율(한 코어가 여러 스킬을 올리면 각각 더한다)
        for n in names:
            sk = skills.get(n) or {}
            bonus = bonus_factor(sk.get("description"), target, snap.final, boss_defense)
            if enhance:
                base = n[:-3] if n.endswith(" 강화") else n
                t = enhance_targets(sk.get("effect"), sk.get("next"), base, shares)
                if t is None:
                    continue
                unvalued += t[1]
                for k, r in t[0].items():
                    ratios[k] = ratios.get(k, 1.0) * r * bonus
                continue
            r = ratio(sk.get("effect"), sk.get("next"))
            if r is not None:
                ratios[n] = ratios.get(n, 1.0) * r * bonus
        gain, parts = 0.0, []
        for k, r in ratios.items():
            share = shares.get(k, 0.0)
            if share:
                gain += share * (r - 1)
                parts.append({"skill": k, "share": share, "ratio": round(r, 5)})
        if gain <= 0 or not frag:
            continue
        cost = frag * fragment_price
        out.append({"slot": "HEXA 코어", "path": "HEXA 코어", "name": f"{core['name']} {lv}→{target}레벨",
                    "cost": cost, "delta_pct": gain, "per_100m": gain / (cost / 1e8), "fragments": frag, "erda": erda,
                    "share_source": source, "skills": parts, "unvalued": unvalued, "set_change": []})
    return out
