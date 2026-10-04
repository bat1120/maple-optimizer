"""경매장 화면 분석: 사용자가 공유한 탭의 캡처 이미지에서 GPT 비전으로 매물 정보를 뽑는다.

넥슨 서버에는 아무 요청도 보내지 않는다 — 사용자 화면에 이미 보이는 내용만 읽는다.
숫자는 모델이 읽은 값이므로 화면에 "읽은 내용"을 그대로 보여 주고 확인받는다.
"""
import hashlib
import json
import os

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
                "required": ["name", "category", "part", "starforce", "total", "potentials", "additional", "price"],
                "properties": {
                    "name": {"type": "string"},
                    "category": {"type": "string", "enum": list(CATEGORIES)},
                    "part": {"type": "string", "description": "무기면 무기 종류(예: 카르타), 아니면 category와 같게"},
                    "starforce": {"type": ["integer", "null"]},
                    "total": {
                        "type": "object", "additionalProperties": False, "required": list(_TOTAL_KEYS),
                        "properties": {k: {"type": ["number", "null"]} for k in _TOTAL_KEYS},
                        "description": "툴팁의 총 수치. 올스탯%는 ALL%, 보스 몬스터 데미지%는 BOSS, 몬스터 방어율 무시%는 IED",
                    },
                    "potentials": {"type": "array", "items": {"type": "string"},
                                   "description": "윗잠(잠재능력) 줄 원문 그대로 (예: 'INT +12%'). 에디셔널은 넣지 않는다"},
                    "additional": {"type": "array", "items": {"type": "string"},
                                   "description": "에디셔널 잠재능력 줄 원문 그대로 (예: '마력 +10')"},
                    "price": {"type": ["integer", "null"], "description": "판매 가격(메소). 보이지 않으면 null"},
                },
            },
        },
    },
}
_PROMPT = """메이플스토리 경매장 화면 캡처다. 보이는 매물을 JSON으로 옮겨라.
- 툴팁이 떠 있으면 그 아이템의 총 수치·잠재·에디 줄을 빠짐없이 옮긴다. 윗잠(잠재능력)은 potentials, 에디셔널 잠재능력은 additional에 따로.
- 목록만 보이면 이름·스타포스·가격만 채우고 나머지는 null/빈 배열.
- 가격은 매물 목록 행(또는 구매 창)의 판매 가격이다. 툴팁 아이템의 가격은 마우스가 올라가 있거나 선택(강조)된 행의 가격이다. 툴팁에 없더라도 같은 아이템 행의 가격을 찾아 넣는다.
- 총 수치는 툴팁 윗부분의 STR/DEX/INT/LUK/최대 HP/공격력/마력/보스/방무/올스탯% 줄(괄호 안 세부 합이 아니라 맨 앞 합계)이다.
- 보조무기(깃펜·포스실드·소울링·오브 등)는 category를 보조무기로. 무기는 캐릭터가 휘두르는 주무기만.
- 잠재·에디 줄은 "에디셔널 잠재능력:" 같은 머리말 없이 옵션 문장만, 숫자(예: "캐릭터 기준 10레벨 당")는 빠짐없이 옮긴다.
- 판매 등록 창 등에 판매 수수료 비율이 보이면 fee_rate에 그 퍼센트 숫자를 넣는다. 보이지 않으면 null(추측 금지).
- 읽을 수 없는 값은 추측하지 말고 null. 숫자 단위(억·만)는 메소 정수로 바꾼다."""


class VisionError(ValueError):
    """비전 응답을 해석할 수 없다."""


def extract_listings(client, image_data_url: str, model: str | None = None,
                     on_usage=None) -> dict:
    resp = client.responses.create(
        model=model or os.environ.get("OPENAI_VISION_MODEL") or os.environ.get("OPENAI_MODEL") or "gpt-6-luna",
        input=[{"role": "user", "content": [
            {"type": "input_text", "text": _PROMPT},
            {"type": "input_image", "image_url": image_data_url, "detail": "high"},
        ]}],
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
    for item in data["listings"]:
        item["total"] = {k: v for k, v in (item.get("total") or {}).items() if v is not None}
        normalize_listing(item)
    return data


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
    return item


def signature(item: dict) -> str:
    """같은 매물을 두 번 평가하지 않도록 쓰는 지문."""
    # 가격·총 옵션은 화면을 읽을 때마다 숫자가 조금씩 흔들려 같은 매물이 둘로 갈린다(2026-10-04 실사용) → 뺀다
    key = json.dumps([item.get("name"), item.get("starforce"), sorted(item.get("potentials") or [])], ensure_ascii=False)
    return hashlib.sha1(key.encode()).hexdigest()[:16]
