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
        "price": {"type": ["integer", "null"], "description": "메소 정수(45억 3000만 → 4530000000). 화면 매물의 price가 null이면 null 그대로"},
        "list_prices": {"type": "array", "items": {"type": "integer"},
                        "description": "화면 매물에 있으면 그대로 넘긴다 — price가 null일 때 후보 가격마다 계산한다"},
        "unverified_lines": {"type": "array", "items": {"type": "string"},
                             "description": "화면 매물에 있으면 그대로 넘긴다 — 공식 옵션표에 없는 줄이라 평가를 보류한다"},
        "special_ring_level": {"type": "integer", "description": "화면 매물에 있으면 그대로 넘긴다(특수 반지 레벨)"},
        "special_ring_note": {"type": "string", "description": "화면 매물에 있으면 그대로 넘긴다"},
        "resale": {"type": "integer", "description": "지금 그 부위 템 판매 예상가(메소), 없으면 0"},
    },
    "required": ["slot", "part", "name"],
}
_SETTING = {
    "type": "object",
    "description": "사용자가 특정 프리셋 조합을 요청했을 때만 넣는다. 생략하면 보스 실딜 최적 세팅으로 계산한다.",
    "properties": {k: {"type": "integer"} for k in ("equipment", "hyper", "ability", "union", "link")},
    "required": ["equipment", "hyper", "ability"],
}
_CONDITIONS = {
    "type": "object",
    "properties": {"discount30": {"type": "boolean"}, "destroy_down30": {"type": "boolean"},
                   "guarantee_5_10_15": {"type": "boolean"}, "protect": {"type": "boolean"},
                   "restore": {"type": "string", "enum": ["full", "basic"]}},
}

_NAME = {"type": "string", "description": "캐릭터 닉네임 — 조회한 캐릭터, 또는 사용자가 말한 이름"}
_COOLDOWN = {"type": "number", "description": "쿨감 1초 = 주스탯 몇 %로 볼지. 사용자가 숫자를 정해 말했을 때만 넣는다(결과의 note가 지금 쿨감을 어떻게 반영했는지 알려 준다)"}
_FEE = {"type": "number", "description": "경매장 판매 수수료(판매 대금에서 빠짐). 사용자가 MVP 실버 이상이나 PC방이라고 하면 0.03, 그 밖에는 생략(0.05)"}

TOOL_DEFS = [
    {"name": "lookup_character", "description": "캐릭터가 지금 무엇을 끼고 있는지 물을 때. 닉네임으로 캐릭터 요약(직업·레벨·적용 세팅·스탯공격력)과 보스 세팅 장비(equipment: 부위·이름·스타포스·잠재·에디)를 조회한다.",
     "input_schema": {"type": "object", "properties": {"name": _NAME}, "required": ["name"]}},
    {"name": "rank_settings", "description": "세팅(프리셋 조합) 자체를 물을 때만. 장비·하이퍼·어빌·유니온·링크 프리셋 조합을 보스 실딜 지수로 정렬한다(상위 10개). relative_to_active는 현재 세팅 대비 배율.",
     "input_schema": {"type": "object", "properties": {"name": _NAME, "boss_defense": {"type": "number"}},
                      "required": ["name"]}},
    {"name": "recommend_searches", "description": "'뭘 사야 해', '경매장에서 뭘 검색해' 질문에. 게임 경매장에서 무엇을 검색할지 추천한다: 부위마다 카드 하나 — 잠재·에디를 각각 지금보다 한 단계 위로 바꾼 조건을 한 번에 검색하도록 묶고(parts), 둘을 함께 바꾸면 보스 실딜이 몇 % 오르는지(delta_pct, 종류별은 parts[].delta_pct) 큰 순서로 돌려준다. 쿨감 줄은 유지(kept). 제네시스 무기처럼 경매장에서 못 사는 템은 빠진다. 각 카드는 그 부위의 다음 한 단계이고, search가 게임 경매장에 그대로 넣는 검색 조건(부위·잠재·에디·최소 스타포스)이다.",
     "input_schema": {"type": "object", "properties": {"name": _NAME, "boss_defense": {"type": "number"},
                                                         "top": {"type": "integer"},
                                                         "cooldown_main_pct": _COOLDOWN},
                      "required": ["name"]}},
    {"name": "upgrade_roadmap", "description": "'전체 부위 어떻게 바꿔', '가성비'·'가격 대비' 질문에(가성비는 value_ranking). 전체 부위 로드맵: 부위마다 잠재·에디를 에픽→유니크→레전드리, 2줄→3줄 단계로 바꿨을 때 보스 실딜 상승(delta_pct)과 한 번에 나올 확률(probability). 부위의 잠재·에디 목록에는 next 단계(실딜이 처음 0.1% 이상 오르는 단계, 목록의 첫 항목)와 그다음 단계만 있다(next가 null이면 올릴 단계 없음). route '큐브'는 경매장에서 못 사는 템(제네시스 무기 등). value_ranking은 가격 대비 순위 상위 15개(메소 재설정 평균 비용 cube_cost·cube_cost_text, 억당 실딜 per_100m). 단계의 market은 화면에서 읽어 쌓인 관측 시세(count·median·min·per_100m).",
     "input_schema": {"type": "object", "properties": {"name": _NAME, "boss_defense": {"type": "number"},
                                                         "cooldown_main_pct": _COOLDOWN}, "required": ["name"]}},
    {"name": "upgrade_paths", "description": "'뭐부터 올려', 구매·직작·큐브·스타포스 중 무엇을 할지 추천할 때 먼저 쓴다. 업그레이드 경로 비교: 구매(관측 매물)·직작(매물+큐브)·지금 템 큐브·스타포스(from_star→to_star, 파괴 시 스페어 비용 제외, expected_destroys=평균 파괴 횟수)를 억당 실딜(per_100m)로 정렬한다. 세트 효과 변화(set_change)가 실딜에 들어가 있다. best_by_slot은 부위별 최선 경로. sold=true는 체결 시세, false는 호가. cost_text를 그대로 인용.",
     "input_schema": {"type": "object", "properties": {"name": _NAME, "boss_defense": {"type": "number"},
                                                         "cooldown_main_pct": _COOLDOWN}, "required": ["name"]}},
    {"name": "target_roadmap", "description": "목표 보스 배율 로드맵: 지금 배율(current_ratio, 예: MapleScouter 효율·보스컷의 익스트림 스우 34.52)에서 목표(target_ratio, 예: 50)까지 억당 효율 순으로 쌓은 업그레이드 단계(스타포스는 한 성씩, 큐브·HEXA). 단계마다 ratio_after·total_cost_text. 배율은 실딜 비례 추정 — 숫자는 결과에서만 인용.",
     "input_schema": {"type": "object", "properties": {"name": _NAME, "current_ratio": {"type": "number"},
                                                       "target_ratio": {"type": "number"},
                                                       "fragment_price": {"type": "number", "description": "솔 에르다 조각 1개 메소(넣으면 HEXA 포함)"}},
                      "required": ["name", "current_ratio", "target_ratio"]}},
    {"name": "budget_roadmap", "description": "사용자가 쓸 수 있는 메소(예산)를 말했을 때: '50억 있는데 어디까지 올려', '예산 100억으로 뭐 할까'. 억당 효율 순으로 업그레이드 단계(추옵 재설정, 스타포스는 한 성씩, 큐브·심볼·HEXA)를 예산이 찰 때까지 쌓아 돌려준다. steps[].total_cost_text는 그 단계까지 누적 비용, gain_pct_after는 그 단계까지 누적 실딜 상승률. spent_text·gain_pct가 합계, next_step은 예산이 모자라 건너뛴 단계 중 효율이 가장 높은 것. 경매장 구매는 들어 있지 않다(매물은 화면으로 받아 evaluate_listings).",
     "input_schema": {"type": "object", "properties": {"name": _NAME,
                                                       "budget": {"type": "integer", "description": "메소 정수(50억 → 5000000000). 사용자가 말한 금액"}},
                      "required": ["name", "budget"]}},
    {"name": "refresh_market", "description": "웹 경매장을 검색해 관측 시세를 갱신한다(로컬 연결 시만). 로드맵 다음 단계 조건으로 판매 중·판매 완료(체결가)를 찾는다. 일일 검색 한도(100회)를 쓰므로 시세가 필요할 때만, max_searches는 작게(기본 10), 질문 하나에 두 번까지. 갱신 뒤 upgrade_paths를 다시 부른다.",
     "input_schema": {"type": "object", "properties": {"name": _NAME,
                                                         "slots": {"type": "array", "items": {"type": "string"}},
                                                         "max_searches": {"type": "integer"}}, "required": ["name"]}},
    {"name": "evaluate_listings", "description": "사용자가 붙여 넣은 매물이나 '[경매장 화면에서 읽은 매물]'을 살지 판단할 때. 툴팁은 total(총 옵션)과 potentials(잠재·에디 줄)로 나눠 넣는다. 매물들을 같은 부위 템과 교체했을 때 실딜 상승률(%)·억당 효율·환산 주스탯으로 평가해 효율순 정렬한다. held는 평가를 보류한 매물과 이유(reason)다.",
     "input_schema": {"type": "object", "properties": {"name": _NAME, "boss_defense": {"type": "number"},
                                                         "setting": _SETTING, "listings": {"type": "array", "items": _LISTING},
                                                         "fee_rate": _FEE},
                      "required": ["name", "listings"]}},
    {"name": "starforce_cost", "description": "스타포스 강화 비용: 정확한 기대값(exact_mean, 메소)과 분포(중앙값·p75·p90). destroy_cost는 파괴 시 비용(스페어+복구). 금액은 exact_mean_text·distribution_text를 그대로 인용.",
     "input_schema": {"type": "object", "properties": {"level": {"type": "integer"}, "start": {"type": "integer"},
                                                         "target": {"type": "integer"}, "destroy_cost": {"type": "number"},
                                                         "conditions": _CONDITIONS},
                      "required": ["level", "start", "target", "destroy_cost"]}},
    {"name": "cube_probability", "description": "레전드리·무기·200제 잠재 재설정에서 목표 옵션이 뜰 1회 확률(probability, 0~1)과 필요 횟수·메소 분포(금액은 meso_text를 그대로 인용). kind=lines면 그 옵션 줄 수 이상, kind=sum이면 % 합 이상.",
     "input_schema": {"type": "object", "properties": {"option": {"type": "string", "enum": ["BOSS", "IED", "MATK", "ATK", "INT", "STR", "DEX", "LUK", "DMG", "CR"]},
                                                         "kind": {"type": "string", "enum": ["lines", "sum"]}, "value": {"type": "number"}},
                      "required": ["option", "kind", "value"]}},
    {"name": "craft_compare", "description": "매물 가격을 직작 비용 분포(베이스 템+스타포스+잠재 재설정, 추옵 미포함)와 비교한다. 금액은 craft_mean_text·distribution_text를 그대로 인용.",
     "input_schema": {"type": "object", "properties": {"price": {"type": "number"}, "base_price": {"type": "number"}, "level": {"type": "integer"},
                                                         "start_star": {"type": "integer"}, "target_star": {"type": "integer"},
                                                         "destroy_cost": {"type": "number"}, "cube_p": {"type": "number"}, "cube_cost": {"type": "number"}},
                      "required": ["price", "base_price", "level"]}},
    {"name": "optimize_budget", "description": "예산 안에서 실딜을 가장 많이 올리는 후보 조합(부위당 1개)과 순서를 고른다.",
     "input_schema": {"type": "object", "properties": {"name": _NAME, "budget": {"type": "number"},
                                                         "boss_defense": {"type": "number"}, "setting": _SETTING,
                                                         "candidates": {"type": "array", "items": _LISTING}, "fee_rate": _FEE},
                      "required": ["name", "budget", "candidates"]}},
]
TOOL_DEFS.append(
    {"name": "request_auction_screen",
     "description": "'경매장에서 ○○ 찾아줘/보여줘'처럼 실제 매물을 봐야 하거나, 관측 시세가 없어 가격을 말할 수 없을 때. 사용자에게 게임 경매장 검색 화면을 채팅 안에서 공유해 달라고 요청한다. 검색 조건(부위·잠재·에디·최소 스타포스)을 "
                    "넣으면 화면에 [화면 연결] 카드가 뜨고, 사용자가 매물을 읽어 보내면 '[경매장 화면에서 읽은 매물]'이 붙은 다음 질문으로 온다. "
                    "조건은 recommend_searches 카드나 사용자가 말한 조건을 글자 그대로 옮긴다.",
     "input_schema": {"type": "object", "properties": {
         "category": {"type": "string", "description": "부위(예: 보조무기, 반지)"},
         "potentials": {"type": "array", "items": {"type": "string"}, "description": "잠재 줄(없으면 빈 목록)"},
         "additional": {"type": "array", "items": {"type": "string"}, "description": "에디 줄(없으면 빈 목록)"},
         "min_starforce": {"type": "integer"},
         "note": {"type": "string", "description": "사용자에게 보일 한 줄 안내"}},
         "required": ["category"]}})


def openai_tools(exclude: tuple = ()) -> list[dict]:
    """Responses API 함수 도구 형식(평평한 구조). 선택 필드가 있어 strict 정규화를 끈다."""
    # 최상위 인자는 정의된 것만 받는다(소형 모델이 없는 인자를 지어내는 것을 줄인다). strict는 선택 필드 때문에 끈다.
    return [{"type": "function", "name": t["name"], "description": t["description"],
             "parameters": {**t["input_schema"], "additionalProperties": False}, "strict": False} for t in TOOL_DEFS if t["name"] not in exclude]


MAX_REFRESH_PER_QUESTION = 2
VALUE_RANKING_TOP = 15  # 가격 대비 순위는 위에서 이만큼만 모델에게 준다(전체는 화면의 로드맵 탭에 있다)
MIN_LISTING_PRICE = 10_000  # 이보다 작은 가격은 '45억'을 45로 넣은 단위 실수다
FEE_RATES = (0.03, 0.05)
_EQUIPMENT_FIELDS = ("slot", "name", "starforce", "potential_grade", "additional_grade", "potentials", "additional")


def compact(value):
    """모델에 보내는 도구 결과의 숫자를 줄인다: 1000 이상(메소)은 정수로, 그 밖의 소수는 유효숫자 6자리로.
    0.007026608358000001 같은 긴 소수가 결과 글자 수의 큰 몫이었다(답변 숫자 검사의 허용 오차 0.1%보다 훨씬 작게 줄인다)."""
    if isinstance(value, float) and value == value and abs(value) != float("inf"):
        return round(value) if abs(value) >= 1000 else float(f"{value:.6g}")
    if isinstance(value, dict):
        return {k: compact(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [compact(v) for v in value]
    return value


def _meso_texts(amounts: dict) -> dict:
    return {k: service.meso_text(v) for k, v in amounts.items()}


class ToolBox:
    """질문 하나에 하나씩 만든다 — refresh_market 횟수 같은 질문 단위 한도를 여기서 센다."""

    def __init__(self, load: Callable[..., CharacterSnapshot], market: Callable[[], list[dict]] | None = None,
                 refresh: Callable[..., dict] | None = None):
        self._load = load
        self._refresh = refresh  # 웹 경매장 검색(maple-auction-mcp)으로 관측 시세 갱신 — 일일 검색 한도 소진
        self._market = market  # 관측 시세(화면 분석으로 쌓인 매물 가격)
        self._refreshes = 0

    def run(self, name: str, args: dict) -> dict:
        """도구 실행. 실패는 예외 대신 {"error": 한국어 메시지}로 돌려 Claude가 보고 고칠 수 있게 한다."""
        try:
            return compact(getattr(self, f"_{name}")(**args))
        except AttributeError:
            return {"error": f"알 수 없는 도구: {name}"}
        except Exception as e:  # noqa: BLE001 — 도구 오류는 모델에게 그대로 보여 준다
            return {"error": f"{type(e).__name__}: {e}"}

    @staticmethod
    def _check_listings(listings, fee_rate):
        """프롬프트로 부탁하던 입력 규칙을 여기서 막는다 — 어기면 고칠 방법이 적힌 오류가 모델에게 간다."""
        if fee_rate not in FEE_RATES:
            raise ValueError(f"fee_rate는 0.05(기본) 또는 0.03(사용자가 MVP 실버 이상·PC방이라고 한 경우)만 넣는다: {fee_rate}")
        for x in listings:
            price = x.get("price")
            if isinstance(price, (int, float)) and 0 < price < MIN_LISTING_PRICE:
                raise ValueError(f"price는 메소 정수다(45억 3000만 → 4530000000). {price}는 억·만 단위로 넣은 것 같다 — 메소로 다시 넣는다")

    @staticmethod
    def _prepare(listings):
        """평가할 매물·보류할 매물·안내를 나눈다. 프롬프트로 부탁하던 일이다:
        공식 옵션표에 없는 줄이 있으면 보류, 가격을 못 읽었으면 목록 가격 후보마다 계산(후보도 없으면 보류), 특수 반지는 레벨로 비교."""
        ready, held, rings, candidates = [], [], {}, []
        for x in listings:
            x = dict(x)
            odd, prices = x.pop("unverified_lines", None), x.pop("list_prices", None)
            level, note = x.pop("special_ring_level", None), x.pop("special_ring_note", None)
            if odd:
                held.append({"name": x.get("name"), "reason": "공식 옵션표에 없는 줄이 있어 평가를 보류했어요(" + ", ".join(odd)
                                                             + ") — 화면에서 그 줄을 다시 확인해 달라고 한다"})
                continue
            if level or note:
                rings[x.get("name")] = ((note or f"특수 반지 스킬 효과는 실딜 계산에 없어요 — 스탯만 계산했어요. 이 매물 {level}레벨")
                                        + " 실딜 수치로 사라/말라 하지 않고, 반지 레벨과 가격으로 지금 낀 반지와 비교한다.")
            if x.get("price") is None:
                if not prices:
                    held.append({"name": x.get("name"), "reason": "가격을 읽지 못했어요 — 사용자에게 가격을 물어본다"})
                    continue
                candidates.append(x.get("name"))
                ready += [{**x, "price": price} for price in prices]
            else:
                ready.append(x)
        return ready, held, rings, candidates

    @staticmethod
    def _annotate(result, held, rings, candidates):
        result["held"] = list(result.get("held") or []) + held
        for row in result.get("ranking") or []:
            if row.get("name") in rings:
                row["special_ring_note"] = rings[row["name"]]
        if candidates:
            result["price_candidates_note"] = ("가격을 못 읽은 매물(" + ", ".join(candidates) + ")은 같은 이름 목록 행의 가격 후보마다 "
                                               "계산했어요 — 후보별 결과를 보여 주고 툴팁이 어느 행인지 확인을 부탁한다")
        return result

    @staticmethod
    def _request_auction_screen(category, potentials=None, additional=None, min_starforce=0, note=None):
        """화면이 이 결과(search)로 채팅 안 [화면 연결] 카드를 띄운다. 계산은 하지 않는다 — 매물은 다음 질문으로 온다."""
        return {"status": "requested", "note": note,
                "search": {"category": category, "potentials": list(potentials or []), "additional": list(additional or []),
                           "min_starforce": int(min_starforce or 0)},
                "next": "사용자가 화면을 연결해 매물을 보내면 evaluate_listings로 평가한다. 지금은 검색 조건만 안내하고 기다린다."}

    @staticmethod
    def _setting(s):
        return Setting(**s) if s else None

    def _lookup_character(self, name):
        snap = self._load(name)
        r = service.summary(snap)
        best = service.settings(snap, 300.0)["ranking"][0]["setting"]
        # 화면용 요약은 프리셋 3개 × 부위별 스탯 내역이라 5만 자가 넘는다(2026-11-22 평가: 질문 하나가 토큰 한도를 넘어 답이 없었다).
        # 모델에게는 평가 기준인 보스 세팅 장비의 이름·스타포스·잠재·에디만 준다. 수치 계산은 다른 도구가 한다
        presets = r.pop("equipment_presets")
        worn = presets.get(str(best["equipment"])) or presets.get(best["equipment"]) or []
        r["equipment"] = [{k: it[k] for k in _EQUIPMENT_FIELDS if it.get(k) not in (None, [], "")}
                          | ({"special_ring_level": it["special_ring_level"]} if it.get("special_ring_level") else {})
                          for it in worn]
        r["evaluation_setting"] = best
        r["evaluation_note"] = ("평가는 보스 실딜 최적 세팅(evaluation_setting) 기준이다. active_setting이 사냥 세팅인 것은 "
                                "사냥 중이라서 정상이다 — 프리셋 전환을 권하지 않는다.")
        return r

    def _rank_settings(self, name, boss_defense=300.0):
        r = service.settings(self._load(name), boss_defense)
        r["ranking"] = r["ranking"][:10]
        return r

    def _observed(self):
        return self._market() if self._market else None

    @staticmethod
    def _market_status(result, observed):
        if not observed:
            result["market_status"] = ("관측 시세 측정값 없음 — 경매장 가격은 이 결과에 없다. 가격을 말하려면 request_auction_screen으로 "
                                       "그 조건의 경매장 화면을 받아야 한다")
        return result

    def _recommend_searches(self, name, boss_defense=300.0, top=5, cooldown_main_pct=None):
        return service.recommend(self._load(name), boss_defense, max(1, min(int(top), 20)), cooldown_main_pct)

    def _upgrade_roadmap(self, name, boss_defense=300.0, cooldown_main_pct=None):
        observed = self._observed()
        r = service.roadmap(self._load(name), boss_defense, cooldown_main_pct, observed)
        # 화면용은 부위마다 모든 단계(종류당 6개)를 싣는다 — 모델에게는 답에 쓰는 'next 단계와 그다음 단계'만 준다(7만 자 → 2만 자대)
        for row in r["slots"]:
            for kind in ("잠재", "에디"):
                first = row["next"].get(kind)
                row[kind] = [] if first is None else [
                    stage | ({"cube_cost_text": service.meso_text(stage["cube_cost"])} if stage.get("cube_cost") else {})
                    for stage in row[kind][first:first + 2]]
                row["next"][kind] = None if first is None else 0
        r["value_ranking"] = r["value_ranking"][:VALUE_RANKING_TOP]
        return self._market_status(r, observed)

    def _upgrade_paths(self, name, boss_defense=300.0, cooldown_main_pct=None):
        observed = self._observed()
        return self._market_status(service.paths(self._load(name), boss_defense, observed, cooldown_main_pct), observed)

    def _target_roadmap(self, name, current_ratio, target_ratio, fragment_price=None):
        from engine.market.events import Events
        r = service.target_roadmap(self._load(name), 300.0, self._market() if self._market else None, current_ratio,
                                   target_ratio, Events(fragment_price=fragment_price or 0.0))
        r.pop("scouter", None)
        return r

    def _budget_roadmap(self, name, budget):
        r = service.budget_roadmap(self._load(name), 300.0, self._observed(), budget)
        return {k: v for k, v in r.items() if k not in ("boss", "basis_warning", "budget")}

    def _refresh_market(self, name, slots=None, max_searches=10):
        if not self._refresh:
            return {"error": "경매장 검색 연결이 없어요(AUCTION_MCP_CMD 미설정)."}
        if self._refreshes >= MAX_REFRESH_PER_QUESTION:
            return {"error": f"이 질문에서 시세 갱신을 이미 {MAX_REFRESH_PER_QUESTION}번 했어요(일일 검색 한도). 지금 있는 관측 시세로 답한다."}
        self._refreshes += 1
        return self._refresh(name, slots, max_searches)

    def _evaluate_listings(self, name, listings, boss_defense=300.0, setting=None, fee_rate=0.05):
        self._check_listings(listings, fee_rate)
        ready, held, rings, candidates = self._prepare(listings)
        r = service.listings(self._load(name), self._setting(setting), boss_defense, [ListingIn(**x) for x in ready], fee_rate)
        return self._annotate(r, held, rings, candidates)

    def _starforce_cost(self, level, start, target, destroy_cost, conditions=None):
        r = service.starforce(StarforceIn(level=level, start=start, target=target, destroy_cost=destroy_cost,
                                          conditions=conditions or {}, trials=20000))
        # 2026-11-22 평가: 모델이 87억 5915만을 '8억 7591만'으로 옮겼다 — 억·만 변환을 모델에게 맡기지 않는다
        return r | {"exact_mean_text": service.meso_text(r["exact_mean"]), "distribution_text": _meso_texts(r["distribution"])}

    def _cube_probability(self, option, kind, value):
        body = {"table": "레전드리/무기/200", "level": 200, "grade": "레전드리"}
        if kind == "lines":
            body["lines_at_least"] = {option: int(value)}
        else:
            body["sum_at_least"] = [{"key": option, "percent": True, "value": value}]
        r = service.cube(CubeIn(**body))
        return r | {"meso_text": _meso_texts(r["meso"])} if isinstance(r.get("meso"), dict) else r

    def _craft_compare(self, **kw):
        r = service.craft_compare(CraftIn(**kw))
        return r | {"craft_mean_text": service.meso_text(r["craft_mean"]), "distribution_text": _meso_texts(r["distribution"])}

    def _optimize_budget(self, name, budget, candidates, boss_defense=300.0, setting=None, fee_rate=0.05):
        self._check_listings(candidates, fee_rate)
        ready, held, rings, priced = self._prepare(candidates)
        r = service.optimize(self._load(name), self._setting(setting), boss_defense, budget,
                             [ListingIn(**x) for x in ready], fee_rate)
        return self._annotate(r, held, rings, priced)
