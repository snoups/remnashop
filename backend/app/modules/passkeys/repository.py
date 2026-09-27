from typing import Optional, cast

from sqlalchemy import CursorResult, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.passkey_credential import PasskeyCredential
from app.core.utils.time import datetime_now
from app.modules.passkeys.dto import CreatePasskeyCredentialDto, PasskeyCredentialDto


class PasskeyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _to_dto(self, row: PasskeyCredential) -> PasskeyCredentialDto:
        return PasskeyCredentialDto.model_validate(row, from_attributes=True)

    async def create(self, data: CreatePasskeyCredentialDto) -> PasskeyCredentialDto:
        row = PasskeyCredential(
            user_id=data.user_id,
            credential_id=data.credential_id,
            public_key=data.public_key,
            sign_count=data.sign_count,
            transports=data.transports,
            device_type=data.device_type,
            backed_up=data.backed_up,
            name=data.name,
        )
        self.session.add(row)
        await self.session.flush()
        return self._to_dto(row)

    async def get_by_credential_id(self, credential_id: str) -> Optional[PasskeyCredentialDto]:
        stmt = select(PasskeyCredential).where(PasskeyCredential.credential_id == credential_id)
        row = await self.session.scalar(stmt)
        return self._to_dto(row) if row else None

    async def get_by_id_and_user(self, id: int, user_id: int) -> Optional[PasskeyCredentialDto]:
        stmt = select(PasskeyCredential).where(
            PasskeyCredential.id == id, PasskeyCredential.user_id == user_id
        )
        row = await self.session.scalar(stmt)
        return self._to_dto(row) if row else None

    async def list_by_user(self, user_id: int) -> list[PasskeyCredentialDto]:
        stmt = (
            select(PasskeyCredential)
            .where(PasskeyCredential.user_id == user_id)
            .order_by(PasskeyCredential.created_at)
        )
        rows = await self.session.scalars(stmt)
        return [self._to_dto(row) for row in rows]

    async def update_name(self, id: int, name: str) -> PasskeyCredentialDto:
        row = await self.session.get_one(PasskeyCredential, id)
        row.name = name
        await self.session.flush()
        await self.session.refresh(row)
        return self._to_dto(row)

    async def update_after_authentication(self, id: int, sign_count: int) -> None:
        row = await self.session.get_one(PasskeyCredential, id)
        row.sign_count = sign_count
        row.last_used_at = datetime_now()
        await self.session.flush()

    async def delete_all_by_user(self, user_id: int) -> int:
        result = await self.session.execute(
            delete(PasskeyCredential).where(PasskeyCredential.user_id == user_id)
        )
        await self.session.flush()
        return cast(CursorResult, result).rowcount

    async def delete_by_id_and_user(self, id: int, user_id: int) -> bool:
        stmt = delete(PasskeyCredential).where(
            PasskeyCredential.id == id, PasskeyCredential.user_id == user_id
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return cast(CursorResult, result).rowcount > 0
