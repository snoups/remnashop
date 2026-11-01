from datetime import datetime, timedelta
from typing import Optional

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.legal_document import LegalAcceptance, LegalDocumentRevision
from app.core.enums import LegalAcceptanceTrigger, LegalDocumentKind, Locale, PurchaseChannel
from app.core.utils.time import datetime_now
from app.modules.legal.dto import (
    CreateLegalAcceptanceDto,
    CreateLegalRevisionDto,
    LegalRevisionDto,
    PendingLegalDocumentsDto,
)
from app.modules.legal.pending import pending_documents
from app.modules.legal.repository import LegalRepository
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository

pytestmark = pytest.mark.usefixtures("shown_documents")

AGREEMENT = LegalDocumentKind.USER_AGREEMENT
POLICY = LegalDocumentKind.PRIVACY_POLICY
OFFER = LegalDocumentKind.OFFER
BOT = PurchaseChannel.BOT
CABINET = PurchaseChannel.CABINET


async def _text(
    repo: LegalRepository,
    session: AsyncSession,
    kind: LegalDocumentKind,
    *,
    locale: Locale = Locale.RU,
    channel: Optional[PurchaseChannel] = None,
    body: str = "text",
    reaccept: bool = False,
    at: Optional[datetime] = None,
) -> LegalRevisionDto:
    revision = await repo.add_revision(
        CreateLegalRevisionDto(
            kind=kind,
            locale=locale,
            channel=channel,
            title="t",
            body=body,
            created_by=None,
            requires_reacceptance=reaccept,
        )
    )
    if at is not None:
        await session.execute(
            update(LegalDocumentRevision)
            .where(LegalDocumentRevision.id == revision.id)
            .values(created_at=at)
        )
    return revision


async def _accept(
    repo: LegalRepository,
    session: AsyncSession,
    user: UserDto,
    revision: LegalRevisionDto,
    channel: PurchaseChannel,
    at: datetime,
    trigger: LegalAcceptanceTrigger = LegalAcceptanceTrigger.SIGN_UP,
) -> None:
    await repo.add_acceptances(
        [
            CreateLegalAcceptanceDto(
                user_id=user.id,
                revision_id=revision.id,
                channel=channel,
                trigger=trigger,
                transaction_id=None,
                ip_address=None,
            )
        ]
    )
    await session.execute(
        update(LegalAcceptance)
        .where(LegalAcceptance.user_id == user.id, LegalAcceptance.revision_id == revision.id)
        .values(accepted_at=at)
    )


async def _pending(
    repo: LegalRepository,
    user: UserDto,
    channel: PurchaseChannel,
    locale: Locale = Locale.RU,
) -> PendingLegalDocumentsDto:
    assert user.created_at is not None
    return await pending_documents(
        repo,
        user_id=user.id,
        user_created_at=user.created_at,
        channel=channel,
        locale=locale,
        default_locale=Locale.EN,
        active_locales=[Locale.RU, Locale.EN],
    )


async def _customer(user_repository: UserRepository) -> UserDto:
    return await user_repository.create(CreateUserDto(name="customer", telegram_id=7001))


def _kinds(result: PendingLegalDocumentsDto) -> list[LegalDocumentKind]:
    return [document.kind for document in result.documents]


async def test_bot_new_customer_gets_agreement_and_policy(
    legal_repository: LegalRepository, session: AsyncSession, user_repository: UserRepository
) -> None:
    user = await _customer(user_repository)
    for kind in (OFFER, AGREEMENT, POLICY):
        await _text(legal_repository, session, kind)

    result = await _pending(legal_repository, user, BOT)

    assert _kinds(result) == [AGREEMENT, POLICY]
    assert result.is_update is False


async def test_bot_accepted_customer_has_nothing_pending(
    legal_repository: LegalRepository, session: AsyncSession, user_repository: UserRepository
) -> None:
    user = await _customer(user_repository)
    now = datetime_now()
    for kind in (AGREEMENT, POLICY):
        revision = await _text(legal_repository, session, kind)
        await _accept(legal_repository, session, user, revision, BOT, now)

    assert _kinds(await _pending(legal_repository, user, BOT)) == []


async def test_bot_reacceptance_flag_reprompts_only_that_document(
    legal_repository: LegalRepository, session: AsyncSession, user_repository: UserRepository
) -> None:
    user = await _customer(user_repository)
    now = datetime_now()
    for kind in (AGREEMENT, POLICY):
        revision = await _text(legal_repository, session, kind)
        await _accept(legal_repository, session, user, revision, BOT, now)
    await _text(legal_repository, session, AGREEMENT, reaccept=True, at=now + timedelta(days=1))

    result = await _pending(legal_repository, user, BOT)

    assert _kinds(result) == [AGREEMENT]
    assert result.is_update is True


async def test_unflagged_revision_does_not_reprompt(
    legal_repository: LegalRepository, session: AsyncSession, user_repository: UserRepository
) -> None:
    user = await _customer(user_repository)
    now = datetime_now()
    for kind in (AGREEMENT, POLICY):
        revision = await _text(legal_repository, session, kind)
        await _accept(legal_repository, session, user, revision, BOT, now)
    await _text(legal_repository, session, AGREEMENT, at=now + timedelta(days=1))

    assert _kinds(await _pending(legal_repository, user, BOT)) == []


async def test_flag_on_other_locale_does_not_reprompt(
    legal_repository: LegalRepository, session: AsyncSession, user_repository: UserRepository
) -> None:
    user = await _customer(user_repository)
    now = datetime_now()
    for kind in (AGREEMENT, POLICY):
        revision = await _text(legal_repository, session, kind)
        await _accept(legal_repository, session, user, revision, BOT, now)
    await _text(
        legal_repository,
        session,
        AGREEMENT,
        locale=Locale.EN,
        reaccept=True,
        at=now + timedelta(days=1),
    )

    assert _kinds(await _pending(legal_repository, user, BOT)) == []


async def test_flag_on_cabinet_override_does_not_reprompt_bot(
    legal_repository: LegalRepository, session: AsyncSession, user_repository: UserRepository
) -> None:
    user = await _customer(user_repository)
    now = datetime_now()
    for kind in (AGREEMENT, POLICY):
        revision = await _text(legal_repository, session, kind)
        await _accept(legal_repository, session, user, revision, BOT, now)
        await _accept(legal_repository, session, user, revision, CABINET, now)
    await _text(
        legal_repository,
        session,
        AGREEMENT,
        channel=CABINET,
        reaccept=True,
        at=now + timedelta(days=1),
    )

    assert _kinds(await _pending(legal_repository, user, BOT)) == []
    assert _kinds(await _pending(legal_repository, user, CABINET)) == [AGREEMENT]


async def test_language_switch_does_not_reprompt(
    legal_repository: LegalRepository, session: AsyncSession, user_repository: UserRepository
) -> None:
    user = await _customer(user_repository)
    now = datetime_now()
    for kind in (AGREEMENT, POLICY):
        revision = await _text(legal_repository, session, kind)
        await _accept(legal_repository, session, user, revision, BOT, now)
        await _text(legal_repository, session, kind, locale=Locale.EN)

    assert _kinds(await _pending(legal_repository, user, BOT, Locale.EN)) == []


async def test_hidden_or_empty_documents_are_not_pending(
    legal_repository: LegalRepository, session: AsyncSession, user_repository: UserRepository
) -> None:
    user = await _customer(user_repository)
    await _text(legal_repository, session, AGREEMENT)
    await _text(legal_repository, session, POLICY)
    await _text(legal_repository, session, POLICY, body="")
    await legal_repository.update_document(AGREEMENT, show_in_bot=False, show_in_cabinet=None)

    assert _kinds(await _pending(legal_repository, user, BOT)) == []


async def test_cabinet_without_cutoff_has_nothing_pending(
    legal_repository: LegalRepository, session: AsyncSession, user_repository: UserRepository
) -> None:
    user = await _customer(user_repository)
    await _text(legal_repository, session, AGREEMENT)
    await _text(legal_repository, session, POLICY)

    assert _kinds(await _pending(legal_repository, user, CABINET)) == []


async def test_cutoff_before_registration_is_ignored(
    legal_repository: LegalRepository, session: AsyncSession, user_repository: UserRepository
) -> None:
    user = await _customer(user_repository)
    assert user.created_at is not None
    await _text(
        legal_repository,
        session,
        AGREEMENT,
        reaccept=True,
        at=user.created_at - timedelta(days=1),
    )

    assert _kinds(await _pending(legal_repository, user, CABINET)) == []


async def test_payment_acceptance_counts(
    legal_repository: LegalRepository, session: AsyncSession, user_repository: UserRepository
) -> None:
    user = await _customer(user_repository)
    now = datetime_now()
    await _text(legal_repository, session, POLICY)
    revision = await _text(
        legal_repository, session, AGREEMENT, reaccept=True, at=now + timedelta(days=1)
    )
    await _accept(
        legal_repository,
        session,
        user,
        revision,
        CABINET,
        now + timedelta(days=2),
        trigger=LegalAcceptanceTrigger.PAYMENT,
    )

    assert _kinds(await _pending(legal_repository, user, CABINET)) == []
