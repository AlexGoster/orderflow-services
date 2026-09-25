"""Circuit breaker для вызовов catalog-service.

В tenacity 9.x встроенного CB больше нет, поэтому контур — своя небольшая
state-машина: closed -> open -> half_open -> closed.
"""

import time
from dataclasses import dataclass, field
from enum import StrEnum


class CircuitState(StrEnum):
    closed = "closed"
    open = "open"
    half_open = "half_open"


class CircuitOpenError(Exception):
    """Контур разомкнут: вызов делать нельзя, нужен фолбэк."""


@dataclass
class CircuitBreaker:
    failure_threshold: int = 3
    recovery_timeout: float = 30.0
    _state: CircuitState = field(default=CircuitState.closed, init=False, repr=False)
    _failures: int = field(default=0, init=False, repr=False)
    _opened_at: float | None = field(default=None, init=False, repr=False)

    @property
    def state(self) -> CircuitState:
        """Текущее состояние; открытый контур уходит в half_open после паузы."""
        if self._state is CircuitState.open:
            opened_at = self._opened_at
            if opened_at is not None and time.monotonic() - opened_at >= self.recovery_timeout:
                self._state = CircuitState.half_open
        return self._state

    @property
    def failures(self) -> int:
        return self._failures

    def before_call(self) -> None:
        if self.state is CircuitState.open:
            raise CircuitOpenError("catalog circuit breaker is open")

    def record_success(self) -> None:
        self._state = CircuitState.closed
        self._failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        self._failures += 1
        if self.state is CircuitState.half_open or self._failures >= self.failure_threshold:
            self._state = CircuitState.open
            self._opened_at = time.monotonic()
