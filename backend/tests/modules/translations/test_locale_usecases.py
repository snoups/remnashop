from typing import Optional

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models import EventOutboxEntry
from app.core.db.models.user import User
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale, PaymentOutcome, Role
from app.core.exceptions import (
    PermissionDeniedError,
    ValidationError,
)
from app.core.ports import EventPublisher
from app.modules.settings.repository import SettingsRepository
from app.modules.translations.events import (
    DefaultLocaleChangedEvent,
    LocaleActivatedEvent,
    LocaleDeactivatedEvent,
)
from app.modules.translations.repository import TranslationRepository
from app.modules.translations.usecases import (
    AddLocaleUseCase,
    ListActiveLocalesUseCase,
    RemoveLocaleUseCase,
    SetDefaultLocaleUseCase,
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
) -> None:
    add_use_case = AddLocaleUseCase(
        translation_repository,
        uow,
        event_publisher,
        make_bot_commands_sync(settings_repository.session, uow),
    )
    list_use_case = ListActiveLocalesUseCase(translation_repository, uow)

    await add_use_case(OWNER, Locale.RU)

    assert set((await list_use_case(OWNER)).active) == {Locale.RU}


async def test_add_locale_copies_english_translations_in_the_same_transaction(
    settings_repository: SettingsRepository,
    translation_repository: TranslationRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    # The dashboard re-reads the translations as soon as this returns, so the
    # copy cannot wait on a worker task.
    await translation_repository.seed_missing(Locale.EN, "command", "start", "Open the main menu")
    await translation_repository.seed_missing(Locale.EN, "command", "paysupport", "Refunds")
    add_use_case = AddLocaleUseCase(
        translation_repository,
        uow,
        event_publisher,
        make_bot_commands_sync(settings_repository.session, uow),
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
) -> None:
    await translation_repository.seed_missing(Locale.EN, "command", "start", "Open the main menu")
    await translation_repository.seed_missing(Locale.EN, "command", "paysupport", "Refunds")
    await translation_repository.seed_missing(Locale.RU, "command", "start", "Открыть меню")
    add_use_case = AddLocaleUseCase(
        translation_repository,
        uow,
        event_publisher,
        make_bot_commands_sync(settings_repository.session, uow),
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
) -> None:
    add_use_case = AddLocaleUseCase(
        translation_repository,
        uow,
        event_publisher,
        make_bot_commands_sync(settings_repository.session, uow),
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
) -> None:
    add_use_case = AddLocaleUseCase(
        translation_repository,
        uow,
        event_publisher,
        make_bot_commands_sync(settings_repository.session, uow),
    )
    first = await add_use_case(OWNER, Locale.RU)

    assert await add_use_case(OWNER, Locale.RU) == first


async def test_remove_locale_publishes_locale_deactivated_event(
    settings_repository: SettingsRepository,
    translation_repository: TranslationRepository,
    uow: UnitOfWork,
    session: AsyncSession,
    event_publisher: EventPublisher,
) -> None:
    add_use_case = AddLocaleUseCase(
        translation_repository,
        uow,
        event_publisher,
        make_bot_commands_sync(settings_repository.session, uow),
    )
    remove_use_case = RemoveLocaleUseCase(
        translation_repository,
        uow,
        event_publisher,
        make_bot_commands_sync(settings_repository.session, uow),
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


class _RecordingSignals:
    def __init__(self) -> None:
        self.restarts = 0

    async def restart(self) -> None:
        self.restarts += 1

    async def dialogs_changed(self) -> None: ...

    async def translation_changed(
        self, locale: Locale, message_id: str, attribute_id: str, value: str
    ) -> None: ...

    async def payment_outcome(
        self, telegram_id: int, order_id: int, outcome: PaymentOutcome
    ) -> int:
        return 0


class _RecordingBanner:
    def __init__(self) -> None:
        self.seeded: list[Locale] = []

    async def ensure(self, locale: Locale) -> None:
        self.seeded.append(locale)


def _locale_use_cases(
    translation_repository: TranslationRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    signals: Optional[_RecordingSignals] = None,
    banner: Optional[_RecordingBanner] = None,
) -> tuple[AddLocaleUseCase, RemoveLocaleUseCase, SetDefaultLocaleUseCase]:
    bot_commands = make_bot_commands_sync(translation_repository.session, uow)
    return (
        AddLocaleUseCase(translation_repository, uow, event_publisher, bot_commands),
        RemoveLocaleUseCase(translation_repository, uow, event_publisher, bot_commands),
        SetDefaultLocaleUseCase(
            translation_repository,
            uow,
            event_publisher,
            bot_commands,
            signals or _RecordingSignals(),
            banner or _RecordingBanner(),
        ),
    )


async def test_remove_locale_rejects_the_default_locale(
    translation_repository: TranslationRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    add, remove, _ = _locale_use_cases(translation_repository, uow, event_publisher)
    await add(OWNER, Locale.EN)
    await translation_repository.set_default_locale(Locale.EN)

    with pytest.raises(ValidationError):
        await remove(OWNER, Locale.EN)


async def test_set_default_locale_moves_the_removal_guard(
    translation_repository: TranslationRepository,
    uow: UnitOfWork,
    session: AsyncSession,
    event_publisher: EventPublisher,
) -> None:
    add, remove, set_default = _locale_use_cases(translation_repository, uow, event_publisher)
    await add(OWNER, Locale.EN)
    await add(OWNER, Locale.RU)
    await translation_repository.set_default_locale(Locale.EN)

    locales = await set_default(OWNER, Locale.RU)

    assert locales.default == Locale.RU
    assert set((await remove(OWNER, Locale.EN)).active) == {Locale.RU}
    with pytest.raises(ValidationError):
        await remove(OWNER, Locale.RU)
    row = (
        await session.scalars(
            select(EventOutboxEntry).where(
                EventOutboxEntry.event_type == DefaultLocaleChangedEvent.__name__
            )
        )
    ).one()
    assert row.payload["locale"] == Locale.RU


async def test_set_default_locale_rejects_an_inactive_locale(
    translation_repository: TranslationRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    _, _, set_default = _locale_use_cases(translation_repository, uow, event_publisher)

    with pytest.raises(ValidationError):
        await set_default(OWNER, Locale.DE)


async def test_regular_user_cannot_set_default_locale(
    translation_repository: TranslationRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    add, _, set_default = _locale_use_cases(translation_repository, uow, event_publisher)
    await add(OWNER, Locale.RU)

    with pytest.raises(PermissionDeniedError):
        await set_default(REGULAR_USER, Locale.RU)


async def test_regular_user_cannot_add_locale(
    settings_repository: SettingsRepository,
    translation_repository: TranslationRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    add_use_case = AddLocaleUseCase(
        translation_repository,
        uow,
        event_publisher,
        make_bot_commands_sync(settings_repository.session, uow),
    )

    with pytest.raises(PermissionDeniedError):
        await add_use_case(REGULAR_USER, Locale.RU)


async def test_default_locale_changes_lock_the_active_locales_first(
    translation_repository: TranslationRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    add, remove, set_default = _locale_use_cases(translation_repository, uow, event_publisher)
    await add(OWNER, Locale.EN)
    await add(OWNER, Locale.RU)
    await translation_repository.set_default_locale(Locale.EN)
    calls: list[str] = []

    def record(name: str, label: str) -> None:
        real = getattr(translation_repository, name)

        async def wrapper(*args: object) -> object:
            calls.append(label)
            return await real(*args)

        monkeypatch.setattr(translation_repository, name, wrapper)

    record("lock_active_locales", "lock")
    record("get_locales", "read")
    record("get_default_locale", "read")

    await set_default(OWNER, Locale.RU)
    assert calls[0] == "lock"

    calls.clear()
    await set_default(OWNER, Locale.EN)
    calls.clear()
    await remove(OWNER, Locale.RU)
    assert calls[0] == "lock"


async def test_changing_the_default_locale_restarts_the_bot_and_seeds_its_banner(
    translation_repository: TranslationRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    signals, banner = _RecordingSignals(), _RecordingBanner()
    add, _, set_default = _locale_use_cases(
        translation_repository, uow, event_publisher, signals, banner
    )
    await add(OWNER, Locale.EN)
    await add(OWNER, Locale.RU)
    await translation_repository.set_default_locale(Locale.EN)

    await set_default(OWNER, Locale.RU)
    assert signals.restarts == 1
    assert banner.seeded == [Locale.RU]

    # already the default: nothing to tell the bot
    await set_default(OWNER, Locale.RU)
    assert signals.restarts == 1
    assert banner.seeded == [Locale.RU]
