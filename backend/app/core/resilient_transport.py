import asyncio
import random
import time
from typing import Final, Optional

import httpx

from app.core.exceptions import RemnawavePanelUnavailableError

# Two states (closed/open), no half-open: after the cooldown every caller that
# arrives before the first result probes, not just one. Remnawave traffic is a
# handful of calls at a time, so that costs nothing; add HALF_OPEN with a probe
# token if it ever gets heavy.
_FAILURE_THRESHOLD: Final[int] = 5
_RECOVERY_TIMEOUT_S: Final[float] = 30.0
_MAX_RETRY_ATTEMPTS: Final[int] = 3
_RETRY_BACKOFF_BASE_S: Final[float] = 0.2
_RETRY_JITTER_S: Final[float] = 0.1
_RETRYABLE_METHODS: Final[frozenset[str]] = frozenset({"GET"})


class ResilientTransport(httpx.AsyncBaseTransport):
    """Wraps another transport with a circuit breaker and retry-with-backoff
    for idempotent (GET) requests. A "failure" is a transport-level
    exception or an HTTP 5xx; a 4xx means the panel is responsive and
    rejecting this specific request, not unhealthy, so it doesn't count
    toward the breaker and is never retried. A request that never gets an answer
    raises RemnawavePanelUnavailableError (503)."""

    def __init__(self, wrapped: httpx.AsyncBaseTransport) -> None:
        self._wrapped = wrapped
        self._lock = asyncio.Lock()
        self._consecutive_failures = 0
        self._opened_at: Optional[float] = None

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        async with self._lock:
            if self._opened_at is not None and (
                time.monotonic() - self._opened_at < _RECOVERY_TIMEOUT_S
            ):
                raise RemnawavePanelUnavailableError("Remnawave panel circuit breaker is open")

        attempts = _MAX_RETRY_ATTEMPTS if request.method in _RETRYABLE_METHODS else 1
        last_error: Optional[httpx.HTTPError] = None

        for attempt in range(attempts):
            if attempt > 0:
                backoff = _RETRY_BACKOFF_BASE_S * (2 ** (attempt - 1))
                await asyncio.sleep(backoff + random.uniform(0, _RETRY_JITTER_S))
            try:
                response = await self._wrapped.handle_async_request(request)
            except httpx.HTTPError as error:
                last_error = error
                await self._record_failure()
                continue
            if response.status_code >= 500:
                await self._record_failure()
                if attempt < attempts - 1:
                    await response.aclose()  # discarded, release the connection
                    continue
                return response  # terminal attempt, the caller reads this one
            await self._record_success()
            return response

        assert last_error is not None  # every attempt raised; none returned above
        # a timeout or a dropped connection is the panel being down, like an open breaker
        raise RemnawavePanelUnavailableError(
            f"Remnawave panel unreachable: {type(last_error).__name__}"
        ) from last_error

    async def _record_failure(self) -> None:
        async with self._lock:
            self._consecutive_failures += 1
            if self._consecutive_failures >= _FAILURE_THRESHOLD:
                self._opened_at = time.monotonic()

    async def _record_success(self) -> None:
        async with self._lock:
            self._consecutive_failures = 0
            self._opened_at = None

    async def aclose(self) -> None:
        await self._wrapped.aclose()
