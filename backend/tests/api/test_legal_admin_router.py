import datetime
from datetime import timedelta, timezone
from typing import AsyncIterator

import httpx
import pytest
from dishka import AsyncContainer
from fastapi import FastAPI

from app.core.config import AppConfig
from app.core.constants import API_V1
from app.core.db.uow import UnitOfWork
from app.core.enums import (
    LegalAcceptanceTrigger,
    LegalDocumentKind,
    Locale,
    PurchaseChannel,
    Role,
    SessionAudience,
)
from app.core.security import create_access_token, hash_password, hash_refresh_token
from app.modules.auth.dto import CreateSessionDto
from app.modules.auth.repository import SessionRepository
from app.modules.legal.dto import CreateLegalAcceptanceDto, CreateLegalRevisionDto
from app.modules.legal.repository import LegalRepository
from app.modules.translations.repository import TranslationRepository
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository


@pytest.fixture
async def client(
    test_container: AsyncContainer, api_app: FastAPI
) -> AsyncIterator[httpx.AsyncClient]:
    app = api_app
    app.state.dishka_container = test_container
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client


async def _token_for(
    role: Role,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> str:
    async with uow:
        user = await user_repository.create(
            CreateUserDto(
                login=f"legaltest{role.value}",
                password_hash=await hash_password("x", config.crypt_key.get_secret_value()),
                name=f"legaltest{role.value}",
                role=role,
                language=Locale.EN,
            )
        )
        await uow.commit()
    session = await session_repository.create(
        CreateSessionDto(
            user_id=user.id,
            refresh_token_hash=hash_refresh_token(f"test-refresh-token-{role.value}"),
            ip_address="127.0.0.1",
            user_agent=None,
            expires_at=datetime.datetime.now(timezone.utc) + timedelta(days=30),
            audience=SessionAudience.DASHBOARD,
        )
    )
    return create_access_token(user.id, session.id, config.jwt_secret.get_secret_value())


async def _owner_headers(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> dict[str, str]:
    token = await _token_for(Role.OWNER, user_repository, session_repository, uow, config)
    return {"Authorization": f"Bearer {token}"}


async def test_put_then_get_shows_text_and_delete_removes_it(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    translation_repository: TranslationRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    await translation_repository.add_active_locale(Locale.EN)
    headers = await _owner_headers(user_repository, session_repository, uow, config)

    put = await client.put(
        f"{API_V1}/legal-documents/OFFER/en",
        params={"channel": "BOT"},
        json={"title": "Offer", "body": "Terms"},
        headers=headers,
    )
    assert put.status_code == 200
    assert put.json()["channel"] == "BOT"
    assert put.json()["revision_id"] > 0

    listed = await client.get(f"{API_V1}/legal-documents", headers=headers)
    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] == 3
    assert "en" in body["locales"]
    offer = next(item for item in body["items"] if item["kind"] == "OFFER")
    assert [(t["locale"], t["channel"], t["body"]) for t in offer["texts"]] == [
        ("en", "BOT", "Terms")
    ]

    deleted = await client.delete(
        f"{API_V1}/legal-documents/OFFER/en", params={"channel": "BOT"}, headers=headers
    )
    assert deleted.status_code == 204
    after = await client.get(f"{API_V1}/legal-documents", headers=headers)
    offer = next(item for item in after.json()["items"] if item["kind"] == "OFFER")
    assert offer["texts"] == []


async def test_patch_updates_flags(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    headers = await _owner_headers(user_repository, session_repository, uow, config)

    response = await client.patch(
        f"{API_V1}/legal-documents/PRIVACY_POLICY", json={"show_in_bot": False}, headers=headers
    )

    assert response.status_code == 200
    assert response.json()["show_in_bot"] is False


async def test_requires_permission(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    token = await _token_for(Role.USER, user_repository, session_repository, uow, config)

    response = await client.get(
        f"{API_V1}/legal-documents", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 403
    assert (await client.get(f"{API_V1}/legal-documents")).status_code == 401


async def test_user_acceptances_listed_and_gated(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    legal_repository: LegalRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    headers = await _owner_headers(user_repository, session_repository, uow, config)
    async with uow:
        customer = await user_repository.create(CreateUserDto(name="cust", role=Role.USER))
        revision = await legal_repository.add_revision(
            CreateLegalRevisionDto(
                kind=LegalDocumentKind.OFFER,
                locale=Locale.EN,
                channel=None,
                title="Offer",
                body="Terms",
                created_by=None,
            )
        )
        await legal_repository.add_acceptances(
            [
                CreateLegalAcceptanceDto(
                    user_id=customer.id,
                    revision_id=revision.id,
                    channel=PurchaseChannel.CABINET,
                    trigger=LegalAcceptanceTrigger.PAYMENT,
                    transaction_id=None,
                    ip_address=None,
                )
            ]
        )
        await uow.commit()

    response = await client.get(f"{API_V1}/users/{customer.id}/legal-acceptances", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert (item["kind"], item["locale"], item["channel"], item["trigger"]) == (
        "OFFER",
        "en",
        "CABINET",
        "PAYMENT",
    )
    assert item["revision_id"] == revision.id
    assert item["title"] == "Offer"
    assert item["transaction_id"] is None
    assert "ip_address" not in item

    token = await _token_for(Role.USER, user_repository, session_repository, uow, config)
    denied = await client.get(
        f"{API_V1}/users/{customer.id}/legal-acceptances",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert denied.status_code == 403
