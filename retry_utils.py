"""
API Retry Utilities
=====================
Exponential backoff retry logic for resilient API calls.
Includes circuit breaker pattern for degraded services.
"""

import time
import requests
import functools
import logging
from typing import Callable, Any, Optional, Tuple

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """
    Circuit breaker to prevent hammering failed APIs.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Requests fail immediately (API is down)
    - HALF_OPEN: Test with single request after cooldown
    """
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(self, failure_threshold: int = 3, reset_timeout: float = 60.0):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.failure_count = 0
        self.state = self.CLOSED
        self.last_failure_time = 0

    def can_execute(self) -> bool:
        if self.state == self.CLOSED:
            return True
        if self.state == self.OPEN:
            if time.time() - self.last_failure_time >= self.reset_timeout:
                self.state = self.HALF_OPEN
                return True
            return False
        return True  # HALF_OPEN — allow one test request

    def record_success(self):
        self.failure_count = 0
        self.state = self.CLOSED

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = self.OPEN


# Shared circuit breakers for each API
_circuit_breakers = {
    "azure_pricing": CircuitBreaker(failure_threshold=3, reset_timeout=120),
    "aws_pricing": CircuitBreaker(failure_threshold=3, reset_timeout=120),
    "anthropic": CircuitBreaker(failure_threshold=2, reset_timeout=300),
    "currency": CircuitBreaker(failure_threshold=3, reset_timeout=600),
}


def get_circuit_breaker(name: str) -> CircuitBreaker:
    """Get or create a circuit breaker by name."""
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker()
    return _circuit_breakers[name]


def retry_with_backoff(
    func: Callable,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    backoff_factor: float = 2.0,
    circuit_breaker_name: Optional[str] = None,
    on_retry: Optional[Callable] = None,
) -> Any:
    """
    Execute function with exponential backoff retry.

    Args:
        func: Function to execute (should raise on failure)
        max_retries: Maximum retry attempts
        base_delay: Initial delay between retries (seconds)
        max_delay: Maximum delay cap (seconds)
        backoff_factor: Multiplier for each retry delay
        circuit_breaker_name: Circuit breaker to use
        on_retry: Callback on retry (receives attempt number, exception)

    Returns:
        Function result on success

    Raises:
        Last exception if all retries exhausted
    """
    cb = get_circuit_breaker(circuit_breaker_name) if circuit_breaker_name else None

    if cb and not cb.can_execute():
        raise ConnectionError(f"Circuit breaker OPEN for {circuit_breaker_name} — API temporarily unavailable")

    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            result = func()
            if cb:
                cb.record_success()
            return result
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.HTTPError) as e:
            last_exception = e
            if cb:
                cb.record_failure()
            if attempt < max_retries:
                delay = min(base_delay * (backoff_factor ** attempt), max_delay)
                if on_retry:
                    on_retry(attempt + 1, e)
                logger.warning(f"Retry {attempt + 1}/{max_retries} after {delay:.1f}s: {e}")
                time.sleep(delay)
        except Exception as e:
            last_exception = e
            if cb:
                cb.record_failure()
            break  # Non-retryable error

    raise last_exception


def resilient_request(
    url: str,
    method: str = "GET",
    params: Optional[dict] = None,
    timeout: float = 12,
    max_retries: int = 3,
    circuit_breaker_name: Optional[str] = None,
    **kwargs,
) -> requests.Response:
    """
    Make an HTTP request with retry logic and circuit breaker.

    Args:
        url: Request URL
        method: HTTP method
        params: Query parameters
        timeout: Request timeout
        max_retries: Maximum retries
        circuit_breaker_name: Circuit breaker name

    Returns:
        requests.Response on success
    """
    def _make_request():
        resp = requests.request(method, url, params=params, timeout=timeout, **kwargs)
        resp.raise_for_status()
        return resp

    return retry_with_backoff(
        _make_request,
        max_retries=max_retries,
        circuit_breaker_name=circuit_breaker_name,
    )


def get_circuit_breaker_status() -> dict:
    """Get status of all circuit breakers (for UI display)."""
    status = {}
    for name, cb in _circuit_breakers.items():
        status[name] = {
            "state": cb.state,
            "failures": cb.failure_count,
            "threshold": cb.failure_threshold,
            "is_available": cb.can_execute(),
        }
    return status
