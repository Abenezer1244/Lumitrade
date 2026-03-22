"""
Lumitrade Circuit Breaker
===========================
Tracks OANDA API failures and trips to protect the account.
CLOSED -> OPEN (3 failures/60s) -> HALF_OPEN (30s) -> CLOSED (success).
Per BDS Section 7.1.
"""
import asyncio
from datetime import datetime, timezone
from ..core.enums import CircuitBreakerState
from ..infrastructure.secure_logger import get_logger

logger = get_logger(__name__)

FAILURE_THRESHOLD = 3
FAILURE_WINDOW_SEC = 60
RESET_TIMEOUT_SEC = 30


class CircuitBreaker:
    def __init__(self):
        self._state = CircuitBreakerState.CLOSED
        self._failures: list[datetime] = []
        self._opened_at: datetime | None = None
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitBreakerState:
        return self._state

    @property
    def is_open(self) -> bool:
        return self._state == CircuitBreakerState.OPEN

    async def record_success(self):
        async with self._lock:
            if self._state == CircuitBreakerState.HALF_OPEN:
                self._state = CircuitBreakerState.CLOSED
                self._failures = []
                self._opened_at = None
                logger.info("circuit_breaker_closed")

    async def record_failure(self):
        async with self._lock:
            now = datetime.now(timezone.utc)
            self._failures = [
                f for f in self._failures
                if (now - f).total_seconds() < FAILURE_WINDOW_SEC
            ]
            self._failures.append(now)
            if len(self._failures) >= FAILURE_THRESHOLD and self._state != CircuitBreakerState.OPEN:
                self._state = CircuitBreakerState.OPEN
                self._opened_at = now
                logger.error("circuit_breaker_tripped", failures=len(self._failures))

    async def check_and_transition(self) -> CircuitBreakerState:
        async with self._lock:
            if self._state == CircuitBreakerState.OPEN and self._opened_at:
                elapsed = (datetime.now(timezone.utc) - self._opened_at).total_seconds()
                if elapsed >= RESET_TIMEOUT_SEC:
                    self._state = CircuitBreakerState.HALF_OPEN
                    logger.info("circuit_breaker_half_open")
            return self._state
