from typing import Optional

import pytest
from dishka import AsyncContainer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.event_outbox import EventOutboxEntry
from app.core.db.models.user_registration import UserRegistration
from app.core.db.uow import UnitOfWork
from app.core.enums import (
    AccessMode,
    BlacklistKind,
    CabinetSignInMethod,
    LegalAcceptanceTrigger,
    LegalDocumentKind,
    Locale,
    PurchaseChannel,
    RegistrationSource,
    SessionAudience,
)
from app.core.error_codes import ErrorCode
from app.core.exceptions import PermissionDeniedError
from app.core.utils.time import datetime_now
from app.modules.auth.repository import SessionRepository
from app.modules.blacklist import BlacklistRepository
from app.modules.cabinet_auth.api.schemas import BotSignInRequest
from app.modules.cabinet_auth.dto import InviteCodesDto, TelegramProfileDto
from app.modules.cabinet_auth.sign_in import CabinetSignIn
from app.modules.legal import CreateLegalRevisionDto, LegalRepository
from app.modules.settings.dto import UpdateAccessSettingsDto
from app.modules.settings.repository import SettingsRepository
from app.modules.translations import TranslationRepository
from app.modules.users import UserDto
from app.modules.users.dto import CreateUserDto, RegisterCabinetUserDto
from app.modules.users.repository import UserRepository
from app.modules.users.usecases import RegisterCabinetUserUseCase

_IP = "203.0.113.1"


async def _set_access(
    settings_repository: SettingsRepository, uow: UnitOfWork, data: UpdateAccessSettingsDto
) -> None:
    async with uow:
        await settings_repository.update_access_settings(data)


async def _outbox(session: AsyncSession, event_type: str) -> list[EventOutboxEntry]:
    return list(
        await session.scalars(
            select(EventOutboxEntry).where(EventOutboxEntry.event_type == event_type)
        )
    )


async def test_telegram_creates_client_and_cabinet_session(
    sign_in: CabinetSignIn, session_repository: SessionRepository, session: AsyncSession
) -> None:
    user, issued = await sign_in.telegram(
        TelegramProfileDto(telegram_id=9001, name="Ann", username="ann", language="ru"),
        InviteCodesDto(),
        _IP,
        "ua",
    )
    assert user.telegram_id == 9001 and user.language is Locale.RU
    assert issued.access_token
    [cabinet_session] = await session_repository.list_active_by_user(user.id)
    assert cabinet_session.audience is SessionAudience.CABINET
    [event] = await _outbox(session, "CabinetUserRegisteredEvent")
    assert event.payload["method"] == "TELEGRAM"
    assert await _outbox(session, "TelegramUserRegisteredEvent") == []
    registration = await session.get(UserRegistration, user.id)
    assert registration is not None
    assert registration.source is RegistrationSource.CABINET_TELEGRAM
    assert (registration.ip_address, registration.user_agent) == (_IP, "ua")
    assert registration.telegram_language_code == "ru"


async def test_a_failed_sign_in_leaves_no_active_session(
    sign_in: CabinetSignIn,
    session_repository: SessionRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with uow:
        user = await user_repository.create(CreateUserDto(name="Ann", telegram_id=9009))

    async def _broken(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("outbox down")

    monkeypatch.setattr(sign_in._event_publisher, "publish", _broken)
    with pytest.raises(RuntimeError):
        await sign_in.issue_for(user, _IP, "ua", CabinetSignInMethod.TELEGRAM)

    assert await session_repository.list_active_by_user(user.id) == []


async def test_telegram_unknown_language_falls_back_to_english(sign_in: CabinetSignIn) -> None:
    user, _ = await sign_in.telegram(
        TelegramProfileDto(telegram_id=9003, name="Bo", username=None, language="xx"),
        InviteCodesDto(),
        _IP,
        None,
    )
    assert user.language is Locale.EN


async def test_telegram_existing_bot_user_reused(
    sign_in: CabinetSignIn, user_repository: UserRepository, uow: UnitOfWork
) -> None:
    async with uow:
        existing = await user_repository.create(CreateUserDto(name="Bot user", telegram_id=9002))

    user, _ = await sign_in.telegram(
        TelegramProfileDto(telegram_id=9002, name="Bot user", username=None, language=None),
        InviteCodesDto(),
        _IP,
        None,
    )
    assert user.id == existing.id


async def test_blocked_user_gets_user_blocked(
    sign_in: CabinetSignIn, user_repository: UserRepository, uow: UnitOfWork
) -> None:
    async with uow:
        await user_repository.create(
            CreateUserDto(name="Blocked", email="blocked@mail.ru", is_blocked=True)
        )

    with pytest.raises(PermissionDeniedError) as error:
        await sign_in.email("blocked@mail.ru", Locale.EN, InviteCodesDto(), _IP, None)
    assert error.value.code is ErrorCode.USER_BLOCKED


async def test_closed_registration(
    sign_in: CabinetSignIn,
    settings_repository: SettingsRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    async with uow:
        existing = await user_repository.create(CreateUserDto(name="Old", email="old@mail.ru"))
    await _set_access(settings_repository, uow, UpdateAccessSettingsDto(registration_enabled=False))

    with pytest.raises(PermissionDeniedError) as error:
        await sign_in.email("new@mail.ru", Locale.EN, InviteCodesDto(), _IP, None)
    assert error.value.code is ErrorCode.REGISTRATION_CLOSED

    user, _ = await sign_in.email("Old@Mail.ru", Locale.EN, InviteCodesDto(), _IP, None)
    assert user.id == existing.id


async def test_invite_only_accepts_referral(
    sign_in: CabinetSignIn,
    settings_repository: SettingsRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    async with uow:
        referrer = await user_repository.create(CreateUserDto(name="Referrer", telegram_id=9100))
    await _set_access(settings_repository, uow, UpdateAccessSettingsDto(mode=AccessMode.INVITED))

    with pytest.raises(PermissionDeniedError) as error:
        await sign_in.email("guest@mail.ru", Locale.EN, InviteCodesDto(), _IP, None)
    assert error.value.code is ErrorCode.REGISTRATION_INVITE_ONLY

    user, _ = await sign_in.email(
        "guest@mail.ru",
        Locale.EN,
        InviteCodesDto(referral_code=referrer.referral_code),
        _IP,
        None,
    )
    assert user.email == "guest@mail.ru"


async def test_restricted_mode(
    sign_in: CabinetSignIn, settings_repository: SettingsRepository, uow: UnitOfWork
) -> None:
    await _set_access(settings_repository, uow, UpdateAccessSettingsDto(mode=AccessMode.RESTRICTED))

    with pytest.raises(PermissionDeniedError) as error:
        await sign_in.telegram(
            TelegramProfileDto(telegram_id=9200, name="Late", username=None, language=None),
            InviteCodesDto(),
            _IP,
            None,
        )
    assert error.value.code is ErrorCode.ACCESS_RESTRICTED


async def test_email_registration_publishes_event(
    sign_in: CabinetSignIn, session: AsyncSession
) -> None:
    user, _ = await sign_in.email(
        "New@Mail.ru", Locale.EN, InviteCodesDto(referral_code="abc"), _IP, None
    )
    assert user.email == "new@mail.ru" and user.name == "new"
    [event] = await _outbox(session, "CabinetUserRegisteredEvent")
    assert event.payload["method"] == "EMAIL"
    assert event.payload["referral_code"] == "abc"
    assert event.payload["user"]["id"] == user.id
    registration = await session.get(UserRegistration, user.id)
    assert registration is not None and registration.source is RegistrationSource.CABINET_EMAIL


async def test_blacklisted_email_blocked(
    sign_in: CabinetSignIn,
    blacklist_repository: BlacklistRepository,
    settings_repository: SettingsRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    session: AsyncSession,
) -> None:
    async with uow:
        await blacklist_repository.add_entry(BlacklistKind.EMAIL, "spam@mail.ru")
    # the blacklist wins over the access mode
    await _set_access(settings_repository, uow, UpdateAccessSettingsDto(registration_enabled=False))

    with pytest.raises(PermissionDeniedError) as error:
        await sign_in.email("spam@mail.ru", Locale.EN, InviteCodesDto(), _IP, None)
    assert error.value.code is ErrorCode.USER_BLOCKED
    blocked = await user_repository.find_by_email("spam@mail.ru")
    assert blocked is not None and blocked.is_blocked
    assert await _outbox(session, "CabinetUserRegisteredEvent") == []
    [event] = await _outbox(session, "CabinetRegistrationBlockedEvent")
    assert event.payload["user"]["id"] == blocked.id


async def test_blacklisted_telegram_id_blocked(
    sign_in: CabinetSignIn,
    blacklist_repository: BlacklistRepository,
    settings_repository: SettingsRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    session: AsyncSession,
) -> None:
    async with uow:
        await blacklist_repository.add_entry(BlacklistKind.TELEGRAM_ID, "9400")
    await _set_access(settings_repository, uow, UpdateAccessSettingsDto(registration_enabled=False))

    with pytest.raises(PermissionDeniedError) as error:
        await sign_in.telegram(
            TelegramProfileDto(telegram_id=9400, name="Spam", username=None, language=None),
            InviteCodesDto(),
            _IP,
            None,
        )
    assert error.value.code is ErrorCode.USER_BLOCKED
    blocked = await user_repository.find_by_telegram_id(9400)
    assert blocked is not None and blocked.is_blocked
    [event] = await _outbox(session, "TelegramRegistrationBlockedEvent")
    assert event.payload["user"]["id"] == blocked.id


async def test_register_cabinet_user_returns_race_winner(
    container: AsyncContainer, user_repository: UserRepository, uow: UnitOfWork
) -> None:
    async with uow:
        winner = await user_repository.create(CreateUserDto(name="Winner", email="race@mail.ru"))

    async with container() as request_container:
        use_case = await request_container.get(RegisterCabinetUserUseCase)
        user = await use_case.system(
            RegisterCabinetUserDto(
                name="race",
                language=Locale.EN,
                method=CabinetSignInMethod.EMAIL,
                email="race@mail.ru",
            )
        )
    assert user.id == winner.id


_FF = "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"


async def test_new_device_sign_in_publishes_event_but_first_is_silent(
    sign_in: CabinetSignIn, user_repository: UserRepository, uow: UnitOfWork, session: AsyncSession
) -> None:
    async with uow:
        existing = await user_repository.create(CreateUserDto(name="Bot user", telegram_id=9100))

    await sign_in.issue_for(existing, _IP, _FF, CabinetSignInMethod.TELEGRAM)
    assert await _outbox(session, "CabinetNewDeviceSignInEvent") == []

    await sign_in.issue_for(existing, _IP, _FF, CabinetSignInMethod.TELEGRAM)
    assert await _outbox(session, "CabinetNewDeviceSignInEvent") == []

    await sign_in.issue_for(existing, "198.51.100.7", _FF, CabinetSignInMethod.TELEGRAM)
    [event] = await _outbox(session, "CabinetNewDeviceSignInEvent")
    assert event.payload["browser"] == "Firefox on Linux"
    assert event.payload["user"]["id"] == existing.id
    assert event.ip_address == "198.51.100.7"


async def test_every_sign_in_publishes_its_method(
    sign_in: CabinetSignIn, user_repository: UserRepository, uow: UnitOfWork, session: AsyncSession
) -> None:
    async with uow:
        existing = await user_repository.create(
            CreateUserDto(name="Ivan", email="ivan@example.com")
        )

    await sign_in.email("ivan@example.com", Locale.EN, InviteCodesDto(), _IP, _FF)
    await sign_in.email("ivan@example.com", Locale.EN, InviteCodesDto(), _IP, _FF)

    events = await _outbox(session, "CabinetSignedInEvent")
    assert [e.payload["method"] for e in events] == ["EMAIL", "EMAIL"]
    assert events[0].payload["user"]["id"] == existing.id
    assert events[0].ip_address == _IP


async def test_email_alias_signs_into_the_existing_account(
    sign_in: CabinetSignIn,
    user_repository: UserRepository,
    uow: UnitOfWork,
    session: AsyncSession,
) -> None:
    async with uow:
        existing = await user_repository.create(
            CreateUserDto(name="Ivan", email="ivan.petrov@gmail.com")
        )
    user, _ = await sign_in.email("Ivan.Petrov+1@gmail.com", Locale.EN, InviteCodesDto(), _IP, None)
    assert user.id == existing.id
    assert await _outbox(session, "CabinetUserRegisteredEvent") == []


async def test_email_sign_in_clears_undeliverable(
    sign_in: CabinetSignIn, user_repository: UserRepository, uow: UnitOfWork
) -> None:
    async with uow:
        existing = await user_repository.create(CreateUserDto(name="Back", email="back@mail.ru"))
        await user_repository.set_email_undeliverable(existing.id, datetime_now())

    await sign_in.email("back@mail.ru", Locale.EN, InviteCodesDto(), _IP, None)

    loaded = await user_repository.find_by_id(existing.id)
    assert loaded is not None and loaded.email_undeliverable_at is None


async def _publish(
    legal_repository: LegalRepository, kind: LegalDocumentKind, locale: Locale
) -> int:
    revision = await legal_repository.add_revision(
        CreateLegalRevisionDto(
            kind=kind, locale=locale, channel=None, title=kind.value, body="text", created_by=None
        )
    )
    return revision.id


async def _telegram_sign_in(
    sign_in: CabinetSignIn, telegram_id: int, legal_locale: Optional[Locale] = None
) -> UserDto:
    user, _ = await sign_in.telegram(
        TelegramProfileDto(telegram_id=telegram_id, name="Ann", username=None, language=None),
        InviteCodesDto(),
        _IP,
        "ua",
        legal_locale=legal_locale,
    )
    return user


async def test_first_cabinet_sign_in_records_sign_up(
    sign_in: CabinetSignIn, legal_repository: LegalRepository
) -> None:
    await _publish(legal_repository, LegalDocumentKind.USER_AGREEMENT, Locale.EN)
    await _publish(legal_repository, LegalDocumentKind.PRIVACY_POLICY, Locale.EN)

    user = await _telegram_sign_in(sign_in, 9101, Locale.EN)

    acceptances = await legal_repository.list_acceptances(user.id)
    assert {a.revision.kind for a in acceptances} == {
        LegalDocumentKind.USER_AGREEMENT,
        LegalDocumentKind.PRIVACY_POLICY,
    }
    assert {(a.trigger, a.channel, a.ip_address) for a in acceptances} == {
        (LegalAcceptanceTrigger.SIGN_UP, PurchaseChannel.CABINET, _IP)
    }


async def test_second_cabinet_sign_in_records_nothing(
    sign_in: CabinetSignIn, legal_repository: LegalRepository
) -> None:
    await _publish(legal_repository, LegalDocumentKind.USER_AGREEMENT, Locale.EN)

    user = await _telegram_sign_in(sign_in, 9102, Locale.EN)
    await _telegram_sign_in(sign_in, 9102, Locale.EN)

    assert len(await legal_repository.list_acceptances(user.id)) == 1


async def test_bot_user_first_cabinet_sign_in_records_sign_up(
    sign_in: CabinetSignIn,
    legal_repository: LegalRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    await _publish(legal_repository, LegalDocumentKind.PRIVACY_POLICY, Locale.EN)
    async with uow:
        existing = await user_repository.create(CreateUserDto(name="Bot user", telegram_id=9103))

    await _telegram_sign_in(sign_in, 9103, Locale.EN)

    [acceptance] = await legal_repository.list_acceptances(existing.id)
    assert acceptance.trigger is LegalAcceptanceTrigger.SIGN_UP
    assert acceptance.channel is PurchaseChannel.CABINET


async def test_sign_in_records_legal_locale(
    sign_in: CabinetSignIn,
    legal_repository: LegalRepository,
    translation_repository: TranslationRepository,
) -> None:
    await translation_repository.add_active_locale(Locale.RU)
    await _publish(legal_repository, LegalDocumentKind.USER_AGREEMENT, Locale.EN)
    ru_id = await _publish(legal_repository, LegalDocumentKind.USER_AGREEMENT, Locale.RU)

    user = await _telegram_sign_in(sign_in, 9104, Locale.RU)

    [acceptance] = await legal_repository.list_acceptances(user.id)
    assert acceptance.revision.id == ru_id


async def test_sign_in_without_legal_locale_records_nothing_until_one_is_sent(
    sign_in: CabinetSignIn, legal_repository: LegalRepository
) -> None:
    await _publish(legal_repository, LegalDocumentKind.USER_AGREEMENT, Locale.EN)

    user = await _telegram_sign_in(sign_in, 9105)
    assert await legal_repository.list_acceptances(user.id) == []

    await _telegram_sign_in(sign_in, 9105, Locale.EN)
    [acceptance] = await legal_repository.list_acceptances(user.id)
    assert acceptance.trigger is LegalAcceptanceTrigger.SIGN_UP


def test_unknown_legal_locale_in_a_request_is_ignored() -> None:
    assert BotSignInRequest(token="t", legal_locale="xx").legal_locale is None  # type: ignore[arg-type]
    assert BotSignInRequest(token="t", legal_locale="ru").legal_locale is Locale.RU  # type: ignore[arg-type]
