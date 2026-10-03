"""`.raw/<캐릭터명>/*.json`(수집 원본)을 익명화해 `tests/fixtures/characters/<직업>/`로,
`.raw-pairs/<이름>/`은 `tests/fixtures/pairs/<이름>/`로 복사한다.

직업명이 겹치면 멈춘다(fixture는 직업당 1명). `.raw/` 바로 아래의 파일(ranking.json 등)은 건너뛴다.
"""
import json
import pathlib
import shutil

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / ".raw"
OUT = ROOT / "tests" / "fixtures" / "characters"
RAW_PAIRS = ROOT / ".raw-pairs"
OUT_PAIRS = ROOT / "tests" / "fixtures" / "pairs"
DROP_KEYS = {"character_name", "character_guild_name", "character_image", "item_description"}


def scrub(o):
    if isinstance(o, dict):
        return {k: scrub(v) for k, v in o.items() if k not in DROP_KEYS and not k.endswith("_icon")}
    if isinstance(o, list):
        return [scrub(x) for x in o]
    return o


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    for d in sorted(p for p in RAW.iterdir() if p.is_dir()):
        basic = json.loads((d / "character_basic.json").read_text(encoding="utf-8"))
        dst = OUT / basic["character_class"]
        if dst.exists():
            raise SystemExit(f"직업 중복: {basic['character_class']}")
        dst.mkdir(parents=True)
        for f in sorted(d.glob("*.json")):
            data = scrub(json.loads(f.read_text(encoding="utf-8")))
            (dst / f.name).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        print(dst.name)
    # 짝 스냅샷(같은 캐릭터의 다른 세팅·시점): 디렉터리 이름을 그대로 쓴다.
    if OUT_PAIRS.exists():
        shutil.rmtree(OUT_PAIRS)
    for d in sorted(p for p in RAW_PAIRS.iterdir() if p.is_dir()) if RAW_PAIRS.exists() else []:
        dst = OUT_PAIRS / d.name
        dst.mkdir(parents=True)
        for f in sorted(d.glob("*.json")):
            data = scrub(json.loads(f.read_text(encoding="utf-8")))
            (dst / f.name).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        print("pair", d.name)


if __name__ == "__main__":
    main()
