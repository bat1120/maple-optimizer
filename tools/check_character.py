"""실제 API로 캐릭터를 불러와 엔진 스탯공격력과 API 값을 비교한다.

사용: uv run python tools/check_character.py <닉네임> [YYYY-MM-DD]
"""
import datetime as dt
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from engine.stats.formula import stat_attack_max  # noqa: E402
from engine.stats.jobs import UnsupportedJob, job_profile  # noqa: E402
from engine.stats.weapons import UnknownWeapon  # noqa: E402
from nexon.client import NexonClient, NexonError, load_api_key  # noqa: E402
from nexon.convert import snapshot  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    day = dt.date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else None
    client = NexonClient(load_api_key(ROOT))
    try:
        bundle = client.fetch_bundle(sys.argv[1], day)
    except NexonError as e:
        print(f"넥슨 API 오류: {e}")
        return 1
    if any(v is None for v in bundle.values()):
        print("해당 날짜 데이터가 없습니다:", [k for k, v in bundle.items() if v is None])
        return 1
    s = snapshot(bundle)
    weapon = s.equipment_presets[s.active_equipment_preset]["무기"].part
    print(f"{s.character_class} Lv.{s.level}  기준: {s.date or '현재'}")
    print(f"프리셋 — 장비 {s.active_equipment_preset}, 하이퍼 {s.active_hyper_preset}, 어빌리티 {s.active_ability_preset}")
    try:
        got = stat_attack_max(s.final, job_profile(s.character_class), weapon)
    except (UnsupportedJob, UnknownWeapon) as e:
        print("계산 제외:", e)
        return 1
    api = s.final.stat_attack_max
    print(f"스탯공격력  엔진 {got:,.0f}  API {api:,}  오차 {abs(got - api) / api:.5%}")
    print(f"전투력(참고, API 기록값) {s.final.combat_power:,}")
    if s.excluded:
        print("계산 제외 옵션:", sorted(set(s.excluded)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
