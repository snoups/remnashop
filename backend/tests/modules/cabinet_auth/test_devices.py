from typing import Optional

import pytest
from redis.asyncio import Redis

from app.core.constants import REDIS_KEY_PREFIX
from app.core.utils.http import describe_user_agent, device_bucket
from app.modules.cabinet_auth.devices import KnownDevices

_CHROME = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
_FIREFOX = "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"


@pytest.fixture
def known_devices(redis: Redis) -> KnownDevices:
    return KnownDevices(redis)


async def test_first_device_is_silent_then_new_ones_notify(known_devices: KnownDevices) -> None:
    assert await known_devices.remember(1, "203.0.113.10", _CHROME) is False
    assert await known_devices.remember(1, "203.0.200.99", _CHROME) is False
    assert await known_devices.remember(1, "198.51.100.5", _CHROME) is True
    assert await known_devices.remember(1, "198.51.100.5", _FIREFOX) is True
    assert await known_devices.remember(1, "198.51.100.5", _FIREFOX) is False


async def test_browser_version_bump_is_silent(known_devices: KnownDevices) -> None:
    await known_devices.remember(3, "203.0.113.10", _CHROME)
    assert await known_devices.remember(3, "203.0.113.10", _CHROME.replace("126", "127")) is False


async def test_ipv6_within_same_48_is_silent(known_devices: KnownDevices) -> None:
    await known_devices.remember(4, "2001:db8:1:2::1", _CHROME)
    assert await known_devices.remember(4, "2001:db8:1:ffff::9", _CHROME) is False
    assert await known_devices.remember(4, "2001:db8:2::1", _CHROME) is True


async def test_keeps_twenty_latest(known_devices: KnownDevices, redis: Redis) -> None:
    for n in range(25):
        await known_devices.remember(2, f"10.{n}.0.1", "UA")
    assert await redis.zcard(f"{REDIS_KEY_PREFIX}cabinet:devices:2") == 20


def test_device_bucket() -> None:
    assert device_bucket("203.0.113.77") == "203.0.0.0/16"
    assert device_bucket("2001:db8:1:2:3::1") == "2001:db8:1::/48"
    assert device_bucket("garbage") == "garbage"


@pytest.mark.parametrize(
    ("agent", "expected"),
    [
        (_CHROME, "Chrome on Windows"),
        (_FIREFOX, "Firefox on Linux"),
        (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
            "Safari on iOS",
        ),
        (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0",
            "Edge on Windows",
        ),
        (
            "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Mobile Safari/537.36 Telegram-Android/10.14",
            "Telegram on Android",
        ),
        (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) Version/17.5 Safari/605.1.15",
            "Safari on macOS",
        ),
        ("curl/8.0", "Unknown browser"),
        (None, "Unknown browser"),
    ],
)
def test_describe_user_agent(agent: Optional[str], expected: str) -> None:
    assert describe_user_agent(agent) == expected
