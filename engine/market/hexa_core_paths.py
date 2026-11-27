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
- API는 다음 1레벨 효과만 주므로 경로 비교는 '다음 1레벨' 단위(헥사 코어 순서 도구와 같은 방식)
- (2026-11-27) 추천 조합은 30레벨까지 본다(all_levels): at_level이 레벨별 효과 문장을 만든다 — 강화 코어는 레벨표,
  그 밖은 레벨당 일정한 증가량. 직업 기준값 지분은 shares_at으로 내 코어 레벨에 맞춘다
"""
import json
import pathlib
import re

_DATA = pathlib.Path(__file__).resolve().parents[1] / "data"
_COST_FILE = json.loads((_DATA / "hexa_core_cost.json").read_text(encoding="utf-8"))
COST = _COST_FILE["costs"]
ENHANCE_FD = _COST_FILE["enhance_final_damage"]  # 강화 코어 레벨 → 최종 데미지 %(나무위키 HEXA 매트릭스)
_SHARE = _DATA / "skill_share.json"
_PCT = re.compile(r"(\d+(?:\.\d+)?)%")
_PCT_DMG = re.compile(r"(\d+(?:\.\d+)?)%(?!\s*확률)")
_SKILL_IED = re.compile(r"방어율 (\d+(?:\.\d+)?)% 추가 무시")
_SKILL_BOSS = re.compile(r"보스 몬스터 공격 시 데미지 (\d+(?:\.\d+)?)% 증가")
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


def _boss_pcts(text: str) -> list[str]:
    """보스 실딜에 쓰는 % 숫자만: '일반 몬스터 …' 구간과 'N% 확률' 은 뺀다(2026-10-11 검토: 마스터리 VI 과대평가)."""
    segs = [seg for ln in text.split("\n") for seg in ln.split(", ") if "일반 몬스터" not in seg]
    return [m for seg in segs for m in _PCT_DMG.findall(seg)]


def ratio(effect: str | None, nxt: str | None, final_damage: bool = False) -> float | None:
    """지금 → 다음 레벨 효과 문장에서 바뀐 % 숫자들의 배율 평균. 문장 구조가 다르면 None."""
    if not effect or not nxt:
        return None
    a, b = _boss_pcts(effect), _boss_pcts(nxt)
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


def bonus_factor(description: str | None, target: int, final, boss_defense: float, effect: str | None = None) -> float:
    """목표 레벨이 10·20·30이면 설명의 보너스(방어율 무시·보스 데미지)를 그 스킬 배율로.
    (2026-10-11) 나무위키 HEXA 매트릭스: 보너스 방무는 스킬 자체 방무와 합적용(어센트 60→70→80→100, 오리진 0→20→50).
    스킬 방무·보뎀 S = 효과 문장의 '방어율 N% 추가 무시'·'보스 … N% 증가' + 목표 미만 레벨 보너스.
    효과 문장이 레벨 보너스를 이미 품는지는 1레벨 픽스처만 있어 미확인 — 품는다면 S가 커져 이득을 낮게 본다(보수적)."""
    items = [(int(lv), kind, float(x)) for lv, text in _BONUS.findall(description or "") for kind, x in _BONUS_ITEM.findall(text)]
    s_ied = sum(map(float, _SKILL_IED.findall(effect or ""))) + sum(x for lv, k, x in items if lv < target and k == "방어율 무시")
    s_boss = sum(map(float, _SKILL_BOSS.findall(effect or ""))) + sum(x for lv, k, x in items if lv < target and k != "방어율 무시")
    d = boss_defense / 100
    f = 1.0
    for lv, kind, x in items:
        if lv != target:
            continue
        if kind == "방어율 무시":
            keep = 1 - final.ied / 100
            old = 1 - d * keep * (1 - min(100.0, s_ied) / 100)
            new = 1 - d * keep * (1 - min(100.0, s_ied + x) / 100)
            f *= (max(0.0, new) / old) if old > 0 else 1.0
            s_ied += x
        else:
            base = 100 + final.dmg + final.boss + s_boss
            f *= (base + x) / base
            s_boss += x
    return f


def at_level(effect: str | None, nxt: str | None, lv: int, target: int, enhance: bool = False) -> str | None:
    """지금(lv)·다음(lv+1) 레벨 효과 문장으로 target 레벨의 효과 문장을 만든다(2026-11-27) — 바뀌는 % 숫자마다:
    · 강화 코어의 최종 데미지(지금·다음 값이 레벨표와 같을 때): 레벨표(engine/data/hexa_core_cost.json enhance_final_damage)
    · 그 밖: 레벨당 증가량이 일정(나무위키 HEXA 매트릭스 '스킬 퍼뎀이 선형적으로 상승', 직업 스킬 문서의 (A + 스킬 레벨×B)% 공식).
      레테 6차 스킬 9개에서 이렇게 이은 30레벨 값이 나무위키 마스터 값과 같다(tests/test_hexa_core.py)
    문장 구조가 다르면 None."""
    if not effect or not nxt:
        return None
    if target == lv + 1:
        return nxt
    a, b = _PCT.findall(effect), _PCT.findall(nxt)
    if len(a) != len(b):
        return None
    vals = []
    for x, y in zip(map(float, a), map(float, b)):
        if x == y:
            v = y
        elif enhance and lv + 1 < len(ENHANCE_FD) and x == ENHANCE_FD[lv] and y == ENHANCE_FD[lv + 1]:
            v = float(ENHANCE_FD[target])
        else:
            v = x + (target - lv) * (y - x)
        vals.append(v)
    it = iter(vals)
    return _PCT.sub(lambda m: f"{round(next(it), 4):g}%", nxt)


def _ratios(core: dict, skills: dict, shares: dict, lv: int, target: int, final, boss_defense: float) -> tuple[dict, list]:
    """코어를 lv → target으로 올릴 때 지분 스킬 → 배율, 계산 못 한 줄."""
    enhance = core["type"] == "강화 코어"
    names = list(core["skills"])
    if core["type"] == "공용 코어":  # 솔 헤카테 : 스틱스처럼 딸린 스킬도 같이 오른다
        names += [n for n in skills if n.startswith(core["name"] + " :") and n not in names]
    ratios, unvalued = {}, []  # 지분 스킬 → 배율(한 코어가 여러 스킬을 올리면 각각 더한다)
    for n in names:
        sk = skills.get(n) or {}
        bonus = 1.0
        for k in range(lv + 1, target + 1):
            bonus *= bonus_factor(sk.get("description"), k, final, boss_defense, sk.get("effect"))
        nxt = at_level(sk.get("effect"), sk.get("next"), lv, target, enhance)
        if enhance:
            base = n[:-3] if n.endswith(" 강화") else n
            t = enhance_targets(sk.get("effect"), nxt, base, shares)
            if t is None:
                continue
            unvalued += t[1]
            for k, r in t[0].items():
                ratios[k] = ratios.get(k, 1.0) * r * bonus
            continue
        r = ratio(sk.get("effect"), nxt)
        if r is not None:
            ratios[n] = ratios.get(n, 1.0) * r * bonus
    return ratios, unvalued


def shares_at(snap, shares: dict, boss_defense: float, ref_level: int = 30) -> dict:
    """직업 기준값(상위 랭커의 연무장 지분)을 이 캐릭터의 코어 레벨에 맞춘다(2026-11-27).
    랭커 기록의 코어 레벨은 저장돼 있지 않아 전부 ref_level(30, 최대)로 본다 — 내 코어가 낮은 스킬의 지분을 가장 많이 낮춰 잡는 쪽이다.
    스킬 k의 지분 × (내 레벨 배율 ÷ ref 레벨 배율)을 구하고 합이 전과 같은 비율이 되게 다시 나눈다."""
    f = {}
    for core in snap.hexa_cores:
        lv = core["level"]
        if lv >= ref_level:
            continue
        for k, r in _ratios(core, snap.hexa_skills, shares, lv, ref_level, snap.final, boss_defense)[0].items():
            if r > 0:
                f[k] = f.get(k, 1.0) / r
    rest = max(0.0, 100.0 - sum(shares.values()))            # 지분 목록에 없는 딜(그대로)
    total = sum(v * f.get(k, 1.0) for k, v in shares.items()) + rest
    whole = sum(shares.values()) + rest                      # 중앙값이라 합이 100을 조금 넘기도 한다 — 그 합을 그대로 둔다
    return {k: v * f.get(k, 1.0) / total * whole for k, v in shares.items()} if total > 0 else dict(shares)


def core_paths(snap, shares: dict, fragment_price: float, boss_defense: float, source: str, all_levels: bool = False) -> list[dict]:
    """shares: 스킬 이름 → 딜 지분(%). snap.hexa_skills: 6차 스킬 이름 → {level, effect, next, description}.
    all_levels: 코어마다 다음 1레벨만이 아니라 30레벨까지 목표 레벨마다 하나씩(비용은 그 사이 레벨의 합)."""
    skills = snap.hexa_skills
    if not fragment_price or not snap.hexa_cores or not shares or not skills:
        return []
    out = []
    for core in snap.hexa_cores:
        col, lv = cost_column(core), core["level"]
        if col is None or lv >= 30:
            continue
        erda = frag = 0
        for target in range(lv + 1, 31 if all_levels else lv + 2):
            e, fr = COST[col][target - 1]
            erda, frag = erda + e, frag + fr
            ratios, unvalued = _ratios(core, skills, shares, lv, target, snap.final, boss_defense)
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
