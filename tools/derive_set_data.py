"""fixture의 착용 장비와 set-effect 개수로 아이템→세트 매핑과 세트 단계 표를 만든다.

넥슨 API는 아이템이 어느 세트에 속하는지 주지 않는다. 대신 캐릭터마다 세트별 개수(total_set_count)를 준다.
"착용 장비 중 세트 S에 속한 개수 = API 개수(무기 규칙 보정 후)"를 제약으로 하는 정수계획을 풀어 매핑을 얻는다.

- 이름 규칙으로 고정: 에테르넬·아케인셰이드·앱솔랩스·도전자의 접두어
- 장비가 아닌 출처의 세트(펫·캐시·심볼 등, EXTERNAL)는 후보에서 뺀다
- 무기 규칙: 제네시스·데스티니 무기는 에테르넬 세트에 +1, 루타비스·앱솔랩스·아케인셰이드에는 그 세트 장비 3개 이상일 때 +1
- `예비 특수 반지` 슬롯은 착용이 아니므로 뺀다

사용: uv run --group analysis python tools/derive_set_data.py
출력: engine/data/set_items.json, engine/data/set_tiers.json
"""
import collections
import json
import pathlib

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCES = [ROOT / "tests" / "fixtures" / "characters", ROOT / "tests" / "fixtures" / "pairs"]
OUT = ROOT / "engine" / "data"
LUCKY_MIN = 3
SPECIAL_WEAPON = ("제네시스", "데스티니")
LUCKY_SETS = ("루타비스", "앱솔랩스", "아케인셰이드")
EXTERNAL = ("쁘띠", "마스터 ", "소멸의 여로", "별하늘", "크리스마스", "폼폼", "컬러링", "인형의 꿈",
            "나이트 일루미네이션", "메이플 트레져", "퓨어 골드", "아르카나", "결속의 반지")
PREFIX = ("에테르넬 ", "아케인셰이드 ", "앱솔랩스 ", "도전자의 ")


def _allowed(item: str, set_name: str) -> bool:
    if set_name.startswith(EXTERNAL):
        return False
    for p in PREFIX:
        if item.startswith(p):
            return set_name.startswith(p.replace("의 ", "").strip())
    return True


def load_chars():
    chars, tiers = [], {}
    for base in SOURCES:
        for d in sorted(p for p in base.iterdir() if p.is_dir()):
            eq = json.loads((d / "character_item-equipment.json").read_text(encoding="utf-8"))
            se = json.loads((d / "character_set-effect.json").read_text(encoding="utf-8"))
            worn = [i for i in eq["item_equipment"] if i["item_equipment_slot"] != "예비 특수 반지"]
            weapon = next(i["item_name"] for i in worn if i["item_equipment_slot"] == "무기")
            special = weapon.startswith(SPECIAL_WEAPON)
            items = sorted({i["item_name"] for i in worn if not (special and i["item_equipment_slot"] == "무기")})
            counts = {x["set_name"]: x["total_set_count"] for x in se.get("set_effect") or []}
            for x in se.get("set_effect") or []:
                tiers[x["set_name"]] = {str(t["set_count"]): t["set_option"] for t in x.get("set_option_full") or []}
            chars.append((d.name, items, counts, special))
    return chars, tiers


def equipment_target(count: int, set_name: str, special: bool) -> int:
    """API 개수에서 무기 규칙 기여분을 뺀, 장비로 채워야 하는 개수."""
    if not special:
        return count
    if set_name.startswith("에테르넬 세트"):
        return count - 1
    if set_name.startswith(LUCKY_SETS) and count - 1 >= LUCKY_MIN:
        return count - 1
    return count


def solve(chars):
    wear = collections.defaultdict(list)
    for ci, c in enumerate(chars):
        for it in c[1]:
            wear[it].append(ci)
    pairs = [(it, st) for it, cis in wear.items()
             for st in set.intersection(*[set(chars[c][2]) for c in cis]) if _allowed(it, st)]
    idx = {p: k for k, p in enumerate(pairs)}
    cs = [(ci, st) for ci, c in enumerate(chars) for st in c[2]]
    n_x, n_c = len(pairs), len(cs)
    rows, lb, ub = [], [], []
    for k, (ci, st) in enumerate(cs):
        row = np.zeros(n_x + 2 * n_c)
        for it in chars[ci][1]:
            if (it, st) in idx:
                row[idx[(it, st)]] = 1
        row[n_x + k], row[n_x + n_c + k] = 1, -1  # 부족분, 초과분
        t = equipment_target(chars[ci][2][st], st, chars[ci][3])
        rows.append(row), lb.append(t), ub.append(t)
    for it in wear:
        row = np.zeros(n_x + 2 * n_c)
        for (i, st), k in idx.items():
            if i == it:
                row[k] = 1
        rows.append(row), lb.append(0), ub.append(1)
    cost = np.r_[np.full(n_x, 0.001), np.ones(2 * n_c)]
    res = milp(cost, constraints=LinearConstraint(np.array(rows), lb, ub),
               integrality=np.r_[np.ones(n_x), np.zeros(2 * n_c)],
               bounds=Bounds(0, np.r_[np.ones(n_x), np.full(2 * n_c, np.inf)]))
    if res.status != 0:
        raise SystemExit(f"ILP 실패: {res.message}")
    assign = {it: None for it in wear}
    for (it, st), k in idx.items():
        if res.x[k] > 0.5:
            assign[it] = st
    return assign


def main() -> None:
    chars, tiers = load_chars()
    assign = solve(chars)
    OUT.mkdir(parents=True, exist_ok=True)
    meta = {"_source": "tests/fixtures 착용 장비·set-effect 개수 제약 ILP (tools/derive_set_data.py)",
            "_collected": "2026-10-02~03"}
    items = {k: v for k, v in sorted(assign.items()) if v is not None}
    (OUT / "set_items.json").write_text(json.dumps({**meta, "items": items}, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "set_tiers.json").write_text(json.dumps({**meta, "sets": dict(sorted(tiers.items()))}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"아이템 {len(items)}개 매핑, 세트 {len(tiers)}개")


if __name__ == "__main__":
    main()
