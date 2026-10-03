"""IP별 슬라이딩 윈도 호출 제한 (프로세스 메모리, 단일 VM 전제)."""
import collections
from collections.abc import Callable


class SlidingWindow:
    def __init__(self, limit: int, window: float, clock: Callable[[], float]):
        self.limit, self.window, self._clock = limit, window, clock
        self._hits: dict[str, collections.deque] = collections.defaultdict(collections.deque)

    def allow(self, key: str) -> bool:
        now = self._clock()
        q = self._hits[key]
        while q and now - q[0] >= self.window:
            q.popleft()
        if len(q) >= self.limit:
            return False
        q.append(now)
        return True
