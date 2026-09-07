import os
import time

import pytest

from app.core.runtime_heartbeat import (
    RUNTIME_PROCESSES,
    _event_loop_stats_ms,
    publish_runtime_heartbeat,
    read_host_memory,
    read_runtime_heartbeats,
)

_KEYS = (
    "remnashop:runtime:heartbeat:api",
    "remnashop:runtime:heartbeat:telegram",
    "remnashop:runtime:heartbeat:worker",
    "remnashop:runtime:heartbeat:scheduler",
)


def test_runtime_processes_covers_every_long_running_process() -> None:
    # docker-entrypoint.sh's four long-running targets: api, telegram,
    # worker, scheduler (cli is a one-shot break-glass command, not tracked).
    assert set(RUNTIME_PROCESSES) == {"api", "telegram", "worker", "scheduler"}


async def test_read_runtime_heartbeats_returns_a_published_heartbeat(redis) -> None:
    await redis.delete(*_KEYS)
    started_at = time.time() - 120

    await publish_runtime_heartbeat(redis, "api", pid=4242, started_at=started_at)
    heartbeats = await read_runtime_heartbeats(redis)

    api = next(hb for hb in heartbeats if hb.process == "api")
    assert api.pid == 4242
    assert api.started_at == started_at
    assert api.rss_bytes > 0

    await redis.delete(*_KEYS)


async def test_read_runtime_heartbeats_skips_processes_that_never_reported(redis) -> None:
    await redis.delete(*_KEYS)

    await publish_runtime_heartbeat(redis, "worker", pid=1, started_at=time.time())
    heartbeats = await read_runtime_heartbeats(redis)

    assert {hb.process for hb in heartbeats} == {"worker"}

    await redis.delete(*_KEYS)


async def test_publish_runtime_heartbeat_expires_on_its_own(redis) -> None:
    await redis.delete(*_KEYS)

    await publish_runtime_heartbeat(redis, "api", pid=1, started_at=time.time())
    ttl = await redis.ttl("remnashop:runtime:heartbeat:api")

    assert 0 < ttl <= 45

    await redis.delete(*_KEYS)


async def test_publish_runtime_heartbeat_defaults_event_loop_stats_to_zero(redis) -> None:
    await redis.delete(*_KEYS)

    await publish_runtime_heartbeat(redis, "api", pid=1, started_at=time.time())
    heartbeats = await read_runtime_heartbeats(redis)

    api = next(hb for hb in heartbeats if hb.process == "api")
    assert api.event_loop_delay_ms == 0.0
    assert api.event_loop_p99_ms == 0.0

    await redis.delete(*_KEYS)


async def test_read_runtime_heartbeats_roundtrips_event_loop_stats(redis) -> None:
    await redis.delete(*_KEYS)

    await publish_runtime_heartbeat(
        redis,
        "api",
        pid=1,
        started_at=time.time(),
        event_loop_delay_ms=2.5,
        event_loop_p99_ms=9.1,
    )
    heartbeats = await read_runtime_heartbeats(redis)

    api = next(hb for hb in heartbeats if hb.process == "api")
    assert api.event_loop_delay_ms == 2.5
    assert api.event_loop_p99_ms == 9.1

    await redis.delete(*_KEYS)


def test_event_loop_stats_ms_computes_mean_and_p99_then_clears_samples() -> None:
    samples = [0.001, 0.002, 0.001, 0.050]  # seconds

    mean_ms, p99_ms = _event_loop_stats_ms(samples)

    assert mean_ms == pytest.approx(13.5)
    assert p99_ms == pytest.approx(48.56, abs=0.5)
    assert samples == []


def test_event_loop_stats_ms_returns_zero_for_no_samples() -> None:
    assert _event_loop_stats_ms([]) == (0.0, 0.0)


def test_read_host_memory_returns_sane_values_or_none_off_linux() -> None:
    result = read_host_memory()

    if result is None:
        assert not os.path.exists("/proc/meminfo")
    else:
        assert result.total_bytes > 0
        assert 0 <= result.used_bytes <= result.total_bytes
