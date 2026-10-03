# G2 (2단계): 매물 평가 엔진 Implementation Plan

> 자동 반복 모드(goal 설정 C). 성공 기준: `GOALS.md` G2. 스펙 §7.

**Goal:** 사용자가 입력한 경매장 매물(아이템 옵션 + 가격)을 현재 보스 세팅의 같은 부위 템과 교체했을 때의 실딜 상승률과 억당 효율을 계산하고 효율순으로 정렬한다.

## Rulings
- Ruling: 매물 입력 단위는 "아이템 총 옵션 수치(스타포스·추옵·주문서 합) + 잠재·에디 문자열"이다 — 넥슨 API에 아이템 기본 스탯 DB가 없어 "아이템명 → 기본 스탯 자동 채움"(스펙 §7)은 아직 데이터가 없다. 경매장 툴팁의 총 옵션을 그대로 옮겨 적는 방식이 입력도 쉽다 — 틀리면 입력 UX만 바뀐다.
- Ruling: 효율 분모는 (가격 − 판매 예상가)/1억. 분모 ≤ 0이면 `InvalidPrice` — 공짜·이득 거래는 효율이 무한대라 순위가 의미 없다.
- Ruling: 상승률 기준은 보스 실딜 지수의 비율 (new/base − 1)×100.

## File Structure
- `engine/market/__init__.py`, `engine/market/listing.py`: `Listing`, `ListingEval`, `InvalidPrice`, `item_from_input`, `evaluate_listing`, `rank_listings`
- `tests/test_market.py`, `tests/goals/test_g2.py`

## Interfaces
- `item_from_input(slot, part, name, total: dict[str, float], potentials: list[str], level: int, starforce: int = 0) -> Item` — `total` 키: STR DEX INT LUK HP ATK MATK ALL%(올스탯%) BOSS IED DMG
- `Listing(slot: str, item: Item, price: int, resale: int = 0)` (메소 단위)
- `evaluate_listing(snap, setting, listing, boss, catalog) -> ListingEval(listing, base, new, delta_pct, per_100m)`
- `rank_listings(snap, setting, listings, boss, catalog) -> list[ListingEval]` (per_100m 내림차순)
