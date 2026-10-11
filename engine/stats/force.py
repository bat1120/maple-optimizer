"""보스 목록과 포스 보정(2026-10-11): engine/data/bosses.json — 나무위키 보스 문서(방어율)·'아케인포스'·'어센틱포스'
(요구 포스, 격차별 주는 피해 비율), 공지 791(11레벨 지역 보스). 출처·확인 날짜는 파일 안.

- 아케인: 캐릭터 ARC / 요구 ARC 비율 구간별 주는 피해(10%~150%)
- 어센틱: 캐릭터 AUT − 요구 AUT 격차 행별 주는 피해(5%~125%). 행 사이 격차는 바로 아래 행(표에 규칙이 없어 보수적으로)
- 캐릭터 포스: 넥슨 character/stat의 '아케인포스'·'어센틱포스'(심볼·하이퍼·길드 등 전부 들어간 값).
  다른 하이퍼 프리셋을 평가하면 하이퍼 아케인포스 몫만 바꾸고, 심볼을 올리면 symbol_force 증가분만 더한다
- 11레벨 지역 보스 '데미지 +20%'는 종류(최종뎀/데미지%)가 공지·API·나무에 없어 넣지 않는다(symbol_region만 둔다)
"""
import json
import pathlib

from engine.stats.metrics import BossProfile

PATH = pathlib.Path(__file__).parent.parent / "data" / "bosses.json"
_T = json.loads(PATH.read_text(encoding="utf-8"))
_BY_ID = {b["id"]: b for b in _T["bosses"]}
CHECKED = _T["_checked"]
KINDS = {"아케인": "아케인포스", "어센틱": "어센틱포스"}


def boss_list() -> list[dict]:
    return list(_T["bosses"])


def boss(boss_id: str) -> BossProfile:
    """보스 id → BossProfile. 없으면 KeyError."""
    b = _BY_ID[boss_id]
    label = " ".join(x for x in (b["name"], b["difficulty"], b.get("phase")) if x)
    return BossProfile(label, float(b["defense"]), b["id"], b["difficulty"], b.get("arcane"), b.get("authentic"),
                       b.get("symbol_region"))


def _rows(table: str) -> list:
    return _T[table]["rows"]


def arcane_mult(have: int, need: int) -> float:
    """비율(%) 구간: 정수 비교로 경계(예: 1452/1320 = 110%)를 정확히 가른다."""
    for at, pct in _rows("arcane_table"):
        if have * 100 >= need * at:
            return pct / 100
    return _rows("arcane_table")[-1][1] / 100


def authentic_mult(have: int, need: int) -> float:
    gap = have - need
    for at, pct in _rows("authentic_table"):
        if gap >= at:
            return pct / 100
    return _rows("authentic_table")[-1][1] / 100


def character_force(snap, setting=None, extra: dict | None = None) -> dict:
    """{'아케인': n|None, '어센틱': n|None} — API 총 포스에서 하이퍼 프리셋 차이와 extra(심볼 레벨업 증가분)만 바꾼다."""
    arc, aut = snap.arcane_force, snap.authentic_force
    if arc is not None and setting is not None and snap.hyper_force:
        arc += snap.hyper_force.get(setting.hyper, 0) - snap.hyper_force.get(snap.active_hyper_preset, 0)
    out = {"아케인": arc, "어센틱": aut}
    for k, v in (extra or {}).items():
        if out.get(k) is not None:
            out[k] += v
    return out


def _need(boss: BossProfile) -> tuple[str, int] | None:
    if boss.arcane:
        return "아케인", boss.arcane
    if boss.authentic:
        return "어센틱", boss.authentic
    return None


def force_mult(boss: BossProfile, force: dict) -> float:
    """요구 포스가 없는 보스이거나 캐릭터 포스를 모르면 1."""
    n = _need(boss)
    if n is None or force.get(n[0]) is None:
        return 1.0
    kind, need = n
    return (arcane_mult if kind == "아케인" else authentic_mult)(force[kind], need)


def force_info(boss: BossProfile, force: dict) -> dict | None:
    """화면 표시용: {'kind': '어센틱포스', 'required': 480, 'current': 450, 'damage_pct': 70.0}. 요구 포스 없는 보스는 None."""
    n = _need(boss)
    if n is None:
        return None
    kind, need = n
    cur = force.get(kind)
    return {"kind": KINDS[kind], "required": need, "current": cur,
            "damage_pct": round(force_mult(boss, force) * 100, 2) if cur is not None else None}
