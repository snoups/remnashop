from datetime import datetime, timedelta, timezone

import httpx
from remnapy import RemnawaveSDK
from remnapy.models import (
    CreateUserRequestDto,
    DeleteUserAllHwidDeviceRequestDto,
    DeleteUserHwidDeviceRequestDto,
    ExtendUserRequestDto,
    UpdateUserRequestDto,
)

from tests.fakes.remnawave import make_fake_remnawave_transport


def _sdk(transport: httpx.MockTransport) -> RemnawaveSDK:
    client = httpx.AsyncClient(transport=transport, base_url="https://fake-panel.test/api")
    return RemnawaveSDK(client=client)


async def test_fake_create_then_update_then_extend_user(remnawave_sdk: RemnawaveSDK) -> None:
    created = await remnawave_sdk.users.create_user(
        CreateUserRequestDto(
            username="rs_test_00000000",
            expire_at=datetime.now(timezone.utc) + timedelta(days=30),
            traffic_limit_bytes=100 * 1024**3,
        )
    )

    assert created.id > 0
    assert created.traffic_limit_bytes == 100 * 1024**3

    updated = await remnawave_sdk.users.update_user(
        UpdateUserRequestDto(id=created.id, traffic_limit_bytes=200 * 1024**3)
    )
    assert updated.traffic_limit_bytes == 200 * 1024**3

    before_extend = updated.expire_at
    extended = await remnawave_sdk.users.extend_user(created.id, ExtendUserRequestDto(days=10))
    assert extended.expire_at == before_extend + timedelta(days=10)


async def test_hwid_endpoints_and_revoke_round_trip() -> None:
    transport, users, devices = make_fake_remnawave_transport()
    sdk = _sdk(transport)

    created = await sdk.users.create_user(
        CreateUserRequestDto(
            username="hwid-test",
            expire_at=datetime.now(timezone.utc) + timedelta(days=1),
        )
    )
    devices[created.id] = [
        {
            "hwid": "hwid-1",
            "userId": created.id,
            "platform": "ios",
            "osVersion": None,
            "deviceModel": None,
            "userAgent": None,
            "requestIp": None,
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "updatedAt": datetime.now(timezone.utc).isoformat(),
        }
    ]

    listed = await sdk.hwid.get_hwid_user(created.id)
    assert len(listed.devices) == 1
    assert listed.devices[0].hwid == "hwid-1"

    await sdk.hwid.delete_hwid_to_user(
        DeleteUserHwidDeviceRequestDto(user_id=created.id, hwid="hwid-1")
    )
    assert devices[created.id] == []

    devices[created.id] = [
        {
            "hwid": "hwid-2",
            "userId": created.id,
            "platform": None,
            "osVersion": None,
            "deviceModel": None,
            "userAgent": None,
            "requestIp": None,
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "updatedAt": datetime.now(timezone.utc).isoformat(),
        }
    ]
    await sdk.hwid.delete_all_hwid_user(DeleteUserAllHwidDeviceRequestDto(user_id=created.id))
    assert devices[created.id] == []

    before_url = users[created.id]["subscriptionUrl"]
    revoked = await sdk.users.revoke_user_subscription(created.id)
    assert revoked.subscription_url != before_url
