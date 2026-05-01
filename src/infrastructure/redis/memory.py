from __future__ import annotations

import fnmatch
import time
from collections import defaultdict
from collections.abc import AsyncIterator
from typing import Any


class InMemoryRedis:
    def __init__(self) -> None:
        self._values: dict[str, Any] = {}
        self._sets: dict[str, set[str]] = defaultdict(set)
        self._expires: dict[str, float] = {}

    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        self._values.clear()
        self._sets.clear()
        self._expires.clear()

    async def aclose(self) -> None:
        await self.close()

    def _normalize(self, key: Any) -> str:
        if isinstance(key, bytes):
            return key.decode()
        return str(key)

    def _is_expired(self, key: str) -> bool:
        expires_at = self._expires.get(key)
        if expires_at is None or expires_at > time.monotonic():
            return False

        self._values.pop(key, None)
        self._sets.pop(key, None)
        self._expires.pop(key, None)
        return True

    def _purge_expired(self) -> None:
        for key in list(self._expires):
            self._is_expired(key)

    async def get(self, name: Any) -> Any:
        key = self._normalize(name)
        if self._is_expired(key):
            return None
        return self._values.get(key)

    async def set(self, name: Any, value: Any, ex: int | None = None, **_: Any) -> bool:
        key = self._normalize(name)
        self._values[key] = value
        if ex is not None:
            self._expires[key] = time.monotonic() + ex
        else:
            self._expires.pop(key, None)
        return True

    async def setex(self, name: Any, time: int, value: Any) -> bool:
        return await self.set(name=name, value=value, ex=time)

    async def delete(self, *names: Any) -> int:
        deleted = 0
        for name in names:
            key = self._normalize(name)
            existed = key in self._values or key in self._sets
            self._values.pop(key, None)
            self._sets.pop(key, None)
            self._expires.pop(key, None)
            deleted += int(existed)
        return deleted

    async def exists(self, *names: Any) -> int:
        count = 0
        for name in names:
            key = self._normalize(name)
            if not self._is_expired(key) and (key in self._values or key in self._sets):
                count += 1
        return count

    async def keys(self, pattern: Any = "*") -> list[str]:
        self._purge_expired()
        raw_pattern = self._normalize(pattern)
        names = set(self._values) | set(self._sets)
        return [key for key in names if fnmatch.fnmatch(key, raw_pattern)]

    async def scan_iter(self, match: Any = "*", **_: Any) -> AsyncIterator[str]:
        for key in await self.keys(match):
            yield key

    async def sadd(self, name: Any, *values: Any) -> int:
        key = self._normalize(name)
        before = len(self._sets[key])
        self._sets[key].update(self._normalize(value) for value in values)
        return len(self._sets[key]) - before

    async def sismember(self, name: Any, value: Any) -> int:
        key = self._normalize(name)
        if self._is_expired(key):
            return 0
        return int(self._normalize(value) in self._sets.get(key, set()))

    async def smembers(self, name: Any) -> set[str]:
        key = self._normalize(name)
        if self._is_expired(key):
            return set()
        return set(self._sets.get(key, set()))
