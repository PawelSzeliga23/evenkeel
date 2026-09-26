from app.auth.rate_limit import RateLimiter


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_allows_up_to_limit_then_blocks() -> None:
    limiter = RateLimiter(3, window_seconds=60, clock=FakeClock())

    assert [limiter.hit("1.2.3.4") for _ in range(4)] == [True, True, True, False]


def test_window_slides() -> None:
    clock = FakeClock()
    limiter = RateLimiter(2, window_seconds=60, clock=clock)
    limiter.hit("ip")
    clock.now = 30
    limiter.hit("ip")
    assert limiter.hit("ip") is False

    clock.now = 60  # first hit left the window
    assert limiter.hit("ip") is True
    assert limiter.hit("ip") is False


def test_keys_are_independent() -> None:
    limiter = RateLimiter(1, window_seconds=60, clock=FakeClock())

    assert limiter.hit("a") is True
    assert limiter.hit("b") is True
    assert limiter.hit("a") is False


def test_idle_key_is_evicted_after_window_passes() -> None:
    clock = FakeClock()
    limiter = RateLimiter(2, window_seconds=60, clock=clock)

    limiter.hit("ip")
    clock.now = 60
    limiter.hit("other")

    assert "ip" not in limiter._hits
