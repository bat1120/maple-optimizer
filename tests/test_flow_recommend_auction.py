"""흐름 테스트(2026-11-13 사용자): 내신부레테로 ① 아이템 추천 → ② 그 조건으로 경매장 검색 → ③ 매물 가격을 억당 실딜로 비교.

화면에서 쓰는 API를 순서대로 부른다: /recommend → /api/market/refresh(관리자) → /paths·/roadmap.
경매장은 가짜 maple-auction-mcp(tests/fake_auction_mcp.py)가 테스트가 고른 매물을 돌려준다 — 진짜 경매장에는 요청하지 않는다
(CLAUDE.md: 경매장 자동 수집 금지). 캐릭터는 픽스처(넥슨 API 실측 응답)라 넥슨에도 요청하지 않는다.

추천 1순위 부위는 엠블렘(골드 서머너 엠블렘, 0성, 잠재 마력 +12% / INT +12% / 마력 +9%, 에디 마력 +6% / 크확 +3% / 마력 +3%).
매물의 기본 옵션(stat)은 지금 엠블렘과 같게 둬서, 매물 사이 실딜 차이는 잠재·에디 줄에서만 난다."""
import json
import sys

import pytest
from fastapi.testclient import TestClient

from helpers import bundle
from server.admin import make_password_hash
from server.app import create_app
from server.auction_mcp import filters_for

FAKE = [sys.executable, "tests/fake_auction_mcp.py"]
NAME = "내신부레테"
SLOT = "엠블렘"
STAT = "STR+10 DEX+10 INT+10 LUK+10 공격력+2 마력+2"  # 지금 엠블렘 기본 옵션 그대로
GOOD_POT = "레전드리: 마력 +12% / 마력 +9% / 몬스터 방어율 무시 +30%"  # 추천 카드 잠재 목표
GOOD_ADD = "유니크: 마력 +9% / 마력 +6%"                                # 추천 카드 에디 목표


def _item(id_, price, status="ON_SALE", my_world=True, pot=GOOD_POT, add=GOOD_ADD, name="골드 서머너 엠블렘"):
    return {"id": id_, "name": name, "price": price, "quantity": 1, "starforce": 0, "stat": STAT,
            "potential": pot, "additional": add, "status": status, "isMyWorld": my_world}


ITEMS = [
    _item("on", 5_000_000_000),                                       # 판매 중 50억
    _item("sold", 4_500_000_000, status="SOLD"),                      # 판매 완료 45억(시세)
    _item("other", 5_000_000_000, my_world=False),                    # 다른 월드 50억 → 구매가 +10%
    _item("same", 300_000_000, pot="레전드리: 마력 +12% / INT +12% / 마력 +9%",
          add="에픽: 마력 +6% / 크리티컬 확률 +3% / 마력 +3%"),         # 지금 템과 똑같음 → 오르는 게 없다
    _item("worse", 200_000_000, pot="에픽: 마력 +6% / INT +6% / 마력 +3%",
          add="레어: 마력 +3%"),                                       # 지금보다 나쁨
]


@pytest.fixture(scope="module")
def flow(tmp_path_factory):
    """흐름을 한 번 돌려 둔다(추천·검색·경로 계산이 무거워 테스트마다 다시 하지 않는다)."""
    tmp_path = tmp_path_factory.mktemp("flow")
    items = tmp_path / "items.json"
    items.write_text(json.dumps(ITEMS, ensure_ascii=False), encoding="utf-8")
    log = tmp_path / "calls.jsonl"
    mp = pytest.MonkeyPatch()
    mp.setenv("FAKE_MCP_ITEMS", str(items))
    mp.setenv("FAKE_MCP_LOG", str(log))
    c = TestClient(create_app(lambda n, d: bundle("레테"), str(tmp_path / "c.sqlite3"),
                              admin_password_hash=make_password_hash("pw", 1000), session_secret="s" * 32,
                              auction_mcp_command=FAKE))
    assert c.post("/api/admin/login", json={"password": "pw"}).status_code == 200
    rec = c.get(f"/api/character/{NAME}/recommend").json()
    card = next(x for x in rec["recommendations"] if x["slot"] == SLOT)
    refresh = c.post("/api/market/refresh", json={"name": NAME, "slots": [SLOT], "max_searches": 5}).json()
    calls = [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines()]
    paths = c.get(f"/api/character/{NAME}/paths").json()
    yield {"client": c, "rec": rec, "card": card, "refresh": refresh, "calls": calls, "paths": paths}
    mp.undo()


def _buys(paths):
    return [p for p in paths["all"] if p["path"] == "구매" and p["slot"] == SLOT]


# ① 추천 ---------------------------------------------------------------------------------------------------------

def test_tc1_recommend_cards_are_ranked_and_searchable(flow):
    """추천 카드: 실딜이 큰 순서, 각 카드에 게임 경매장에 그대로 넣을 검색 문구와 목표 줄이 있다."""
    cards = flow["rec"]["recommendations"]
    assert [c["slot"] for c in cards][0] == SLOT
    deltas = [c["delta_pct"] for c in cards]
    assert deltas == sorted(deltas, reverse=True) and all(d > 0 for d in deltas)
    card = flow["card"]
    assert {p["kind"] for p in card["parts"]} == {"잠재", "에디"}
    for p in card["parts"]:
        assert all(line in card["search"] for line in p["target"])  # 검색 문구에 목표 줄이 다 들어 있다


# ② 경매장 검색 -------------------------------------------------------------------------------------------------

def test_tc2_auction_search_uses_the_recommended_conditions(flow):
    """경매장 검색 조건 = 추천 카드 조건. 잠재·에디 각각 판매 중·판매 완료를 찾고, 직업군·성 하한을 건다."""
    calls, card = flow["calls"], flow["card"]
    assert flow["refresh"]["searched"] == len(calls) == 5
    want = {"potentialOptions": filters_for(next(p["target"] for p in card["parts"] if p["kind"] == "잠재")),
            "additionalPotentialOptions": filters_for(next(p["target"] for p in card["parts"] if p["kind"] == "에디"))}
    for key, f in want.items():
        hits = [c["arguments"] for c in calls if c["arguments"].get(key) == f]
        assert {bool(a.get("sold")) for a in hits} == {True, False}, key  # 판매 중 + 판매 완료(시세)
    for c in calls:
        a = c["arguments"]
        assert c["name"] == "search_armor" and a["jobClass"] == "MAGE"
        assert a["starforceMin"] == card["min_starforce"]


def test_tc3_search_budget_is_respected(flow, tmp_path, monkeypatch):
    """하루 검색 한도가 있어 갱신 한 번에 max_searches보다 많이 찾지 않는다."""
    log = tmp_path / "few.jsonl"
    monkeypatch.setenv("FAKE_MCP_LOG", str(log))
    r = flow["client"].post("/api/market/refresh", json={"name": NAME, "slots": [SLOT], "max_searches": 2}).json()
    assert r["searched"] == 2 and len(log.read_text(encoding="utf-8").splitlines()) == 2


# ③ 가격 비교 ---------------------------------------------------------------------------------------------------

def test_tc4_listing_price_becomes_per_100m_value(flow):
    """구매 경로 비용 = 매물 가격, 억당 실딜 = 실딜 상승 ÷ (가격/1억)."""
    buys = _buys(flow["paths"])
    assert buys, "추천 조건 매물이 구매 경로로 안 나왔다"
    for b in buys:
        assert b["per_100m"] == pytest.approx(b["delta_pct"] / (b["cost"] / 1e8))
        assert b["delta_pct"] > 0


def test_tc5_same_item_cheaper_price_is_better_value(flow):
    """같은 옵션이면 실딜은 같고, 싼 매물(판매 완료 45억)이 비싼 매물(판매 중 50억)보다 억당이 높다."""
    buys = _buys(flow["paths"])
    on = next(b for b in buys if not b["sold"] and b["cost"] == 5_000_000_000)
    sold = next(b for b in buys if b["sold"])
    assert sold["cost"] == 4_500_000_000
    assert sold["delta_pct"] == pytest.approx(on["delta_pct"])
    assert sold["per_100m"] / on["per_100m"] == pytest.approx(50 / 45)


def test_tc6_other_world_listing_costs_10_percent_more(flow):
    """다른 월드 매물은 가격의 10%를 더 낸다(메이플포인트) — 같은 50억이면 55억으로 비교."""
    costs = sorted(b["cost"] for b in _buys(flow["paths"]) if not b["sold"])
    assert costs == [5_000_000_000, pytest.approx(5_500_000_000)]


def test_tc7_listings_not_better_than_current_are_not_offered(flow):
    """지금 템과 같거나 나쁜 매물(3억·2억)은 싸도 구매 추천에 나오지 않는다."""
    assert all(b["cost"] >= 4_500_000_000 for b in _buys(flow["paths"]))
    assert flow["paths"]["observed_count"] == len(ITEMS)


def test_tc8_purchase_competes_with_other_paths_by_per_100m(flow):
    """부위별 최선 = 그 부위의 모든 경로(구매·직작·큐브·스타포스…) 중 억당 최고. 전체 목록은 억당 내림차순."""
    paths = flow["paths"]
    per = [p["per_100m"] for p in paths["all"]]
    assert per == sorted(per, reverse=True)
    best = next(p for p in paths["best_by_slot"] if p["slot"] == SLOT)
    assert best["per_100m"] == max(p["per_100m"] for p in paths["all"] if p["slot"] == SLOT)


def test_tc9_roadmap_shows_market_price_for_the_recommended_tier(flow):
    """로드맵의 추천 단계(잠재 레전드리 3줄)에 조건을 채우는 매물 시세가 붙는다(나쁜 매물은 안 셈)."""
    rm = flow["client"].get(f"/api/character/{NAME}/roadmap").json()
    row = next(s for s in rm["slots"] if s["slot"] == SLOT)
    target = next(p["target"] for p in flow["card"]["parts"] if p["kind"] == "잠재")
    tier = next(t for t in row["잠재"] if t["target"] == target)
    m = tier["market"]
    assert m["count"] >= 2 and m["min"] >= 4_500_000_000
    assert m["per_100m"] == pytest.approx(tier["delta_pct"] / (m["median"] / 1e8))
