"""Lumitrade custom exception hierarchy."""


class LumitradeError(Exception):
    """Base exception for all Lumitrade errors."""


class DataValidationError(LumitradeError):
    """Raised when market data fails validation."""


class AIValidationError(LumitradeError):
    """Raised when AI output fails validation."""


class RiskRejectionError(LumitradeError):
    """Raised when a signal is rejected by risk engine."""


class ExecutionError(LumitradeError):
    """Raised when order execution fails."""


class CircuitBreakerOpenError(LumitradeError):
    """Raised when circuit breaker is OPEN."""


class OrderExpiredError(ExecutionError):
    """Raised when an ApprovedOrder has expired."""


class ReconciliationError(LumitradeError):
    """Raised when position reconciliation finds discrepancies."""


class LockAcquisitionError(LumitradeError):
    """Raised when distributed lock cannot be acquired."""
