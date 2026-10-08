import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.event_outbox import EventOutboxEntry
from app.core.db.models.user import User
from app.core.db.uow import UnitOfWork
from app.core.enums import AccessMode, Locale, Role
from app.core.ports import EventPublisher
from app.modules.settings.dto import UpdateAccessSettingsDto
from app.modules.settings.repository import SettingsRepository
from app.modules.settings.usecases import GetAccessSettingsUseCase, UpdateAccessSettingsUseCase
from app.modules.users.dto import UserDto

_OWNER = UserDto(id=1, name="owner", role=Role.OWNER)


@pytest.fixture(autouse=True)
async def _seed_owner_row(session: AsyncSession) -> None:
    # event_outbox.actor_id is a real FK
    session.add(
        User(
            id=1,
            name="owner",
            telegram_id=1,
            role=Role.OWNER,
            language=Locale.EN,
            is_blocked=False,
        )
    )
    await session.flush()


async def test_access_settings_default_to_open(
    settings_repository: SettingsRepository, uow: UnitOfWork
) -> None:
    settings = await GetAccessSettingsUseCase(settings_repository, uow).system()

    assert settings.mode is AccessMode.PUBLIC
    assert settings.registration_enabled is True
    assert settings.payments_enabled is True


async def test_update_access_settings_patches_only_given_fields(
    settings_repository: SettingsRepository, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    use_case = UpdateAccessSettingsUseCase(settings_repository, uow, event_publisher)

    await use_case(_OWNER, UpdateAccessSettingsDto(mode=AccessMode.INVITED))
    settings = await use_case(_OWNER, UpdateAccessSettingsDto(payments_enabled=False))

    assert settings.mode is AccessMode.INVITED
    assert settings.payments_enabled is False


async def _last_event(session: AsyncSession) -> EventOutboxEntry:
    rows = (await session.scalars(select(EventOutboxEntry).order_by(EventOutboxEntry.id))).all()
    return rows[-1]


async def test_reenabling_payments_is_flagged_on_the_event(
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    session: AsyncSession,
) -> None:
    use_case = UpdateAccessSettingsUseCase(settings_repository, uow, event_publisher)
    await use_case(_OWNER, UpdateAccessSettingsDto(payments_enabled=False))
    assert (await _last_event(session)).payload["payments_reenabled"] is False

    await use_case(_OWNER, UpdateAccessSettingsDto(payments_enabled=True))

    entry = await _last_event(session)
    assert entry.event_type == "AccessSettingsChangedEvent"
    assert entry.payload["payments_reenabled"] is True
    assert entry.payload["changed_fields"] == ["payments_enabled"]


async def test_setting_payments_on_when_already_on_is_not_a_reenable(
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    session: AsyncSession,
) -> None:
    use_case = UpdateAccessSettingsUseCase(settings_repository, uow, event_publisher)

    await use_case(_OWNER, UpdateAccessSettingsDto(payments_enabled=True))

    assert (await _last_event(session)).payload["payments_reenabled"] is False


async def test_patching_mode_to_its_current_value_records_no_change(
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    session: AsyncSession,
) -> None:
    use_case = UpdateAccessSettingsUseCase(settings_repository, uow, event_publisher)

    await use_case(_OWNER, UpdateAccessSettingsDto(mode=AccessMode.PUBLIC))

    assert (await _last_event(session)).payload["changed_fields"] == []
