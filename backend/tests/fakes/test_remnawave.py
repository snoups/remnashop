from datetime import datetime, timedelta, timezone

from remnapy import RemnawaveSDK
from remnapy.models import CreateUserRequestDto, ExtendUserRequestDto, UpdateUserRequestDto


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
