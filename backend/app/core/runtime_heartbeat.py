import asyncio
import contextlib
import json
import os
import resource
import socket
import statistics
import sys
import time
from dataclasses import dataclass
from typing import Final, Optional

from loguru import logger
from redis.asyncio import Redis

from app.core.constants import REDIS_KEY_PREFIX

RUNTIME_PROCESSES: Final[tuple[str, ...]] = ("api", "telegram", "worker", "scheduler")
RUNTIME_HEARTBEAT_INTERVAL_S: Final[float] = 15.0
RUNTIME_HEARTBEAT_TTL_S: Final[int] = 45
EVENT_LOOP_SAMPLE_INTERVAL_S: Final[float] = 0.01


@dataclass(frozen=True, kw_only=True)
class RuntimeHeartbeat:
    process: str
    # APP_INSTANCE_NAME of the container, when set
    instance: Optional[str]
    pid: int
    started_at: float
    rss_bytes: int
    event_loop_delay_ms: float
    event_loop_p99_ms: float


@dataclass(frozen=True, kw_only=True)
class HostMemory:
    total_bytes: int
    used_bytes: int


def read_host_memory() -> Optional[HostMemory]:
    # /proc/meminfo is Linux-only; in a container it shows the host/VM kernel's
    # memory (not cgroup-scoped), which is what the card wants
    try:
        with open("/proc/meminfo") as f:
            values: dict[str, int] = {}
            for line in f:
                key, _, rest = line.partition(":")
                if key in ("MemTotal", "MemAvailable"):
                    values[key] = int(rest.split()[0]) * 1024  # kB -> bytes
    except OSError:
        return None
    if "MemTotal" not in values or "MemAvailable" not in values:
        return None
    return HostMemory(
        total_bytes=values["MemTotal"],
        used_bytes=values["MemTotal"] - values["MemAvailable"],
    )


_KEY_PREFIX: Final[str] = f"{REDIS_KEY_PREFIX}runtime:heartbeat:"


def _heartbeat_key(process: str, pid: int) -> str:
    # one key per process: a role may run in several containers (a second api)
    # and several processes (WORKER_PROCESSES, APP_WORKERS)
    return f"{_KEY_PREFIX}{process}:{socket.gethostname()}:{pid}"


def _current_rss_bytes() -> int:
    # ru_maxrss is KB on Linux, bytes on Darwin; peak, not current, but close
    # enough for a dashboard card
    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return raw if sys.platform == "darwin" else raw * 1024


async def publish_runtime_heartbeat(
    redis: Redis,
    process: str,
    *,
    pid: int,
    started_at: float,
    instance: Optional[str] = None,
    event_loop_delay_ms: float = 0.0,
    event_loop_p99_ms: float = 0.0,
) -> None:
    payload = {
        "instance": instance,
        "pid": pid,
        "started_at": started_at,
        "rss_bytes": _current_rss_bytes(),
        "event_loop_delay_ms": event_loop_delay_ms,
        "event_loop_p99_ms": event_loop_p99_ms,
    }
    await redis.set(_heartbeat_key(process, pid), json.dumps(payload), ex=RUNTIME_HEARTBEAT_TTL_S)


async def read_runtime_heartbeats(redis: Redis) -> list[RuntimeHeartbeat]:
    heartbeats = []
    async for key in redis.scan_iter(match=f"{_KEY_PREFIX}*", count=100):
        process = key.removeprefix(_KEY_PREFIX).split(":", 1)[0]
        raw = await redis.get(key)
        if process not in RUNTIME_PROCESSES or raw is None:
            continue
        data = json.loads(raw)
        heartbeats.append(
            RuntimeHeartbeat(
                process=process,
                instance=data.get("instance"),
                pid=data["pid"],
                started_at=data["started_at"],
                rss_bytes=data["rss_bytes"],
                # a heartbeat from an older process (mid-rollout) lacks these
                event_loop_delay_ms=data.get("event_loop_delay_ms", 0.0),
                event_loop_p99_ms=data.get("event_loop_p99_ms", 0.0),
            )
        )
    return sorted(heartbeats, key=lambda hb: (hb.instance or "", hb.started_at))


async def _sample_event_loop_delay(samples: list[float]) -> None:
    loop = asyncio.get_running_loop()
    while True:
        start = loop.time()
        await asyncio.sleep(EVENT_LOOP_SAMPLE_INTERVAL_S)
        samples.append(max(0.0, loop.time() - start - EVENT_LOOP_SAMPLE_INTERVAL_S))


def _event_loop_stats_ms(samples: list[float]) -> tuple[float, float]:
    if not samples:
        return 0.0, 0.0
    samples_ms = [s * 1000 for s in samples]
    samples.clear()
    mean_ms = statistics.mean(samples_ms)
    p99_ms = (
        statistics.quantiles(samples_ms, n=100, method="inclusive")[-1]
        if len(samples_ms) >= 2
        else samples_ms[0]
    )
    return mean_ms, p99_ms


async def poll_runtime_heartbeat(
    redis: Redis, process: str, instance: Optional[str] = None
) -> None:
    pid = os.getpid()
    started_at = time.time()
    samples: list[float] = []
    sampler_task = asyncio.create_task(_sample_event_loop_delay(samples))
    try:
        while True:
            try:
                delay_ms, p99_ms = _event_loop_stats_ms(samples)
                await publish_runtime_heartbeat(
                    redis,
                    process,
                    pid=pid,
                    started_at=started_at,
                    instance=instance,
                    event_loop_delay_ms=delay_ms,
                    event_loop_p99_ms=p99_ms,
                )
            except Exception:  # a transient Redis blip must not kill the poller
                logger.warning(f"Failed to publish runtime heartbeat for '{process}'")
            await asyncio.sleep(RUNTIME_HEARTBEAT_INTERVAL_S)
    finally:
        sampler_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await sampler_task
        # a restart starts a new pid: without this the old one lingers on the
        # dashboard until its key expires
        with contextlib.suppress(Exception):
            await redis.delete(_heartbeat_key(process, pid))
