"""경매장 화면 분석: 사용자가 공유한 탭의 캡처 이미지에서 GPT 비전으로 매물 정보를 뽑는다.

넥슨 서버에는 아무 요청도 보내지 않는다 — 사용자 화면에 이미 보이는 내용만 읽는다.
숫자는 모델이 읽은 값이므로 화면에 "읽은 내용"을 그대로 보여 주고 확인받는다.
"""
import functools
import hashlib
import json
import os
import pathlib
import re

_TOTAL_KEYS = ("STR", "DEX", "INT", "LUK", "HP", "ATK", "MATK", "ALL%", "BOSS", "IED", "DMG")
CATEGORIES = ("무기", "보조무기", "엠블렘", "모자", "상의", "하의", "신발", "장갑", "망토", "어깨장식", "벨트",
              "반지", "펜던트", "귀고리", "얼굴장식", "눈장식", "뱃지", "포켓 아이템", "기계 심장", "훈장", "기타")
SLOTS_BY_CATEGORY = {"반지": ("반지1", "반지2", "반지3", "반지4"), "펜던트": ("펜던트", "펜던트2")}

_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["tooltip_visible", "listings", "fee_rate"],
    "properties": {
        "fee_rate": {"type": ["number", "null"],
                     "description": "화면에 경매장 판매 수수료 비율이 보이면(판매 등록 창의 '수수료 5%' 등) 그 퍼센트 숫자(예: 5). 안 보이면 null"},
        "tooltip_visible": {"type": "boolean", "description": "아이템 상세 툴팁(잠재 옵션이 보이는 창)이 화면에 떠 있는가"},
        "listings": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["name", "category", "part", "starforce", "level", "potential_grade", "additional_grade",
                             "total", "breakdown", "potentials", "additional", "price", "price_text", "power_delta_text", "equipped", "tooltip",
                             "special_ring_level", "equip_type", "job_groups"],
                "properties": {
                    "name": {"type": "string"},
                    "category": {"type": "string", "enum": list(CATEGORIES)},
                    "part": {"type": "string", "description": "무기면 무기 종류(예: 카르타), 아니면 category와 같게"},
                    "starforce": {"type": ["integer", "null"]},
                    "level": {"type": ["integer", "null"], "description": "툴팁의 착용 레벨(REQ LEV). 안 보이면 null"},
                    "potential_grade": {"type": ["string", "null"], "enum": ["레어", "에픽", "유니크", "레전드리", None],
                                        "description": "잠재능력 등급. 안 보이면 null"},
                    "additional_grade": {"type": ["string", "null"], "enum": ["레어", "에픽", "유니크", "레전드리", None],
                                         "description": "에디셔널 잠재능력 등급. 안 보이면 null"},
                    "total": {
                        "type": "object", "additionalProperties": False, "required": list(_TOTAL_KEYS),
                        "properties": {k: {"type": ["number", "null"]} for k in _TOTAL_KEYS},
                        "description": "툴팁의 총 수치. 올스탯%는 ALL%, 보스 몬스터 데미지%는 BOSS, 몬스터 방어율 무시%는 IED",
                    },
                    "breakdown": {
                        "type": "object", "additionalProperties": False, "required": list(_TOTAL_KEYS),
                        "properties": {k: {"type": ["array", "null"], "items": {"type": "number"}} for k in _TOTAL_KEYS},
                        "description": "총 수치 줄 괄호 안의 값들(예: 'STR +316 (80 +80 +156)' → [80, 80, 156]). 괄호가 없으면 null",
                    },
                    "tooltip": {"type": ["integer", "null"],
                                "description": "이 매물의 잠재·총 수치를 읽은 '툴팁 N' 이미지 번호(0부터). 목록 행만 보고 읽었으면 null"},
                    "equipped": {"type": "boolean",
                                 "description": "'현재 장착 중인 장비'라고 적힌 비교 툴팁(사용자가 끼고 있는 템)이면 true. 매물이면 false"},
                    "potentials": {"type": "array", "items": {"type": "string"},
                                   "description": "윗잠(잠재능력) 줄 원문 그대로 (예: 'INT +12%'). 에디셔널은 넣지 않는다"},
                    "additional": {"type": "array", "items": {"type": "string"},
                                   "description": "에디셔널 잠재능력 줄 원문 그대로 (예: '마력 +10')"},
                    "price": {"type": ["integer", "null"], "description": "판매 가격(메소). 보이지 않으면 null"},
                    "price_text": {"type": ["string", "null"],
                                   "description": "판매 가격 글자를 화면 그대로(예: '1,774,480,000', '17억 7,448만'). 단위를 바꾸지 않는다. 안 보이면 null"},
                    "power_delta_text": {"type": ["string", "null"],
                                         "description": "툴팁의 '전투력 증가량' 글자 그대로(예: '-193만 1721'). 가격이 아니다. 안 보이면 null"},
                    "equip_type": {"type": ["string", "null"],
                                   "description": "툴팁의 '장비분류' 값 그대로(예: 마법깃펜, 포스실드, 방패, 화살깃, 한손검). 안 보이면 null"},
                    "job_groups": {"type": ["array", "null"], "items": {"type": "string", "enum": ["전사", "마법사", "궁수", "도적", "해적"]},
                                   "description": "툴팁 아래 착용 가능 직업군 중 착용 가능으로 표시된 것(초보자 제외). 확실하지 않으면 null"},
                    "special_ring_level": {"type": ["integer", "null"],
                                           "description": "특수 반지(컨티뉴어스·리스트레인트·웨폰퍼프 등) 툴팁에 적힌 스킬 레벨. 특수 반지가 아니거나 안 보이면 null"},
                },
            },
        },
    },
}
_PROMPT = """메이플스토리 경매장 화면 캡처다. 보이는 매물을 JSON으로 옮겨라.
- 마우스를 올린 매물 툴팁 옆에 '현재 장착 중인 장비'라고 적힌 비교 툴팁이 뜰 수 있다. 그것은 사용자가 끼고 있는 템이라 매물이 아니다 — equipped=true로 표시한다.
- 총 수치 줄의 괄호 안 값(기본 + 추가옵션 + 주문서 + 스타포스)을 breakdown에 그대로 옮긴다. 작은 값(+1, +3)까지 하나도 빠짐없이. 괄호가 없는 줄은 null.
- 화면 글자를 그대로 옮긴다. 고치거나 줄이거나 바꿔 쓰지 않는다(옵션 문장·아이템 이름 포함). 화면에 없는 값은 채우지 않는다.
- 일부가 가려지거나 잘린 값은 null. 스타포스는 툴팁 위쪽 별을 셀 수 있을 때만 채운다(별을 셀 수 있을 때만, 잘렸으면 null).
- 툴팁이 떠 있으면 그 아이템의 총 수치·잠재·에디 줄을 빠짐없이 옮긴다. 윗잠(잠재능력)은 potentials, 에디셔널 잠재능력은 additional에 따로.
- 목록만 보이면 이름·스타포스·가격만 채우고 나머지는 null/빈 배열.
- 가격은 매물 목록 행(또는 구매 창)의 판매 가격이다. 툴팁 아이템의 가격은 마우스가 올라가 있거나 선택(강조)된 행의 가격이다. 툴팁에 없더라도 같은 아이템 행의 가격을 찾아 넣는다.
- 총 수치는 툴팁 윗부분의 STR/DEX/INT/LUK/최대 HP/공격력/마력/보스/방무/올스탯% 줄(괄호 안 세부 합이 아니라 맨 앞 합계)이다.
- 보조무기(깃펜·포스실드·소울링·오브 등)는 category를 보조무기로. 무기는 캐릭터가 휘두르는 주무기만.
- equip_type은 툴팁의 '장비분류 :' 뒤 글자 그대로, job_groups는 툴팁 아래 직업군(전사 마법사 궁수 도적 해적) 중 착용 가능으로 밝게 표시된 것만. 애매하면 null.
- 잠재·에디 줄은 "에디셔널 잠재능력:" 같은 머리말 없이 옵션 문장만, 숫자(예: "캐릭터 기준 10레벨 당")는 빠짐없이 옮긴다.
- 판매 등록 창 등에 판매 수수료 비율이 보이면 fee_rate에 그 퍼센트 숫자를 넣는다. 보이지 않으면 null(추측 금지).
- 첫 이미지는 화면 전체, 그다음 '툴팁 0', '툴팁 1'… 이미지는 화면에서 찾은 툴팁을 원래 크기로 자른 것이다.
  잠재·에디·총 수치·breakdown은 툴팁 이미지에서 읽고, 가격·목록 행은 화면 전체에서 읽는다. 읽은 툴팁 번호를 tooltip에 넣는다.
  툴팁 이미지의 아이템은 목록에 같은 이름 행이 안 보여도 반드시 listings에 넣는다(가격은 같은 이름 행이 있을 때만, 없으면 null).
- 예시(툴팁 글자 → 옮기는 법):
  "STR +253 (55 +91 +107)" → total.STR=253, breakdown.STR=[55, 91, 107] / "올스탯 +5% (0% +5%)" → total["ALL%"]=5, breakdown["ALL%"]=[0, 5]
  "잠재능력 : 레전드리" 아래 "크리티컬 데미지 +8%" → potential_grade="레전드리", potentials에 "크리티컬 데미지 +8%" 그대로
  "스타포스, 주문서, 추가옵션 강화 불가" → starforce=0 / 별이 잘려 안 보이면 starforce=null
- 가격 글자는 price_text에 화면 그대로(쉼표·억·만 포함) 옮긴다. 단위를 바꾸거나 자릿수를 고치지 않는다.
- 툴팁의 '전투력 증가량'(예: -193만 1721)은 가격이 아니다 — power_delta_text에만 옮긴다.
  목록 행의 가격 칸이 툴팁에 가려 안 보이면 그 매물의 price·price_text는 null(다른 숫자로 채우지 않는다).
- 읽을 수 없는 값은 추측하지 말고 null."""


class VisionError(ValueError):
    """비전 응답을 해석할 수 없다."""


def extract_listings(client, image_data_url: str, model: str | None = None,
                     on_usage=None, crops: list[str] | None = None) -> dict:
    content = [{"type": "input_text", "text": _PROMPT}]
    if image_data_url:  # 경매장 매물 툴팁만 읽을 때는 화면 전체를 보내지 않는다
        content.append({"type": "input_image", "image_url": image_data_url, "detail": "high"})
    for i, c in enumerate(crops or []):
        content += [{"type": "input_text", "text": f"툴팁 {i}"}, {"type": "input_image", "image_url": c, "detail": "high"}]
    resp = client.responses.create(
        model=model or os.environ.get("OPENAI_VISION_MODEL") or os.environ.get("OPENAI_MODEL") or "gpt-6-luna",
        input=[{"role": "user", "content": content}],
        text={"format": {"type": "json_schema", "name": "auction_listings", "schema": _SCHEMA, "strict": True}},
        reasoning={"effort": "low"}, max_output_tokens=16000, store=False,
    )
    if on_usage and getattr(resp, "usage", None):
        on_usage(int(resp.usage.input_tokens) + int(resp.usage.output_tokens))
    try:
        data = json.loads(resp.output_text or "")
    except json.JSONDecodeError as e:
        raise VisionError(f"화면을 매물 정보로 읽지 못했어요: {e}") from None
    if not isinstance(data, dict) or not isinstance(data.get("listings"), list):
        raise VisionError("화면 분석 결과 형식이 올바르지 않아요.")
    equipped = [x for x in data["listings"] if x.get("equipped")]
    data["equipped"] = [x.get("name") for x in equipped]  # 비교 툴팁(끼고 있는 템)은 매물이 아니다
    data["equipped_items"] = equipped                      # 판독은 따로 남긴다(학습 데이터용)
    data["listings"] = [x for x in data["listings"] if not x.get("equipped")]
    for item in data["listings"] + equipped:
        item["total"] = {k: v for k, v in (item.get("total") or {}).items() if v is not None}
        item["breakdown"] = {k: v for k, v in (item.get("breakdown") or {}).items() if v}
        normalize_listing(item)
    return data


def checksum_failures(item: dict) -> list[str]:
    """괄호 안 값의 합이 총 수치와 다른 줄 — 숫자를 잘못 읽었다(2026-10-04 측정: 255→2550, 76→276)."""
    total, parts = item.get("total") or {}, item.get("breakdown") or {}
    out = []
    for k, ps in parts.items():
        if not ps or total.get(k) is None:
            continue
        if abs(sum(ps) - total[k]) > 1e-6:
            fmt = lambda v: f"{v:g}"  # noqa: E731
            out.append(f"{k}: {fmt(total[k])} ≠ {'+'.join(fmt(p) for p in ps)}")
    return out


@functools.lru_cache(maxsize=1)
def _official_options() -> frozenset[str]:
    """공식 큐브 확률표(engine/data/cube_tables.json)에 있는 잠재·에디 옵션 문장 전부."""
    data = pathlib.Path(__file__).resolve().parents[1] / "engine" / "data"
    tables = json.loads((data / "cube_tables.json").read_text(encoding="utf-8"))["tables"]
    opts = {o for kind in tables.values() for g in kind.values() for p in g.values()
            for band in p.values() for line in band for o in line}
    wide = data / "cube_options.json"  # 레어·낮은 레벨까지 넓힌 목록(tools/fetch_cube_tables.py --all)
    if wide.exists():
        opts |= set(json.loads(wide.read_text(encoding="utf-8"))["options"])
    return frozenset(opts)


def unverified_lines(lines: list[str]) -> list[str]:
    """공식 옵션표에 없는 줄 — 화면 글자와 다르게 옮겼을 수 있다(2026-10-04 골든셋: AI가 문장을 줄여 적음)."""
    from engine.options import parse_option
    official = _official_options()
    # 실딜 계산에 안 쓰는 줄(parse_option이 빈 결과 — '공격 시 HP 회복' 등)은 레벨마다 숫자가 달라 대조하지 않는다
    return [x for x in lines if x and x.strip() not in official and parse_option(x.strip(), 250) != []]


def normalize_fee(v) -> float | None:
    """판독한 수수료 → 소수(0.05). 퍼센트(5)로 와도 받는다. 0 이하·10% 초과는 잘못 읽은 것으로 보고 버린다."""
    if not isinstance(v, (int, float)) or isinstance(v, bool) or v <= 0:
        return None
    rate = v / 100 if v >= 1 else float(v)
    return round(rate, 4) if rate <= 0.1 else None


def normalize_listing(item: dict) -> dict:
    """판독 결과 보정.
    - 무기로 읽었지만 무기 종류표에 없는 템(깃펜·포스실드 등)은 보조무기다.
    - 윗잠(potential_lines)·에디(additional)를 따로 보관하고, 평가용 potentials는 둘을 합친다(관측 시세가 둘을 구분한다).
      이미 보정된 매물을 다시 넣어도(재평가) 줄이 두 번 붙지 않는다."""
    from engine.stats.weapons import WEAPON_CONSTANTS
    if item.get("category") == "무기" and item.get("part") not in WEAPON_CONSTANTS:
        item["category"] = item["part"] = "보조무기"
    if "potential_lines" not in item:
        item["potential_lines"] = list(item.get("potentials") or [])
        item["additional"] = list(item.get("additional") or [])
        item["potentials"] = item["potential_lines"] + item["additional"]
    meso = parse_meso(item.get("price_text"))
    if meso:
        item["price"] = meso
    # 2026-11-13 실사용: 가격 칸이 툴팁에 가려 안 보이자 툴팁의 '전투력 증가량 -193만 1721'을 가격으로 읽음 → 같은 숫자면 버린다
    power = power_of(item)
    if power and item.get("price") == power:
        item["price"] = item["price_text"] = None
    return item


def price_log(listings: list[dict]) -> str:
    """매물마다 화면 가격 글자 → 환산값(서버 로그용, 2026-11-13 가격 오독 진단). 툴팁 매물은 [툴팁], 가격도 툴팁도 없는 목록 행은 뺀다."""
    return ", ".join(f"{x.get('name')}{' [툴팁]' if x.get('tooltip') is not None else ''} "
                     f"{repr(x.get('price_text')) if x.get('price_text') else None}→{x.get('price')}"
                     f"{' 전투력 ' + repr(x['power_delta_text']) if x.get('tooltip') is not None and x.get('power_delta_text') else ''}"
                     for x in listings if x.get("tooltip") is not None or x.get("price") or x.get("price_text"))


def list_log(size, rows: list[dict]) -> str:
    """프레임 크기와 AI 없이 읽은 목록 줄(서버 로그용, 2026-11-13 목록 가격이 툴팁 매물에 안 붙은 원인 진단)."""
    head = f"{size[0]}×{size[1]} · 목록 줄 {len(rows)}개" if size else f"이미지 없음 · 목록 줄 {len(rows)}개"
    return head + (" · 전투력 " + ", ".join(f"{r['power']}→{r['price']}" for r in rows) if rows else "")


_MESO_UNITS = (("억", 100_000_000), ("만", 10_000))


def parse_meso(text) -> int | None:
    """화면 가격 글자 → 메소. '1,774,480,000' · '17억 7,448만' · '883만 9385'. 숫자가 없으면 None."""
    if not isinstance(text, str):
        return None
    s = text.replace(",", "").replace(" ", "").replace("메소", "")
    if not re.fullmatch(r"(\d+억)?(\d+만)?\d*", s) or not re.search(r"\d", s):
        return None
    total = 0
    for unit, mult in _MESO_UNITS:
        m = re.match(rf"(\d+){unit}", s)
        if m:
            total += int(m.group(1)) * mult
            s = s[m.end():]
    return total + (int(s) if s else 0)


def signature(item: dict) -> str:
    """같은 매물을 두 번 평가하지 않도록 쓰는 지문."""
    # 가격·총 옵션은 화면을 읽을 때마다 숫자가 조금씩 흔들려 같은 매물이 둘로 갈린다(2026-10-04 실사용) → 뺀다
    parts = [item.get("name"), item.get("starforce"), sorted(item.get("potentials") or [])]
    if item.get("special_ring_level"):  # 이름이 같은 특수 반지도 레벨이 다르면 다른 매물
        parts.append(item["special_ring_level"])
    if (power := power_of(item)) is not None:
        # 2026-11-14: 잠재가 똑같은 18성 커포링 8개가 3장으로 합쳐짐 — 전투력 증가량은 매물마다 다르다
        parts.append(power)
    key = json.dumps(parts, ensure_ascii=False)
    return hashlib.sha1(key.encode()).hexdigest()[:16]


def _data_url(img) -> str:
    import base64
    import io
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


@functools.lru_cache(maxsize=1)
def _item_names() -> tuple[str, ...]:
    """이름 보정에 쓰는 아는 템: 세트 템 + 실측 템 표(세트가 없는 템 포함, engine/data/item_bases.json)."""
    from engine.market.swaps import BASES
    from engine.stats.sets import SetCatalog
    return tuple(dict.fromkeys([*SetCatalog.load().items, *BASES]))


def _power_mask(tip):
    """큰 색 글자(경매장 '전투력 증가량' 숫자) 칸 — 툴팁 오른쪽 위. 착용 장비 툴팁('현재 장착 중인 장비')은 20~30칸뿐."""
    import numpy as np
    c = np.asarray(tip.convert("RGB"), dtype=np.int16)[48:176]
    c = c[:, c.shape[1] * 2 // 5:max(c.shape[1] * 2 // 5 + 1, c.shape[1] - 4)]  # 오른쪽 테두리 4px 제외(뒤 배경색이 JPEG로 번진다)
    hi, lo = c.max(axis=2), c.min(axis=2)
    return (hi > 150) & (hi - lo > 90)


class FrameCache:
    """같은 툴팁·같은 화면을 다시 AI에 보내지 않는다(2026-10-05 실측: 화면 46장 중 쓸모 있는 판독 15개, 하루 토큰 한도 소진).
    - 툴팁이 있으면: 잘라낸 툴팁들의 축소 회색조 지문이 같으면 이전 판독을 그대로 쓴다.
    - 툴팁이 없으면: 바로 전 '툴팁 없는 화면'과 거의 같으면(목록이 안 바뀜) 이전 판독을 쓴다."""

    HOLD_S = 3.0  # 재사용은 '방금 대고 있던 툴팁'만 — 마지막으로 쓴 지 3초 안
    # 전투력 숫자(큰 색 글자)까지 맞대 본 툴팁은 다른 매물일 수 없다 — 다시 대도 60초 안이면 재사용(2026-11-14: 같은 매물 3번 판독)
    NUMBER_HOLD_S = 60.0

    def __init__(self, size: int = 300, clock=None):
        import threading
        import time
        self.clock = clock or time.monotonic
        self.tips: dict = {}  # 키 → (판독, 마지막으로 쓴 시각)
        self.size = size
        self.plain = None  # (지문, 판독)
        # 화면이 동시에 여러 장 보내므로(2026-10-06) 같은 툴팁을 읽는 중이면 기다렸다가 그 판독을 쓴다
        self.lock = threading.Lock()
        self.pending: list = []  # (지문, threading.Event)

    @staticmethod
    def textprint(tip, box=(0, 0, 0, 0)) -> tuple:
        """툴팁 지문 = 글자(밝은 픽셀) 모양. 툴팁은 반투명이라 픽셀 지문은 뒤 배경에 흔들린다(같은 템 8~14% 차이, 2026-10-06).
        맨 위 별 줄(반짝이)은 뺀다 — 별은 재사용할 때 지금 화면에서 다시 센다."""
        import numpy as np
        from PIL import Image as _I
        a = np.asarray(tip.convert("L"), dtype=np.uint8)[48:]
        m = _I.fromarray(((a > 170) * 255).astype(np.uint8)).resize((24, 40), _I.BOX)
        color = _power_mask(tip)
        return (box[0], box[1], tip.width, tip.height,
                tuple((np.asarray(m, dtype=np.float32) / 255).round(3).flatten().tolist()),
                (color.shape, np.packbits(color).tobytes()))

    @staticmethod
    def tip_close(a: tuple, b: tuple) -> bool:
        """같은 자리의 같은 툴팁: 위치·크기 4px 이내, 글자 지문 거리 0.02 미만(대고 있는 동안 실측 ≤0.009).
        그림만으로는 숫자 하나 다른 매물을 못 가른다(재압축만으로 글자 픽셀 925개 어긋남, 숫자 하나 26개) —
        그래서 위치(마우스를 옮기면 툴팁이 따라 움직인다)와 시간(HOLD_S)으로 '같은 hover'일 때만 재사용한다."""
        if any(abs(x - y) > 4 for x, y in zip(a[:4], b[:4])):
            return False
        if sum(abs(x - y) for x, y in zip(a[4], b[4])) / len(a[4]) >= 0.02:
            return False
        return FrameCache._color_close(a[5], b[5])

    COLOR_MIN = 200    # 색 글자 칸이 이만큼 있어야 비교한다('현재 장착 중인 장비' 툴팁은 20~30칸)
    COLOR_DIFF = 0.5   # 2026-11-14 실측 불일치: 다른 매물 0.75~0.81, 같은 툴팁 재압축 0.20~0.24

    @staticmethod
    def _color_close(a, b) -> bool:
        """경매장 툴팁은 어느 줄에 대든 같은 자리에 떠서, 위치·글자 지문만으로는 -177만 4480과 -9만 8551 매물을 못 갈랐다(2026-11-14).
        큰 색 글자(전투력 증가량)를 원래 크기로 맞대 본다 — 오른쪽 끝 정렬, ±1px 흔들림 허용."""
        import numpy as np
        (sa, pa), (sb, pb) = a, b
        x = np.unpackbits(np.frombuffer(pa, np.uint8), count=sa[0] * sa[1]).reshape(sa).astype(bool)
        y = np.unpackbits(np.frombuffer(pb, np.uint8), count=sb[0] * sb[1]).reshape(sb).astype(bool)
        if x.sum() < FrameCache.COLOR_MIN or y.sum() < FrameCache.COLOR_MIN:
            return True  # 비교할 큰 숫자가 없다 — 글자 지문 판정을 따른다
        h, w = min(x.shape[0], y.shape[0]), min(x.shape[1], y.shape[1])
        x, y = x[:h, -w:], y[:h, -w:]
        best = 1.0
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                z = np.roll(np.roll(y, dy, 0), dx, 1)
                best = min(best, float((x ^ z).sum() / max(1, (x | z).sum())))
        return best < FrameCache.COLOR_DIFF

    @staticmethod
    def _has_number(key: tuple) -> bool:
        """툴팁 중 하나라도 큰 색 글자(전투력 증가량)가 있다."""
        import numpy as np
        return any(len(t) > 5 and int(np.unpackbits(np.frombuffer(t[5][1], np.uint8)).sum()) >= FrameCache.COLOR_MIN
                   for t in key)

    def find(self, key: tuple):
        now = self.clock()
        for k, (v, at) in list(self.tips.items()):
            if now - at > (self.NUMBER_HOLD_S if self._has_number(k) else self.HOLD_S):
                del self.tips[k]
            elif len(k) == len(key) and all(map(self.tip_close, k, key)):
                self.tips[k] = (v, now)  # 대고 있는 동안은 계속 연장
                return v
        return None

    def claim(self, key: tuple):
        """(이전 판독, None) · (None, 내가 읽을 표시) · (None, None) = 같은 툴팁을 다른 요청이 읽는 중."""
        import threading
        with self.lock:
            hit = self.find(key)
            if hit is not None:
                return hit, None
            if any(len(k) == len(key) and all(map(self.tip_close, k, key)) for k, _ in self.pending):
                return None, None
            mine = (key, threading.Event())
            self.pending.append(mine)
            return None, mine

    def release(self, mine, data):
        with self.lock:
            if data is not None:
                self.tips[mine[0]] = (data, self.clock())
                while len(self.tips) > self.size:
                    self.tips.pop(next(iter(self.tips)))
            if mine in self.pending:
                self.pending.remove(mine)
        mine[1].set()

    @staticmethod
    def fingerprint(img, n: int = 24) -> tuple:
        import numpy as np
        a = np.asarray(img.convert("L").resize((n, n)), dtype=np.int16)
        return tuple((a // 24).flatten().tolist())

    @staticmethod
    def close(a: tuple, b: tuple) -> bool:
        return sum(x != y for x, y in zip(a, b)) <= len(a) * 0.03


MAX_PIXELS = 16_000_000  # 디코드 전에 가로×세로를 본다(약 4K 두 장) — 거대한 PNG로 2GB 서버 메모리를 터뜨리지 못하게


class ImageTooLarge(Exception):
    """화면 이미지 해상도가 MAX_PIXELS를 넘는다(디코드 전에 거절)."""


class VisionQuota(Exception):
    """AI 판독이 필요한데 한도가 끝났다(일반 유저 하루 상한). 건너뛰기·재사용은 한도와 무관하게 된다."""


class ScanRegistry:
    """스캔(사용자·연결)마다 본 툴팁과 분석 상태 — '인식 N개 · 분석 중 M개'를 AI와 상관없이 바로 보여 준다(2026-11-14 요청).
    같은 툴팁 판정은 FrameCache.tip_close(위치·글자 지문·전투력 숫자)."""

    def __init__(self, ttl: float = 1800, max_scans: int = 2000, max_tips: int = 300):
        import threading
        self.ttl, self.max_scans, self.max_tips = ttl, max_scans, max_tips
        self.scans: dict = {}  # scan → (마지막 시각, [[키, 끝남]])
        self.lock = threading.Lock()

    def _live(self, scan, now):
        got = self.scans.get(scan)
        if got and now - got[0] > self.ttl:
            del self.scans[scan]
            return None
        return got

    def mark(self, scan, key: tuple, done: bool, now: float) -> None:
        with self.lock:
            got = self._live(scan, now)
            tips = got[1] if got else []
            for e in tips:
                if len(e[0]) == len(key) and all(map(FrameCache.tip_close, e[0], key)):
                    e[1] = e[1] or done
                    break
            else:
                if len(tips) < self.max_tips:
                    tips.append([key, done])
            self.scans[scan] = (now, tips)
            while len(self.scans) > self.max_scans:
                self.scans.pop(next(iter(self.scans)))

    def counts(self, scan, now: float) -> tuple[int, int]:
        """(인식한 툴팁 수, 분석 중인 수)."""
        with self.lock:
            got = self._live(scan, now)
            tips = got[1] if got else []
            return len(tips), sum(not d for _, d in tips)


def analyze_frame(client, image_data_url: str, model: str | None = None, on_usage=None,
                  cache: FrameCache | None = None, tooltips_only: bool = False, allow_ai=None, on_tip=None) -> dict:
    """화면 공유 프레임 분석: 툴팁을 찾아 원래 크기로 잘라 함께 보내고, AI 판독값 중 코드로 확인할 수 있는 것은 바꾼다.
    - 스타포스: 툴팁 별을 코드로 센 값(로컬 실측 15/15, AI 판독 1/9 — 2026-10-04)
    - 이름: 세트 장비 이름 목록과 한두 글자만 다르면 바로잡는다(에테르널 → 에테르넬)"""
    import base64
    import io

    from PIL import Image

    from server.tooltip import correct_name, crop, find_tooltips, stars_near
    listing_only = False  # 매물 툴팁만 보낸다(화면 전체 없이)
    try:
        img = Image.open(io.BytesIO(base64.b64decode(image_data_url.split(",", 1)[1])))
        if img.size[0] * img.size[1] > MAX_PIXELS:  # 헤더만 읽은 상태 — 아직 풀지 않았다
            raise ImageTooLarge()
        img = img.convert("RGB")
        boxes = find_tooltips(img)
        stars = [stars_near(img, b) for b in boxes]
        if any(s is None for s in stars) and (any(s is not None for s in stars) or _auction_list_visible(img)):
            # 경매장 다크모드(2026-11-13): 필터 칸·목록 칸도 어두운 상자로 잡힌다. 실제 캡처 3장의 가짜 상자 9개는 별 줄이 0개,
            # 진짜 툴팁 2개는 18성 — 목록의 동전 줄이 보이면 별 줄 없는 상자는 툴팁으로 보지 않는다.
            # 별 줄 있는 툴팁이 함께 있어도 뺀다(2026-11-14: 필터 칸 높이가 752·760·768로 흔들려 같은 툴팁을 AI로 또 읽음)
            boxes, stars = [b for b, s in zip(boxes, stars) if s is not None], [s for s in stars if s is not None]
        tips = [crop(img, b) for b in boxes]
        color = [int(_power_mask(t).sum()) for t in tips]
        if tooltips_only and color and max(color) >= FrameCache.COLOR_MIN:
            # 경매장: 전투력 숫자가 있는 매물 툴팁만 보낸다 — 착용 장비 툴팁은 넥슨 API로 안다(2026-11-14 실측 12초 → 7~8초).
            # 착용 툴팁도 주황 '교환 불가' 줄이 있어 241칸까지 나온다(매물 1317칸) — 가장 많은 툴팁의 절반 이상만 남긴다
            keep = [i for i, n in enumerate(color) if n >= max(FrameCache.COLOR_MIN, max(color) / 2)]
            boxes, stars, tips = [boxes[i] for i in keep], [stars[i] for i in keep], [tips[i] for i in keep]
            listing_only = True
    except (ValueError, OSError, Image.DecompressionBombError):  # 이미지를 열 수 없으면 툴팁 자르기 없이 화면 전체만 보낸다
        img, boxes, tips, stars = None, [], [], []
    rows = _list_rows(img)  # 목록 줄 가격·전투력(AI 없이) — 툴팁이 가격 칸을 가리기 전에 읽어 둔다(2026-11-13)
    extra = {"list_rows": rows, "frame_size": img.size if img is not None else None}
    if tooltips_only and img is not None and not tips:
        # 툴팁이 없는 화면은 AI에 보내지 않는다(실측: 장비창 훑기 46장 중 31장이 툴팁 없음, 판독 0)
        return {"tooltip_visible": False, "fee_rate": None, "listings": [], "equipped": [], "equipped_items": [],
                "tooltips_found": 0, "skipped": "툴팁 없음", **extra}
    import copy
    mine = None
    if cache is not None and img is not None:
        if tips:
            key = tuple(cache.textprint(t, b) for t, b in zip(tips, boxes))  # 왼쪽부터 순서대로
            hit, mine = cache.claim(key)
            if on_tip is not None:
                on_tip(key, hit is not None)  # 인식(AI와 상관없이) — 이전 판독을 쓰면 바로 '완료'
            if hit is None and mine is None:
                # 같은 툴팁을 다른 요청이 읽는 중 — 기다리지 않고 돌려준다(결과는 먼저 온 요청이 돌려준다).
                # 기다리면 브라우저 동시 전송 칸을 다 차지해 다음 매물을 10~20초 못 보냈다(2026-11-14)
                return {"tooltip_visible": True, "fee_rate": None, "listings": [], "equipped": [], "equipped_items": [],
                        "tooltips_found": len(tips), "skipped": "판독 중", **extra}
            if hit is not None:
                out = {**copy.deepcopy(hit), "cached": True}
                for x in out["listings"] + out.get("equipped_items", []):
                    i = x.get("tooltip")
                    if x.get("starforce_source") == "별 세기" and isinstance(i, int) and 0 <= i < len(stars)                             and stars[i] is not None:
                        x["starforce"] = stars[i]  # 별은 지문에 없다 — 지금 화면에서 센 값
                return {**out, **extra}
        else:
            fp = cache.fingerprint(img, 32)
            if cache.plain and cache.close(cache.plain[0], fp):
                return {**copy.deepcopy(cache.plain[1]), "cached": True, **extra}
    data = None
    try:
        if allow_ai is not None and not allow_ai():
            raise VisionQuota()
        data = _read_frame(client, None if listing_only else image_data_url, model, on_usage, tips, stars)
    finally:
        if mine is not None:
            cache.release(mine, copy.deepcopy(data) if data is not None else None)
            if on_tip is not None:
                on_tip(mine[0], True)  # 판독이 끝났다(실패해도 '분석 중'에 남기지 않는다)
    if cache is not None and img is not None and not tips:
        cache.plain = (cache.fingerprint(img, 32), copy.deepcopy(data))
    return {**data, **extra}


def _auction_list_visible(img) -> bool:
    """경매장 목록의 동전 줄(가격 칸 왼쪽 동전이 한 열에 둘 이상)이 보이는 화면."""
    import numpy as np
    from server.listprice import find_coins
    try:
        return bool(find_coins(np.asarray(img, dtype=int)))
    except Exception:
        return False


def _list_rows(img) -> list[dict]:
    """화면의 경매장 목록 줄 중 전투력 증가량·가격을 둘 다 읽은 줄. 목록이 없거나 못 읽으면 빈 목록(평가는 계속)."""
    if img is None:
        return []
    from server.listprice import read_rows
    try:
        return [{"power": r["power"], "price": r["price"]} for r in read_rows(img) if r["power"] and r["price"]]
    except Exception:  # 목록 읽기 실패가 화면 평가를 막으면 안 된다
        return []


def power_of(item: dict) -> int | None:
    """툴팁의 전투력 증가량 글자(AI 판독) → 크기. '-193만 1721' → 1931721."""
    text = str(item.get("power_delta_text") or "")
    for sign in "-+＋－−":  # AI가 부호를 전각 '＋'·'－'로 옮기기도 한다(2026-11-14 실사용)
        text = text.replace(sign, "")
    return parse_meso(text)


def _read_frame(client, image_data_url, model, on_usage, tips, stars) -> dict:
    from server.tooltip import correct_name
    crop_urls = [_data_url(t) for t in tips]
    data = extract_listings(client, image_data_url, model, on_usage, crops=crop_urls)
    data["tooltips_found"] = len(tips)
    for x in data["listings"] + data.get("equipped_items", []):
        i = x.get("tooltip")
        counted = stars[i] if isinstance(i, int) and 0 <= i < len(stars) else None
        x["starforce_ai"] = x.get("starforce")
        if counted is not None:
            x["starforce"], x["starforce_source"] = counted, "별 세기"
        else:
            x["starforce_source"] = "화면 판독(확인 필요)"
        x["name_read"] = x.get("name")
        x["name"], _ = correct_name(x.get("name"), _item_names())
        failed = [k for k in (x.get("breakdown") or {}) if any(c.startswith(f"{k}:") for c in checksum_failures(x))]
        if failed and isinstance(i, int) and 0 <= i < len(crop_urls):
            x["reread"] = _reread(client, crop_urls[i], x, failed, model, on_usage)
    return data


_REREAD_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["lines"],
    "properties": {"lines": {"type": "array", "items": {
        "type": "object", "additionalProperties": False, "required": ["key", "total", "parts"],
        "properties": {"key": {"type": "string", "enum": list(_TOTAL_KEYS)}, "total": {"type": "number"},
                       "parts": {"type": "array", "items": {"type": "number"}}}}}},
}
_LABEL = {"STR": "STR", "DEX": "DEX", "INT": "INT", "LUK": "LUK", "HP": "최대 HP", "ATK": "공격력", "MATK": "마력",
          "ALL%": "올스탯", "BOSS": "보스 몬스터 데미지", "IED": "몬스터 방어율 무시", "DMG": "데미지"}


def _reread(client, crop_url: str, x: dict, keys: list[str], model, on_usage) -> list[str]:
    """괄호 합이 안 맞는 줄만 그 툴팁에서 다시 읽는다(2026-10-05 실측: 검산 실패 대부분이 괄호 안 작은 값 누락).
    다시 읽은 괄호 값의 합이 총 수치와 맞을 때만 받아들인다. 받아들인 줄 이름 목록을 돌려준다."""
    names = ", ".join(_LABEL[k] for k in keys)
    resp = client.responses.create(
        model=model or os.environ.get("OPENAI_VISION_MODEL") or os.environ.get("OPENAI_MODEL") or "gpt-6-luna",
        input=[{"role": "user", "content": [
            {"type": "input_text", "text": f"이 툴팁에서 다음 줄만 옮겨라: {names}. 맨 앞 합계(total)와 괄호 안 값(parts)을 "
                                           "작은 값(+1, +3)까지 하나도 빠짐없이 화면 글자 그대로. key는 STR/DEX/INT/LUK/HP/ATK/MATK/ALL%/BOSS/IED/DMG."},
            {"type": "input_image", "image_url": crop_url, "detail": "high"}]}],
        text={"format": {"type": "json_schema", "name": "lines", "schema": _REREAD_SCHEMA, "strict": True}},
        reasoning={"effort": "low"}, max_output_tokens=4000, store=False)
    if on_usage and getattr(resp, "usage", None):
        on_usage(int(resp.usage.input_tokens) + int(resp.usage.output_tokens))
    try:
        lines = json.loads(resp.output_text or "")["lines"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return []
    fixed = []
    for ln in lines:
        k, parts = ln.get("key"), ln.get("parts") or []
        if k in keys and parts and abs(sum(parts) - (x.get("total") or {}).get(k, float("nan"))) < 1e-6                 and abs(ln.get("total", -1) - x["total"][k]) < 1e-6:
            x["breakdown"][k] = parts
            fixed.append(k)
    return fixed
