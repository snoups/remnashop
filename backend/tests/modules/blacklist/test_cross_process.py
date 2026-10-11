import datetime
from datetime import timedelta, timezone
from typing import Final

import httpx
from dishka import Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import setup_dishka
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.api.app import get_app
from app.core.config import AppConfig
from app.core.constants import API_V1
from app.core.db.uow import UnitOfWork
from app.core.di.providers import get_core_providers
from app.core.enums import Locale, Role, SessionAudience
from app.core.outbox_event_publisher import OutboxEventPublisher
from app.core.security import create_access_token, hash_password, hash_refresh_token
from app.modules.auth.dto import CreateSessionDto
from app.modules.auth.repository import SessionRepository
from app.modules.blacklist.repository import BlacklistRepository
from app.modules.providers import get_module_providers
from app.modules.users import BlockBlacklistMatchesUseCase
from app.modules.users.blacklist_repository import UserBlacklistRepository
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository
from tests.fakes.dispatch import RecordingDispatch

_OWNER_TELEGRAM_ID: Final[int] = 51500
_TARGET_TELEGRAM_ID: Final[int] = 51501


class _SessionProvider(Provider):
    scope = Scope.REQUEST

    def __init__(self, session: AsyncSession) -> None:
        super().__init__()
        self._session = session

    @provide
    def get_session(self) -> AsyncSession:
        return self._session


async def test_api_written_entry_is_visible_to_a_separate_session(config: AppConfig) -> None:
    # Genuinely cross-process: the entry is written through the real HTTP API on
    # one engine/session, then read back by a reconcile run on a *second* engine.
    # A flush-without-commit in the write path is invisible to the reader, which
    # only a second engine catches.
    # Both sessions commit for real, so cleanup is explicit rather than the
    # rolled-back `session` fixture every other test uses.
    write_engine = create_async_engine(config.database.dsn)
    read_engine = create_async_engine(config.database.dsn)
    try:
        async with AsyncSession(write_engine, expire_on_commit=False) as write_session:
            user_repository = UserRepository(write_session)
            owner = await user_repository.create(
                CreateUserDto(
                    login="crossprocess-owner",
                    password_hash=await hash_password("x", config.crypt_key.get_secret_value()),
                    name="crossprocess-owner",
                    role=Role.OWNER,
                    language=Locale.EN,
                    telegram_id=_OWNER_TELEGRAM_ID,
                )
            )
            await user_repository.create(
                CreateUserDto(
                    name="crossprocess-target",
                    telegram_id=_TARGET_TELEGRAM_ID,
                    language=Locale.EN,
                )
            )
            session_row = await SessionRepository(write_session).create(
                CreateSessionDto(
                    user_id=owner.id,
                    refresh_token_hash=hash_refresh_token("crossprocess-refresh"),
                    ip_address="127.0.0.1",
                    user_agent=None,
                    expires_at=datetime.datetime.now(timezone.utc) + timedelta(days=30),
                    audience=SessionAudience.DASHBOARD,
                )
            )
            await write_session.commit()

            token = create_access_token(
                owner.id, session_row.id, config.jwt_secret.get_secret_value()
            )
            container = make_async_container(
                *get_core_providers(),
                *get_module_providers(),
                _SessionProvider(write_session),
                context={AppConfig: config},
            )
            app = get_app(config)
            setup_dishka(container, app)
            try:
                transport = httpx.ASGITransport(app=app)
                async with httpx.AsyncClient(
                    transport=transport, base_url="http://testserver"
                ) as client:
                    response = await client.put(
                        f"{API_V1}/blacklist/entries/TELEGRAM_ID/{_TARGET_TELEGRAM_ID}",
                        headers={"Authorization": f"Bearer {token}"},
                    )
                assert response.status_code == 200
            finally:
                await container.close()

        async with AsyncSession(read_engine, expire_on_commit=False) as read_session:
            read_user_repository = UserRepository(read_session)
            read_uow = UnitOfWork(read_session)
            await BlockBlacklistMatchesUseCase(
                BlacklistRepository(read_session),
                UserBlacklistRepository(read_session),
                read_uow,
                OutboxEventPublisher(read_uow, RecordingDispatch()),
            ).system()
            refetched = await read_user_repository.get_by_telegram_id(_TARGET_TELEGRAM_ID)
            assert refetched is not None and refetched.is_blocked is True
    finally:
        async with read_engine.begin() as connection:
            await connection.execute(text("DELETE FROM event_outbox"))
            await connection.execute(text("DELETE FROM blacklist"))
            await connection.execute(
                text("DELETE FROM users WHERE telegram_id IN (:owner, :target)"),
                {"owner": _OWNER_TELEGRAM_ID, "target": _TARGET_TELEGRAM_ID},
            )
        await write_engine.dispose()
        await read_engine.dispose()
