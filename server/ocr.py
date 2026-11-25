"""툴팁 글자를 로컬 OCR(PP-OCRv5 한국어, onnxruntime)로 읽어 매물 정보로 옮긴다 — AI 판독(7~8초·토큰)을 대신한다.

2026-11-21 측정(실제 경매장 툴팁 14장, 이 PC): 숫자(총 수치·괄호·전투력 증가량·잠재 수치)는 전부 맞고 툴팁당 1.7~2.5초.
틀린 것은 한글뿐('홀스탯', '칠혹', 띄어쓰기) — 이름은 아는 템 목록, 옵션 줄은 공식 옵션표와 맞춰 본다.
코드로 확인되지 않는 판독(모르는 이름·분류, 괄호 합 불일치, 옵션표에 없는 줄)은 None을 돌려 AI가 읽게 한다.
"""
import functools
import logging
import os
import re
import statistics
import time

_log = logging.getLogger("uvicorn.error")

_STAT_KEYS = {"STR": "STR", "DEX": "DEX", "INT": "INT", "LUK": "LUK", "최대HP": "HP", "공격력": "ATK", "마력": "MATK",
              "올스탯": "ALL%", "보스몬스터데미지": "BOSS", "보스몬스터공격시데미지": "BOSS", "몬스터방어율무시": "IED",
              "데미지": "DMG"}
_OTHER_LABELS = ("최대MP", "방어력", "이동속도", "점프력", "착용레벨감소")  # 실딜 계산에 안 쓰는 줄 — 읽되 버린다
_GRADES = ("레전드리", "유니크", "에픽", "레어")
_OCR_CATEGORIES = ("모자", "상의", "하의", "신발", "장갑", "망토", "어깨장식", "벨트", "반지", "펜던트", "귀고리", "얼굴장식",
                   "눈장식", "뱃지", "포켓 아이템", "기계 심장", "훈장")  # 무기·보조무기·엠블렘은 종류·직업 판정이 필요해 AI가 읽는다
_STAT_ROW = re.compile(r"^(.*?)\+([\d,]+)(%?)(?:\((.*)\))?$")
_POWER = re.compile(r"^[-+−－＋]?((\d+억)?(\d+만)?\d*)$")


def _squash(s: str) -> str:
    return re.sub(r"\s+", "", s)


def _rows(boxes) -> list[tuple[float, str, list[str]]]:
    """OCR 상자 (x, y, 글자) → 줄 (y, 이어 붙인 글자, 상자 글자들). 같은 줄은 y가 7px 안."""
    rows: list[list] = []
    for x, y, t in sorted(boxes, key=lambda b: (b[1], b[0])):
        if rows and abs(y - rows[-1][0]) <= 7:
            rows[-1][1].append((x, t))
        else:
            rows.append([y, [(x, t)]])
    return [(y, " ".join(t for _, t in sorted(ts)), [t for _, t in sorted(ts)]) for y, ts in rows]


def _closest(word: str, known) -> str | None:
    """오독 한 글자까지: 같거나, 한 글자 다른 후보가 하나뿐일 때 그 후보."""
    from server.tooltip import _distance
    if word in known:
        return word
    near = [k for k in known if _distance(word, k) <= 1]
    return near[0] if len(near) == 1 else None


@functools.lru_cache(maxsize=1)
def _options() -> dict[str, str]:
    from server.vision import _official_options
    return {_squash(o): o for o in _official_options()}


def _option(text: str) -> str | None:
    """옵션 줄을 공식 옵션표의 문장으로. 글자 한 자 오독은 고치지만 숫자가 다르면 고치지 않는다."""
    from server.tooltip import _distance
    s = _squash(re.sub(r"^[^0-9A-Za-z가-힣]+", "", text.strip()))
    table = _options()
    if s in table:
        return table[s]
    digits = re.findall(r"\d+", s)
    near = [o for k, o in table.items() if re.findall(r"\d+", k) == digits and _distance(s, k) <= 1]
    return near[0] if len(near) == 1 else None


def _name(rows, names) -> str | None:
    from server.tooltip import correct_name
    squashed = {_squash(n): n for n in names}
    for _, text, _ in rows:
        s = _squash(text)
        if s in squashed:
            return squashed[s]
        fixed, changed = correct_name(s, tuple(squashed))
        if changed:
            return squashed[fixed]
    return None


def _section(rows, start: int, pitch: float) -> list[str] | None:
    """머리말(start) 아래 옵션 줄들. 줄 간격(pitch)으로 이어진 줄만 — 한 줄이라도 옵션표에 없으면 None.
    간격이 벌어져 끊었는데 바로 다음 줄도 옵션이면(끊은 자리가 애매하다) None."""
    out, prev = [], rows[start][0]
    for y, text, _ in rows[start + 1:]:
        s = _squash(text)
        if any(w in s for w in ("에디셔널", "익셉셔널", "가위", "잠재능력")):
            break
        if y - prev > pitch * 1.15:
            return None if _option(text) else out
        opt = _option(text)
        if opt is None:
            return None
        out.append(opt)
        prev = y
    return out


def parse_tooltip(boxes, names=None, why: list | None = None) -> dict | None:
    """OCR 상자 [(x, y, 글자)] → AI 판독과 같은 모양의 매물 dict. 확인되지 않으면 None(AI가 읽는다).
    why(목록)를 주면 확인되지 않은 까닭을 한 줄 넣는다 — 운영에서 왜 AI로 넘어갔는지 보려고(2026-11-25)."""
    def no(reason: str) -> None:
        if why is not None:
            why.append(reason)
        return None

    from server.vision import _item_names, checksum_failures
    rows = _rows(boxes)
    squashed = [_squash(t) for _, t, _ in rows]
    power_at = next((i for i, s in enumerate(squashed) if "전투력증가량" in s), None)
    level_at = next((i for i, s in enumerate(squashed) if re.search(r"Lv\.?\d", s)), None)
    if power_at is None or level_at is None or level_at <= power_at:
        return no("전투력 증가량·레벨 줄을 못 찾음")
    name = _name(rows[:power_at], names or _item_names())
    if name is None:
        return no("모르는 이름: " + " / ".join(t for _, t, _ in rows[:power_at])[:60])
    equipped = any("현재장착중인장비" in s for s in squashed)
    power = None
    if not equipped and power_at + 1 < len(rows) and (m := _POWER.match(squashed[power_at + 1])) and m.group(1):
        power = " ".join(p for p in (m.group(2), m.group(3), m.group(1)[len((m.group(2) or "") + (m.group(3) or "")):]) if p)
    cats = {_squash(c): c for c in _OCR_CATEGORIES}
    found = [cats[_squash(t)] for _, _, ts in rows[power_at:level_at] for t in ts if _squash(t) in cats]
    if len(found) != 1:
        return no(f"장비 분류를 못 정함: {found}")
    category = found[0]
    if category == "반지" and any(re.search(r"\d레벨", s) for s in squashed):
        return no("특수 반지")  # 특수 반지(스킬 레벨)는 AI가 읽는다
    lv = re.search(r"Lv\.?(\d+)(?:\((\d+)-\d+\))?", squashed[level_at])
    level = int(lv.group(2) or lv.group(1))  # 'Lv. 175 (200 - 25)'는 착용 레벨 감소 — 템의 원래 레벨 200
    pot_at = next((i for i, s in enumerate(squashed) if "잠재능력" in s and "에디셔널" not in s), None)
    add_at = next((i for i, s in enumerate(squashed) if "에디셔널잠재능력" in s), None)
    end = min(i for i in (pot_at, add_at, len(rows)) if i is not None)
    total, breakdown, stat_ys = {}, {}, []
    labels = (*_STAT_KEYS, *_OTHER_LABELS)
    for (y, _, _), s in zip(rows[level_at + 1:end], squashed[level_at + 1:end]):
        m = _STAT_ROW.match(s)
        if not m or not m.group(1):
            continue
        label = _closest(m.group(1), labels)
        if label is None:
            return no(f"모르는 스탯 줄: {s[:30]}")  # 수치 줄인데 무슨 스탯인지 모른다
        stat_ys.append(y)
        key = _STAT_KEYS.get(label)
        if key is None or key in total:
            continue
        total[key] = int(m.group(2).replace(",", ""))
        if m.group(4) is not None:
            breakdown[key] = [int(v.replace(",", "")) for v in re.findall(r"[\d,]+", m.group(4))]
    if not total or len(stat_ys) < 2:
        return no("스탯 줄이 2줄 미만")
    pitch = statistics.median(b - a for a, b in zip(stat_ys, stat_ys[1:]))
    grades, lines = [], []
    for at in (pot_at, add_at):
        if at is None:
            grades.append(None), lines.append([])
            continue
        grade = next((g for g in _GRADES if squashed[at].endswith(g)), None)
        got = _section(rows, at, pitch)
        if got is None or (got and grade is None) or (grade is None and not squashed[at].endswith("없음")):
            return no("잠재 줄을 옵션표에서 못 찾음: " + " / ".join(t for _, t, _ in rows[at:at + 5])[:90])
        grades.append(grade), lines.append(got)
    item = {"name": name, "category": category, "part": category, "starforce": None, "level": level,
            "potential_grade": grades[0], "additional_grade": grades[1], "total": total, "breakdown": breakdown,
            "potentials": lines[0], "additional": lines[1], "price": None, "price_text": None,
            "power_delta_text": power, "equipped": equipped, "tooltip": None, "special_ring_level": None,
            "equip_type": None, "job_groups": None}
    failed = checksum_failures(item)
    return no(f"괄호 합 불일치: {failed}") if failed else item


def reader():
    """툴팁 이미지 → [(x, y, 글자)]를 돌려주는 함수. VISION_OCR=0이거나 OCR 패키지가 없으면 None(AI만 쓴다)."""
    if os.environ.get("VISION_OCR", "1").lower() in ("0", "false", "off"):
        return None
    try:
        import threading

        import numpy as np
        from rapidocr import LangRec, ModelType, OCRVersion, RapidOCR
        logging.getLogger("RapidOCR").setLevel(logging.WARNING)
        engine = RapidOCR(params={"Rec.lang_type": LangRec.KOREAN, "Rec.ocr_version": OCRVersion.PPOCRV5,
                                  "Rec.model_type": ModelType.MOBILE, "Global.use_cls": False})
        engine(np.zeros((64, 160, 3), np.uint8))  # 글자 모델은 처음 읽을 때 받는다 — 여기서 미리 받아 둔다
    except Exception as e:  # noqa: BLE001 — 패키지·모델이 없으면 OCR 없이 돈다
        _log.warning("툴팁 OCR 꺼짐(AI만 사용): %s", type(e).__name__)
        return None
    _log.info("툴팁 OCR 켜짐(PP-OCRv5 한국어)")
    lock = threading.Lock()  # CPU를 다 쓰는 작업이라 한 번에 한 장

    def read(tip) -> list[tuple[int, int, str]]:
        with lock:
            t0 = time.monotonic()
            r = engine(np.asarray(tip.convert("RGB"))[..., ::-1].copy())  # OpenCV 순서(BGR)
            _log.info("툴팁 OCR %.1f초 · 글자 상자 %d개", time.monotonic() - t0, len(r.txts or ()))
        if r.txts is None:
            return []
        return [(int(b[0][0]), int(b[0][1]), t) for b, t in zip(r.boxes, r.txts)]

    return read


def lazy_reader():
    """reader()를 첫 툴팁이 올 때 만든다(서버 시작을 늦추지 않는다). OCR을 쓸 수 없으면 읽을 때마다 예외 — 부르는 쪽이 AI로 넘긴다."""
    import threading
    lock, made = threading.Lock(), []

    def read(tip):
        with lock:
            if not made:
                made.append(reader())
        if made[0] is None:
            raise RuntimeError("OCR을 쓸 수 없다")
        return made[0](tip)

    return read
