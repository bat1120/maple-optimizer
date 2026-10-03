"""테스트용 fixture 로더. 익명화된 실제 넥슨 응답을 직업명 디렉터리에서 읽는다."""
import json
import pathlib

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "characters"
PAIRS = pathlib.Path(__file__).parent / "fixtures" / "pairs"
WEAPONS = pathlib.Path(__file__).parent / "fixtures" / "weapons"
ENDPOINTS = (
    "character/basic",
    "character/stat",
    "character/item-equipment",
    "character/set-effect",
    "character/hyper-stat",
    "character/ability",
    "character/symbol-equipment",
    "user/union-raider",
)


def classes() -> list[str]:
    return sorted(p.name for p in FIXTURES.iterdir() if p.is_dir())


def load(cls: str, endpoint: str) -> dict:
    path = FIXTURES / cls / (endpoint.replace("/", "_") + ".json")
    return json.loads(path.read_text(encoding="utf-8"))


def bundle(cls: str) -> dict[str, dict]:
    return {ep: load(cls, ep) for ep in ENDPOINTS}


def pair_bundle(name: str) -> dict[str, dict]:
    """같은 캐릭터의 다른 세팅·시점 스냅샷 (예: "레테_boss")."""
    return {ep: json.loads((PAIRS / name / (ep.replace("/", "_") + ".json")).read_text(encoding="utf-8")) for ep in ENDPOINTS}


def weapon_samples() -> list[str]:
    """무기 상수 표본 디렉터리 이름 (예: "한손검_1")."""
    return sorted(p.name for p in WEAPONS.iterdir() if p.is_dir()) if WEAPONS.exists() else []


def weapon_bundle(name: str) -> dict[str, dict]:
    return {ep: json.loads((WEAPONS / name / (ep.replace("/", "_") + ".json")).read_text(encoding="utf-8")) for ep in ENDPOINTS}
