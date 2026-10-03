"""분포 요약: 평균·중앙값·p75·p90 (꼬리가 긴 비용 분포라 평균만 보여주지 않는다)."""
import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Distribution:
    mean: float
    median: float
    p75: float
    p90: float

    @classmethod
    def from_samples(cls, samples: list[float]) -> "Distribution":
        s = sorted(samples)
        n = len(s)

        def q(p: float) -> float:  # 최근접 순위 백분위
            return s[max(0, math.ceil(p * n) - 1)]

        return cls(sum(s) / n, q(0.5), q(0.75), q(0.9))
