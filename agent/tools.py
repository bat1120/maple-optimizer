"""에이전트 도구: 엔진/서비스 함수를 감싼 얇은 래퍼. 입력 검증은 서버 스키마(pydantic)를 재사용한다."""
from collections.abc import Callable

from engine.stats.snapshot import CharacterSnapshot, Setting
from server import service
from server.schemas import CraftIn, CubeIn, ListingIn, StarforceIn

_LISTING = {
    "type": "object",
    "description": "경매장 매물. total은 툴팁의 총 옵션(키: STR DEX INT LUK HP ATK MATK ALL% BOSS IED DMG), potentials는 잠재·에디 문자열.",
    "properties": {
        "slot": {"type": "string", "description": "부위 (예: 반지4, 무기, 펜던트)"},
        "part": {"type": "string", "description": "아이템 종류 (예: 반지, 카르타)"},
        "name": {"type": "string"},
        "total": {"type": "object", "additionalProperties": {"type": "number"}},
        "potentials": {"type": "array", "items": {"type": "string"}},
        "price": {"type": "integer", "description": "메소"},
        "resale": {"type": "integer", "description": "지금 그 부위 템 판매 예상가(메소), 없으면 0"},
    },
    "required": ["slot", "part", "name", "price"],
}
_SETTING = {
    "type": "object",
    "properties": {k: {"type": "integer"} for k in ("equipment", "hyper", "ability", "union", "link")},
    "required": ["equipment", "hyper", "ability"],
}
_CONDITIONS = {
    "type": "object",
    "properties": {"discount30": {"type": "boolean"}, "destroy_down30": {"type": "boolean"},
                   "guarantee_5_10_15": {"type": "boolean"}, "protect": {"type": "boolean"},
                   "restore": {"type": "string", "enum": ["full", "basic"]}},
}

TOOL_DEFS = [
    {"name": "lookup_character", "description": "닉네임으로 캐릭터 요약(직업·레벨·적용 세팅·스탯공격력·장비 프리셋)을 조회한다.",
     "input_schema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}},
    {"name": "rank_settings", "description": "장비·하이퍼·어빌·유니온·링크 프리셋 조합을 보스 실딜 지수로 정렬한다(상위 10개). relative_to_active는 현재 세팅 대비 배율.",
     "input_schema": {"type": "object", "properties": {"name": {"type": "string"}, "boss_defense": {"type": "number"}},
                      "required": ["name"]}},
    {"name": "evaluate_listings", "description": "매물들을 같은 부위 템과 교체했을 때 실딜 상승률(%)·억당 효율·환산 주스탯으로 평가해 효율순 정렬한다. setting을 생략하면 최적 보스 세팅 기준.",
     "input_schema": {"type": "object", "properties": {"name": {"type": "string"}, "boss_defense": {"type": "number"},
                                                         "setting": _SETTING, "listings": {"type": "array", "items": _LISTING}},
                      "required": ["name", "listings"]}},
    {"name": "starforce_cost", "description": "스타포스 강화 비용: 정확한 기대값(exact_mean, 메소)과 분포(중앙값·p75·p90). destroy_cost는 파괴 시 비용(스페어+복구).",
     "input_schema": {"type": "object", "properties": {"level": {"type": "integer"}, "start": {"type": "integer"},
                                                         "target": {"type": "integer"}, "destroy_cost": {"type": "number"},
                                                         "conditions": _CONDITIONS},
                      "required": ["level", "start", "target", "destroy_cost"]}},
    {"name": "cube_probability", "description": "레전드리·무기·200제 잠재 재설정에서 목표 옵션이 뜰 1회 확률(probability, 0~1)과 필요 횟수·메소 분포. kind=lines면 그 옵션 줄 수 이상, kind=sum이면 % 합 이상.",
     "input_schema": {"type": "object", "properties": {"option": {"type": "string", "enum": ["BOSS", "IED", "MATK", "ATK", "INT", "STR", "DEX", "LUK", "DMG", "CR"]},
                                                         "kind": {"type": "string", "enum": ["lines", "sum"]}, "value": {"type": "number"}},
                      "required": ["option", "kind", "value"]}},
    {"name": "craft_compare", "description": "매물 가격을 직작 비용 분포(베이스 템+스타포스+잠재 재설정, 추옵 미포함)와 비교한다.",
     "input_schema": {"type": "object", "properties": {"price": {"type": "number"}, "base_price": {"type": "number"}, "level": {"type": "integer"},
                                                         "start_star": {"type": "integer"}, "target_star": {"type": "integer"},
                                                         "destroy_cost": {"type": "number"}, "cube_p": {"type": "number"}, "cube_cost": {"type": "number"}},
                      "required": ["price", "base_price", "level"]}},
    {"name": "optimize_budget", "description": "예산 안에서 실딜을 가장 많이 올리는 후보 조합(부위당 1개)과 순서를 고른다.",
     "input_schema": {"type": "object", "properties": {"name": {"type": "string"}, "budget": {"type": "number"},
                                                         "boss_defense": {"type": "number"}, "setting": _SETTING,
                                                         "candidates": {"type": "array", "items": _LISTING}},
                      "required": ["name", "budget", "candidates"]}},
]


def openai_tools() -> list[dict]:
    """Responses API 함수 도구 형식(평평한 구조). 선택 필드가 있어 strict 정규화를 끈다."""
    # 최상위 인자는 정의된 것만 받는다(소형 모델이 없는 인자를 지어내는 것을 줄인다). strict는 선택 필드 때문에 끈다.
    return [{"type": "function", "name": t["name"], "description": t["description"],
             "parameters": {**t["input_schema"], "additionalProperties": False}, "strict": False} for t in TOOL_DEFS]


class ToolBox:
    def __init__(self, load: Callable[..., CharacterSnapshot]):
        self._load = load

    def run(self, name: str, args: dict) -> dict:
        """도구 실행. 실패는 예외 대신 {"error": 한국어 메시지}로 돌려 Claude가 보고 고칠 수 있게 한다."""
        try:
            return getattr(self, f"_{name}")(**args)
        except AttributeError:
            return {"error": f"알 수 없는 도구: {name}"}
        except Exception as e:  # noqa: BLE001 — 도구 오류는 모델에게 그대로 보여 준다
            return {"error": f"{type(e).__name__}: {e}"}

    @staticmethod
    def _setting(s):
        return Setting(**s) if s else None

    def _lookup_character(self, name):
        return service.summary(self._load(name))

    def _rank_settings(self, name, boss_defense=300.0):
        r = service.settings(self._load(name), boss_defense)
        r["ranking"] = r["ranking"][:10]
        return r

    def _evaluate_listings(self, name, listings, boss_defense=300.0, setting=None):
        return service.listings(self._load(name), self._setting(setting), boss_defense, [ListingIn(**x) for x in listings])

    def _starforce_cost(self, level, start, target, destroy_cost, conditions=None):
        return service.starforce(StarforceIn(level=level, start=start, target=target, destroy_cost=destroy_cost,
                                             conditions=conditions or {}, trials=20000))

    def _cube_probability(self, option, kind, value):
        body = {"table": "레전드리/무기/200", "level": 200, "grade": "레전드리"}
        if kind == "lines":
            body["lines_at_least"] = {option: int(value)}
        else:
            body["sum_at_least"] = [{"key": option, "percent": True, "value": value}]
        return service.cube(CubeIn(**body))

    def _craft_compare(self, **kw):
        return service.craft_compare(CraftIn(**kw))

    def _optimize_budget(self, name, budget, candidates, boss_defense=300.0, setting=None):
        return service.optimize(self._load(name), self._setting(setting), boss_defense, budget,
                                [ListingIn(**x) for x in candidates])
