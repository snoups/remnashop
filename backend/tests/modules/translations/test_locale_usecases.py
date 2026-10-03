import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import AppConfig
from app.core.db.models import EventOutboxEntry
from app.core.db.models.user import User
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale, Role
from app.core.exceptions import (
    PermissionDeniedError,
    ValidationError,
)
from app.core.ports import EventPublisher
from app.modules.settings.repository import SettingsRepository
from app.modules.translations.events import LocaleActivatedEvent, LocaleDeactivatedEvent
from app.modules.translations.repository import TranslationRepository
from app.modules.translations.usecases import (
    AddLocaleUseCase,
    ListActiveLocalesUseCase,
    RemoveLocaleUseCase,
)
from app.modules.users.dto import UserDto
from tests.modules.settings.factories import make_bot_commands_sync

OWNER = UserDto(id=1, login="admin", name="admin", role=Role.OWNER, language=Locale.EN)
REGULAR_USER = UserDto(id=2, name="Bob", role=Role.USER, language=Locale.EN)


@pytest.fixture(autouse=True)
async def _seed_actor_rows(session: AsyncSession) -> None:
    # event_outbox.actor_id is a real FK, and the actor DTOs above have no rows
    for user_id in (1, 2):
        session.add(
            User(
                id=user_id,
                name=f"u{user_id}",
                telegram_id=user_id,
                role=Role.USER,
                language=Locale.EN,
                is_blocked=False,
            )
        )
    await session.flush()


async def test_owner_can_add_and_list_active_locales(
    settings_repository: SettingsRepository,
    translation_repository: TranslationRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    config: AppConfig,
) -> None:
    add_use_case = AddLocaleUseCase(
        translation_repository,
        uow,
        event_publisher,
        make_bot_commands_sync(settings_repository.session, uow, config),
    )
    list_use_case = ListActiveLocalesUseCase(translation_repository, uow)

    await add_use_case(OWNER, Locale.RU)

    assert set(await list_use_case(OWNER)) == {Locale.RU}


async def test_add_locale_copies_english_translations_in_the_same_transaction(
    settings_repository: SettingsRepository,
    translation_repository: TranslationRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    config: AppConfig,
) -> None:
    # The dashboard re-reads the translations as soon as this returns, so the
    # copy cannot wait on a worker task.
    await translation_repository.seed_missing(Locale.EN, "command", "start", "Open the main menu")
    await translation_repository.seed_missing(Locale.EN, "command", "paysupport", "Refunds")
    add_use_case = AddLocaleUseCase(
        translation_repository,
        uow,
        event_publisher,
        make_bot_commands_sync(settings_repository.session, uow, config),
    )

    await add_use_case(OWNER, Locale.RU)

    copied = await translation_repository.get(Locale.RU, "command", "start")
    assert copied is not None
    assert copied.value == "Open the main menu"


async def test_add_locale_keeps_the_translations_of_a_reactivated_locale(
    settings_repository: SettingsRepository,
    translation_repository: TranslationRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    config: AppConfig,
) -> None:
    await translation_repository.seed_missing(Locale.EN, "command", "start", "Open the main menu")
    await translation_repository.seed_missing(Locale.EN, "command", "paysupport", "Refunds")
    await translation_repository.seed_missing(Locale.RU, "command", "start", "Открыть меню")
    add_use_case = AddLocaleUseCase(
        translation_repository,
        uow,
        event_publisher,
        make_bot_commands_sync(settings_repository.session, uow, config),
    )

    await add_use_case(OWNER, Locale.RU)

    kept = await translation_repository.get(Locale.RU, "command", "start")
    assert kept is not None
    assert kept.value == "Открыть меню"


async def test_add_locale_publishes_locale_activated_event(
    settings_repository: SettingsRepository,
    translation_repository: TranslationRepository,
    uow: UnitOfWork,
    session: AsyncSession,
    event_publisher: EventPublisher,
    config: AppConfig,
) -> None:
    add_use_case = AddLocaleUseCase(
        translation_repository,
        uow,
        event_publisher,
        make_bot_commands_sync(settings_repository.session, uow, config),
    )

    await add_use_case(OWNER, Locale.RU)

    row = (
        await session.scalars(
            select(EventOutboxEntry).where(
                EventOutboxEntry.event_type == LocaleActivatedEvent.__name__
            )
        )
    ).one()
    assert row.payload["locale"] == Locale.RU
    assert row.actor_login == OWNER.login


async def test_add_locale_is_idempotent(
    settings_repository: SettingsRepository,
    translation_repository: TranslationRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    config: AppConfig,
) -> None:
    add_use_case = AddLocaleUseCase(
        translation_repository,
        uow,
        event_publisher,
        make_bot_commands_sync(settings_repository.session, uow, config),
    )
    first = await add_use_case(OWNER, Locale.RU)

    assert await add_use_case(OWNER, Locale.RU) == first


async def test_remove_locale_publishes_locale_deactivated_event(
    settings_repository: SettingsRepository,
    translation_repository: TranslationRepository,
    uow: UnitOfWork,
    session: AsyncSession,
    event_publisher: EventPublisher,
    config: AppConfig,
) -> None:
    add_use_case = AddLocaleUseCase(
        translation_repository,
        uow,
        event_publisher,
        make_bot_commands_sync(settings_repository.session, uow, config),
    )
    remove_use_case = RemoveLocaleUseCase(
        translation_repository,
        uow,
        event_publisher,
        make_bot_commands_sync(settings_repository.session, uow, config),
        config,
    )
    await add_use_case(OWNER, Locale.RU)

    await remove_use_case(OWNER, Locale.RU)

    row = (
        await session.scalars(
            select(EventOutboxEntry).where(
                EventOutboxEntry.event_type == LocaleDeactivatedEvent.__name__
            )
        )
    ).one()
    assert row.payload["locale"] == Locale.RU


async def test_remove_locale_rejects_the_default_locale(
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    config: AppConfig,
) -> None:
    remove_use_case = RemoveLocaleUseCase(
        TranslationRepository(settings_repository.session),
        uow,
        event_publisher,
        make_bot_commands_sync(settings_repository.session, uow, config),
        config,
    )

    with pytest.raises(ValidationError):
        await remove_use_case(OWNER, config.default_locale)


async def test_remove_locale_rejects_a_non_en_default_locale(
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    config: AppConfig,
) -> None:
    # The guard has to follow APP_DEFAULT_LOCALE, not a hardcoded `en`: the
    # default locale is the TranslatorHub's root_locale, and losing it crashes
    # the telegram process on startup rather than just dropping a language.
    ru_default = config.model_copy(update={"default_locale": Locale.RU})
    remove_use_case = RemoveLocaleUseCase(
        TranslationRepository(settings_repository.session),
        uow,
        event_publisher,
        make_bot_commands_sync(settings_repository.session, uow, ru_default),
        ru_default,
    )

    with pytest.raises(ValidationError):
        await remove_use_case(OWNER, Locale.RU)


async def test_regular_user_cannot_add_locale(
    settings_repository: SettingsRepository,
    translation_repository: TranslationRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    config: AppConfig,
) -> None:
    add_use_case = AddLocaleUseCase(
        translation_repository,
        uow,
        event_publisher,
        make_bot_commands_sync(settings_repository.session, uow, config),
    )

    with pytest.raises(PermissionDeniedError):
        await add_use_case(REGULAR_USER, Locale.RU)
