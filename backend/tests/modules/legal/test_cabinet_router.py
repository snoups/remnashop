from datetime import datetime, timedelta, timezone
from typing import AsyncIterator

import httpx
import pytest
from dishka.integrations.fastapi import setup_dishka
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.app import get_app
from app.core.config import AppConfig
from app.core.constants import API_V1
from app.core.db.models.legal_document import LegalAcceptance
from app.core.enums import LegalDocumentKind, Locale, SessionAudience
from app.core.security import create_access_token, hash_refresh_token
from app.modules.auth.dto import CreateSessionDto
from app.modules.auth.repository import SessionRepository
from app.modules.legal.dto import CreateLegalRevisionDto
from app.modules.legal.repository import LegalRepository
from app.modules.translations.repository import TranslationRepository
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository
from tests.fakes.container import make_test_container

pytestmark = pytest.mark.usefixtures("shown_documents")

URL = f"{API_V1}/cabinet/legal"


@pytest.fixture
async def client(session: AsyncSession, config: AppConfig) -> AsyncIterator[httpx.AsyncClient]:
    container = make_test_container(session, config)
    app = get_app(config)
    setup_dishka(container, app)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
    await container.close()


@pytest.fixture
async def customer(user_repository: UserRepository) -> UserDto:
    user = await user_repository.create(CreateUserDto(name="customer", telegram_id=7201))
    assert user.created_at is not None
    return user


async def _bearer(
    user_id: int,
    session_repository: SessionRepository,
    config: AppConfig,
    audience: SessionAudience = SessionAudience.CABINET,
) -> dict[str, str]:
    session = await session_repository.create(
        CreateSessionDto(
            user_id=user_id,
            refresh_token_hash=hash_refresh_token(f"legal-{user_id}-{audience}"),
            ip_address="127.0.0.1",
            user_agent=None,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            audience=audience,
        )
    )
    token = create_access_token(user_id, session.id, config.jwt_secret.get_secret_value())
    return {"Authorization": f"Bearer {token}"}


async def _flagged_agreement(
    legal_repository: LegalRepository, translation_repository: TranslationRepository
) -> int:
    await translation_repository.add_active_locale(Locale.EN)
    revision = await legal_repository.add_revision(
        CreateLegalRevisionDto(
            kind=LegalDocumentKind.USER_AGREEMENT,
            locale=Locale.EN,
            channel=None,
            title="Agreement",
            body="v2",
            created_by=None,
            requires_reacceptance=True,
        )
    )
    return revision.id


async def test_pending_requires_cabinet_session(
    client: httpx.AsyncClient,
    customer: UserDto,
    session_repository: SessionRepository,
    config: AppConfig,
) -> None:
    headers = await _bearer(customer.id, session_repository, config, SessionAudience.DASHBOARD)

    response = await client.get(f"{URL}/pending", params={"locale": "en"}, headers=headers)

    assert response.status_code == 403
    assert response.json()["code"] == "SESSION_AUDIENCE_MISMATCH"


async def test_pending_lists_flagged_document(
    client: httpx.AsyncClient,
    customer: UserDto,
    session_repository: SessionRepository,
    legal_repository: LegalRepository,
    translation_repository: TranslationRepository,
    config: AppConfig,
) -> None:
    revision_id = await _flagged_agreement(legal_repository, translation_repository)
    headers = await _bearer(customer.id, session_repository, config)

    response = await client.get(f"{URL}/pending", params={"locale": "en"}, headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["is_update"] is False
    assert body["items"][0]["revision_id"] == revision_id
    assert body["items"][0]["kind"] == "USER_AGREEMENT"
    assert body["items"][0]["created_at"]


async def test_accept_returns_empty_and_records_ip(
    client: httpx.AsyncClient,
    customer: UserDto,
    session_repository: SessionRepository,
    legal_repository: LegalRepository,
    translation_repository: TranslationRepository,
    session: AsyncSession,
    config: AppConfig,
) -> None:
    revision_id = await _flagged_agreement(legal_repository, translation_repository)
    headers = await _bearer(customer.id, session_repository, config)

    response = await client.post(
        f"{URL}/actions/accept",
        json={"locale": "en", "revision_ids": [revision_id]},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["total"] == 0
    (row,) = (await session.scalars(select(LegalAcceptance))).all()
    assert row.revision_id == revision_id
    assert row.ip_address is not None
