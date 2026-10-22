from typing import AsyncIterator

import pytest
from redis.asyncio import Redis
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import AppConfig
from app.core.db.models.legal_document import LegalAcceptance
from app.core.db.uow import UnitOfWork
from app.core.enums import LegalAcceptanceTrigger, LegalDocumentKind, Locale, PurchaseChannel
from app.modules.legal.dto import AcceptLegalDocumentsDto, CreateLegalRevisionDto
from app.modules.legal.recorder import LegalAcceptanceRecorder
from app.modules.legal.repository import LegalRepository
from app.modules.legal.usecases import (
    AcceptLegalDocumentsUseCase,
    GetPendingLegalDocumentsUseCase,
)
from app.modules.translations.repository import TranslationRepository
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository

BOT = PurchaseChannel.BOT


@pytest.fixture
async def redis(config: AppConfig) -> AsyncIterator[Redis]:
    client = Redis.from_url(config.redis.dsn, decode_responses=True)
    yield client
    await client.aclose()


@pytest.fixture
async def customer(user_repository: UserRepository) -> UserDto:
    return await user_repository.create(CreateUserDto(name="customer", telegram_id=7101))


@pytest.fixture
async def texts(
    legal_repository: LegalRepository, translation_repository: TranslationRepository
) -> None:
    await translation_repository.add_active_locale(Locale.EN)
    for kind in (LegalDocumentKind.USER_AGREEMENT, LegalDocumentKind.PRIVACY_POLICY):
        await _revision(legal_repository, kind, "v1")


async def _revision(repo: LegalRepository, kind: LegalDocumentKind, body: str) -> int:
    revision = await repo.add_revision(
        CreateLegalRevisionDto(
            kind=kind, locale=Locale.EN, channel=None, title="t", body=body, created_by=None
        )
    )
    return revision.id


def _get(
    legal_repository: LegalRepository,
    translation_repository: TranslationRepository,
    uow: UnitOfWork,
    redis: Redis,
) -> GetPendingLegalDocumentsUseCase:
    return GetPendingLegalDocumentsUseCase(legal_repository, translation_repository, redis, uow)


def _accept(
    legal_repository: LegalRepository,
    translation_repository: TranslationRepository,
    uow: UnitOfWork,
) -> AcceptLegalDocumentsUseCase:
    return AcceptLegalDocumentsUseCase(
        legal_repository,
        translation_repository,
        LegalAcceptanceRecorder(legal_repository, translation_repository),
        uow,
    )


async def _rows(session: AsyncSession) -> list[LegalAcceptance]:
    return list((await session.scalars(select(LegalAcceptance))).all())


async def test_accept_records_one_row_per_revision(
    texts: None,
    customer: UserDto,
    legal_repository: LegalRepository,
    translation_repository: TranslationRepository,
    uow: UnitOfWork,
    session: AsyncSession,
    redis: Redis,
) -> None:
    pending = await _get(legal_repository, translation_repository, uow, redis).execute(
        customer, BOT, Locale.EN
    )
    ids = [document.id for document in pending.documents]

    result = await _accept(legal_repository, translation_repository, uow).execute(
        AcceptLegalDocumentsDto(
            user=customer, channel=BOT, locale=Locale.EN, revision_ids=ids, client_ip=None
        )
    )

    assert result.documents == []
    rows = await _rows(session)
    assert sorted(row.revision_id for row in rows) == sorted(ids)
    assert {(row.channel, row.trigger) for row in rows} == {(BOT, LegalAcceptanceTrigger.SIGN_UP)}


async def test_accept_refuses_stale_revision(
    texts: None,
    customer: UserDto,
    legal_repository: LegalRepository,
    translation_repository: TranslationRepository,
    uow: UnitOfWork,
    session: AsyncSession,
    redis: Redis,
) -> None:
    pending = await _get(legal_repository, translation_repository, uow, redis).execute(
        customer, BOT, Locale.EN
    )
    shown = [document.id for document in pending.documents]
    fresh = await _revision(legal_repository, LegalDocumentKind.USER_AGREEMENT, "v2")

    result = await _accept(legal_repository, translation_repository, uow).execute(
        AcceptLegalDocumentsDto(
            user=customer, channel=BOT, locale=Locale.EN, revision_ids=shown, client_ip=None
        )
    )

    assert await _rows(session) == []
    assert fresh in [document.id for document in result.documents]


async def test_accept_with_nothing_pending_is_noop(
    customer: UserDto,
    legal_repository: LegalRepository,
    translation_repository: TranslationRepository,
    uow: UnitOfWork,
    session: AsyncSession,
) -> None:
    result = await _accept(legal_repository, translation_repository, uow).execute(
        AcceptLegalDocumentsDto(
            user=customer, channel=BOT, locale=Locale.EN, revision_ids=[], client_ip=None
        )
    )

    assert result.documents == []
    assert (await session.scalar(select(func.count(LegalAcceptance.id)))) == 0


async def test_nothing_pending_is_cached(
    texts: None,
    customer: UserDto,
    legal_repository: LegalRepository,
    translation_repository: TranslationRepository,
    uow: UnitOfWork,
    session: AsyncSession,
    redis: Redis,
) -> None:
    get = _get(legal_repository, translation_repository, uow, redis)
    pending = await get.execute(customer, BOT, Locale.EN)
    await _accept(legal_repository, translation_repository, uow).execute(
        AcceptLegalDocumentsDto(
            user=customer,
            channel=BOT,
            locale=Locale.EN,
            revision_ids=[d.id for d in pending.documents],
            client_ip=None,
        )
    )
    assert (await get.execute(customer, BOT, Locale.EN)).documents == []

    await session.execute(delete(LegalAcceptance))

    assert (await get.execute(customer, BOT, Locale.EN)).documents == []


async def test_new_revision_invalidates_the_cache(
    texts: None,
    customer: UserDto,
    legal_repository: LegalRepository,
    translation_repository: TranslationRepository,
    uow: UnitOfWork,
    session: AsyncSession,
    redis: Redis,
) -> None:
    get = _get(legal_repository, translation_repository, uow, redis)
    pending = await get.execute(customer, BOT, Locale.EN)
    await _accept(legal_repository, translation_repository, uow).execute(
        AcceptLegalDocumentsDto(
            user=customer,
            channel=BOT,
            locale=Locale.EN,
            revision_ids=[d.id for d in pending.documents],
            client_ip=None,
        )
    )
    assert (await get.execute(customer, BOT, Locale.EN)).documents == []
    await session.execute(delete(LegalAcceptance))

    await _revision(legal_repository, LegalDocumentKind.USER_AGREEMENT, "v2")

    assert len((await get.execute(customer, BOT, Locale.EN)).documents) == 2
