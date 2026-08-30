import pytest

from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale, Role
from app.core.event_bus import EventBus
from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError, ValidationError
from app.core.ports import EventPublisher
from app.core.security import hash_password
from app.core.security.password import PASSWORD_MIN_LENGTH
from app.core.security.permissions import Permission
from app.modules.auth.repository import SessionRepository
from app.modules.auth.session_issuer import SessionIssuer
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.events import (
    AdminCreatedEvent,
    AdminDeletedEvent,
    AdminDemotedEvent,
    AdminPermissionsUpdatedEvent,
    AdminPromotedEvent,
    TelegramUserRegisteredEvent,
    UserDeletedEvent,
)
from app.modules.users.repository import UserRepository
from app.modules.users.usecases import (
    CreateAdminDto,
    CreateAdminUseCase,
    DeleteAdminDto,
    DeleteAdminUseCase,
    DeleteUserDto,
    DeleteUserUseCase,
    DemoteAdminDto,
    DemoteAdminUseCase,
    ListAdminsUseCase,
    ListUsersInput,
    ListUsersUseCase,
    PromoteToAdminDto,
    PromoteToAdminUseCase,
    RegisterTelegramUserDto,
    RegisterTelegramUserUseCase,
    UpdateAdminDto,
    UpdateAdminUseCase,
    UpdateOwnSecuritySettingsUseCase,
    UpdateSecuritySettingsDto,
)

OWNER = UserDto(id=1, login="owner", name="owner", role=Role.OWNER, language=Locale.EN)
ADMIN = UserDto(id=2, login="admin", name="admin", role=Role.ADMIN, language=Locale.EN)
REGULAR_USER = UserDto(id=3, name="Bob", role=Role.USER, language=Locale.EN)


async def test_owner_can_create_admin(
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
) -> None:
    use_case = CreateAdminUseCase(user_repository, uow, config, event_publisher)

    admin, password = await use_case(
        OWNER, CreateAdminDto(client_ip="127.0.0.1", login="newadmin", name="New Admin")
    )

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

    admin, _ = await use_case(
        OWNER,
        CreateAdminDto(
            client_ip="127.0.0.1",
            login="newadmin2",
            name="New Admin 2",
            permission_grants=[Permission.OWN_ACCOUNT_MANAGE],
        ),
    )

    assert admin.permission_grants == [Permission.OWN_ACCOUNT_MANAGE]


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
    admin, password = await use_case(
        OWNER,
        PromoteToAdminDto(client_ip="127.0.0.1", email="client@example.com", login="client-admin"),
    )

    assert admin.id == target.id
    assert admin.role == Role.ADMIN
    assert admin.login == "client-admin"
    assert len(password) == PASSWORD_MIN_LENGTH


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
    admin, password = await use_case(
        OWNER,
        PromoteToAdminDto(
            client_ip="127.0.0.1", email="haspassword@example.com", login="haspw-admin"
        ),
    )

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
    admin, _ = await use_case(
        OWNER,
        PromoteToAdminDto(
            client_ip="127.0.0.1", telegram_username="client_tg", login="client-admin2"
        ),
    )

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
    admin, _ = await use_case(
        OWNER, PromoteToAdminDto(client_ip="127.0.0.1", email="haslogin@example.com")
    )

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
    admin, _ = await create_use_case(
        OWNER, CreateAdminDto(client_ip="127.0.0.1", login="tochange", name="X")
    )

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
    admin, _ = await create_use_case(
        OWNER, CreateAdminDto(client_ip="127.0.0.1", login="tosession", name="X")
    )
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
    admin, _ = await create_use_case(
        OWNER, CreateAdminDto(client_ip="127.0.0.1", login="tosession2", name="X")
    )
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
) -> None:
    assert isinstance(event_publisher, EventBus)
    received: list[AdminPermissionsUpdatedEvent] = []

    async def _collect(event: AdminPermissionsUpdatedEvent) -> None:
        received.append(event)

    event_publisher.subscribe(AdminPermissionsUpdatedEvent, _collect)

    create_use_case = CreateAdminUseCase(user_repository, uow, config, event_publisher)
    admin, _ = await create_use_case(
        OWNER,
        CreateAdminDto(
            client_ip="127.0.0.1",
            login="tochange3",
            name="X",
            permission_grants=[Permission.OAUTH_SETTINGS_MANAGE],
            permission_revokes=[Permission.BOT_SETTINGS_MANAGE],
        ),
    )

    update_use_case = UpdateAdminUseCase(user_repository, uow, event_publisher, session_repository)
    updated = await update_use_case(OWNER, UpdateAdminDto(client_ip="127.0.0.1", user_id=admin.id))
    await event_publisher.shutdown()

    assert updated.permission_grants == [Permission.OAUTH_SETTINGS_MANAGE]
    assert updated.permission_revokes == [Permission.BOT_SETTINGS_MANAGE]
    assert len(received) == 1
    assert received[0].permission_grants is None
    assert received[0].permission_revokes is None


async def test_update_admin_explicit_empty_list_clears_overrides(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
) -> None:
    create_use_case = CreateAdminUseCase(user_repository, uow, config, event_publisher)
    admin, _ = await create_use_case(
        OWNER,
        CreateAdminDto(
            client_ip="127.0.0.1",
            login="tochange4",
            name="X",
            permission_grants=[Permission.OAUTH_SETTINGS_MANAGE],
            permission_revokes=[Permission.BOT_SETTINGS_MANAGE],
        ),
    )

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
    admin, _ = await create_use_case(
        OWNER, CreateAdminDto(client_ip="127.0.0.1", login="tochange2", name="X")
    )

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
    # OWNER in these tests is a plain in-memory UserDto (id=1), not a persisted
    # row -- targeting it directly would raise NotFoundError, not the ConflictError
    # this test means to check. Persist a real OWNER row and target that instead.
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
) -> None:
    create_use_case = CreateAdminUseCase(user_repository, uow, config, event_publisher)
    admin, _ = await create_use_case(
        OWNER,
        CreateAdminDto(
            client_ip="127.0.0.1",
            login="todemote",
            name="X",
            permission_grants=[Permission.OWN_ACCOUNT_MANAGE],
        ),
    )

    demote_use_case = DemoteAdminUseCase(user_repository, uow, event_publisher)
    demoted = await demote_use_case(OWNER, DemoteAdminDto(user_id=admin.id, client_ip="127.0.0.1"))

    assert demoted.role == Role.USER
    assert demoted.login is None
    assert demoted.password_hash is None
    assert demoted.permission_grants is None
    assert demoted.permission_revokes is None
    assert demoted.ip_allowlist is None


async def test_demote_admin_unknown_id_raises_not_found(
    user_repository: UserRepository, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    demote_use_case = DemoteAdminUseCase(user_repository, uow, event_publisher)

    with pytest.raises(NotFoundError):
        await demote_use_case(OWNER, DemoteAdminDto(user_id=999_999, client_ip="127.0.0.1"))


async def test_demote_admin_rejects_targeting_owner(
    user_repository: UserRepository, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    async with uow:
        owner_row = await user_repository.create(
            CreateUserDto(
                login="realowner2", name="realowner2", role=Role.OWNER, language=Locale.EN
            )
        )
        await uow.commit()

    demote_use_case = DemoteAdminUseCase(user_repository, uow, event_publisher)

    with pytest.raises(ConflictError):
        await demote_use_case(OWNER, DemoteAdminDto(user_id=owner_row.id, client_ip="127.0.0.1"))


async def test_demote_admin_preserves_customer_identity(
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
                telegram_id=777,
                email="client3@example.com",
            )
        )
        await uow.commit()

    promote_use_case = PromoteToAdminUseCase(user_repository, uow, config, event_publisher)
    admin, _ = await promote_use_case(
        OWNER,
        PromoteToAdminDto(
            client_ip="127.0.0.1", email="client3@example.com", login="client3-admin"
        ),
    )

    demote_use_case = DemoteAdminUseCase(user_repository, uow, event_publisher)
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

    list_use_case = ListAdminsUseCase(user_repository)
    admins = await list_use_case(OWNER)

    logins = {a.login for a in admins}
    assert "owner3" in logins
    assert "listedadmin" in logins
    assert "Regular" not in {a.name for a in admins}


async def test_regular_user_cannot_list_admins(user_repository: UserRepository) -> None:
    list_use_case = ListAdminsUseCase(user_repository)

    with pytest.raises(PermissionDeniedError):
        await list_use_case(REGULAR_USER)


async def test_list_users_returns_every_role(
    user_repository: UserRepository, uow: UnitOfWork
) -> None:
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

    list_use_case = ListUsersUseCase(user_repository)
    users, total = await list_use_case(OWNER, ListUsersInput())

    assert {u.name for u in users} == {"owner10", "admin10", "Regular10"}
    assert total == 3


async def test_admin_with_view_users_grant_sees_every_role(
    user_repository: UserRepository, uow: UnitOfWork
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
    list_use_case = ListUsersUseCase(user_repository)

    users, _total = await list_use_case(granted_admin, ListUsersInput())

    assert {u.name for u in users} == {"owner12", "admin12", "Regular12"}


async def test_admin_without_view_users_grant_cannot_list_users(
    user_repository: UserRepository,
) -> None:
    list_use_case = ListUsersUseCase(user_repository)

    with pytest.raises(PermissionDeniedError):
        await list_use_case(ADMIN)


async def test_admin_with_view_users_grant_can_list_users(
    user_repository: UserRepository, uow: UnitOfWork
) -> None:
    async with uow:
        await user_repository.create(
            CreateUserDto(name="Regular11", role=Role.USER, language=Locale.EN)
        )
        await uow.commit()

    granted_admin = ADMIN.model_copy(update={"permission_grants": ["USERS_VIEW"]})
    list_use_case = ListUsersUseCase(user_repository)

    everyone, _total = await list_use_case(granted_admin, ListUsersInput())

    assert "Regular11" in {u.name for u in everyone}


async def test_actor_can_set_own_ip_allowlist_including_current_ip(
    user_repository: UserRepository, uow: UnitOfWork
) -> None:
    async with uow:
        actor = await user_repository.create(
            CreateUserDto(login="secowner", name="secowner", role=Role.OWNER, language=Locale.EN)
        )
        await uow.commit()

    use_case = UpdateOwnSecuritySettingsUseCase(user_repository, uow)
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

    use_case = UpdateOwnSecuritySettingsUseCase(user_repository, uow)
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

    use_case = UpdateOwnSecuritySettingsUseCase(user_repository, uow)

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
) -> None:
    assert isinstance(event_publisher, EventBus)
    received: list[AdminCreatedEvent] = []

    async def _collect(event: AdminCreatedEvent) -> None:
        received.append(event)

    event_publisher.subscribe(AdminCreatedEvent, _collect)

    use_case = CreateAdminUseCase(user_repository, uow, config, event_publisher)
    admin, _ = await use_case(
        OWNER, CreateAdminDto(client_ip="127.0.0.1", login="eventtest1", name="X")
    )
    await event_publisher.shutdown()

    assert len(received) == 1
    assert received[0].actor == OWNER
    assert received[0].target.id == admin.id


async def test_promote_publishes_admin_promoted_event(
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
) -> None:
    assert isinstance(event_publisher, EventBus)
    async with uow:
        target = await user_repository.create(
            CreateUserDto(
                name="Client", role=Role.USER, language=Locale.EN, email="evt2@example.com"
            )
        )
        await uow.commit()

    received: list[AdminPromotedEvent] = []

    async def _collect(event: AdminPromotedEvent) -> None:
        received.append(event)

    event_publisher.subscribe(AdminPromotedEvent, _collect)

    use_case = PromoteToAdminUseCase(user_repository, uow, config, event_publisher)
    await use_case(
        OWNER,
        PromoteToAdminDto(client_ip="127.0.0.1", email="evt2@example.com", login="evt2-admin"),
    )
    await event_publisher.shutdown()

    assert len(received) == 1
    assert received[0].target.id == target.id


async def test_update_admin_publishes_permissions_updated_event(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
) -> None:
    assert isinstance(event_publisher, EventBus)
    create_use_case = CreateAdminUseCase(user_repository, uow, config, event_publisher)
    admin, _ = await create_use_case(
        OWNER, CreateAdminDto(client_ip="127.0.0.1", login="evt3", name="X")
    )

    received: list[AdminPermissionsUpdatedEvent] = []

    async def _collect(event: AdminPermissionsUpdatedEvent) -> None:
        received.append(event)

    event_publisher.subscribe(AdminPermissionsUpdatedEvent, _collect)

    update_use_case = UpdateAdminUseCase(user_repository, uow, event_publisher, session_repository)
    await update_use_case(
        OWNER,
        UpdateAdminDto(
            client_ip="127.0.0.1",
            user_id=admin.id,
            permission_grants=[Permission.OAUTH_SETTINGS_MANAGE],
        ),
    )
    await event_publisher.shutdown()

    assert len(received) == 1
    assert received[0].permission_grants == ["OAUTH_SETTINGS_MANAGE"]


async def test_demote_admin_publishes_admin_demoted_event(
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
) -> None:
    assert isinstance(event_publisher, EventBus)
    create_use_case = CreateAdminUseCase(user_repository, uow, config, event_publisher)
    admin, _ = await create_use_case(
        OWNER, CreateAdminDto(client_ip="127.0.0.1", login="evt4", name="X")
    )

    received: list[AdminDemotedEvent] = []

    async def _collect(event: AdminDemotedEvent) -> None:
        received.append(event)

    event_publisher.subscribe(AdminDemotedEvent, _collect)

    demote_use_case = DemoteAdminUseCase(user_repository, uow, event_publisher)
    await demote_use_case(OWNER, DemoteAdminDto(user_id=admin.id, client_ip="127.0.0.1"))
    await event_publisher.shutdown()

    assert len(received) == 1
    assert received[0].target.id == admin.id


async def test_register_telegram_user_creates_new_user(
    user_repository: UserRepository, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    use_case = RegisterTelegramUserUseCase(user_repository, uow, event_publisher)

    user = await use_case.system(
        RegisterTelegramUserDto(telegram_id=555, name="Alice", language=Locale.EN)
    )

    assert user.telegram_id == 555
    assert user.role == Role.USER
    assert user.name == "Alice"


async def test_register_telegram_user_returns_existing_user_without_duplicating(
    user_repository: UserRepository, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    use_case = RegisterTelegramUserUseCase(user_repository, uow, event_publisher)
    data = RegisterTelegramUserDto(telegram_id=777, name="Bob", language=Locale.EN)

    first = await use_case.system(data)
    second = await use_case.system(data)

    assert first.id == second.id


async def test_register_telegram_user_publishes_event_only_on_creation(
    user_repository: UserRepository, uow: UnitOfWork
) -> None:
    bus = EventBus()
    received: list[TelegramUserRegisteredEvent] = []

    async def _collect(event: TelegramUserRegisteredEvent) -> None:
        received.append(event)

    bus.subscribe(TelegramUserRegisteredEvent, _collect)

    use_case = RegisterTelegramUserUseCase(user_repository, uow, bus)
    data = RegisterTelegramUserDto(telegram_id=888, name="Carol", language=Locale.EN)

    await use_case.system(data)
    await use_case.system(data)
    await bus.shutdown()

    assert len(received) == 1
    assert received[0].user.telegram_id == 888


async def test_register_telegram_user_denies_non_system_actor(
    user_repository: UserRepository, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    use_case = RegisterTelegramUserUseCase(user_repository, uow, event_publisher)

    with pytest.raises(PermissionDeniedError):
        await use_case(
            REGULAR_USER,
            RegisterTelegramUserDto(telegram_id=999, name="Mallory", language=Locale.EN),
        )


async def test_owner_can_delete_admin(
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
) -> None:
    create_use_case = CreateAdminUseCase(user_repository, uow, config, event_publisher)
    admin, _ = await create_use_case(
        OWNER, CreateAdminDto(client_ip="127.0.0.1", login="todelete1", name="X")
    )

    delete_use_case = DeleteAdminUseCase(user_repository, uow, event_publisher)
    await delete_use_case(OWNER, DeleteAdminDto(user_id=admin.id, client_ip="127.0.0.1"))

    assert await user_repository.get_by_id(admin.id) is None


async def test_delete_admin_unknown_id_raises_not_found(
    user_repository: UserRepository, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    delete_use_case = DeleteAdminUseCase(user_repository, uow, event_publisher)

    with pytest.raises(NotFoundError):
        await delete_use_case(OWNER, DeleteAdminDto(user_id=999_999, client_ip="127.0.0.1"))


async def test_delete_admin_rejects_non_admin_target(
    user_repository: UserRepository, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    async with uow:
        target = await user_repository.create(
            CreateUserDto(name="Regular12", role=Role.USER, language=Locale.EN)
        )
        await uow.commit()

    delete_use_case = DeleteAdminUseCase(user_repository, uow, event_publisher)

    with pytest.raises(ConflictError):
        await delete_use_case(OWNER, DeleteAdminDto(user_id=target.id, client_ip="127.0.0.1"))

    assert await user_repository.get_by_id(target.id) is not None


async def test_delete_admin_rejects_self_delete(
    user_repository: UserRepository, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
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

    delete_use_case = DeleteAdminUseCase(user_repository, uow, event_publisher)

    with pytest.raises(ConflictError):
        await delete_use_case(
            self_actor, DeleteAdminDto(user_id=self_admin.id, client_ip="127.0.0.1")
        )

    assert await user_repository.get_by_id(self_admin.id) is not None


async def test_plain_admin_cannot_delete_admin(
    user_repository: UserRepository, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    async with uow:
        target = await user_repository.create(
            CreateUserDto(
                login="targetadmin", name="targetadmin", role=Role.ADMIN, language=Locale.EN
            )
        )
        await uow.commit()

    delete_use_case = DeleteAdminUseCase(user_repository, uow, event_publisher)

    with pytest.raises(PermissionDeniedError):
        await delete_use_case(ADMIN, DeleteAdminDto(user_id=target.id, client_ip="127.0.0.1"))


async def test_delete_admin_publishes_admin_deleted_event(
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
) -> None:
    assert isinstance(event_publisher, EventBus)
    create_use_case = CreateAdminUseCase(user_repository, uow, config, event_publisher)
    admin, _ = await create_use_case(
        OWNER, CreateAdminDto(client_ip="127.0.0.1", login="evtdel1", name="X")
    )

    received: list[AdminDeletedEvent] = []

    async def _collect(event: AdminDeletedEvent) -> None:
        received.append(event)

    event_publisher.subscribe(AdminDeletedEvent, _collect)

    delete_use_case = DeleteAdminUseCase(user_repository, uow, event_publisher)
    await delete_use_case(OWNER, DeleteAdminDto(user_id=admin.id, client_ip="127.0.0.1"))
    await event_publisher.shutdown()

    assert len(received) == 1
    assert received[0].target.login == "evtdel1"


async def test_owner_can_delete_regular_user(
    user_repository: UserRepository, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    async with uow:
        target = await user_repository.create(
            CreateUserDto(name="Regular13", role=Role.USER, language=Locale.EN)
        )
        await uow.commit()

    delete_use_case = DeleteUserUseCase(user_repository, uow, event_publisher)
    await delete_use_case(OWNER, DeleteUserDto(user_id=target.id, client_ip="127.0.0.1"))

    assert await user_repository.get_by_id(target.id) is None


async def test_delete_user_unknown_id_raises_not_found(
    user_repository: UserRepository, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    delete_use_case = DeleteUserUseCase(user_repository, uow, event_publisher)

    with pytest.raises(NotFoundError):
        await delete_use_case(OWNER, DeleteUserDto(user_id=999_999, client_ip="127.0.0.1"))


async def test_delete_user_rejects_admin_target(
    user_repository: UserRepository, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    async with uow:
        target = await user_repository.create(
            CreateUserDto(
                login="notdeletable", name="notdeletable", role=Role.ADMIN, language=Locale.EN
            )
        )
        await uow.commit()

    delete_use_case = DeleteUserUseCase(user_repository, uow, event_publisher)

    with pytest.raises(ConflictError):
        await delete_use_case(OWNER, DeleteUserDto(user_id=target.id, client_ip="127.0.0.1"))

    assert await user_repository.get_by_id(target.id) is not None


async def test_delete_user_rejects_self_delete(
    user_repository: UserRepository, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    async with uow:
        self_user = await user_repository.create(
            CreateUserDto(name="SelfDeleteUser", role=Role.USER, language=Locale.EN)
        )
        await uow.commit()
    self_actor = self_user.model_copy(update={"permission_grants": ["USERS_DELETE"]})

    delete_use_case = DeleteUserUseCase(user_repository, uow, event_publisher)

    with pytest.raises(ConflictError):
        await delete_use_case(
            self_actor, DeleteUserDto(user_id=self_user.id, client_ip="127.0.0.1")
        )

    assert await user_repository.get_by_id(self_user.id) is not None


async def test_admin_without_delete_user_grant_is_denied(
    user_repository: UserRepository, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    async with uow:
        target = await user_repository.create(
            CreateUserDto(name="Regular14", role=Role.USER, language=Locale.EN)
        )
        await uow.commit()

    delete_use_case = DeleteUserUseCase(user_repository, uow, event_publisher)

    with pytest.raises(PermissionDeniedError):
        await delete_use_case(ADMIN, DeleteUserDto(user_id=target.id, client_ip="127.0.0.1"))

    assert await user_repository.get_by_id(target.id) is not None


async def test_admin_with_delete_user_grant_can_delete_regular_user(
    user_repository: UserRepository, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    async with uow:
        target = await user_repository.create(
            CreateUserDto(name="Regular15", role=Role.USER, language=Locale.EN)
        )
        await uow.commit()

    granted_admin = ADMIN.model_copy(update={"permission_grants": ["USERS_DELETE"]})
    delete_use_case = DeleteUserUseCase(user_repository, uow, event_publisher)
    await delete_use_case(granted_admin, DeleteUserDto(user_id=target.id, client_ip="127.0.0.1"))

    assert await user_repository.get_by_id(target.id) is None


async def test_delete_user_publishes_user_deleted_event(
    user_repository: UserRepository, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    assert isinstance(event_publisher, EventBus)
    async with uow:
        target = await user_repository.create(
            CreateUserDto(name="Regular16", role=Role.USER, language=Locale.EN, telegram_id=555)
        )
        await uow.commit()

    received: list[UserDeletedEvent] = []

    async def _collect(event: UserDeletedEvent) -> None:
        received.append(event)

    event_publisher.subscribe(UserDeletedEvent, _collect)

    delete_use_case = DeleteUserUseCase(user_repository, uow, event_publisher)
    await delete_use_case(OWNER, DeleteUserDto(user_id=target.id, client_ip="127.0.0.1"))
    await event_publisher.shutdown()

    assert len(received) == 1
    assert received[0].target.telegram_id == 555


async def test_delete_admin_twice_raises_not_found_on_second_call(
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
) -> None:
    create_use_case = CreateAdminUseCase(user_repository, uow, config, event_publisher)
    admin, _ = await create_use_case(
        OWNER, CreateAdminDto(client_ip="127.0.0.1", login="doubledel1", name="X")
    )

    delete_use_case = DeleteAdminUseCase(user_repository, uow, event_publisher)
    await delete_use_case(OWNER, DeleteAdminDto(user_id=admin.id, client_ip="127.0.0.1"))

    with pytest.raises(NotFoundError):
        await delete_use_case(OWNER, DeleteAdminDto(user_id=admin.id, client_ip="127.0.0.1"))


async def test_delete_user_twice_raises_not_found_on_second_call(
    user_repository: UserRepository, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    async with uow:
        target = await user_repository.create(
            CreateUserDto(name="Regular17", role=Role.USER, language=Locale.EN)
        )
        await uow.commit()

    delete_use_case = DeleteUserUseCase(user_repository, uow, event_publisher)
    await delete_use_case(OWNER, DeleteUserDto(user_id=target.id, client_ip="127.0.0.1"))

    with pytest.raises(NotFoundError):
        await delete_use_case(OWNER, DeleteUserDto(user_id=target.id, client_ip="127.0.0.1"))
