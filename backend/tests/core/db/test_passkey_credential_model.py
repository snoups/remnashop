from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models import PasskeyCredential, User
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale, Role


async def test_passkey_credential_persists_with_expected_columns(
    session: AsyncSession, uow: UnitOfWork
) -> None:
    async with uow:
        user = User(name="owner", role=Role.OWNER, language=Locale.EN, is_blocked=False)
        session.add(user)
        await session.flush()

        row = PasskeyCredential(
            user_id=user.id,
            credential_id="abc123",
            public_key=b"public-key-bytes",
            sign_count=0,
            transports=["internal", "hybrid"],
            device_type="single_device",
            backed_up=False,
            name="My laptop",
        )
        session.add(row)
        await uow.commit()

    fetched = await session.scalar(
        select(PasskeyCredential).where(PasskeyCredential.credential_id == "abc123")
    )
    assert fetched is not None
    assert fetched.user_id == user.id
    assert fetched.public_key == b"public-key-bytes"
    assert fetched.transports == ["internal", "hybrid"]
    assert fetched.device_type == "single_device"
    assert fetched.backed_up is False
    assert fetched.name == "My laptop"
    assert fetched.last_used_at is None
    assert fetched.created_at is not None
