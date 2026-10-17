from datetime import datetime, timedelta, timezone
from typing import AsyncIterator

import httpx
import pytest
from dishka import Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import setup_dishka
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.app import get_app
from app.core.config import AppConfig
from app.core.constants import API_V1
from app.core.db.uow import UnitOfWork
from app.core.di.providers import get_core_providers
from app.core.enums import Locale, PromocodeRewardType, Role, SessionAudience
from app.core.security import create_access_token, hash_password, hash_refresh_token
from app.modules.auth.dto import CreateSessionDto
from app.modules.auth.repository import SessionRepository
from app.modules.promocodes.dto import CreatePromocodeDto, UpdatePromocodeDto
from app.modules.promocodes.repository import PromocodeRepository
from app.modules.providers import get_module_providers
from app.modules.users.dto import CreateUserDto, UpdateUserDto, UserDto
from app.modules.users.repository import UserRepository

_ME = f"{API_V1}/users/me"


async def _customer(user_repository: UserRepository, uow: UnitOfWork) -> UserDto:
    async with uow:
        user = await user_repository.create(
            CreateUserDto(
                name="Customer", telegram_id=88001, email="c@example.com", language=Locale.EN
            )
        )
        await uow.commit()
    return user


async def _bearer(
    user_id: int,
    audience: SessionAudience,
    session_repository: SessionRepository,
    config: AppConfig,
) -> dict[str, str]:
    session = await session_repository.create(
        CreateSessionDto(
            user_id=user_id,
            refresh_token_hash=hash_refresh_token(f"profile-{user_id}-{audience.value}"),
            ip_address="127.0.0.1",
            user_agent=None,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            audience=audience,
        )
    )
    token = create_access_token(user_id, session.id, config.jwt_secret.get_secret_value())
    return {"Authorization": f"Bearer {token}"}


async def test_a_customer_reads_their_profile_with_a_cabinet_session(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    user = await _customer(user_repository, uow)
    headers = await _bearer(user.id, SessionAudience.CABINET, session_repository, config)

    response = await client.get(_ME, headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == user.id
    assert body["email"] == "c@example.com"
    assert body["telegram_id"] == 88001
    assert body["role"] == "USER"
    assert body["effective_permissions"] == []
    assert body["created_at"] is not None
    assert body["points"] == "0"  # Decimal goes out as a JSON string
    assert body["bonus_days"] == 0
    assert body["personal_discount"] == 0
    assert body["purchase_discount"] == 0
    assert body["loyalty_discount"] == 0


async def test_the_profile_hides_a_discount_from_an_ended_promocode(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    promocode_repository: PromocodeRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    user = await _customer(user_repository, uow)
    async with uow:
        dead = await promocode_repository.create(
            CreatePromocodeDto(
                code="PROFDEAD", reward_type=PromocodeRewardType.PERSONAL_DISCOUNT, reward=20
            )
        )
        await promocode_repository.update(UpdatePromocodeDto(promocode_id=dead.id, is_active=False))
        live = await promocode_repository.create(
            CreatePromocodeDto(
                code="PROFLIVE", reward_type=PromocodeRewardType.PURCHASE_DISCOUNT, reward=15
            )
        )
        await user_repository.update_fields(
            user.id,
            UpdateUserDto(
                personal_discount=20,
                personal_discount_promocode_id=dead.id,
                purchase_discount=15,
                purchase_discount_promocode_id=live.id,
            ),
        )
    headers = await _bearer(user.id, SessionAudience.CABINET, session_repository, config)

    body = (await client.get(_ME, headers=headers)).json()

    assert body["personal_discount"] == 0
    assert body["purchase_discount"] == 15


async def test_the_profile_keeps_a_manual_discount(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    user = await _customer(user_repository, uow)
    async with uow:
        await user_repository.update_fields(user.id, UpdateUserDto(personal_discount=10))
    headers = await _bearer(user.id, SessionAudience.CABINET, session_repository, config)

    body = (await client.get(_ME, headers=headers)).json()

    assert body["personal_discount"] == 10


async def test_a_customer_dashboard_session_is_refused(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    user = await _customer(user_repository, uow)
    headers = await _bearer(user.id, SessionAudience.DASHBOARD, session_repository, config)

    response = await client.get(_ME, headers=headers)

    assert response.status_code == 403
    assert response.json()["code"] == "SESSION_AUDIENCE_MISMATCH"


async def test_a_customer_renames_but_cannot_set_a_password(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    user = await _customer(user_repository, uow)
    headers = await _bearer(user.id, SessionAudience.CABINET, session_repository, config)

    renamed = await client.patch(_ME, json={"name": "Anna", "language": "ru"}, headers=headers)
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Anna"

    password = await client.patch(
        _ME,
        json={"current_password": "x", "new_password": "A-Long-New-Passphrase-For-Test-1"},
        headers=headers,
    )
    assert password.status_code == 403
    assert password.json()["code"] == "PERMISSION_DENIED"


async def test_staff_cannot_change_the_password_from_a_cabinet_session(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    pepper = config.crypt_key.get_secret_value()
    current = "Current-Passphrase-For-Test-1"
    async with uow:
        owner = await user_repository.create(
            CreateUserDto(
                name="Owner",
                login="owner-profile",
                role=Role.OWNER,
                password_hash=await hash_password(current, pepper),
            )
        )
        await uow.commit()
    payload = {"current_password": current, "new_password": "A-Long-New-Passphrase-For-Test-1"}

    cabinet = await _bearer(owner.id, SessionAudience.CABINET, session_repository, config)
    refused = await client.patch(_ME, json=payload, headers=cabinet)
    assert refused.status_code == 403
    assert refused.json()["code"] == "PERMISSION_DENIED"

    dashboard = await _bearer(owner.id, SessionAudience.DASHBOARD, session_repository, config)
    assert (await client.patch(_ME, json=payload, headers=dashboard)).status_code == 200


async def test_the_cabinet_me_path_is_gone(client: httpx.AsyncClient) -> None:
    assert (await client.get(f"{API_V1}/cabinet/me")).status_code == 404


class _TestSessionProvider(Provider):
    scope = Scope.REQUEST

    def __init__(self, session: AsyncSession) -> None:
        super().__init__()
        self._session = session

    @provide
    def get_session(self) -> AsyncSession:
        return self._session


@pytest.fixture
async def client(session: AsyncSession, config: AppConfig) -> AsyncIterator[httpx.AsyncClient]:
    container = make_async_container(
        *get_core_providers(),
        *get_module_providers(),
        _TestSessionProvider(session),
        context={AppConfig: config},
    )
    app = get_app(config)
    setup_dishka(container, app)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as http:
        yield http
    await container.close()
