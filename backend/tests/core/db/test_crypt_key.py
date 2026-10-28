from sqlalchemy import String, select, type_coerce, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import AppConfig
from app.core.db.crypt_key import find_undecryptable_column, reset_encrypted_secrets
from app.core.db.models import BotSettings, PaymentGateway
from app.core.enums import PaymentGatewayType
from app.core.security.crypt import encrypt_value

_OTHER_KEY = "Wq0AJoICLDf3qB3Hw4DTXRtVCo_Nep5n0hb4Mk0iQ4c="


async def _store_bot_token(session: AsyncSession, ciphertext: str) -> None:
    session.add(BotSettings(id=1))
    await session.flush()
    await session.execute(update(BotSettings).values(token=type_coerce(ciphertext, String)))


async def test_a_database_without_secrets_matches_any_key(
    session: AsyncSession, config: AppConfig
) -> None:
    assert await find_undecryptable_column(session, config.crypt_key.get_secret_value()) is None


async def test_a_secret_encrypted_with_this_key_matches(
    session: AsyncSession, config: AppConfig
) -> None:
    key = config.crypt_key.get_secret_value()
    await _store_bot_token(session, encrypt_value("123:abc", key))

    assert await find_undecryptable_column(session, key) is None


async def test_a_secret_encrypted_with_another_key_is_reported(
    session: AsyncSession, config: AppConfig
) -> None:
    await _store_bot_token(session, encrypt_value("123:abc", _OTHER_KEY))

    column = await find_undecryptable_column(session, config.crypt_key.get_secret_value())

    assert column == "bot_settings.token"


async def test_reset_clears_every_secret_and_switches_gateways_off(
    session: AsyncSession, config: AppConfig
) -> None:
    await _store_bot_token(session, encrypt_value("123:abc", _OTHER_KEY))
    session.add(
        PaymentGateway(type=PaymentGatewayType.YOOKASSA, is_active=True, settings='{"k": "v"}')
    )
    await session.flush()

    await reset_encrypted_secrets(session)

    key = config.crypt_key.get_secret_value()
    assert await find_undecryptable_column(session, key) is None
    assert await session.scalar(select(type_coerce(BotSettings.token, String))) is None
    gateway = await session.scalar(
        select(PaymentGateway.is_active).where(PaymentGateway.type == PaymentGatewayType.YOOKASSA)
    )
    assert gateway is False
