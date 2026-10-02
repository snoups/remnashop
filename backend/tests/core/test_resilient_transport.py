import asyncio

import httpx
import pytest

import app.core.resilient_transport as module
from app.core.exceptions import RemnawavePanelUnavailableError
from app.core.resilient_transport import (
    _FAILURE_THRESHOLD,
    _RECOVERY_TIMEOUT_S,
    ResilientTransport,
)


def _client(transport: httpx.AsyncBaseTransport) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=transport, base_url="http://panel.test")


async def test_successful_request_passes_through_unchanged() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    transport = ResilientTransport(httpx.MockTransport(handler))
    async with _client(transport) as client:
        response = await client.get("/users/1")

    assert response.status_code == 200
    assert response.json() == {"ok": True}


async def test_a_4xx_response_is_not_retried_and_does_not_count_as_a_failure() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(404, json={"message": "not found"})

    transport = ResilientTransport(httpx.MockTransport(handler))
    async with _client(transport) as client:
        response = await client.get("/users/999")

    assert response.status_code == 404
    assert calls == 1  # no retry -- a 4xx means the panel is responsive


async def test_a_get_request_retries_a_5xx_and_succeeds_on_the_second_attempt() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503)
        return httpx.Response(200, json={"ok": True})

    transport = ResilientTransport(httpx.MockTransport(handler))
    async with _client(transport) as client:
        response = await client.get("/users/1")

    assert response.status_code == 200
    assert calls == 2


async def test_a_post_request_is_never_retried() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503)

    transport = ResilientTransport(httpx.MockTransport(handler))
    async with _client(transport) as client:
        response = await client.post("/users", json={})

    assert response.status_code == 503
    assert calls == 1  # POST is not idempotent -- one attempt, no retry


async def test_circuit_opens_after_the_failure_threshold_and_fails_fast() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503)

    transport = ResilientTransport(httpx.MockTransport(handler))
    async with _client(transport) as client:
        # POSTs are never retried, so each call below is exactly one attempt --
        # _FAILURE_THRESHOLD consecutive POST failures opens the breaker.
        for _ in range(_FAILURE_THRESHOLD):
            await client.post("/users", json={})

        calls_before_open_check = calls
        with pytest.raises(RemnawavePanelUnavailableError):
            await client.post("/users", json={})

        # the breaker rejected the call before it ever reached the transport
        assert calls == calls_before_open_check


async def test_circuit_closes_again_after_the_recovery_timeout_on_a_successful_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_now = [1000.0]
    monkeypatch.setattr(module.time, "monotonic", lambda: fake_now[0])

    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200)

    transport = ResilientTransport(httpx.MockTransport(handler))
    # Force the breaker open directly rather than re-deriving it via failures --
    # this test is about the recovery half, not the opening half (already covered
    # by test_circuit_opens_after_the_failure_threshold_and_fails_fast).
    transport._consecutive_failures = _FAILURE_THRESHOLD
    transport._opened_at = fake_now[0]

    async with _client(transport) as client:
        with pytest.raises(RemnawavePanelUnavailableError):
            await client.get("/users/1")

        fake_now[0] += _RECOVERY_TIMEOUT_S + 1
        response = await client.get("/users/1")

    assert response.status_code == 200
    assert calls == 1


async def _always_503(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    """Minimal keep-alive HTTP/1.1 server: answers every request with a bodyless 503."""
    try:
        while True:
            data = await reader.read(65536)
            if not data:
                break
            writer.write(
                b"HTTP/1.1 503 Service Unavailable\r\n"
                b"Content-Length: 0\r\n"
                b"Connection: keep-alive\r\n"
                b"\r\n"
            )
            await writer.drain()
    except (ConnectionResetError, BrokenPipeError):
        pass
    finally:
        writer.close()


async def test_a_discarded_5xx_retry_response_releases_its_pooled_connection() -> None:
    # Regression for a leak that httpx.MockTransport (every other test in this
    # file) cannot see: MockTransport has no real connection pool, so a
    # forgotten `response.aclose()` on a discarded retry is invisible to it.
    # This uses a real httpcore-backed transport against a real local socket
    # so the pool bookkeeping is real too.
    server = await asyncio.start_server(_always_503, "127.0.0.1", 0)
    host, port = server.sockets[0].getsockname()[:2]

    async with server:
        real_transport = httpx.AsyncHTTPTransport(
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=10)
        )
        pool = real_transport._pool
        transport = ResilientTransport(real_transport)

        async with httpx.AsyncClient(
            transport=transport, base_url=f"http://{host}:{port}"
        ) as client:
            response = await client.get("/users/1")

            assert response.status_code == 503
            # _MAX_RETRY_ATTEMPTS attempts were made, all 503; only the
            # terminal one is a live connection still held by the response --
            # the other _MAX_RETRY_ATTEMPTS - 1 must have been released back
            # to the pool by an explicit aclose(), not leaked. Before the fix
            # this was `_MAX_RETRY_ATTEMPTS` (every discarded response leaked
            # its connection, and this assertion sees `client` before its own
            # teardown would otherwise close everything and mask the leak).
            assert len(pool._connections) == 1
