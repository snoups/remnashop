import pytest

from app.core.db.uow import UnitOfWork
from app.core.enums import Locale, Role
from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.modules.api_tokens.dto import IssueApiTokenDto
from app.modules.api_tokens.repository import ApiTokenRepository
from app.modules.api_tokens.usecases import (
    CreateApiTokenUseCase,
    ListApiTokensUseCase,
    RevokeApiTokenUseCase,
)
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository

OWNER = UserDto(id=1, login="owner", name="owner", role=Role.OWNER, language=Locale.EN)
REGULAR_USER = UserDto(id=2, name="Bob", role=Role.USER, language=Locale.EN)


@pytest.fixture
async def owner(user_repository: UserRepository, uow: UnitOfWork) -> UserDto:
    # CreateApiTokenUseCase persists created_by_user_id, which has a real FK
    # to users.id -- unlike OWNER above, this actor must exist in the DB.
    async with uow:
        user = await user_repository.create(
            CreateUserDto(login="owner", name="owner", role=Role.OWNER, language=Locale.EN)
        )
        await uow.commit()
    return user


async def test_owner_can_create_token_and_secret_is_returned_once(
    api_token_repository: ApiTokenRepository,
    uow: UnitOfWork,
    owner: UserDto,
    event_publisher: EventPublisher,
) -> None:
    use_case = CreateApiTokenUseCase(api_token_repository, uow, event_publisher)

    result = await use_case(
        owner,
        IssueApiTokenDto(
            name="ci-script", scopes=[Permission.BANNERS_UPLOAD.value], expires_in_days=30
        ),
    )

    assert result.token.name == "ci-script"
    assert result.token.scopes == [Permission.BANNERS_UPLOAD.value]
    assert len(result.secret) > 20


async def test_create_token_rejects_manage_admins_permission(
    api_token_repository: ApiTokenRepository, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    use_case = CreateApiTokenUseCase(api_token_repository, uow, event_publisher)

    with pytest.raises(ValidationError):
        await use_case(
            OWNER,
            IssueApiTokenDto(
                name="bad", scopes=[Permission.ADMINS_MANAGE.value], expires_in_days=30
            ),
        )


async def test_create_token_rejects_manage_own_account_permission(
    api_token_repository: ApiTokenRepository, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    use_case = CreateApiTokenUseCase(api_token_repository, uow, event_publisher)

    with pytest.raises(ValidationError):
        await use_case(
            OWNER,
            IssueApiTokenDto(
                name="bad", scopes=[Permission.OWN_ACCOUNT_MANAGE.value], expires_in_days=30
            ),
        )


async def test_regular_user_cannot_create_token(
    api_token_repository: ApiTokenRepository, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    use_case = CreateApiTokenUseCase(api_token_repository, uow, event_publisher)

    with pytest.raises(PermissionDeniedError):
        await use_case(
            REGULAR_USER,
            IssueApiTokenDto(
                name="ci-script", scopes=[Permission.BANNERS_UPLOAD.value], expires_in_days=30
            ),
        )


async def test_list_returns_created_tokens_without_secret(
    api_token_repository: ApiTokenRepository,
    uow: UnitOfWork,
    owner: UserDto,
    event_publisher: EventPublisher,
) -> None:
    create_use_case = CreateApiTokenUseCase(api_token_repository, uow, event_publisher)
    list_use_case = ListApiTokensUseCase(api_token_repository, uow)

    await create_use_case(
        owner,
        IssueApiTokenDto(
            name="ci-script", scopes=[Permission.BANNERS_UPLOAD.value], expires_in_days=30
        ),
    )

    tokens = await list_use_case(OWNER)
    assert len(tokens) == 1
    assert tokens[0].name == "ci-script"


async def test_revoke_removes_token_from_list(
    api_token_repository: ApiTokenRepository,
    uow: UnitOfWork,
    owner: UserDto,
    event_publisher: EventPublisher,
) -> None:
    create_use_case = CreateApiTokenUseCase(api_token_repository, uow, event_publisher)
    revoke_use_case = RevokeApiTokenUseCase(api_token_repository, uow, event_publisher)
    list_use_case = ListApiTokensUseCase(api_token_repository, uow)

    created = await create_use_case(
        owner,
        IssueApiTokenDto(
            name="ci-script", scopes=[Permission.BANNERS_UPLOAD.value], expires_in_days=30
        ),
    )

    await revoke_use_case(owner, created.token.id)

    tokens = await list_use_case(OWNER)
    assert tokens == []


async def test_revoke_unknown_token_raises_not_found(
    api_token_repository: ApiTokenRepository, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    revoke_use_case = RevokeApiTokenUseCase(api_token_repository, uow, event_publisher)

    with pytest.raises(NotFoundError):
        await revoke_use_case(OWNER, 999_999)


async def test_create_token_with_expires_in_days_computes_expiry(
    api_token_repository: ApiTokenRepository,
    uow: UnitOfWork,
    owner: UserDto,
    event_publisher: EventPublisher,
) -> None:
    use_case = CreateApiTokenUseCase(api_token_repository, uow, event_publisher)

    result = await use_case(
        owner,
        IssueApiTokenDto(
            name="ci-script", scopes=[Permission.BANNERS_IMAGE_VIEW.value], expires_in_days=30
        ),
    )

    assert result.token.expires_at is not None


async def test_create_token_rejects_a_scope_granting_nothing(
    api_token_repository: ApiTokenRepository, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    use_case = CreateApiTokenUseCase(api_token_repository, uow, event_publisher)

    for scope in ("users:delete", "nonexistent:*", "oauth_settings:write", "NOT_A_PERMISSION"):
        with pytest.raises(ValidationError):
            await use_case(OWNER, IssueApiTokenDto(name="bad", scopes=[scope], expires_in_days=30))
