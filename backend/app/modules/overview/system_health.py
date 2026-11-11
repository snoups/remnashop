from dataclasses import dataclass
from typing import Final, Optional

from redis.asyncio import Redis

from app.core.host_metrics import read_host_disk
from app.core.runtime_heartbeat import read_host_memory, read_runtime_heartbeats
from app.modules.overview.dto import AttentionKind

WATCHED_PROCESSES: Final[tuple[str, ...]] = ("worker", "scheduler")
DISK_CRITICAL_PERCENT: Final[int] = 90
MEMORY_CRITICAL_PERCENT: Final[int] = 95
EVENT_LOOP_LAG_MS: Final[int] = 500


@dataclass(frozen=True, kw_only=True)
class HealthProblem:
    kind: AttentionKind
    # process name for process_down and event_loop_lag
    subject: Optional[str] = None
    # percent for the host, p99 in ms for the event loop
    value: Optional[int] = None

    @property
    def key(self) -> str:
        return f"{self.kind.value}:{self.subject or ''}"


def _percent(used: int, total: int) -> int:
    return round(100 * used / total) if total > 0 else 0


async def read_health_problems(redis: Redis) -> list[HealthProblem]:
    heartbeats = await read_runtime_heartbeats(redis)
    alive = {hb.process for hb in heartbeats}
    problems = [
        HealthProblem(kind=AttentionKind.PROCESS_DOWN, subject=process)
        for process in WATCHED_PROCESSES
        if process not in alive
    ]
    disk = read_host_disk("/")
    if disk is not None and (percent := _percent(disk.used_bytes, disk.total_bytes)) >= (
        DISK_CRITICAL_PERCENT
    ):
        problems.append(HealthProblem(kind=AttentionKind.HOST_DISK_FULL, value=percent))
    memory = read_host_memory()
    if memory is not None and (percent := _percent(memory.used_bytes, memory.total_bytes)) >= (
        MEMORY_CRITICAL_PERCENT
    ):
        problems.append(HealthProblem(kind=AttentionKind.HOST_MEMORY_HIGH, value=percent))
    # one item per role: the worst of its processes
    worst: dict[str, float] = {}
    for hb in heartbeats:
        worst[hb.process] = max(worst.get(hb.process, 0.0), hb.event_loop_p99_ms)
    problems += [
        HealthProblem(kind=AttentionKind.EVENT_LOOP_LAG, subject=process, value=round(p99))
        for process, p99 in worst.items()
        if p99 >= EVENT_LOOP_LAG_MS
    ]
    return problems


# consecutive one-minute checks before an admin is told: a deploy restart or a
# short spike must not page anyone
ALERT_AFTER_CHECKS: Final[dict[AttentionKind, int]] = {
    AttentionKind.PROCESS_DOWN: 2,
    AttentionKind.HOST_DISK_FULL: 1,
    AttentionKind.HOST_MEMORY_HIGH: 5,
    AttentionKind.EVENT_LOOP_LAG: 5,
}
RESTORE_AFTER_CHECKS: Final[int] = 3


@dataclass(frozen=True, kw_only=True)
class HealthState:
    # problem key -> bad checks in a row, before the alert
    streaks: dict[str, int]
    # alerted problem key -> good checks in a row since
    alerted: dict[str, int]


@dataclass(frozen=True, kw_only=True)
class HealthTransition:
    state: HealthState
    degraded: list[HealthProblem]
    restored: list[str]


def advance(state: HealthState, problems: list[HealthProblem]) -> HealthTransition:
    current = {p.key: p for p in problems}
    streaks = {k: state.streaks.get(k, 0) + 1 for k in current if k not in state.alerted}
    degraded = [p for k, p in current.items() if streaks.get(k, 0) >= ALERT_AFTER_CHECKS[p.kind]]
    alerted: dict[str, int] = {}
    restored: list[str] = []
    for key, good in state.alerted.items():
        if key in current:
            alerted[key] = 0
        elif good + 1 >= RESTORE_AFTER_CHECKS:
            restored.append(key)
        else:
            alerted[key] = good + 1
    for p in degraded:
        streaks.pop(p.key)
        alerted[p.key] = 0
    return HealthTransition(
        state=HealthState(streaks=streaks, alerted=alerted), degraded=degraded, restored=restored
    )
