import pytest

from app.core.enums import LegalAcceptanceTrigger, LegalDocumentKind, Locale, PurchaseChannel
from app.modules.legal.dto import CreateLegalRevisionDto
from app.modules.legal.recorder import LegalAcceptanceRecorder
from app.modules.legal.repository import LegalRepository
from app.modules.translations import TranslationRepository
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository

pytestmark = pytest.mark.usefixtures("shown_documents")

ALL = frozenset(LegalDocumentKind)


async def _user(user_repository: UserRepository) -> int:
    return (await user_repository.create(CreateUserDto(name="u", telegram_id=7001))).id


async def _text(repo: LegalRepository, kind: LegalDocumentKind, locale: Locale, body: str) -> int:
    revision = await repo.add_revision(
        CreateLegalRevisionDto(
            kind=kind, locale=locale, channel=None, title="t", body=body, created_by=None
        )
    )
    return revision.id


def _recorder(
    repo: LegalRepository, translations: TranslationRepository
) -> LegalAcceptanceRecorder:
    return LegalAcceptanceRecorder(repo, translations)


async def test_record_writes_only_visible_kinds(
    legal_repository: LegalRepository,
    translation_repository: TranslationRepository,
    user_repository: UserRepository,
) -> None:
    user_id = await _user(user_repository)
    default = await translation_repository.get_default_locale()
    await _text(legal_repository, LegalDocumentKind.OFFER, default, "offer")
    await _text(legal_repository, LegalDocumentKind.PRIVACY_POLICY, default, "privacy")
    await legal_repository.update_document(
        LegalDocumentKind.PRIVACY_POLICY, show_in_bot=False, show_in_cabinet=None
    )

    await _recorder(legal_repository, translation_repository).record(
        user_id=user_id,
        channel=PurchaseChannel.BOT,
        trigger=LegalAcceptanceTrigger.PAYMENT,
        locale=default,
        kinds=ALL,
    )

    rows = await legal_repository.list_acceptances(user_id)
    assert [r.revision.kind for r in rows] == [LegalDocumentKind.OFFER]


async def test_record_stores_the_resolved_revision(
    legal_repository: LegalRepository,
    translation_repository: TranslationRepository,
    user_repository: UserRepository,
) -> None:
    user_id = await _user(user_repository)
    default = await translation_repository.get_default_locale()
    other = Locale.RU if default != Locale.RU else Locale.EN
    revision_id = await _text(legal_repository, LegalDocumentKind.OFFER, default, "offer")

    await _recorder(legal_repository, translation_repository).record(
        user_id=user_id,
        channel=PurchaseChannel.CABINET,
        trigger=LegalAcceptanceTrigger.SIGN_UP,
        locale=other,
        kinds=frozenset({LegalDocumentKind.OFFER}),
        ip_address="1.2.3.4",
    )

    (row,) = await legal_repository.list_acceptances(user_id)
    assert row.revision.id == revision_id
    assert row.ip_address == "1.2.3.4"


async def test_has_signed_up(
    legal_repository: LegalRepository,
    translation_repository: TranslationRepository,
    user_repository: UserRepository,
) -> None:
    user_id = await _user(user_repository)
    default = await translation_repository.get_default_locale()
    await _text(legal_repository, LegalDocumentKind.OFFER, default, "offer")
    recorder = _recorder(legal_repository, translation_repository)

    assert not await recorder.has_signed_up(user_id, PurchaseChannel.BOT)
    await recorder.record(
        user_id=user_id,
        channel=PurchaseChannel.BOT,
        trigger=LegalAcceptanceTrigger.SIGN_UP,
        locale=default,
        kinds=ALL,
    )

    assert await recorder.has_signed_up(user_id, PurchaseChannel.BOT)
    assert not await recorder.has_signed_up(user_id, PurchaseChannel.CABINET)


async def test_record_with_a_disabled_locale_stores_the_default_revision(
    legal_repository: LegalRepository,
    translation_repository: TranslationRepository,
    user_repository: UserRepository,
) -> None:
    user_id = await _user(user_repository)
    default = await translation_repository.get_default_locale()
    other = Locale.RU if default != Locale.RU else Locale.EN
    default_id = await _text(legal_repository, LegalDocumentKind.OFFER, default, "offer")
    await _text(legal_repository, LegalDocumentKind.OFFER, other, "other")
    await translation_repository.add_active_locale(other)
    await translation_repository.remove_active_locale(other)

    await _recorder(legal_repository, translation_repository).record(
        user_id=user_id,
        channel=PurchaseChannel.CABINET,
        trigger=LegalAcceptanceTrigger.PAYMENT,
        locale=other,
        kinds=ALL,
    )

    (row,) = await legal_repository.list_acceptances(user_id)
    assert row.revision.id == default_id
