import pytest
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models import EventOutboxEntry
from app.core.db.uow import UnitOfWork
from app.core.enums import BlacklistKind, OAuthProvider, Role
from app.core.error_codes import ErrorCode
from app.core.exceptions import ConflictError, PermissionDeniedError, ValidationError
from app.modules.blacklist.repository import BlacklistRepository
from app.modules.cabinet_auth import TelegramProfileDto
from app.modules.identity_links.api.schemas import LinkResultResponse
from app.modules.identity_links.dto import IdentityClaimDto, IdentityKind
from app.modules.identity_links.linker import IdentityLinker
from app.modules.oauth import CreateOAuthIdentityDto, OAuthProfile
from app.modules.oauth.repository import OAuthIdentityRepository
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository
from tests.modules.broadcasts.factories import add_subscription


def _email(address: str) -> IdentityClaimDto:
    return IdentityClaimDto(kind=IdentityKind.EMAIL, email=address)


def _telegram(telegram_id: int, username: str = "tg") -> IdentityClaimDto:
    return IdentityClaimDto(
        kind=IdentityKind.TELEGRAM,
        telegram=TelegramProfileDto(
            telegram_id=telegram_id, name="Tg", username=username, language="en"
        ),
    )


async def _outbox(session: AsyncSession, event_type: str) -> int:
    return int(
        await session.scalar(
            select(func.count())
            .select_from(EventOutboxEntry)
            .where(EventOutboxEntry.event_type == event_type)
        )
        or 0
    )


async def _merge_keys(redis: Redis) -> list[str]:
    return [key async for key in redis.scan_iter("*identity:merge:*")]


async def test_free_email_links(
    linker: IdentityLinker, user_repository: UserRepository, session: AsyncSession
) -> None:
    user = await user_repository.create(CreateUserDto(name="me", telegram_id=5001))

    result = await linker.link(user, _email("Me@Gmail.com"), "127.0.0.1")

    assert result.status == "linked"
    fresh = await user_repository.find_by_id(user.id)
    assert fresh is not None and fresh.email == "me@gmail.com"
    assert await _outbox(session, "SignInMethodLinkedEvent") == 1


async def test_free_telegram_links_with_username(
    linker: IdentityLinker, user_repository: UserRepository
) -> None:
    user = await user_repository.create(CreateUserDto(name="me", email="me@gmail.com"))

    result = await linker.link(user, _telegram(5002, "neo"), "127.0.0.1")

    assert result.status == "linked"
    fresh = await user_repository.find_by_id(user.id)
    assert fresh is not None and fresh.telegram_id == 5002 and fresh.username == "neo"
    assert fresh.name == "me"


async def test_free_oauth_links(
    linker: IdentityLinker,
    user_repository: UserRepository,
    oauth_identity_repository: OAuthIdentityRepository,
) -> None:
    user = await user_repository.create(CreateUserDto(name="me", email="me@gmail.com"))

    result = await linker.link(
        user,
        IdentityClaimDto(kind=IdentityKind.GOOGLE, oauth=OAuthProfile("g-1", "me@g")),
        "127.0.0.1",
    )

    assert result.status == "linked"
    identity = await oauth_identity_repository.find_by_provider_external_id(
        OAuthProvider.GOOGLE, "g-1"
    )
    assert identity is not None and identity.user_id == user.id


async def test_own_email_already_linked(
    linker: IdentityLinker, user_repository: UserRepository, session: AsyncSession
) -> None:
    user = await user_repository.create(CreateUserDto(name="me", email="me@gmail.com"))

    result = await linker.link(user, _email("me@gmail.com"), "127.0.0.1")

    assert result.status == "already_linked"
    assert await _outbox(session, "SignInMethodLinkedEvent") == 0


async def test_second_email_refused(
    linker: IdentityLinker, user_repository: UserRepository
) -> None:
    user = await user_repository.create(CreateUserDto(name="me", email="a@gmail.com"))

    with pytest.raises(ConflictError) as error:
        await linker.link(user, _email("b@gmail.com"), "127.0.0.1")

    assert error.value.code == ErrorCode.MERGE_IDENTITY_CONFLICT


async def test_second_oauth_of_same_provider_refused(
    linker: IdentityLinker,
    user_repository: UserRepository,
    oauth_identity_repository: OAuthIdentityRepository,
) -> None:
    user = await user_repository.create(CreateUserDto(name="me", email="a@gmail.com"))
    await oauth_identity_repository.create(
        CreateOAuthIdentityDto(
            user_id=user.id, provider=OAuthProvider.YANDEX, external_id="y-1", external_login=None
        )
    )

    with pytest.raises(ConflictError) as error:
        await linker.link(
            user,
            IdentityClaimDto(kind=IdentityKind.YANDEX, oauth=OAuthProfile("y-2", None)),
            "127.0.0.1",
        )

    assert error.value.code == ErrorCode.MERGE_IDENTITY_CONFLICT


async def test_disallowed_domain_refused(
    linker: IdentityLinker, user_repository: UserRepository
) -> None:
    user = await user_repository.create(CreateUserDto(name="me", telegram_id=5003))

    with pytest.raises(ValidationError) as error:
        await linker.link(user, _email("me@evil.example"), "127.0.0.1")

    assert error.value.code == ErrorCode.EMAIL_DOMAIN_NOT_ALLOWED


async def test_blacklisted_email_refused(
    linker: IdentityLinker,
    user_repository: UserRepository,
    blacklist_repository: BlacklistRepository,
    uow: UnitOfWork,
) -> None:
    user = await user_repository.create(CreateUserDto(name="me", telegram_id=5004))
    async with uow:
        await blacklist_repository.add_entry(BlacklistKind.EMAIL, "spam@gmail.com")

    with pytest.raises(PermissionDeniedError) as error:
        await linker.link(user, _email("spam@gmail.com"), "127.0.0.1")

    assert error.value.code == ErrorCode.IDENTITY_BLACKLISTED
    fresh = await user_repository.find_by_id(user.id)
    assert fresh is not None and fresh.email is None


async def test_blacklisted_telegram_refused(
    linker: IdentityLinker,
    user_repository: UserRepository,
    blacklist_repository: BlacklistRepository,
    uow: UnitOfWork,
) -> None:
    user = await user_repository.create(CreateUserDto(name="me", email="me@gmail.com"))
    async with uow:
        await blacklist_repository.add_entry(BlacklistKind.TELEGRAM_ID, "5005")

    with pytest.raises(PermissionDeniedError) as error:
        await linker.link(user, _telegram(5005), "127.0.0.1")

    assert error.value.code == ErrorCode.IDENTITY_BLACKLISTED


async def test_foreign_email_requires_merge(
    linker: IdentityLinker,
    user_repository: UserRepository,
    session: AsyncSession,
    redis: Redis,
) -> None:
    user = await user_repository.create(CreateUserDto(name="me"))
    other = await user_repository.create(
        CreateUserDto(name="other", email="other@gmail.com", telegram_id=5007, username="twin")
    )
    await add_subscription(session, other.id)

    result = await linker.link(user, _email("other@gmail.com"), "127.0.0.1")

    assert result.status == "merge_required"
    assert result.merge_token and result.expires_in == 600
    assert result.other is not None and result.other.subscriptions == 1
    labels = {item.kind: item.label for item in result.other.identities}
    assert labels[IdentityKind.TELEGRAM] == "@twin"
    assert labels[IdentityKind.EMAIL] == "other@gmail.com"
    assert len(await _merge_keys(redis)) == 1
    body = LinkResultResponse.model_validate(result, from_attributes=True).model_dump(mode="json")
    assert body["other"]["identities"][0] == {"kind": "TELEGRAM", "linked": True, "label": "@twin"}


async def test_foreign_staff_refused(
    linker: IdentityLinker, user_repository: UserRepository, redis: Redis
) -> None:
    user = await user_repository.create(CreateUserDto(name="me", telegram_id=5008))
    await user_repository.create(
        CreateUserDto(name="boss", email="boss@gmail.com", role=Role.ADMIN, login="boss")
    )

    with pytest.raises(ConflictError) as error:
        await linker.link(user, _email("boss@gmail.com"), "127.0.0.1")

    assert error.value.code == ErrorCode.MERGE_ACCOUNT_PRIVILEGED
    assert await _merge_keys(redis) == []
