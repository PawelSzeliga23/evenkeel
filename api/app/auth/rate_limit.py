import time
from collections import deque
from collections.abc import Callable


class RateLimiter:
    """Sliding-window limiter held in process memory; enough for a single API process."""

    def __init__(
        self, limit: int, window_seconds: float = 60.0, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}

    def _evict_stale(self, now: float) -> None:
        """Drop stale hits from every key, and drop keys left with no hits at all.

        Runs on every call so idle keys (e.g. IPs that hit once and never return)
        don't accumulate in memory forever.
        """
        empty_keys = []
        for tracked_key, hits in self._hits.items():
            while hits and now - hits[0] >= self.window_seconds:
                hits.popleft()
            if not hits:
                empty_keys.append(tracked_key)
        for tracked_key in empty_keys:
            del self._hits[tracked_key]

    def hit(self, key: str) -> bool:
        now = self._clock()
        self._evict_stale(now)
        hits = self._hits.get(key, deque())
        if len(hits) >= self.limit:
            return False
        hits.append(now)
        self._hits[key] = hits
        return True
