import secrets
from datetime import timedelta
from typing import Awaitable, Callable

import pytest

from app.core.security import hash_refresh_token
from app.core.utils.time import datetime_now
from app.modules.auth.dto import CreateSessionDto
from app.modules.auth.repository import SessionRepository

NewSession = Callable[[int], Awaitable[int]]


@pytest.fixture
def new_session(session_repository: SessionRepository) -> NewSession:
    # a push subscription only counts while the session that made it is live
    async def create(user_id: int) -> int:
        created = await session_repository.create(
            CreateSessionDto(
                user_id=user_id,
                refresh_token_hash=hash_refresh_token(secrets.token_urlsafe(16)),
                ip_address="127.0.0.1",
                user_agent=None,
                expires_at=datetime_now() + timedelta(days=30),
            )
        )
        return created.id

    return create
