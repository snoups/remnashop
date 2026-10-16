from app.core.db.uow import UnitOfWork
from app.core.enums import CabinetSignInMethod, Locale, RegistrationSource, Role
from app.modules.blacklist import BlacklistRepository
from app.modules.users.dto import (
    CreateUserDto,
    RegisterCabinetUserDto,
    RegisterTelegramUserDto,
    RegistrationSnapshotDto,
    UserDto,
)
from app.modules.users.repository import UserRepository
from app.modules.users.usecases import (
    GetUserRegistrationUseCase,
    RegisterCabinetUserUseCase,
    RegisterTelegramUserUseCase,
)
from tests.fakes.events import RecordingEventPublisher

_OWNER = UserDto(id=1, login="owner", name="owner", role=Role.OWNER, language=Locale.EN)
_BOT = RegistrationSnapshotDto(
    source=RegistrationSource.BOT,
    start_payload="ad_summer",
    telegram_language_code="pt-br",
    telegram_is_premium=True,
)


async def test_bot_sign_up_keeps_the_first_snapshot(
    user_repository: UserRepository, blacklist_repository: BlacklistRepository, uow: UnitOfWork
) -> None:
    register = RegisterTelegramUserUseCase(
        user_repository, blacklist_repository, uow, RecordingEventPublisher()
    )
    data = RegisterTelegramUserDto(telegram_id=8801, name="a", language=Locale.EN, snapshot=_BOT)

    user = await register.system(data)
    later = RegistrationSnapshotDto(source=RegistrationSource.BOT, start_payload="ref_x")
    await register.system(
        RegisterTelegramUserDto(telegram_id=8801, name="a", language=Locale.EN, snapshot=later)
    )

    registration = await GetUserRegistrationUseCase(user_repository, uow)(_OWNER, user.id)
    assert registration is not None
    assert registration.start_payload == "ad_summer"
    assert (registration.telegram_language_code, registration.telegram_is_premium) == (
        "pt-br",
        True,
    )


async def test_cabinet_sign_up_records_ip_and_browser(
    user_repository: UserRepository, blacklist_repository: BlacklistRepository, uow: UnitOfWork
) -> None:
    register = RegisterCabinetUserUseCase(
        user_repository, blacklist_repository, uow, RecordingEventPublisher()
    )
    user = await register.system(
        RegisterCabinetUserDto(
            name="b",
            language=Locale.EN,
            method=CabinetSignInMethod.EMAIL,
            email="snap@example.com",
            snapshot=RegistrationSnapshotDto(
                source=RegistrationSource.CABINET_EMAIL,
                ip_address="203.0.113.7",
                user_agent="Mozilla/5.0",
            ),
        )
    )

    registration = await GetUserRegistrationUseCase(user_repository, uow)(_OWNER, user.id)
    assert registration is not None
    assert registration.source is RegistrationSource.CABINET_EMAIL
    assert registration.ip_address == "203.0.113.7"


async def test_older_accounts_have_no_snapshot_and_deletion_erases_it(
    user_repository: UserRepository, uow: UnitOfWork
) -> None:
    old = await user_repository.create(CreateUserDto(name="old", telegram_id=8802))
    fresh = await user_repository.create(CreateUserDto(name="new", telegram_id=8803))
    await user_repository.add_registration(fresh.id, _BOT)
    get = GetUserRegistrationUseCase(user_repository, uow)

    assert await get(_OWNER, old.id) is None
    await user_repository.anonymize(fresh.id)
    assert await get(_OWNER, fresh.id) is None
