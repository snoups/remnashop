import asyncio
import os
import shutil
from dataclasses import dataclass
from typing import Final, Optional

_CPU_SAMPLE_S: Final[float] = 0.2
_IDLE_FIELDS: Final[tuple[int, int]] = (3, 4)  # idle, iowait in /proc/stat's cpu line


@dataclass(frozen=True, kw_only=True)
class HostLoad:
    load_1: float
    load_5: float
    load_15: float
    cpu_count: int


@dataclass(frozen=True, kw_only=True)
class HostDisk:
    total_bytes: int
    used_bytes: int


def read_host_load() -> Optional[HostLoad]:
    try:
        load_1, load_5, load_15 = os.getloadavg()
    except OSError:
        return None
    return HostLoad(load_1=load_1, load_5=load_5, load_15=load_15, cpu_count=os.cpu_count() or 1)


def read_host_disk(path: str = "/") -> Optional[HostDisk]:
    try:
        usage = shutil.disk_usage(path)
    except OSError:
        return None
    return HostDisk(total_bytes=usage.total, used_bytes=usage.used)


def parse_cpu_times(line: str) -> Optional[tuple[int, int]]:
    parts = line.split()
    if not parts or parts[0] != "cpu":
        return None
    values = [int(value) for value in parts[1:9]]
    idle = sum(values[index] for index in _IDLE_FIELDS if index < len(values))
    return sum(values), idle


def _read_cpu_times() -> Optional[tuple[int, int]]:
    try:
        with open("/proc/stat") as f:
            return parse_cpu_times(f.readline())
    except OSError:
        return None


async def read_host_cpu_percent() -> Optional[float]:
    # two /proc/stat reads a moment apart: Linux only, None elsewhere
    first = _read_cpu_times()
    if first is None:
        return None
    await asyncio.sleep(_CPU_SAMPLE_S)
    second = _read_cpu_times()
    if second is None:
        return None
    total = second[0] - first[0]
    idle = second[1] - first[1]
    return round(100 * (1 - idle / total), 1) if total > 0 else None
