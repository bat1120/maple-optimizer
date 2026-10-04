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
    "required": ["tooltip_visible", "listings"],
    "properties": {
        "tooltip_visible": {"type": "boolean", "description": "아이템 상세 툴팁(잠재 옵션이 보이는 창)이 화면에 떠 있는가"},
        "listings": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["name", "category", "part", "starforce", "total", "potentials", "price"],
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
                                   "description": "잠재·에디셔널 줄 원문 그대로 (예: 'INT +12%')"},
                    "price": {"type": ["integer", "null"], "description": "판매 가격(메소). 보이지 않으면 null"},
                },
            },
        },
    },
}
_PROMPT = """메이플스토리 경매장 화면 캡처다. 보이는 매물을 JSON으로 옮겨라.
- 툴팁이 떠 있으면 그 아이템의 총 수치·잠재·에디 줄을 빠짐없이 옮긴다.
- 목록만 보이면 이름·스타포스·가격만 채우고 나머지는 null/빈 배열.
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
    return data


def signature(item: dict) -> str:
    """같은 매물을 두 번 평가하지 않도록 쓰는 지문."""
    key = json.dumps([item.get("name"), item.get("starforce"), sorted(item.get("potentials") or []),
                      item.get("price"), sorted((item.get("total") or {}).items())], ensure_ascii=False)
    return hashlib.sha1(key.encode()).hexdigest()[:16]
