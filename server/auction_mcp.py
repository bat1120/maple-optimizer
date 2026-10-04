"""maple-auction-mcp(https://github.com/oyc0401/maple-auction-mcp) 연결: 웹 경매장 검색 결과를 관측 시세로 쌓는다.

- 그 MCP는 사용자가 로그인한 크롬 + 확장 프로그램을 통해 웹 경매장 검색을 대신 해 준다. 공식 Open API가 아니다 —
  사용자가 위험을 알고 켰을 때만(AUCTION_MCP_CMD) 동작하고, 로컬 PC에서만 쓸 수 있다.
- 읽기 도구(search_armor·search_weapon)만 부른다. 찜 추가·삭제 같은 계정 변경 도구는 부르지 않는다.
- 검색은 일일 한도(100회)가 있어 갱신 한 번에 max_searches회까지만 쓴다. 대량·주기 수집은 하지 않는다.
"""
import json
import re
import shlex
import subprocess
import threading
import time

from engine.market.recommend import KINDS, _part, roadmap, value_ranking
from engine.stats.evaluate import rank_settings
from engine.stats.jobs import job_profile
from engine.stats.metrics import BossProfile
from engine.stats.sets import SetCatalog
from engine.stats.snapshot import CharacterSnapshot

ARMOR = {"모자": "ARMOR_ARMOR_CAP", "상의": "ARMOR_ARMOR_COAT", "하의": "ARMOR_ARMOR_PANTS", "신발": "ARMOR_ARMOR_SHOES",
         "장갑": "ARMOR_ARMOR_GLOVE", "망토": "ARMOR_ARMOR_CAPE", "얼굴장식": "ARMOR_ACCESSORY_FACE",
         "눈장식": "ARMOR_ACCESSORY_EYE", "귀고리": "ARMOR_ACCESSORY_EAR", "반지": "ARMOR_ACCESSORY_RING",
         "펜던트": "ARMOR_ACCESSORY_PENDANT", "벨트": "ARMOR_ACCESSORY_BELT", "어깨장식": "ARMOR_ACCESSORY_SHOULDER",
         "엠블렘": "ARMOR_ACCESSORY_EMBLEM"}
WEAPON = {"보조무기": "WEAPON_SUB"}  # 주무기는 무기 종류별 분류가 필요해 검색하지 않는다
JOB_CLASS = {"전사": "WARRIOR", "마법사": "MAGE", "궁수": "ARCHER", "도적": "THIEF", "해적": "PIRATE"}

_FILTERS = [
    (re.compile(r"^(STR|DEX|INT|LUK) \+(\d+)%$"), lambda m: f"{m[1].lower()}Percent"),
    (re.compile(r"^올스탯 \+(\d+)%$"), lambda m: "allStatsPercent"),
    (re.compile(r"^공격력 \+(\d+)%$"), lambda m: "physicalAttackPercent"),
    (re.compile(r"^마력 \+(\d+)%$"), lambda m: "magicAttackPercent"),
    (re.compile(r"^공격력 \+(\d+)$"), lambda m: "physicalAttack"),
    (re.compile(r"^마력 \+(\d+)$"), lambda m: "magicAttack"),
    (re.compile(r"^보스 몬스터 데미지 \+(\d+)%$"), lambda m: "bossDamagePercent"),
    (re.compile(r"^몬스터 방어율 무시 \+(\d+)%$"), lambda m: "ignoreMonsterDefense"),
    (re.compile(r"^데미지 \+(\d+)%$"), lambda m: "damagePercent"),
    (re.compile(r"^크리티컬 데미지 \+(\d+)%$"), lambda m: "criticalDamagePercent"),
    (re.compile(r"^캐릭터 기준 9레벨 당 (STR|DEX|INT|LUK) \+(\d+)$"), lambda m: f"{m[1].lower()}PerLevel"),
    (re.compile(r"^스킬 재사용 대기시간 -(\d+)초$"), lambda m: "skillCooldownReduction"),
    (re.compile(r"^(STR|DEX|INT|LUK) \+(\d+)$"), lambda m: m[1].lower()),
]
_STAT = {"STR": "STR", "DEX": "DEX", "INT": "INT", "LUK": "LUK", "올스탯%": "ALL%", "HP": "HP", "공격력": "ATK",
         "마력": "MATK", "보공%": "BOSS", "뎀%": "DMG", "방무%": "IED"}
GRADES = ("레어", "에픽", "유니크", "레전드리")


class McpUnavailable(RuntimeError):
    """MCP를 실행할 수 없거나 브라우저 확장이 연결되지 않았다."""


def filters_for(lines: list[str]) -> list[dict]:
    """목표 줄 → [{option, minValue}] (같은 옵션은 합산 — MCP 기본 합산 모드)."""
    out: dict[str, float] = {}
    for line in lines:
        for rx, key in _FILTERS:
            m = rx.match(line.strip())
            if m:
                k = key(m)
                out[k] = out.get(k, 0) + int(m.groups()[-1])
                break
    return [{"option": k, "minValue": v} for k, v in out.items()]


def _lines(text: str | None) -> tuple[str | None, list[str]]:
    if not text:
        return None, []
    grade, _, rest = text.partition(": ")
    if grade not in GRADES:
        grade, rest = None, text
    return grade, [x.strip() for x in rest.split(" / ") if x.strip()]


def to_observed(item: dict, category: str, part: str) -> dict:
    total = {}
    for tok in (item.get("stat") or "").split():
        label, _, value = tok.rpartition("+")
        if label in _STAT and value:
            total[_STAT[label]] = float(value) if "." in value else int(value)
    pg, pl = _lines(item.get("potential"))
    ag, al = _lines(item.get("additional"))
    return {"category": category, "part": part, "name": item.get("name"), "starforce": item.get("starforce") or 0,
            "level": None, "potential_grade": pg, "additional_grade": ag, "total": total,
            "potential_lines": pl, "additional": al, "potentials": pl + al, "price": item.get("price"),
            "sold": item.get("status") == "SOLD", "other_world": item.get("isMyWorld") is False,
            "source": "경매장 검색"}


class McpStdioClient:
    """MCP stdio 클라이언트(JSON-RPC 한 줄씩). with 블록으로 쓴다."""

    def __init__(self, command, timeout: float = 90.0):
        self.cmd = shlex.split(command, posix=False) if isinstance(command, str) else list(command)
        self.timeout, self._id, self.proc = timeout, 0, None

    def __enter__(self):
        try:
            self.proc = subprocess.Popen(self.cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                         stderr=subprocess.DEVNULL, text=True, encoding="utf-8")
        except OSError as e:
            raise McpUnavailable(f"경매장 MCP를 실행하지 못했어요({e}). AUCTION_MCP_CMD를 확인해 주세요.") from None
        self._rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                 "clientInfo": {"name": "maple-optimizer", "version": "1"}})
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        return self

    def __exit__(self, *exc):
        if self.proc:
            self.proc.kill()
            self.proc.wait()

    def _send(self, msg: dict) -> None:
        self.proc.stdin.write(json.dumps(msg, ensure_ascii=False) + "\n")
        self.proc.stdin.flush()

    def _rpc(self, method: str, params: dict) -> dict:
        self._id += 1
        my = self._id
        self._send({"jsonrpc": "2.0", "id": my, "method": method, "params": params})
        timer = threading.Timer(self.timeout, self.proc.kill)
        timer.start()
        try:
            for raw in self.proc.stdout:
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if msg.get("id") == my:
                    if "error" in msg:
                        raise McpUnavailable(f"경매장 MCP 오류: {msg['error'].get('message')}")
                    return msg.get("result") or {}
        finally:
            timer.cancel()
        raise McpUnavailable("경매장 MCP가 응답 없이 끝났어요(시간 초과 또는 실행 실패).")

    def call(self, tool: str, args: dict):
        """도구 결과 텍스트. JSON이면 파싱해서, 아니면(안내문·오류) 문자열 그대로."""
        res = self._rpc("tools/call", {"name": tool, "arguments": args})
        text = "".join(c.get("text", "") for c in res.get("content") or [] if c.get("type") == "text")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text


def _plan(snap: CharacterSnapshot, rm: dict, slots: list[str]) -> list[tuple[str, str, dict, str]]:
    """(슬롯, 도구, 인자, 설명) 검색 계획: 다음 단계 조건의 판매 중·판매 완료, 그다음 직작 베이스."""
    job = job_profile(snap.character_class)
    plan = []
    for slot in slots:
        row = rm.get(slot)
        cat = _part(slot)
        if row is None or (cat not in ARMOR and cat not in WEAPON):
            continue
        tool, sub = ("search_armor", ARMOR[cat]) if cat in ARMOR else ("search_weapon", WEAPON[cat])
        base = {"subCategory": sub, "starforceMin": row["starforce"], "levelMin": row.get("level") or 0}
        if len(job.branches) == 1 and job.branches[0] in JOB_CLASS:
            base["jobClass"] = JOB_CLASS[job.branches[0]]
        for kind in KINDS:
            i = row["next"][kind]
            if i is None:
                continue
            key = "potentialOptions" if kind == "잠재" else "additionalPotentialOptions"
            f = filters_for(row[kind][i]["target"])
            if f:
                plan.append((slot, tool, {**base, key: f}, f"{slot} {kind} 다음 단계 판매 중"))
                plan.append((slot, tool, {**base, key: f, "sold": True}, f"{slot} {kind} 다음 단계 시세"))
        plan.append((slot, tool, dict(base), f"{slot} 직작 베이스(판매 중)"))
    return plan


def refresh_market(snap: CharacterSnapshot, command, store, slots: list[str] | None = None, max_searches: int = 15,
                   defense: float = 300.0, pause: float = 0.3) -> dict:
    catalog, b = SetCatalog.load(), BossProfile("기준", defense)
    setting = rank_settings(snap, b, catalog)[0][0]
    rm = roadmap(snap, setting, b, catalog)
    if not slots:  # 가격 대비 순위 상위 부위부터
        slots = list(dict.fromkeys(v["slot"] for v in value_ranking(rm) if rm[v["slot"]]["route"] == "경매장"))
    plan = _plan(snap, rm, slots)[:max(0, max_searches)]
    searched, recorded, remaining, errors = 0, 0, None, []
    with McpStdioClient(command) as client:
        for n, (slot, tool, args, desc) in enumerate(plan):
            r = client.call(tool, args)
            searched += 1
            if isinstance(r, str):
                if n == 0:
                    raise McpUnavailable(r)
                errors.append(f"{desc}: {r[:120]}")
                continue
            remaining = r.get("searchRemaining", remaining)
            cat = _part(slot)
            for item in r.get("items") or []:
                recorded += store.record(to_observed(item, cat, cat))
            if pause and n + 1 < len(plan):
                time.sleep(pause)
    return {"searched": searched, "recorded": recorded, "search_remaining": remaining, "errors": errors,
            "plan": [d for *_, d in plan]}

