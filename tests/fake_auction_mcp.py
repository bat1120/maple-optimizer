"""테스트용 가짜 maple-auction-mcp: MCP stdio(JSON-RPC 한 줄씩)로 search_armor/search_weapon에 고정 응답을 준다.
받은 호출은 환경 변수 FAKE_MCP_LOG 파일에 한 줄씩 남긴다."""
import json
import os
import sys

sys.stdin.reconfigure(encoding="utf-8")
sys.stdout.reconfigure(encoding="utf-8")  # 실제 MCP(node)처럼 UTF-8

ITEM = {"id": "x:1", "name": "에테르넬 메이지로브", "price": 20_000_000_000, "quantity": 1, "starforce": 22,
        "stat": "INT+520 LUK+330 마력+220", "potential": "레전드리: INT +13% / INT +10% / INT +10%",
        "additional": "레어: 마력 +12", "status": "ON_SALE", "endDate": "2026-10-10", "wishlist": 0, "isMyWorld": True}
SOLD = {**ITEM, "id": "x:2", "price": 18_000_000_000, "status": "SOLD", "tradeDate": "2026-10-01"}


def reply(i, result):
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": i, "result": result}, ensure_ascii=False) + "\n")
    sys.stdout.flush()


for raw in sys.stdin:
    msg = json.loads(raw)
    if "id" not in msg:
        continue
    if msg["method"] == "initialize":
        reply(msg["id"], {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}},
                          "serverInfo": {"name": "fake", "version": "0"}})
    elif msg["method"] == "tools/call":
        p = msg["params"]
        if os.environ.get("FAKE_MCP_LOG"):
            with open(os.environ["FAKE_MCP_LOG"], "a", encoding="utf-8") as f:
                f.write(json.dumps(p, ensure_ascii=False) + "\n")
        if os.environ.get("FAKE_MCP_DOWN"):
            text = "브라우저 확장이 연결되지 않았습니다. 크롬에서 경매장에 로그인해 주세요."
        else:
            sold = p["arguments"].get("sold", False)
            text = json.dumps({"total": 1, "page": 1, "totalPages": 1, "hasNext": False, "searchKey": "k",
                               "items": [SOLD if sold else ITEM], "searchRemaining": 87}, ensure_ascii=False)
        reply(msg["id"], {"content": [{"type": "text", "text": text}]})
    else:
        reply(msg["id"], {})
