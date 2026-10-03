"""내 운 분석: 확률 정보 조회 기록(잠재 재설정·큐브)의 실제 지출과 운 백분위 (스펙 §6)."""
from dataclasses import dataclass

from engine.enhance.cube import Predicate, reset_cost
from engine.options import parse_option

MESO_RESET = "잠재능력 재설정"


@dataclass(frozen=True)
class CubeAttempt:
    kind: str          # "잠재능력 재설정" | 캐시 큐브 이름
    item: str
    part: str
    level: int
    grade: str         # 시도 당시 잠재 등급
    after: list[str]   # 결과 옵션 문자열 3줄
    date: str          # ISO 시각


@dataclass(frozen=True)
class Spent:
    meso: int
    counted: int    # 메소 가격을 아는 기록 수
    uncounted: int  # 캐시 큐브 등 가격을 모르는 기록 수


@dataclass(frozen=True)
class Luck:
    tries: int
    achieved: bool
    percentile: float  # 달성: 그 횟수 안에 달성할 확률(낮을수록 운 좋음) / 미달성: 그만큼 연속 실패할 확률(낮을수록 운 나쁨)


def meso_spent(attempts: list[CubeAttempt]) -> Spent:
    meso = counted = uncounted = 0
    for a in attempts:
        if a.kind == MESO_RESET:
            meso += reset_cost(a.level, a.grade)
            counted += 1
        else:
            uncounted += 1
    return Spent(meso, counted, uncounted)


def luck(attempts: list[CubeAttempt], item: str, predicate: Predicate, p: float) -> Luck:
    """그 아이템의 재설정 기록을 시간순으로 보고 목표가 처음 뜬 시도를 찾는다."""
    tries = 0
    for a in sorted((x for x in attempts if x.item == item and x.kind == MESO_RESET), key=lambda x: x.date):
        tries += 1
        options = [tuple(parse_option(t, a.level) or ()) for t in a.after]
        if predicate(options):
            return Luck(tries, True, 1 - (1 - p) ** tries)
    if tries == 0:
        raise ValueError(f"{item}의 재설정 기록이 없습니다")
    return Luck(tries, False, (1 - p) ** tries)
