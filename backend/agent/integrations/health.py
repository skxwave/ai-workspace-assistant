import asyncio
import logging
from dataclasses import dataclass
from time import monotonic

from .base import IntegrationProvider

logger = logging.getLogger(__name__)


@dataclass
class _Breaker:
    failures: int = 0
    opened_at: float | None = None


class IntegrationHealth:
    """Per-integration circuit breaker and upstream concurrency limiter.

    State is process-local: a breaker reflects what this worker can reach, and
    each worker recovers independently on its own half-open probe.
    """

    def __init__(self, *, failure_threshold: int, cooldown_seconds: float) -> None:
        self._failure_threshold = failure_threshold
        self._cooldown_seconds = cooldown_seconds
        self._breakers: dict[str, _Breaker] = {}
        self._limiters: dict[str, asyncio.Semaphore] = {}

    def is_available(self, name: str) -> bool:
        breaker = self._breakers.get(name)
        if breaker is None or breaker.opened_at is None:
            return True
        if monotonic() - breaker.opened_at >= self._cooldown_seconds:
            breaker.opened_at = None
            breaker.failures = 0
            logger.info("Circuit for %s entering half-open probe", name)
            return True
        return False

    def record_success(self, name: str) -> None:
        self._breakers.pop(name, None)

    def record_failure(self, name: str) -> None:
        breaker = self._breakers.setdefault(name, _Breaker())
        breaker.failures += 1
        if breaker.failures >= self._failure_threshold and breaker.opened_at is None:
            breaker.opened_at = monotonic()
            logger.warning(
                "Circuit for %s opened after %d consecutive failures",
                name,
                breaker.failures,
            )

    def limiter(self, provider: IntegrationProvider) -> asyncio.Semaphore:
        limiter = self._limiters.get(provider.name)
        if limiter is None:
            limiter = asyncio.Semaphore(provider.max_concurrency)
            self._limiters[provider.name] = limiter
        return limiter
