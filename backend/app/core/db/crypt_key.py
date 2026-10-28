from typing import Any, Optional

from cryptography.fernet import InvalidToken
from sqlalchemy import Column, String, select, type_coerce, update
from sqlalchemy.ext.asyncio import AsyncSession

import app.core.db.models  # noqa: F401  every table on the metadata
from app.core.config import AppConfig
from app.core.db.base import BaseSql
from app.core.db.encrypted_string import EncryptedString
from app.core.db.models import NotificationSettings, PaymentGateway
from app.core.db.standalone import standalone_session
from app.core.security.crypt import decrypt_value


def _encrypted_columns() -> list[Column[Any]]:
    return [
        column
        for table in BaseSql.metadata.sorted_tables
        for column in table.columns
        if isinstance(column.type, EncryptedString)
    ]


async def find_undecryptable_column(session: AsyncSession, key: str) -> Optional[str]:
    for column in _encrypted_columns():
        # read as stored: the column type itself would decrypt, and raise
        stored = await session.scalar(
            select(type_coerce(column, String)).where(column.is_not(None)).limit(1)
        )
        if stored is None:
            continue
        try:
            decrypt_value(stored, key)
        except InvalidToken:
            return f"{column.table.name}.{column.name}"
    return None


async def assert_crypt_key_matches(config: AppConfig) -> None:
    async with standalone_session(config) as session:
        column = await find_undecryptable_column(session, config.crypt_key.get_secret_value())
    if column is not None:
        raise RuntimeError(
            f"APP_CRYPT_KEY does not decrypt {column}: the database was set up with another "
            "key. Put that key back, or run the rescue CLI (docker compose run --rm "
            '--entrypoint python remnashop -m app.cli) and choose "Reset encrypted secrets", '
            'then "Reset owner access", and enter the secrets in the dashboard again.'
        )


async def reset_encrypted_secrets(session: AsyncSession) -> None:
    for table in BaseSql.metadata.sorted_tables:
        names = [column.name for column in _encrypted_columns() if column.table is table]
        if names:
            await session.execute(update(table).values(dict.fromkeys(names)))
    # a gateway without credentials can't take payments
    await session.execute(update(PaymentGateway).values(is_active=False))
    # a public key without its private half signs nothing
    await session.execute(update(NotificationSettings).values(vapid_public_key=None))
