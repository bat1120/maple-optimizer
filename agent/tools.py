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

_FEE = {"type": "number", "description": "경매장 판매 수수료(판매 대금에서 빠짐). 기본 0.05, MVP 실버 이상·PC방이면 0.03"}

TOOL_DEFS = [
    {"name": "lookup_character", "description": "닉네임으로 캐릭터 요약(직업·레벨·적용 세팅·스탯공격력·장비 프리셋)을 조회한다.",
     "input_schema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}},
    {"name": "rank_settings", "description": "장비·하이퍼·어빌·유니온·링크 프리셋 조합을 보스 실딜 지수로 정렬한다(상위 10개). relative_to_active는 현재 세팅 대비 배율.",
     "input_schema": {"type": "object", "properties": {"name": {"type": "string"}, "boss_defense": {"type": "number"}},
                      "required": ["name"]}},
    {"name": "recommend_searches", "description": "게임 경매장에서 무엇을 검색할지 추천한다: 부위·잠재/에디마다 지금보다 한 단계 위(grade·lines_good)로 바꾸면 보스 실딜이 몇 % 오르는지 계산해 큰 순서로 돌려준다. 쿨감 줄은 유지(kept). 제네시스 무기처럼 경매장에서 못 사는 템은 빠진다. 각 카드의 search가 검색 조건(부위·잠재·최소 스타포스)이다.",
     "input_schema": {"type": "object", "properties": {"name": {"type": "string"}, "boss_defense": {"type": "number"},
                                                         "top": {"type": "integer"},
                                                         "cooldown_main_pct": {"type": "number", "description": "쿨감 1초 = 주스탯 몇 %로 볼지. 사용자가 정한 값만 넣는다"}},
                      "required": ["name"]}},
    {"name": "upgrade_roadmap", "description": "전체 부위 로드맵: 부위마다 잠재·에디를 에픽→유니크→레전드리, 2줄→3줄 단계로 바꿨을 때 보스 실딜 상승(delta_pct)과 한 번에 나올 확률(probability). next는 실딜이 처음 0.1% 이상 오르는 단계, route '큐브'는 경매장에서 못 사는 템(제네시스 무기 등). value_ranking은 가격 대비 순위(메소 재설정 평균 비용 cube_cost·cube_cost_text, 억당 실딜 per_100m). 단계의 market은 화면에서 읽어 쌓인 관측 시세(count·median·min·per_100m).",
     "input_schema": {"type": "object", "properties": {"name": {"type": "string"}, "boss_defense": {"type": "number"},
                                                         "cooldown_main_pct": {"type": "number"}}, "required": ["name"]}},
    {"name": "upgrade_paths", "description": "업그레이드 경로 비교(추천의 기본 근거): 구매(관측 매물)·직작(매물+큐브)·지금 템 큐브·스타포스(from_star→to_star, 파괴 시 스페어 비용 제외, expected_destroys=평균 파괴 횟수)를 억당 실딜(per_100m)로 정렬한다. 세트 효과 변화(set_change)가 실딜에 들어가 있다. best_by_slot은 부위별 최선 경로. cost_text를 그대로 인용.",
     "input_schema": {"type": "object", "properties": {"name": {"type": "string"}, "boss_defense": {"type": "number"},
                                                         "cooldown_main_pct": {"type": "number"}}, "required": ["name"]}},
    {"name": "target_roadmap", "description": "목표 보스 배율 로드맵: 지금 배율(current_ratio, 예: MapleScouter 효율·보스컷의 익스트림 스우 34.52)에서 목표(target_ratio, 예: 50)까지 억당 효율 순으로 쌓은 업그레이드 단계(스타포스는 한 성씩, 큐브·HEXA). 단계마다 ratio_after·total_cost_text. 배율은 실딜 비례 추정 — 숫자는 결과에서만 인용.",
     "input_schema": {"type": "object", "properties": {"name": {"type": "string"}, "current_ratio": {"type": "number"},
                                                       "target_ratio": {"type": "number"},
                                                       "fragment_price": {"type": "number", "description": "솔 에르다 조각 1개 메소(넣으면 HEXA 포함)"}},
                      "required": ["name", "current_ratio", "target_ratio"]}},
    {"name": "refresh_market", "description": "웹 경매장을 검색해 관측 시세를 갱신한다(로컬 연결 시만). 로드맵 다음 단계 조건으로 판매 중·판매 완료(체결가)를 찾는다. 일일 검색 한도(100회)를 쓰므로 시세가 필요할 때만, max_searches는 작게(기본 10). 갱신 뒤 upgrade_paths를 다시 부른다.",
     "input_schema": {"type": "object", "properties": {"name": {"type": "string"},
                                                         "slots": {"type": "array", "items": {"type": "string"}},
                                                         "max_searches": {"type": "integer"}}, "required": ["name"]}},
    {"name": "evaluate_listings", "description": "매물들을 같은 부위 템과 교체했을 때 실딜 상승률(%)·억당 효율·환산 주스탯으로 평가해 효율순 정렬한다. setting을 생략하면 최적 보스 세팅 기준.",
     "input_schema": {"type": "object", "properties": {"name": {"type": "string"}, "boss_defense": {"type": "number"},
                                                         "setting": _SETTING, "listings": {"type": "array", "items": _LISTING},
                                                         "fee_rate": _FEE},
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
                                                         "candidates": {"type": "array", "items": _LISTING}, "fee_rate": _FEE},
                      "required": ["name", "budget", "candidates"]}},
]


def openai_tools() -> list[dict]:
    """Responses API 함수 도구 형식(평평한 구조). 선택 필드가 있어 strict 정규화를 끈다."""
    # 최상위 인자는 정의된 것만 받는다(소형 모델이 없는 인자를 지어내는 것을 줄인다). strict는 선택 필드 때문에 끈다.
    return [{"type": "function", "name": t["name"], "description": t["description"],
             "parameters": {**t["input_schema"], "additionalProperties": False}, "strict": False} for t in TOOL_DEFS]


class ToolBox:
    def __init__(self, load: Callable[..., CharacterSnapshot], market: Callable[[], list[dict]] | None = None,
                 refresh: Callable[..., dict] | None = None):
        self._load = load
        self._refresh = refresh  # 웹 경매장 검색(maple-auction-mcp)으로 관측 시세 갱신 — 일일 검색 한도 소진
        self._market = market  # 관측 시세(화면 분석으로 쌓인 매물 가격)

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
        snap = self._load(name)
        r = service.summary(snap)
        best = service.settings(snap, 300.0)["ranking"][0]["setting"]
        r["evaluation_setting"] = best
        r["evaluation_note"] = ("평가는 보스 실딜 최적 세팅(evaluation_setting) 기준이다. active_setting이 사냥 세팅인 것은 "
                                "사냥 중이라서 정상이다 — 프리셋 전환을 권하지 않는다.")
        return r

    def _rank_settings(self, name, boss_defense=300.0):
        r = service.settings(self._load(name), boss_defense)
        r["ranking"] = r["ranking"][:10]
        return r

    def _recommend_searches(self, name, boss_defense=300.0, top=5, cooldown_main_pct=None):
        return service.recommend(self._load(name), boss_defense, max(1, min(int(top), 20)), cooldown_main_pct)

    def _upgrade_roadmap(self, name, boss_defense=300.0, cooldown_main_pct=None):
        return service.roadmap(self._load(name), boss_defense, cooldown_main_pct,
                               self._market() if self._market else None)

    def _upgrade_paths(self, name, boss_defense=300.0, cooldown_main_pct=None):
        return service.paths(self._load(name), boss_defense, self._market() if self._market else None,
                             cooldown_main_pct)

    def _target_roadmap(self, name, current_ratio, target_ratio, fragment_price=None):
        from engine.market.events import Events
        r = service.target_roadmap(self._load(name), 300.0, self._market() if self._market else None, current_ratio,
                                   target_ratio, Events(fragment_price=fragment_price or 0.0))
        r.pop("scouter", None)
        return r

    def _refresh_market(self, name, slots=None, max_searches=10):
        if not self._refresh:
            return {"error": "경매장 검색 연결이 없어요(AUCTION_MCP_CMD 미설정)."}
        return self._refresh(name, slots, max_searches)

    def _evaluate_listings(self, name, listings, boss_defense=300.0, setting=None, fee_rate=0.05):
        return service.listings(self._load(name), self._setting(setting), boss_defense, [ListingIn(**x) for x in listings],
                                fee_rate)

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

    def _optimize_budget(self, name, budget, candidates, boss_defense=300.0, setting=None, fee_rate=0.05):
        return service.optimize(self._load(name), self._setting(setting), boss_defense, budget,
                                [ListingIn(**x) for x in candidates], fee_rate)
