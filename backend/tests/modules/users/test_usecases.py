from datetime import timedelta
from typing import Optional

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import SyntheticActor
from app.core.config import AppConfig
from app.core.db.models import EventOutboxEntry, User
from app.core.db.uow import UnitOfWork
from app.core.enums import BlacklistKind, Locale, Role, SessionAudience
from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError, ValidationError
from app.core.ports import EventPublisher
from app.core.security import hash_password
from app.core.security.password import PASSWORD_MIN_LENGTH
from app.core.security.permissions import Permission
from app.core.security.session_token import hash_refresh_token
from app.core.utils.time import datetime_now
from app.modules.auth.dto import CreateSessionDto
from app.modules.auth.repository import SessionRepository
from app.modules.auth.session_issuer import SessionIssuer
from app.modules.blacklist import BlacklistRepository
from app.modules.blacklist.dto import AddBlacklistSourceDto, ParsedSourceList
from app.modules.passkeys.dto import CreatePasskeyCredentialDto
from app.modules.passkeys.repository import PasskeyRepository
from app.modules.users.dto import (
    BlockUserDto,
    CreateAdminDto,
    CreateUserDto,
    DeleteAdminDto,
    DeleteUserDto,
    DemoteAdminDto,
    ListUsersDto,
    PromoteToAdminDto,
    RegisterTelegramUserDto,
    SetUserDiscountDto,
    UpdateAdminDto,
    UpdateSecuritySettingsDto,
    UpdateUserDto,
    UserDto,
)
from app.modules.users.events import (
    AdminCreatedEvent,
    AdminDeletedEvent,
    AdminDemotedEvent,
    AdminPermissionsUpdatedEvent,
    AdminPromotedEvent,
    TelegramRegistrationBlockedEvent,
    TelegramUserRegisteredEvent,
    UserDeletedEvent,
    UserPersonalDiscountChangedEvent,
    UserPurchaseDiscountChangedEvent,
)
from app.modules.users.repository import UserRepository
from app.modules.users.usecases import (
    BlockUserUseCase,
    CreateAdminUseCase,
    DeleteAdminUseCase,
    DeleteUserUseCase,
    DemoteAdminUseCase,
    ListAdminsUseCase,
    ListUsersUseCase,
    PromoteToAdminUseCase,
    RegisterTelegramUserUseCase,
    SetUserDiscountUseCase,
    UpdateAdminUseCase,
    UpdateOwnSecuritySettingsUseCase,
)
from app.modules.users.usecases import promote_to_admin as promote_to_admin_module
from tests.fakes.events import RecordingEventPublisher

OWNER = UserDto(id=1, login="owner", name="owner", role=Role.OWNER, language=Locale.EN)
ADMIN = UserDto(id=2, login="admin", name="admin", role=Role.ADMIN, language=Locale.EN)
REGULAR_USER = UserDto(id=3, name="Bob", role=Role.USER, language=Locale.EN)


@pytest.fixture(autouse=True)
async def _seed_actor_row(session: AsyncSession) -> None:
    # event_outbox.actor_id is a real FK into users, and OWNER/ADMIN act on
    # almost every use case below. Role.USER, not their own role --
    # ux_users_single_owner would otherwise reject the owner rows several
    # tests create themselves.
    for actor in (OWNER, ADMIN):
        session.add(
            User(
                id=actor.id,
                login=actor.login,
                name=actor.name,
                role=Role.USER,
                language=actor.language,
                is_blocked=False,
            )
        )
    await session.flush()


async def _outbox_rows(session: AsyncSession, event_type: str) -> list[EventOutboxEntry]:
    return list(
        (
            await session.scalars(
                select(EventOutboxEntry)
                .where(EventOutboxEntry.event_type == event_type)
                .order_by(EventOutboxEntry.id)
            )
        ).all()
    )


async def test_owner_can_create_admin(
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
) -> None:
    use_case = CreateAdminUseCase(user_repository, uow, config, event_publisher)

    result = await use_case(
        OWNER, CreateAdminDto(client_ip="127.0.0.1", login="newadmin", name="New Admin")
    )
    admin, password = result.admin, result.password

    assert admin.role == Role.ADMIN
    assert admin.login == "newadmin"
    assert len(password) == PASSWORD_MIN_LENGTH


async def test_create_admin_stores_permission_overrides(
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
) -> None:
    use_case = CreateAdminUseCase(user_repository, uow, config, event_publisher)

    admin = (
        await use_case(
            OWNER,
            CreateAdminDto(
                client_ip="127.0.0.1",
                login="newadmin2",
                name="New Admin 2",
                permission_grants=[Permission.EVENT_LOG_VIEW],
            ),
        )
    ).admin

    assert admin.permission_grants == [Permission.EVENT_LOG_VIEW]


async def test_create_admin_rejects_manage_admins_grant(
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
) -> None:
    use_case = CreateAdminUseCase(user_repository, uow, config, event_publisher)

    with pytest.raises(ValidationError):
        await use_case(
            OWNER,
            CreateAdminDto(
                client_ip="127.0.0.1",
                login="newadmin3",
                name="X",
                permission_grants=[Permission.ADMINS_MANAGE],
            ),
        )


async def test_create_admin_rejects_revoking_own_account_access(
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
) -> None:
    use_case = CreateAdminUseCase(user_repository, uow, config, event_publisher)

    with pytest.raises(ValidationError):
        await use_case(
            OWNER,
            CreateAdminDto(
                client_ip="127.0.0.1",
                login="newadmin4",
                name="X",
                permission_revokes=[Permission.OWN_ACCOUNT_MANAGE],
            ),
        )


async def test_create_admin_rejects_duplicate_login(
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
) -> None:
    use_case = CreateAdminUseCase(user_repository, uow, config, event_publisher)
    await use_case(OWNER, CreateAdminDto(client_ip="127.0.0.1", login="dupe", name="First"))

    with pytest.raises(ConflictError):
        await use_case(OWNER, CreateAdminDto(client_ip="127.0.0.1", login="dupe", name="Second"))


async def test_regular_admin_cannot_create_admin(
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
) -> None:
    use_case = CreateAdminUseCase(user_repository, uow, config, event_publisher)

    with pytest.raises(PermissionDeniedError):
        await use_case(ADMIN, CreateAdminDto(client_ip="127.0.0.1", login="x", name="x"))


async def test_regular_user_cannot_create_admin(
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
) -> None:
    use_case = CreateAdminUseCase(user_repository, uow, config, event_publisher)

    with pytest.raises(PermissionDeniedError):
        await use_case(REGULAR_USER, CreateAdminDto(client_ip="127.0.0.1", login="x", name="x"))


async def test_owner_can_promote_existing_user_by_email(
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
) -> None:
    async with uow:
        target = await user_repository.create(
            CreateUserDto(
                name="Client", role=Role.USER, language=Locale.EN, email="client@example.com"
            )
        )
        await uow.commit()

    use_case = PromoteToAdminUseCase(user_repository, uow, config, event_publisher)
    result = await use_case(
        OWNER,
        PromoteToAdminDto(client_ip="127.0.0.1", email="client@example.com", login="client-admin"),
    )
    admin, password = result.admin, result.password

    assert admin.id == target.id
    assert admin.role == Role.ADMIN
    assert admin.login == "client-admin"
    assert len(password) == PASSWORD_MIN_LENGTH


async def test_owner_can_promote_existing_user_by_id(
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
) -> None:
    async with uow:
        target = await user_repository.create(
            CreateUserDto(name="Client", role=Role.USER, language=Locale.EN, telegram_id=840_001)
        )
        await uow.commit()

    use_case = PromoteToAdminUseCase(user_repository, uow, config, event_publisher)
    result = await use_case(
        OWNER, PromoteToAdminDto(client_ip="127.0.0.1", user_id=target.id, login="byid-admin")
    )
    admin, password = result.admin, result.password

    assert admin.id == target.id
    assert admin.role == Role.ADMIN
    assert password is not None


async def test_promote_reuses_existing_password_hash_when_already_set(
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
) -> None:
    existing_hash = await hash_password("existing-password", config.crypt_key.get_secret_value())
    async with uow:
        await user_repository.create(
            CreateUserDto(
                name="Client",
                role=Role.USER,
                language=Locale.EN,
                email="haspassword@example.com",
                password_hash=existing_hash,
            )
        )
        await uow.commit()

    use_case = PromoteToAdminUseCase(user_repository, uow, config, event_publisher)
    result = await use_case(
        OWNER,
        PromoteToAdminDto(
            client_ip="127.0.0.1", email="haspassword@example.com", login="haspw-admin"
        ),
    )
    admin, password = result.admin, result.password

    assert password is None
    assert admin.password_hash == existing_hash


async def test_owner_can_promote_existing_user_by_telegram_username(
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
) -> None:
    async with uow:
        await user_repository.create(
            CreateUserDto(
                name="Client",
                role=Role.USER,
                language=Locale.EN,
                telegram_id=555,
                username="client_tg",
            )
        )
        await uow.commit()

    use_case = PromoteToAdminUseCase(user_repository, uow, config, event_publisher)
    admin = (
        await use_case(
            OWNER,
            PromoteToAdminDto(
                client_ip="127.0.0.1", telegram_username="client_tg", login="client-admin2"
            ),
        )
    ).admin

    assert admin.role == Role.ADMIN


async def test_promote_reuses_existing_login_when_already_set(
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
) -> None:
    async with uow:
        await user_repository.create(
            CreateUserDto(
                name="Client",
                role=Role.USER,
                language=Locale.EN,
                email="haslogin@example.com",
                login="already-set",
            )
        )
        await uow.commit()

    use_case = PromoteToAdminUseCase(user_repository, uow, config, event_publisher)
    admin = (
        await use_case(
            OWNER, PromoteToAdminDto(client_ip="127.0.0.1", email="haslogin@example.com")
        )
    ).admin

    assert admin.login == "already-set"


async def test_promote_requires_login_when_target_has_none(
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
) -> None:
    async with uow:
        await user_repository.create(
            CreateUserDto(
                name="Client", role=Role.USER, language=Locale.EN, email="nologin@example.com"
            )
        )
        await uow.commit()

    use_case = PromoteToAdminUseCase(user_repository, uow, config, event_publisher)

    with pytest.raises(ValidationError):
        await use_case(OWNER, PromoteToAdminDto(client_ip="127.0.0.1", email="nologin@example.com"))


async def test_promote_unknown_user_raises_not_found(
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
) -> None:
    use_case = PromoteToAdminUseCase(user_repository, uow, config, event_publisher)

    with pytest.raises(NotFoundError):
        await use_case(
            OWNER, PromoteToAdminDto(client_ip="127.0.0.1", email="nobody@example.com", login="x")
        )


async def test_promote_already_privileged_user_raises_conflict(
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
) -> None:
    async with uow:
        await user_repository.create(
            CreateUserDto(
                name="Already",
                role=Role.ADMIN,
                language=Locale.EN,
                email="already@example.com",
                login="already",
            )
        )
        await uow.commit()

    use_case = PromoteToAdminUseCase(user_repository, uow, config, event_publisher)

    with pytest.raises(ConflictError):
        await use_case(OWNER, PromoteToAdminDto(client_ip="127.0.0.1", email="already@example.com"))


async def test_owner_can_update_admin_permissions(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
) -> None:
    create_use_case = CreateAdminUseCase(user_repository, uow, config, event_publisher)
    admin = (
        await create_use_case(
            OWNER, CreateAdminDto(client_ip="127.0.0.1", login="tochange", name="X")
        )
    ).admin

    update_use_case = UpdateAdminUseCase(user_repository, uow, event_publisher, session_repository)
    updated = await update_use_case(
        OWNER,
        UpdateAdminDto(
            client_ip="127.0.0.1",
            user_id=admin.id,
            permission_grants=[Permission.OAUTH_SETTINGS_MANAGE],
        ),
    )

    assert updated.permission_grants == [Permission.OAUTH_SETTINGS_MANAGE]


async def test_revoking_permissions_also_revokes_active_sessions(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
) -> None:
    create_use_case = CreateAdminUseCase(user_repository, uow, config, event_publisher)
    admin = (
        await create_use_case(
            OWNER, CreateAdminDto(client_ip="127.0.0.1", login="tosession", name="X")
        )
    ).admin
    issuer = SessionIssuer(session_repository, uow, config)
    await issuer.issue(admin.id, "127.0.0.1", "pytest")
    assert len(await session_repository.list_active_by_user(admin.id)) == 1

    update_use_case = UpdateAdminUseCase(user_repository, uow, event_publisher, session_repository)
    await update_use_case(
        OWNER,
        UpdateAdminDto(
            client_ip="127.0.0.1",
            user_id=admin.id,
            permission_revokes=[Permission.BOT_SETTINGS_MANAGE],
        ),
    )

    assert await session_repository.list_active_by_user(admin.id) == []


async def test_granting_permissions_alone_does_not_revoke_sessions(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
) -> None:
    create_use_case = CreateAdminUseCase(user_repository, uow, config, event_publisher)
    admin = (
        await create_use_case(
            OWNER, CreateAdminDto(client_ip="127.0.0.1", login="tosession2", name="X")
        )
    ).admin
    issuer = SessionIssuer(session_repository, uow, config)
    await issuer.issue(admin.id, "127.0.0.1", "pytest")

    update_use_case = UpdateAdminUseCase(user_repository, uow, event_publisher, session_repository)
    await update_use_case(
        OWNER,
        UpdateAdminDto(
            client_ip="127.0.0.1",
            user_id=admin.id,
            permission_grants=[Permission.OAUTH_SETTINGS_MANAGE],
        ),
    )

    assert len(await session_repository.list_active_by_user(admin.id)) == 1


async def test_update_admin_omitted_field_leaves_it_unchanged(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
    session: AsyncSession,
) -> None:
    create_use_case = CreateAdminUseCase(user_repository, uow, config, event_publisher)
    admin = (
        await create_use_case(
            OWNER,
            CreateAdminDto(
                client_ip="127.0.0.1",
                login="tochange3",
                name="X",
                permission_grants=[Permission.OAUTH_SETTINGS_MANAGE],
                permission_revokes=[Permission.BOT_SETTINGS_MANAGE],
            ),
        )
    ).admin

    update_use_case = UpdateAdminUseCase(user_repository, uow, event_publisher, session_repository)
    updated = await update_use_case(OWNER, UpdateAdminDto(client_ip="127.0.0.1", user_id=admin.id))

    assert updated.permission_grants == [Permission.OAUTH_SETTINGS_MANAGE]
    assert updated.permission_revokes == [Permission.BOT_SETTINGS_MANAGE]
    rows = await _outbox_rows(session, AdminPermissionsUpdatedEvent.__name__)
    assert len(rows) == 1
    assert rows[0].payload["permission_grants"] is None
    assert rows[0].payload["permission_revokes"] is None


async def test_update_admin_explicit_empty_list_clears_overrides(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
) -> None:
    create_use_case = CreateAdminUseCase(user_repository, uow, config, event_publisher)
    admin = (
        await create_use_case(
            OWNER,
            CreateAdminDto(
                client_ip="127.0.0.1",
                login="tochange4",
                name="X",
                permission_grants=[Permission.OAUTH_SETTINGS_MANAGE],
                permission_revokes=[Permission.BOT_SETTINGS_MANAGE],
            ),
        )
    ).admin

    update_use_case = UpdateAdminUseCase(user_repository, uow, event_publisher, session_repository)
    updated = await update_use_case(
        OWNER,
        UpdateAdminDto(
            client_ip="127.0.0.1", user_id=admin.id, permission_grants=[], permission_revokes=[]
        ),
    )

    assert updated.permission_grants == []
    assert updated.permission_revokes == []


async def test_update_admin_rejects_manage_admins_grant(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
) -> None:
    create_use_case = CreateAdminUseCase(user_repository, uow, config, event_publisher)
    admin = (
        await create_use_case(
            OWNER, CreateAdminDto(client_ip="127.0.0.1", login="tochange2", name="X")
        )
    ).admin

    update_use_case = UpdateAdminUseCase(user_repository, uow, event_publisher, session_repository)

    with pytest.raises(ValidationError):
        await update_use_case(
            OWNER,
            UpdateAdminDto(
                client_ip="127.0.0.1",
                user_id=admin.id,
                permission_grants=[Permission.ADMINS_MANAGE],
            ),
        )


async def test_update_admin_unknown_id_raises_not_found(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    update_use_case = UpdateAdminUseCase(user_repository, uow, event_publisher, session_repository)

    with pytest.raises(NotFoundError):
        await update_use_case(OWNER, UpdateAdminDto(client_ip="127.0.0.1", user_id=999_999))


async def test_update_admin_rejects_targeting_owner(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    # OWNER here is an in-memory UserDto with no row, which would give
    # NotFoundError instead of ConflictError, so a real OWNER row is created
    async with uow:
        owner_row = await user_repository.create(
            CreateUserDto(login="realowner", name="realowner", role=Role.OWNER, language=Locale.EN)
        )
        await uow.commit()

    update_use_case = UpdateAdminUseCase(user_repository, uow, event_publisher, session_repository)

    with pytest.raises(ConflictError):
        await update_use_case(OWNER, UpdateAdminDto(client_ip="127.0.0.1", user_id=owner_row.id))


async def test_update_admin_rejects_targeting_regular_user(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    async with uow:
        target = await user_repository.create(
            CreateUserDto(name="Regular", role=Role.USER, language=Locale.EN)
        )
        await uow.commit()

    update_use_case = UpdateAdminUseCase(user_repository, uow, event_publisher, session_repository)

    with pytest.raises(ConflictError):
        await update_use_case(OWNER, UpdateAdminDto(client_ip="127.0.0.1", user_id=target.id))


async def test_owner_can_demote_admin(
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
    session_repository: SessionRepository,
    passkey_repository: PasskeyRepository,
) -> None:
    create_use_case = CreateAdminUseCase(user_repository, uow, config, event_publisher)
    admin = (
        await create_use_case(
            OWNER,
            CreateAdminDto(
                client_ip="127.0.0.1",
                login="todemote",
                name="X",
                permission_grants=[Permission.EVENT_LOG_VIEW],
            ),
        )
    ).admin

    demote_use_case = DemoteAdminUseCase(
        user_repository, uow, event_publisher, session_repository, passkey_repository
    )
    demoted = await demote_use_case(OWNER, DemoteAdminDto(user_id=admin.id, client_ip="127.0.0.1"))

    assert demoted.role == Role.USER
    assert demoted.login is None
    assert demoted.password_hash is None
    assert demoted.permission_grants is None
    assert demoted.permission_revokes is None
    assert demoted.ip_allowlist is None


async def test_demote_admin_unknown_id_raises_not_found(
    user_repository: UserRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    session_repository: SessionRepository,
    passkey_repository: PasskeyRepository,
) -> None:
    demote_use_case = DemoteAdminUseCase(
        user_repository, uow, event_publisher, session_repository, passkey_repository
    )

    with pytest.raises(NotFoundError):
        await demote_use_case(OWNER, DemoteAdminDto(user_id=999_999, client_ip="127.0.0.1"))


async def test_demote_admin_rejects_targeting_owner(
    user_repository: UserRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    session_repository: SessionRepository,
    passkey_repository: PasskeyRepository,
) -> None:
    async with uow:
        owner_row = await user_repository.create(
            CreateUserDto(
                login="realowner2", name="realowner2", role=Role.OWNER, language=Locale.EN
            )
        )
        await uow.commit()

    demote_use_case = DemoteAdminUseCase(
        user_repository, uow, event_publisher, session_repository, passkey_repository
    )

    with pytest.raises(ConflictError):
        await demote_use_case(OWNER, DemoteAdminDto(user_id=owner_row.id, client_ip="127.0.0.1"))


async def test_demote_admin_preserves_customer_identity(
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
    session_repository: SessionRepository,
    passkey_repository: PasskeyRepository,
) -> None:
    async with uow:
        await user_repository.create(
            CreateUserDto(
                name="Client",
                role=Role.USER,
                language=Locale.EN,
                telegram_id=777,
                email="client3@example.com",
            )
        )
        await uow.commit()

    promote_use_case = PromoteToAdminUseCase(user_repository, uow, config, event_publisher)
    admin = (
        await promote_use_case(
            OWNER,
            PromoteToAdminDto(
                client_ip="127.0.0.1", email="client3@example.com", login="client3-admin"
            ),
        )
    ).admin

    demote_use_case = DemoteAdminUseCase(
        user_repository, uow, event_publisher, session_repository, passkey_repository
    )
    demoted = await demote_use_case(OWNER, DemoteAdminDto(user_id=admin.id, client_ip="127.0.0.1"))

    assert demoted.telegram_id == 777
    assert demoted.email == "client3@example.com"


async def test_list_admins_returns_admins_and_owner(
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
) -> None:
    async with uow:
        await user_repository.create(
            CreateUserDto(login="owner3", name="owner3", role=Role.OWNER, language=Locale.EN)
        )
        await user_repository.create(
            CreateUserDto(name="Regular", role=Role.USER, language=Locale.EN)
        )
        await uow.commit()

    create_use_case = CreateAdminUseCase(user_repository, uow, config, event_publisher)
    await create_use_case(
        OWNER, CreateAdminDto(client_ip="127.0.0.1", login="listedadmin", name="X")
    )

    list_use_case = ListAdminsUseCase(user_repository, uow)
    admins = await list_use_case(OWNER)

    logins = {a.login for a in admins}
    assert "owner3" in logins
    assert "listedadmin" in logins
    assert "Regular" not in {a.name for a in admins}


async def test_regular_user_cannot_list_admins(
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    list_use_case = ListAdminsUseCase(user_repository, uow)

    with pytest.raises(PermissionDeniedError):
        await list_use_case(REGULAR_USER)


async def test_list_users_excludes_admins_and_owner(
    user_repository: UserRepository,
    uow: UnitOfWork,
    blacklist_repository: BlacklistRepository,
) -> None:
    # USERS_VIEW can be granted to any admin or token, so it never lists staff
    # (ListAdminsUseCase does, behind ADMINS_MANAGE)
    async with uow:
        await user_repository.create(
            CreateUserDto(login="owner10", name="owner10", role=Role.OWNER, language=Locale.EN)
        )
        await user_repository.create(
            CreateUserDto(login="admin10", name="admin10", role=Role.ADMIN, language=Locale.EN)
        )
        await user_repository.create(
            CreateUserDto(name="Regular10", role=Role.USER, language=Locale.EN)
        )
        await uow.commit()

    list_use_case = ListUsersUseCase(user_repository, blacklist_repository, uow)
    users, _total = await list_use_case(OWNER, ListUsersDto())

    names = {u.name for u in users}
    assert "Regular10" in names
    assert "owner10" not in names
    assert "admin10" not in names


async def test_admin_with_view_users_grant_does_not_see_admins_or_owner(
    user_repository: UserRepository,
    uow: UnitOfWork,
    blacklist_repository: BlacklistRepository,
) -> None:
    async with uow:
        await user_repository.create(
            CreateUserDto(login="owner12", name="owner12", role=Role.OWNER, language=Locale.EN)
        )
        await user_repository.create(
            CreateUserDto(login="admin12", name="admin12", role=Role.ADMIN, language=Locale.EN)
        )
        await user_repository.create(
            CreateUserDto(name="Regular12", role=Role.USER, language=Locale.EN)
        )
        await uow.commit()

    granted_admin = ADMIN.model_copy(update={"permission_grants": ["USERS_VIEW"]})
    list_use_case = ListUsersUseCase(user_repository, blacklist_repository, uow)

    users, _total = await list_use_case(granted_admin, ListUsersDto())

    names = {u.name for u in users}
    assert "Regular12" in names
    assert "owner12" not in names
    assert "admin12" not in names


async def test_owner_with_include_staff_sees_admins_and_owner(
    user_repository: UserRepository,
    uow: UnitOfWork,
    blacklist_repository: BlacklistRepository,
) -> None:
    async with uow:
        await user_repository.create(
            CreateUserDto(login="owner13", name="owner13", role=Role.OWNER, language=Locale.EN)
        )
        await user_repository.create(
            CreateUserDto(login="admin13", name="admin13", role=Role.ADMIN, language=Locale.EN)
        )
        await user_repository.create(
            CreateUserDto(name="Regular13", role=Role.USER, language=Locale.EN)
        )
        await uow.commit()

    list_use_case = ListUsersUseCase(user_repository, blacklist_repository, uow)
    users, _total = await list_use_case(OWNER, ListUsersDto(include_staff=True))

    names = {u.name for u in users}
    assert {"Regular13", "owner13", "admin13"} <= names


async def test_admin_with_view_users_grant_cannot_use_include_staff(
    user_repository: UserRepository,
    uow: UnitOfWork,
    blacklist_repository: BlacklistRepository,
) -> None:
    granted_admin = ADMIN.model_copy(update={"permission_grants": ["USERS_VIEW"]})
    list_use_case = ListUsersUseCase(user_repository, blacklist_repository, uow)

    with pytest.raises(PermissionDeniedError):
        await list_use_case(granted_admin, ListUsersDto(include_staff=True))


async def test_admin_with_view_users_revoked_cannot_list_users(
    user_repository: UserRepository,
    uow: UnitOfWork,
    blacklist_repository: BlacklistRepository,
) -> None:
    list_use_case = ListUsersUseCase(user_repository, blacklist_repository, uow)
    revoked_admin = ADMIN.model_copy(update={"permission_revokes": ["USERS_VIEW"]})

    with pytest.raises(PermissionDeniedError):
        await list_use_case(revoked_admin)


async def test_admin_with_view_users_grant_can_list_users(
    user_repository: UserRepository,
    uow: UnitOfWork,
    blacklist_repository: BlacklistRepository,
) -> None:
    async with uow:
        await user_repository.create(
            CreateUserDto(name="Regular11", role=Role.USER, language=Locale.EN)
        )
        await uow.commit()

    granted_admin = ADMIN.model_copy(update={"permission_grants": ["USERS_VIEW"]})
    list_use_case = ListUsersUseCase(user_repository, blacklist_repository, uow)

    everyone, _total = await list_use_case(granted_admin, ListUsersDto())

    assert "Regular11" in {u.name for u in everyone}


async def test_actor_can_set_own_ip_allowlist_including_current_ip(
    user_repository: UserRepository, uow: UnitOfWork
) -> None:
    async with uow:
        actor = await user_repository.create(
            CreateUserDto(login="secowner", name="secowner", role=Role.OWNER, language=Locale.EN)
        )
        await uow.commit()

    use_case = UpdateOwnSecuritySettingsUseCase(user_repository, uow, RecordingEventPublisher())
    updated = await use_case(
        actor,
        UpdateSecuritySettingsDto(ip_allowlist=["10.0.0.5"], client_ip="10.0.0.5"),
    )

    assert updated.ip_allowlist == ["10.0.0.5"]


async def test_actor_can_clear_own_ip_allowlist(
    user_repository: UserRepository, uow: UnitOfWork
) -> None:
    async with uow:
        actor = await user_repository.create(
            CreateUserDto(login="secowner2", name="secowner2", role=Role.OWNER, language=Locale.EN)
        )
        await uow.commit()

    use_case = UpdateOwnSecuritySettingsUseCase(user_repository, uow, RecordingEventPublisher())
    updated = await use_case(
        actor, UpdateSecuritySettingsDto(ip_allowlist=[], client_ip="10.0.0.5")
    )

    assert updated.ip_allowlist == []


async def test_update_own_ip_allowlist_rejects_self_lockout(
    user_repository: UserRepository, uow: UnitOfWork
) -> None:
    async with uow:
        actor = await user_repository.create(
            CreateUserDto(login="secowner3", name="secowner3", role=Role.OWNER, language=Locale.EN)
        )
        await uow.commit()

    use_case = UpdateOwnSecuritySettingsUseCase(user_repository, uow, RecordingEventPublisher())

    with pytest.raises(ValidationError):
        await use_case(
            actor,
            UpdateSecuritySettingsDto(ip_allowlist=["10.0.0.99"], client_ip="10.0.0.5"),
        )


async def test_create_admin_publishes_admin_created_event(
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
    session: AsyncSession,
) -> None:
    use_case = CreateAdminUseCase(user_repository, uow, config, event_publisher)
    admin = (
        await use_case(OWNER, CreateAdminDto(client_ip="127.0.0.1", login="eventtest1", name="X"))
    ).admin

    rows = await _outbox_rows(session, AdminCreatedEvent.__name__)
    assert len(rows) == 1
    assert rows[0].actor_login == OWNER.login
    assert rows[0].payload["target"]["id"] == admin.id


async def test_promote_publishes_admin_promoted_event(
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
    session: AsyncSession,
) -> None:
    async with uow:
        target = await user_repository.create(
            CreateUserDto(
                name="Client", role=Role.USER, language=Locale.EN, email="evt2@example.com"
            )
        )
        await uow.commit()

    use_case = PromoteToAdminUseCase(user_repository, uow, config, event_publisher)
    await use_case(
        OWNER,
        PromoteToAdminDto(client_ip="127.0.0.1", email="evt2@example.com", login="evt2-admin"),
    )

    rows = await _outbox_rows(session, AdminPromotedEvent.__name__)
    assert len(rows) == 1
    assert rows[0].payload["target"]["id"] == target.id


async def test_update_admin_publishes_permissions_updated_event(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
    session: AsyncSession,
) -> None:
    create_use_case = CreateAdminUseCase(user_repository, uow, config, event_publisher)
    admin = (
        await create_use_case(OWNER, CreateAdminDto(client_ip="127.0.0.1", login="evt3", name="X"))
    ).admin

    update_use_case = UpdateAdminUseCase(user_repository, uow, event_publisher, session_repository)
    await update_use_case(
        OWNER,
        UpdateAdminDto(
            client_ip="127.0.0.1",
            user_id=admin.id,
            permission_grants=[Permission.OAUTH_SETTINGS_MANAGE],
        ),
    )

    rows = await _outbox_rows(session, AdminPermissionsUpdatedEvent.__name__)
    assert len(rows) == 1
    assert rows[0].payload["permission_grants"] == ["OAUTH_SETTINGS_MANAGE"]


async def test_demote_admin_publishes_admin_demoted_event(
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
    session: AsyncSession,
    session_repository: SessionRepository,
    passkey_repository: PasskeyRepository,
) -> None:
    create_use_case = CreateAdminUseCase(user_repository, uow, config, event_publisher)
    admin = (
        await create_use_case(OWNER, CreateAdminDto(client_ip="127.0.0.1", login="evt4", name="X"))
    ).admin

    demote_use_case = DemoteAdminUseCase(
        user_repository, uow, event_publisher, session_repository, passkey_repository
    )
    await demote_use_case(OWNER, DemoteAdminDto(user_id=admin.id, client_ip="127.0.0.1"))

    rows = await _outbox_rows(session, AdminDemotedEvent.__name__)
    assert len(rows) == 1
    assert rows[0].payload["target"]["id"] == admin.id


async def test_register_telegram_user_creates_new_user(
    user_repository: UserRepository,
    blacklist_repository: BlacklistRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    use_case = RegisterTelegramUserUseCase(
        user_repository, blacklist_repository, uow, event_publisher
    )

    user = await use_case.system(
        RegisterTelegramUserDto(telegram_id=555, name="Alice", language=Locale.EN)
    )

    assert user.telegram_id == 555
    assert user.role == Role.USER
    assert user.name == "Alice"


async def test_register_telegram_user_returns_existing_user_without_duplicating(
    user_repository: UserRepository,
    blacklist_repository: BlacklistRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    use_case = RegisterTelegramUserUseCase(
        user_repository, blacklist_repository, uow, event_publisher
    )
    data = RegisterTelegramUserDto(telegram_id=777, name="Bob", language=Locale.EN)

    first = await use_case.system(data)
    second = await use_case.system(data)

    assert first.id == second.id


async def test_register_telegram_user_returns_winner_of_registration_race(
    user_repository: UserRepository,
    blacklist_repository: BlacklistRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with uow:
        winner = await user_repository.create(
            CreateUserDto(telegram_id=778, name="Winner", language=Locale.EN)
        )
    # the concurrent update's existence check ran before the winner committed
    real_lookup = user_repository.get_by_telegram_id
    calls = 0

    async def lookup(telegram_id: int) -> Optional[UserDto]:
        nonlocal calls
        calls += 1
        return None if calls == 1 else await real_lookup(telegram_id)

    monkeypatch.setattr(user_repository, "get_by_telegram_id", lookup)
    use_case = RegisterTelegramUserUseCase(
        user_repository, blacklist_repository, uow, event_publisher
    )

    user = await use_case.system(
        RegisterTelegramUserDto(telegram_id=778, name="Loser", language=Locale.EN)
    )

    assert user.id == winner.id


async def test_register_telegram_user_syncs_changed_telegram_profile(
    user_repository: UserRepository,
    blacklist_repository: BlacklistRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    use_case = RegisterTelegramUserUseCase(
        user_repository, blacklist_repository, uow, event_publisher
    )
    created = await use_case.system(
        RegisterTelegramUserDto(telegram_id=779, name="Bob", username="bob", language=Locale.EN)
    )
    assert created.username == "bob"

    renamed = await use_case.system(
        RegisterTelegramUserDto(telegram_id=779, name="Robert", username=None, language=Locale.EN)
    )

    assert renamed.id == created.id
    assert renamed.name == "Robert"
    assert renamed.username is None
    async with uow:
        stored = await user_repository.get_by_telegram_id(779)
    assert stored is not None and stored.name == "Robert" and stored.username is None


async def test_register_telegram_user_keeps_a_staff_name(
    user_repository: UserRepository,
    blacklist_repository: BlacklistRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    async with uow:
        await user_repository.create(
            CreateUserDto(name="Dashboard Name", role=Role.ADMIN, telegram_id=780)
        )
    use_case = RegisterTelegramUserUseCase(
        user_repository, blacklist_repository, uow, event_publisher
    )

    user = await use_case.system(
        RegisterTelegramUserDto(telegram_id=780, name="Tg Name", username="adm", language=Locale.EN)
    )

    assert user.name == "Dashboard Name"
    assert user.username == "adm"


async def test_register_telegram_user_keeps_a_staff_language(
    user_repository: UserRepository,
    blacklist_repository: BlacklistRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    async with uow:
        await user_repository.create(
            CreateUserDto(name="Admin", role=Role.ADMIN, telegram_id=781, language=Locale.RU)
        )
    use_case = RegisterTelegramUserUseCase(
        user_repository, blacklist_repository, uow, event_publisher
    )

    user = await use_case.system(
        RegisterTelegramUserDto(
            telegram_id=781, name="Admin", language=Locale.EN, sync_language=True
        )
    )

    assert user.language == Locale.RU


async def test_register_telegram_user_publishes_event_only_on_creation(
    user_repository: UserRepository,
    blacklist_repository: BlacklistRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    session: AsyncSession,
) -> None:
    use_case = RegisterTelegramUserUseCase(
        user_repository, blacklist_repository, uow, event_publisher
    )
    data = RegisterTelegramUserDto(telegram_id=888, name="Carol", language=Locale.EN)

    created = await use_case.system(data)
    await use_case.system(data)

    rows = await _outbox_rows(session, TelegramUserRegisteredEvent.__name__)
    assert len(rows) == 1
    assert rows[0].payload["user"]["id"] == created.id


async def test_register_telegram_user_denies_non_system_actor(
    user_repository: UserRepository,
    blacklist_repository: BlacklistRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    use_case = RegisterTelegramUserUseCase(
        user_repository, blacklist_repository, uow, event_publisher
    )

    with pytest.raises(PermissionDeniedError):
        await use_case(
            REGULAR_USER,
            RegisterTelegramUserDto(telegram_id=999, name="Mallory", language=Locale.EN),
        )


async def test_register_telegram_user_blocks_blacklisted_telegram_id(
    user_repository: UserRepository,
    blacklist_repository: BlacklistRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    session: AsyncSession,
) -> None:
    await blacklist_repository.add_entry(BlacklistKind.TELEGRAM_ID, "1010")
    use_case = RegisterTelegramUserUseCase(
        user_repository, blacklist_repository, uow, event_publisher
    )

    user = await use_case.system(
        RegisterTelegramUserDto(telegram_id=1010, name="Mallory", language=Locale.EN)
    )

    assert user.is_blocked is True

    blocked_rows = await _outbox_rows(session, TelegramRegistrationBlockedEvent.__name__)
    assert len(blocked_rows) == 1
    assert blocked_rows[0].payload["user"]["id"] == user.id

    registered_rows = await _outbox_rows(session, TelegramUserRegisteredEvent.__name__)
    assert not any(row.payload["user"]["id"] == user.id for row in registered_rows)


async def test_register_telegram_user_carries_ad_link_code_on_creation(
    user_repository: UserRepository,
    blacklist_repository: BlacklistRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    session: AsyncSession,
) -> None:
    use_case = RegisterTelegramUserUseCase(
        user_repository, blacklist_repository, uow, event_publisher
    )
    data = RegisterTelegramUserDto(
        telegram_id=1001,
        name="Dave",
        language=Locale.EN,
        ad_link_code="yt-jan",
        referral_code="AB12CD34",
    )

    await use_case.system(data)

    rows = await _outbox_rows(session, TelegramUserRegisteredEvent.__name__)
    assert len(rows) == 1
    assert rows[0].payload["ad_link_code"] == "yt-jan"
    assert rows[0].payload["referral_code"] == "AB12CD34"


async def test_register_telegram_user_existing_user_ignores_ad_link_code(
    user_repository: UserRepository,
    blacklist_repository: BlacklistRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    session: AsyncSession,
) -> None:
    use_case = RegisterTelegramUserUseCase(
        user_repository, blacklist_repository, uow, event_publisher
    )
    first_call = RegisterTelegramUserDto(telegram_id=1002, name="Erin", language=Locale.EN)
    second_call = RegisterTelegramUserDto(
        telegram_id=1002, name="Erin", language=Locale.EN, ad_link_code="late-click"
    )

    await use_case.system(first_call)
    await use_case.system(second_call)

    rows = await _outbox_rows(session, TelegramUserRegisteredEvent.__name__)
    assert len(rows) == 1
    assert rows[0].payload["ad_link_code"] is None


async def test_owner_can_delete_admin(
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
    session_repository,
    passkey_repository,
) -> None:
    subscription_revoker = _NoopRevoker()
    create_use_case = CreateAdminUseCase(user_repository, uow, config, event_publisher)
    admin = (
        await create_use_case(
            OWNER, CreateAdminDto(client_ip="127.0.0.1", login="todelete1", name="X")
        )
    ).admin

    delete_use_case = DeleteAdminUseCase(
        user_repository,
        uow,
        event_publisher,
        subscription_revoker,
        session_repository,
        passkey_repository,
    )
    await delete_use_case(OWNER, DeleteAdminDto(user_id=admin.id, client_ip="127.0.0.1"))

    # soft delete, like a customer's: panel access revoked, the row anonymized
    # and demoted so payment history keeps pointing at it
    deleted = await user_repository.find_by_id(admin.id)
    assert deleted is not None
    assert deleted.deleted_at is not None
    assert deleted.role is Role.USER
    assert deleted.login is None
    assert subscription_revoker.revoked == [admin.id]


async def test_delete_admin_unknown_id_raises_not_found(
    user_repository: UserRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    session_repository,
    passkey_repository,
) -> None:
    subscription_revoker = _NoopRevoker()
    delete_use_case = DeleteAdminUseCase(
        user_repository,
        uow,
        event_publisher,
        subscription_revoker,
        session_repository,
        passkey_repository,
    )

    with pytest.raises(NotFoundError):
        await delete_use_case(OWNER, DeleteAdminDto(user_id=999_999, client_ip="127.0.0.1"))


async def test_delete_admin_rejects_non_admin_target(
    user_repository: UserRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    session_repository,
    passkey_repository,
) -> None:
    subscription_revoker = _NoopRevoker()
    async with uow:
        target = await user_repository.create(
            CreateUserDto(name="Regular12", role=Role.USER, language=Locale.EN)
        )
        await uow.commit()

    delete_use_case = DeleteAdminUseCase(
        user_repository,
        uow,
        event_publisher,
        subscription_revoker,
        session_repository,
        passkey_repository,
    )

    with pytest.raises(ConflictError):
        await delete_use_case(OWNER, DeleteAdminDto(user_id=target.id, client_ip="127.0.0.1"))

    assert await user_repository.find_by_id(target.id) is not None


async def test_delete_admin_rejects_self_delete(
    user_repository: UserRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    session_repository,
    passkey_repository,
) -> None:
    subscription_revoker = _NoopRevoker()
    async with uow:
        self_admin = await user_repository.create(
            CreateUserDto(
                login="selfdeleteadmin", name="selfdeleteadmin", role=Role.ADMIN, language=Locale.EN
            )
        )
        await uow.commit()
    # Fabricated actor: ADMINS_MANAGE is never actually grantable to an ADMIN
    # in production (see permissions.py), but the usecase's defensive
    # self-delete guard must hold regardless of how the permission was
    # obtained.
    self_actor = self_admin.model_copy(update={"permission_grants": ["ADMINS_MANAGE"]})

    delete_use_case = DeleteAdminUseCase(
        user_repository,
        uow,
        event_publisher,
        subscription_revoker,
        session_repository,
        passkey_repository,
    )

    with pytest.raises(ConflictError):
        await delete_use_case(
            self_actor, DeleteAdminDto(user_id=self_admin.id, client_ip="127.0.0.1")
        )

    assert await user_repository.find_by_id(self_admin.id) is not None


async def test_plain_admin_cannot_delete_admin(
    user_repository: UserRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    session_repository,
    passkey_repository,
) -> None:
    subscription_revoker = _NoopRevoker()
    async with uow:
        target = await user_repository.create(
            CreateUserDto(
                login="targetadmin", name="targetadmin", role=Role.ADMIN, language=Locale.EN
            )
        )
        await uow.commit()

    delete_use_case = DeleteAdminUseCase(
        user_repository,
        uow,
        event_publisher,
        subscription_revoker,
        session_repository,
        passkey_repository,
    )

    with pytest.raises(PermissionDeniedError):
        await delete_use_case(ADMIN, DeleteAdminDto(user_id=target.id, client_ip="127.0.0.1"))


async def test_delete_admin_publishes_admin_deleted_event(
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
    session: AsyncSession,
    session_repository,
    passkey_repository,
) -> None:
    subscription_revoker = _NoopRevoker()
    create_use_case = CreateAdminUseCase(user_repository, uow, config, event_publisher)
    admin = (
        await create_use_case(
            OWNER, CreateAdminDto(client_ip="127.0.0.1", login="evtdel1", name="X")
        )
    ).admin

    delete_use_case = DeleteAdminUseCase(
        user_repository,
        uow,
        event_publisher,
        subscription_revoker,
        session_repository,
        passkey_repository,
    )
    await delete_use_case(OWNER, DeleteAdminDto(user_id=admin.id, client_ip="127.0.0.1"))

    rows = await _outbox_rows(session, AdminDeletedEvent.__name__)
    assert len(rows) == 1
    assert rows[0].payload["target"]["login"] == "evtdel1"


async def test_owner_can_delete_regular_user(
    user_repository: UserRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    session_repository: SessionRepository,
    passkey_repository: PasskeyRepository,
) -> None:
    async with uow:
        target = await user_repository.create(
            CreateUserDto(
                name="Regular13",
                telegram_id=13013,
                username="regular13",
                role=Role.USER,
                language=Locale.EN,
            )
        )
        await user_repository.update_fields(target.id, UpdateUserDto(personal_discount=15))
        await uow.commit()

    delete_use_case = DeleteUserUseCase(
        user_repository,
        uow,
        event_publisher,
        _NoopRevoker(),
        session_repository,
        passkey_repository,
    )
    await delete_use_case(OWNER, DeleteUserDto(user_id=target.id, client_ip="127.0.0.1"))

    # soft delete: the row stays for history, personal data is gone
    deleted = await user_repository.find_by_id(target.id)
    assert deleted is not None
    assert deleted.deleted_at is not None
    assert (deleted.name, deleted.telegram_id, deleted.username, deleted.referral_code) == (
        "",
        None,
        None,
        None,
    )
    assert (deleted.personal_discount, deleted.points) == (0, 0)

    visible, _ = await user_repository.list_filtered(roles=[Role.USER])
    assert target.id not in {u.id for u in visible}
    only_deleted, _ = await user_repository.list_filtered(roles=[Role.USER], deleted="only")
    assert [u.id for u in only_deleted] == [target.id]


class _NoopRevoker:
    def __init__(self, error: Optional[Exception] = None) -> None:
        self.revoked: list[int] = []
        self._error = error

    async def revoke_all_by_user(self, user_id: int) -> None:
        if self._error is not None:
            raise self._error
        self.revoked.append(user_id)


async def test_delete_user_revokes_panel_access_first(
    user_repository: UserRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    session_repository: SessionRepository,
    passkey_repository: PasskeyRepository,
) -> None:
    async with uow:
        target = await user_repository.create(
            CreateUserDto(name="Regular14", role=Role.USER, language=Locale.EN)
        )
    revoker = _NoopRevoker()

    await DeleteUserUseCase(
        user_repository,
        uow,
        event_publisher,
        revoker,
        session_repository,
        passkey_repository,
    )(OWNER, DeleteUserDto(user_id=target.id, client_ip="127.0.0.1"))

    assert revoker.revoked == [target.id]


async def test_delete_user_keeps_the_user_when_panel_revocation_fails(
    user_repository: UserRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    session_repository: SessionRepository,
    passkey_repository: PasskeyRepository,
) -> None:
    # the local row must not vanish while VPN access still works
    async with uow:
        target = await user_repository.create(
            CreateUserDto(name="Regular15", role=Role.USER, language=Locale.EN)
        )
    revoker = _NoopRevoker(error=RuntimeError("panel down"))

    with pytest.raises(RuntimeError):
        await DeleteUserUseCase(
            user_repository,
            uow,
            event_publisher,
            revoker,
            session_repository,
            passkey_repository,
        )(OWNER, DeleteUserDto(user_id=target.id, client_ip="127.0.0.1"))

    assert await user_repository.find_by_id(target.id) is not None


async def test_delete_user_unknown_id_raises_not_found(
    user_repository: UserRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    session_repository: SessionRepository,
    passkey_repository: PasskeyRepository,
) -> None:
    delete_use_case = DeleteUserUseCase(
        user_repository,
        uow,
        event_publisher,
        _NoopRevoker(),
        session_repository,
        passkey_repository,
    )

    with pytest.raises(NotFoundError):
        await delete_use_case(OWNER, DeleteUserDto(user_id=999_999, client_ip="127.0.0.1"))


async def test_delete_user_rejects_admin_target(
    user_repository: UserRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    session_repository: SessionRepository,
    passkey_repository: PasskeyRepository,
) -> None:
    async with uow:
        target = await user_repository.create(
            CreateUserDto(
                login="notdeletable", name="notdeletable", role=Role.ADMIN, language=Locale.EN
            )
        )
        await uow.commit()

    delete_use_case = DeleteUserUseCase(
        user_repository,
        uow,
        event_publisher,
        _NoopRevoker(),
        session_repository,
        passkey_repository,
    )

    with pytest.raises(ConflictError):
        await delete_use_case(OWNER, DeleteUserDto(user_id=target.id, client_ip="127.0.0.1"))

    assert await user_repository.find_by_id(target.id) is not None


async def test_delete_user_rejects_self_delete(
    user_repository: UserRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    session_repository: SessionRepository,
    passkey_repository: PasskeyRepository,
) -> None:
    async with uow:
        self_user = await user_repository.create(
            CreateUserDto(name="SelfDeleteUser", role=Role.USER, language=Locale.EN)
        )
        await uow.commit()
    self_actor = self_user.model_copy(update={"permission_grants": ["USERS_DELETE"]})

    delete_use_case = DeleteUserUseCase(
        user_repository,
        uow,
        event_publisher,
        _NoopRevoker(),
        session_repository,
        passkey_repository,
    )

    with pytest.raises(ConflictError):
        await delete_use_case(
            self_actor, DeleteUserDto(user_id=self_user.id, client_ip="127.0.0.1")
        )

    assert await user_repository.find_by_id(self_user.id) is not None


async def test_admin_without_delete_user_grant_is_denied(
    user_repository: UserRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    session_repository: SessionRepository,
    passkey_repository: PasskeyRepository,
) -> None:
    async with uow:
        target = await user_repository.create(
            CreateUserDto(name="Regular14", role=Role.USER, language=Locale.EN)
        )
        await uow.commit()

    delete_use_case = DeleteUserUseCase(
        user_repository,
        uow,
        event_publisher,
        _NoopRevoker(),
        session_repository,
        passkey_repository,
    )

    with pytest.raises(PermissionDeniedError):
        await delete_use_case(ADMIN, DeleteUserDto(user_id=target.id, client_ip="127.0.0.1"))

    assert await user_repository.find_by_id(target.id) is not None


async def test_admin_with_delete_user_grant_can_delete_regular_user(
    user_repository: UserRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    session_repository: SessionRepository,
    passkey_repository: PasskeyRepository,
) -> None:
    async with uow:
        target = await user_repository.create(
            CreateUserDto(name="Regular15", role=Role.USER, language=Locale.EN)
        )
        await uow.commit()

    granted_admin = ADMIN.model_copy(update={"permission_grants": ["USERS_DELETE"]})
    delete_use_case = DeleteUserUseCase(
        user_repository,
        uow,
        event_publisher,
        _NoopRevoker(),
        session_repository,
        passkey_repository,
    )
    await delete_use_case(granted_admin, DeleteUserDto(user_id=target.id, client_ip="127.0.0.1"))

    deleted = await user_repository.find_by_id(target.id)
    assert deleted is not None and deleted.deleted_at is not None


async def test_delete_user_publishes_user_deleted_event(
    user_repository: UserRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    session: AsyncSession,
    session_repository: SessionRepository,
    passkey_repository: PasskeyRepository,
) -> None:
    async with uow:
        target = await user_repository.create(
            CreateUserDto(name="Regular16", role=Role.USER, language=Locale.EN)
        )
        await uow.commit()

    delete_use_case = DeleteUserUseCase(
        user_repository,
        uow,
        event_publisher,
        _NoopRevoker(),
        session_repository,
        passkey_repository,
    )
    await delete_use_case(OWNER, DeleteUserDto(user_id=target.id, client_ip="127.0.0.1"))

    rows = await _outbox_rows(session, UserDeletedEvent.__name__)
    assert len(rows) == 1
    assert rows[0].payload["target"]["id"] == target.id


async def test_delete_admin_twice_raises_not_found_on_second_call(
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
    session_repository,
    passkey_repository,
) -> None:
    subscription_revoker = _NoopRevoker()
    create_use_case = CreateAdminUseCase(user_repository, uow, config, event_publisher)
    admin = (
        await create_use_case(
            OWNER, CreateAdminDto(client_ip="127.0.0.1", login="doubledel1", name="X")
        )
    ).admin

    delete_use_case = DeleteAdminUseCase(
        user_repository,
        uow,
        event_publisher,
        subscription_revoker,
        session_repository,
        passkey_repository,
    )
    await delete_use_case(OWNER, DeleteAdminDto(user_id=admin.id, client_ip="127.0.0.1"))

    with pytest.raises(NotFoundError):
        await delete_use_case(OWNER, DeleteAdminDto(user_id=admin.id, client_ip="127.0.0.1"))


async def test_delete_user_twice_raises_not_found_on_second_call(
    user_repository: UserRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    session_repository: SessionRepository,
    passkey_repository: PasskeyRepository,
) -> None:
    async with uow:
        target = await user_repository.create(
            CreateUserDto(name="Regular17", role=Role.USER, language=Locale.EN)
        )
        await uow.commit()

    delete_use_case = DeleteUserUseCase(
        user_repository,
        uow,
        event_publisher,
        _NoopRevoker(),
        session_repository,
        passkey_repository,
    )
    await delete_use_case(OWNER, DeleteUserDto(user_id=target.id, client_ip="127.0.0.1"))

    with pytest.raises(NotFoundError):
        await delete_use_case(OWNER, DeleteUserDto(user_id=target.id, client_ip="127.0.0.1"))


async def test_set_user_discount_updates_the_user(
    user_repository: UserRepository, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    async with uow:
        target = await user_repository.create(
            CreateUserDto(name="target", role=Role.USER, language=Locale.EN)
        )
        await uow.commit()

    use_case = SetUserDiscountUseCase(user_repository, uow, event_publisher)
    result = await use_case(
        OWNER, SetUserDiscountDto(user_id=target.id, personal_discount=50, client_ip="127.0.0.1")
    )

    assert result.personal_discount == 50


async def test_set_user_discount_publishes_an_event_per_changed_discount(
    user_repository: UserRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    session: AsyncSession,
) -> None:
    async with uow:
        target = await user_repository.create(
            CreateUserDto(name="discount-events", role=Role.USER, language=Locale.EN)
        )
        await user_repository.update_fields(target.id, UpdateUserDto(personal_discount=5))
        await uow.commit()

    use_case = SetUserDiscountUseCase(user_repository, uow, event_publisher)
    result = await use_case(
        OWNER,
        SetUserDiscountDto(
            user_id=target.id, personal_discount=5, purchase_discount=20, client_ip="127.0.0.1"
        ),
    )

    assert (result.personal_discount, result.purchase_discount) == (5, 20)
    # personal_discount was already 5: no change, no event
    assert await _outbox_rows(session, UserPersonalDiscountChangedEvent.__name__) == []
    [row] = await _outbox_rows(session, UserPurchaseDiscountChangedEvent.__name__)
    assert row.actor_id == OWNER.id
    assert row.payload["target"]["id"] == target.id
    assert (row.payload["old_percent"], row.payload["new_percent"]) == (0, 20)


async def test_set_user_discount_rejects_out_of_range_percent(
    user_repository: UserRepository, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    async with uow:
        target = await user_repository.create(
            CreateUserDto(name="target2", role=Role.USER, language=Locale.EN)
        )
        await uow.commit()

    use_case = SetUserDiscountUseCase(user_repository, uow, event_publisher)
    with pytest.raises(ValidationError):
        await use_case(
            OWNER,
            SetUserDiscountDto(user_id=target.id, personal_discount=150, client_ip="127.0.0.1"),
        )


async def test_regular_admin_cannot_set_discount_on_staff_account(
    user_repository: UserRepository, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    async with uow:
        target = await user_repository.create(
            CreateUserDto(
                login="staff-target", name="staff-target", role=Role.ADMIN, language=Locale.EN
            )
        )
        await uow.commit()

    granted_admin = ADMIN.model_copy(update={"permission_grants": ["USERS_DISCOUNT_MANAGE"]})
    use_case = SetUserDiscountUseCase(user_repository, uow, event_publisher)

    with pytest.raises(NotFoundError):
        await use_case(
            granted_admin,
            SetUserDiscountDto(user_id=target.id, personal_discount=10, client_ip="127.0.0.1"),
        )


async def test_owner_can_set_discount_on_staff_account(
    user_repository: UserRepository, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    async with uow:
        target = await user_repository.create(
            CreateUserDto(
                login="staff-target2", name="staff-target2", role=Role.ADMIN, language=Locale.EN
            )
        )
        await uow.commit()

    use_case = SetUserDiscountUseCase(user_repository, uow, event_publisher)
    result = await use_case(
        OWNER, SetUserDiscountDto(user_id=target.id, personal_discount=10, client_ip="127.0.0.1")
    )

    assert result.personal_discount == 10


async def test_demote_admin_revokes_sessions_and_passkeys(
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
    session_repository: SessionRepository,
    passkey_repository: PasskeyRepository,
) -> None:
    create_use_case = CreateAdminUseCase(user_repository, uow, config, event_publisher)
    admin = (
        await create_use_case(
            OWNER,
            CreateAdminDto(
                client_ip="127.0.0.1",
                login="losesaccess",
                name="X",
                permission_grants=[Permission.EVENT_LOG_VIEW],
            ),
        )
    ).admin
    async with uow:
        await session_repository.create(
            CreateSessionDto(
                user_id=admin.id,
                refresh_token_hash=hash_refresh_token("still-valid"),
                ip_address="203.0.113.1",
                user_agent="pytest",
                expires_at=datetime_now() + timedelta(days=30),
                audience=SessionAudience.DASHBOARD,
            )
        )
        await passkey_repository.create(
            CreatePasskeyCredentialDto(
                user_id=admin.id,
                credential_id="cred-demote",
                public_key=b"pubkey",
                sign_count=0,
                transports=None,
                device_type="single_device",
                backed_up=False,
                name="Laptop",
            )
        )

    demote_use_case = DemoteAdminUseCase(
        user_repository, uow, event_publisher, session_repository, passkey_repository
    )
    await demote_use_case(OWNER, DemoteAdminDto(user_id=admin.id, client_ip="127.0.0.1"))

    assert await session_repository.list_active_by_user(admin.id) == []
    assert await passkey_repository.list_by_user(admin.id) == []


async def test_block_user_demotes_an_admin_before_blocking(
    user_repository: UserRepository,
    blacklist_repository: BlacklistRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
    session_repository: SessionRepository,
    passkey_repository: PasskeyRepository,
) -> None:
    create_use_case = CreateAdminUseCase(user_repository, uow, config, event_publisher)
    admin = (
        await create_use_case(
            OWNER,
            CreateAdminDto(client_ip="127.0.0.1", login="toblock", name="X", permission_grants=[]),
        )
    ).admin
    async with uow:
        await session_repository.create(
            CreateSessionDto(
                user_id=admin.id,
                refresh_token_hash=hash_refresh_token("blocked-admin"),
                ip_address="203.0.113.1",
                user_agent="pytest",
                expires_at=datetime_now() + timedelta(days=30),
                audience=SessionAudience.DASHBOARD,
            )
        )
        await passkey_repository.create(
            CreatePasskeyCredentialDto(
                user_id=admin.id,
                credential_id="cred-block",
                public_key=b"pubkey",
                sign_count=0,
                transports=None,
                device_type="single_device",
                backed_up=False,
                name="Laptop",
            )
        )

    use_case = BlockUserUseCase(
        user_repository,
        blacklist_repository,
        uow,
        event_publisher,
        session_repository,
        passkey_repository,
    )
    blocked = await use_case(OWNER, BlockUserDto(user_id=admin.id, client_ip="127.0.0.1"))

    assert (blocked.role, blocked.is_blocked, blocked.login) == (Role.USER, True, None)
    assert await session_repository.list_active_by_user(admin.id) == []
    assert await passkey_repository.list_by_user(admin.id) == []


async def test_block_user_allows_an_api_token_actor_to_block_a_plain_user(
    user_repository: UserRepository,
    blacklist_repository: BlacklistRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    session_repository: SessionRepository,
    passkey_repository: PasskeyRepository,
) -> None:
    # An API token authenticates as a synthetic actor with Role.USER; the
    # guard must key on the target being staff, not on outranking them.
    token_actor = SyntheticActor(
        id=0,
        role=Role.USER,
        name="API Token: ops",
        is_privileged=True,
        log="[api_token:ops]",
        permission_grants=[Permission.USERS_BLOCK.value],
    )
    async with uow:
        target = await user_repository.create(CreateUserDto(name="customer", telegram_id=9100))

    use_case = BlockUserUseCase(
        user_repository,
        blacklist_repository,
        uow,
        event_publisher,
        session_repository,
        passkey_repository,
    )
    blocked = await use_case(token_actor, BlockUserDto(user_id=target.id, client_ip="127.0.0.1"))

    assert blocked.is_blocked is True


async def test_block_user_treats_an_anonymized_account_as_missing(
    user_repository: UserRepository,
    blacklist_repository: BlacklistRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    session_repository: SessionRepository,
    passkey_repository: PasskeyRepository,
) -> None:
    async with uow:
        target = await user_repository.create(CreateUserDto(name="gone", telegram_id=9101))
        await user_repository.anonymize(target.id)

    use_case = BlockUserUseCase(
        user_repository,
        blacklist_repository,
        uow,
        event_publisher,
        session_repository,
        passkey_repository,
    )

    with pytest.raises(NotFoundError):
        await use_case(OWNER, BlockUserDto(user_id=target.id, client_ip="127.0.0.1"))


async def test_block_user_still_refuses_an_api_token_against_staff(
    user_repository: UserRepository,
    blacklist_repository: BlacklistRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
    session_repository: SessionRepository,
    passkey_repository: PasskeyRepository,
) -> None:
    token_actor = SyntheticActor(
        id=0,
        role=Role.USER,
        name="API Token: ops",
        is_privileged=True,
        log="[api_token:ops]",
        permission_grants=[Permission.USERS_BLOCK.value],
    )
    create_use_case = CreateAdminUseCase(user_repository, uow, config, event_publisher)
    admin = (
        await create_use_case(
            OWNER,
            CreateAdminDto(
                client_ip="127.0.0.1", login="staffmember", name="X", permission_grants=[]
            ),
        )
    ).admin

    use_case = BlockUserUseCase(
        user_repository,
        blacklist_repository,
        uow,
        event_publisher,
        session_repository,
        passkey_repository,
    )
    with pytest.raises(NotFoundError):
        await use_case(token_actor, BlockUserDto(user_id=admin.id, client_ip="127.0.0.1"))


async def test_list_users_filters_blocked_by_origin(
    user_repository: UserRepository, blacklist_repository: BlacklistRepository, uow: UnitOfWork
) -> None:
    async with uow:
        manual = await user_repository.create(
            CreateUserDto(name="Manual", telegram_id=5001, role=Role.USER, language=Locale.EN)
        )
        listed = await user_repository.create(
            CreateUserDto(
                name="Listed", email="listed@example.com", role=Role.USER, language=Locale.EN
            )
        )
        await user_repository.create(
            CreateUserDto(name="Unblocked", telegram_id=5003, role=Role.USER, language=Locale.EN)
        )
        await user_repository.set_blocked(manual.id, True)
        await user_repository.set_blocked(listed.id, True)
        await blacklist_repository.add_entry(BlacklistKind.TELEGRAM_ID, "5001")
        await blacklist_repository.add_entry(BlacklistKind.TELEGRAM_ID, "5003")
        source = await blacklist_repository.add_source(
            AddBlacklistSourceDto(url="https://example.com/list.txt")
        )
        await blacklist_repository.replace_source_lists(
            source.id, ParsedSourceList(emails=["listed@example.com"]), error=None
        )
        await uow.commit()
    list_use_case = ListUsersUseCase(user_repository, blacklist_repository, uow)

    by_manual, _ = await list_use_case(OWNER, ListUsersDto(blocked_by="manual"))
    assert [u.name for u in by_manual] == ["Manual"]

    by_lists, total = await list_use_case(OWNER, ListUsersDto(blocked_by="lists"))
    assert [u.name for u in by_lists] == ["Listed"]
    assert total == 1


async def _promote_while(
    monkeypatch: pytest.MonkeyPatch,
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
    meanwhile: dict[str, object],
) -> None:
    async with uow:
        target = await user_repository.create(
            CreateUserDto(name="Client", role=Role.USER, language=Locale.EN, telegram_id=840_777)
        )
    real_hash = promote_to_admin_module.hash_password

    async def hash_while_the_target_changes(password: str, pepper: str) -> str:
        # another request lands between the check and the write
        async with uow:
            await user_repository.session.execute(
                update(User).where(User.id == target.id).values(**meanwhile)
            )
        return await real_hash(password, pepper)

    monkeypatch.setattr(promote_to_admin_module, "hash_password", hash_while_the_target_changes)
    await PromoteToAdminUseCase(user_repository, uow, config, event_publisher)(
        OWNER, PromoteToAdminDto(client_ip="127.0.0.1", user_id=target.id, login="raced-admin")
    )


async def test_promote_refuses_an_account_deleted_while_its_password_was_hashed(
    monkeypatch: pytest.MonkeyPatch,
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
) -> None:
    with pytest.raises(NotFoundError):
        await _promote_while(
            monkeypatch,
            user_repository,
            uow,
            config,
            event_publisher,
            {"deleted_at": datetime_now()},
        )


async def test_promote_refuses_an_account_promoted_while_its_password_was_hashed(
    monkeypatch: pytest.MonkeyPatch,
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
) -> None:
    with pytest.raises(ConflictError):
        await _promote_while(
            monkeypatch,
            user_repository,
            uow,
            config,
            event_publisher,
            {"role": Role.ADMIN, "login": "first-admin"},
        )
