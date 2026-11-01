from typing import Optional

import pytest

from app.core.db.uow import UnitOfWork
from app.core.enums import (
    LegalAcceptanceTrigger,
    LegalDocumentKind,
    Locale,
    PurchaseChannel,
    Role,
)
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from app.modules.legal.dto import (
    CreateLegalAcceptanceDto,
    CreateLegalRevisionDto,
    LegalTextKeyDto,
    SetLegalTextDto,
    UpdateLegalDocumentDto,
)
from app.modules.legal.events import LegalDocumentChangedEvent
from app.modules.legal.repository import LegalRepository
from app.modules.legal.usecases import (
    ListLegalDocumentsUseCase,
    ListUserLegalAcceptancesUseCase,
    RemoveLegalTextUseCase,
    SetLegalTextUseCase,
    UpdateLegalDocumentUseCase,
)
from app.modules.translations.repository import TranslationRepository
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository
from tests.fakes.events import RecordingEventPublisher

OWNER = UserDto(id=1, login="admin", name="admin", role=Role.OWNER, language=Locale.EN)
REGULAR_USER = UserDto(id=2, name="Bob", role=Role.USER, language=Locale.EN)
OFFER = LegalDocumentKind.OFFER
LIMIT = 32768


@pytest.fixture
async def owner(user_repository: UserRepository) -> UserDto:
    return await user_repository.create(
        CreateUserDto(login="legal-admin", name="legal-admin", role=Role.OWNER)
    )


def _set(
    title: str = "Offer",
    body: str = "text",
    locale: Locale = Locale.EN,
    channel: Optional[PurchaseChannel] = None,
    kind: LegalDocumentKind = OFFER,
    reaccept: bool = False,
) -> SetLegalTextDto:
    return SetLegalTextDto(
        kind=kind,
        locale=locale,
        channel=channel,
        title=title,
        body=body,
        requires_reacceptance=reaccept,
        client_ip="1.1.1.1",
    )


def _set_use_case(
    legal_repository: LegalRepository,
    translation_repository: TranslationRepository,
    uow: UnitOfWork,
    events: RecordingEventPublisher,
) -> SetLegalTextUseCase:
    return SetLegalTextUseCase(legal_repository, translation_repository, events, uow)


async def test_set_text_creates_a_new_revision_each_time(
    owner: UserDto,
    legal_repository: LegalRepository,
    translation_repository: TranslationRepository,
    uow: UnitOfWork,
) -> None:
    await translation_repository.add_active_locale(Locale.EN)
    use_case = _set_use_case(
        legal_repository, translation_repository, uow, RecordingEventPublisher()
    )

    first = await use_case(owner, _set(body="one"))
    second = await use_case(owner, _set(body="two"))

    assert first.id != second.id
    assert first.body == "one"
    current = await legal_repository.list_current_revisions()
    assert [r.body for r in current if r.kind == OFFER] == ["two"]


@pytest.mark.parametrize(("extra", "ok"), [(0, True), (1, False)])
async def test_set_text_counts_title_in_limit(
    owner: UserDto,
    legal_repository: LegalRepository,
    translation_repository: TranslationRepository,
    uow: UnitOfWork,
    extra: int,
    ok: bool,
) -> None:
    await translation_repository.add_active_locale(Locale.EN)
    use_case = _set_use_case(
        legal_repository, translation_repository, uow, RecordingEventPublisher()
    )
    title = "Offer"
    body = "x" * (LIMIT - 4 - len(title) + extra)

    if ok:
        await use_case(owner, _set(title=title, body=body))
    else:
        with pytest.raises(ValidationError) as err:
            await use_case(owner, _set(title=title, body=body))
        assert err.value.code == ErrorCode.LEGAL_TEXT_TOO_LONG


@pytest.mark.parametrize(("title", "body"), [(" ", "text"), ("Offer", "  ")])
async def test_set_text_refuses_blank_title_or_body(
    legal_repository: LegalRepository,
    translation_repository: TranslationRepository,
    uow: UnitOfWork,
    title: str,
    body: str,
) -> None:
    await translation_repository.add_active_locale(Locale.EN)
    use_case = _set_use_case(
        legal_repository, translation_repository, uow, RecordingEventPublisher()
    )

    with pytest.raises(ValidationError) as err:
        await use_case(OWNER, _set(title=title, body=body))
    assert err.value.code == ErrorCode.LEGAL_TEXT_REQUIRED


async def test_set_text_refuses_disabled_locale(
    legal_repository: LegalRepository,
    translation_repository: TranslationRepository,
    uow: UnitOfWork,
) -> None:
    await translation_repository.add_active_locale(Locale.EN)
    use_case = _set_use_case(
        legal_repository, translation_repository, uow, RecordingEventPublisher()
    )

    with pytest.raises(ValidationError) as err:
        await use_case(OWNER, _set(locale=Locale.RU))
    assert err.value.code == ErrorCode.LOCALE_NOT_ENABLED


async def test_set_text_publishes_event(
    owner: UserDto,
    legal_repository: LegalRepository,
    translation_repository: TranslationRepository,
    uow: UnitOfWork,
) -> None:
    await translation_repository.add_active_locale(Locale.EN)
    events = RecordingEventPublisher()

    await _set_use_case(legal_repository, translation_repository, uow, events)(
        owner, _set(channel=PurchaseChannel.BOT)
    )

    (event,) = events.events
    assert isinstance(event, LegalDocumentChangedEvent)
    assert (event.action, event.kind, event.channel) == ("text_set", OFFER, PurchaseChannel.BOT)
    assert event.ip_address == "1.1.1.1"


async def test_set_text_stores_reacceptance_flag(
    owner: UserDto,
    legal_repository: LegalRepository,
    translation_repository: TranslationRepository,
    uow: UnitOfWork,
) -> None:
    await translation_repository.add_active_locale(Locale.EN)
    events = RecordingEventPublisher()

    saved = await _set_use_case(legal_repository, translation_repository, uow, events)(
        owner, _set(kind=LegalDocumentKind.USER_AGREEMENT, reaccept=True)
    )

    assert saved.requires_reacceptance is True
    (event,) = events.events
    assert isinstance(event, LegalDocumentChangedEvent)
    assert "requires_reacceptance" in event.changed


async def test_reacceptance_flag_rejected_for_offer(
    owner: UserDto,
    legal_repository: LegalRepository,
    translation_repository: TranslationRepository,
    uow: UnitOfWork,
) -> None:
    await translation_repository.add_active_locale(Locale.EN)
    use_case = _set_use_case(
        legal_repository, translation_repository, uow, RecordingEventPublisher()
    )

    with pytest.raises(ValidationError) as error:
        await use_case(owner, _set(kind=OFFER, reaccept=True))

    assert error.value.code is ErrorCode.LEGAL_REACCEPTANCE_NOT_ALLOWED


async def test_remove_text_without_text_is_404(
    legal_repository: LegalRepository, uow: UnitOfWork
) -> None:
    use_case = RemoveLegalTextUseCase(legal_repository, RecordingEventPublisher(), uow)

    with pytest.raises(NotFoundError):
        await use_case(
            OWNER, LegalTextKeyDto(kind=OFFER, locale=Locale.EN, channel=None, client_ip="x")
        )


async def test_remove_text_writes_empty_revision_and_keeps_history(
    owner: UserDto, legal_repository: LegalRepository, uow: UnitOfWork
) -> None:
    first = await legal_repository.add_revision(
        CreateLegalRevisionDto(
            kind=OFFER, locale=Locale.EN, channel=None, title="t", body="b", created_by=None
        )
    )
    key = LegalTextKeyDto(kind=OFFER, locale=Locale.EN, channel=None, client_ip="x")
    use_case = RemoveLegalTextUseCase(legal_repository, RecordingEventPublisher(), uow)

    await use_case(owner, key)

    (current,) = [r for r in await legal_repository.list_current_revisions() if r.kind == OFFER]
    assert current.body == "" and current.id != first.id
    with pytest.raises(NotFoundError):
        await use_case(owner, key)


async def test_update_publishes_changed_fields(
    legal_repository: LegalRepository, uow: UnitOfWork
) -> None:
    events = RecordingEventPublisher()
    use_case = UpdateLegalDocumentUseCase(legal_repository, events, uow)

    document = await use_case(
        OWNER,
        UpdateLegalDocumentDto(
            kind=OFFER, show_in_bot=True, show_in_cabinet=False, client_ip="1.1.1.1"
        ),
    )

    assert document.show_in_bot is True
    (event,) = events.events
    assert isinstance(event, LegalDocumentChangedEvent)
    assert event.changed == ["show_in_bot"]
    assert event.ip_address == "1.1.1.1"


async def test_requires_permission(legal_repository: LegalRepository, uow: UnitOfWork) -> None:
    use_case = UpdateLegalDocumentUseCase(legal_repository, RecordingEventPublisher(), uow)

    with pytest.raises(PermissionDeniedError):
        await use_case(
            REGULAR_USER,
            UpdateLegalDocumentDto(
                kind=OFFER, show_in_bot=False, show_in_cabinet=None, client_ip="x"
            ),
        )


def _list_use_case(
    legal_repository: LegalRepository,
    translation_repository: TranslationRepository,
    uow: UnitOfWork,
) -> ListLegalDocumentsUseCase:
    return ListLegalDocumentsUseCase(legal_repository, translation_repository, uow)


async def test_list_documents_reports_last_reacceptance_at(
    legal_repository: LegalRepository,
    translation_repository: TranslationRepository,
    uow: UnitOfWork,
) -> None:
    use_case = _list_use_case(legal_repository, translation_repository, uow)

    def _revision(channel: Optional[PurchaseChannel], reaccept: bool) -> CreateLegalRevisionDto:
        return CreateLegalRevisionDto(
            kind=LegalDocumentKind.USER_AGREEMENT,
            locale=Locale.EN,
            channel=channel,
            title="t",
            body="b",
            created_by=None,
            requires_reacceptance=reaccept,
        )

    flagged = await legal_repository.add_revision(_revision(None, True))
    await legal_repository.add_revision(_revision(None, False))
    await legal_repository.add_revision(_revision(PurchaseChannel.BOT, False))

    texts = {t.channel: t for t in (await use_case(OWNER)).texts}

    assert texts[None].last_reacceptance_at == flagged.created_at
    assert texts[PurchaseChannel.BOT].last_reacceptance_at is None


async def _accept(legal_repository: LegalRepository, user_id: int, title: str) -> None:
    revision = await legal_repository.add_revision(
        CreateLegalRevisionDto(
            kind=OFFER,
            locale=Locale.EN,
            channel=None,
            title=title,
            body="text",
            created_by=None,
        )
    )
    await legal_repository.add_acceptances(
        [
            CreateLegalAcceptanceDto(
                user_id=user_id,
                revision_id=revision.id,
                channel=PurchaseChannel.BOT,
                trigger=LegalAcceptanceTrigger.SIGN_UP,
                transaction_id=None,
                ip_address=None,
            )
        ]
    )


async def test_list_user_acceptances_newest_first(
    legal_repository: LegalRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    owner: UserDto,
) -> None:
    customer = await user_repository.create(CreateUserDto(name="c", role=Role.USER))
    await _accept(legal_repository, customer.id, "old")
    await _accept(legal_repository, customer.id, "new")
    use_case = ListUserLegalAcceptancesUseCase(legal_repository, user_repository, uow)

    result = await use_case(owner, customer.id)

    assert [item.revision.title for item in result] == ["new", "old"]


async def test_list_user_acceptances_hidden_staff_is_not_found(
    legal_repository: LegalRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    other = await user_repository.create(CreateUserDto(login="o", name="o", role=Role.OWNER))
    admin = await user_repository.create(CreateUserDto(login="a", name="a", role=Role.ADMIN))
    use_case = ListUserLegalAcceptancesUseCase(legal_repository, user_repository, uow)

    with pytest.raises(NotFoundError):
        await use_case(admin, other.id)
