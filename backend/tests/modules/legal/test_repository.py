import asyncio
from typing import Optional

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.db.models.legal_document import LegalDocument
from app.core.enums import LegalDocumentKind, Locale, PurchaseChannel
from app.modules.legal.dto import CreateLegalRevisionDto
from app.modules.legal.repository import LegalRepository

KIND = LegalDocumentKind.OFFER


async def _add(
    repo: LegalRepository, locale: Locale, channel: Optional[PurchaseChannel], body: str
) -> None:
    await repo.add_revision(
        CreateLegalRevisionDto(
            kind=KIND, locale=locale, channel=channel, title="t", body=body, created_by=None
        )
    )


async def test_resolve_prefers_own_language_over_channel_override(
    legal_repository: LegalRepository,
) -> None:
    await _add(legal_repository, Locale.RU, None, "ru common")
    await _add(legal_repository, Locale.EN, PurchaseChannel.CABINET, "en cabinet")

    found = await legal_repository.resolve(KIND, PurchaseChannel.CABINET, Locale.RU, Locale.EN)

    assert found is not None and found.body == "ru common"


async def test_resolve_uses_channel_override(legal_repository: LegalRepository) -> None:
    await _add(legal_repository, Locale.RU, None, "common")
    await _add(legal_repository, Locale.RU, PurchaseChannel.BOT, "bot")

    bot = await legal_repository.resolve(KIND, PurchaseChannel.BOT, Locale.RU, Locale.EN)
    cabinet = await legal_repository.resolve(KIND, PurchaseChannel.CABINET, Locale.RU, Locale.EN)

    assert bot is not None and bot.body == "bot"
    assert cabinet is not None and cabinet.body == "common"


async def test_removed_override_falls_back_to_common(legal_repository: LegalRepository) -> None:
    await _add(legal_repository, Locale.RU, None, "common")
    await _add(legal_repository, Locale.RU, PurchaseChannel.BOT, "bot")
    await _add(legal_repository, Locale.RU, PurchaseChannel.BOT, "")

    found = await legal_repository.resolve(KIND, PurchaseChannel.BOT, Locale.RU, Locale.EN)

    assert found is not None and found.body == "common"


async def test_resolve_falls_back_to_default_locale(legal_repository: LegalRepository) -> None:
    await _add(legal_repository, Locale.EN, None, "en")

    found = await legal_repository.resolve(KIND, PurchaseChannel.BOT, Locale.RU, Locale.EN)

    assert found is not None and found.body == "en"


async def test_resolve_returns_none_when_all_empty(legal_repository: LegalRepository) -> None:
    await _add(legal_repository, Locale.RU, None, "")
    await _add(legal_repository, Locale.EN, None, "  ")

    assert await legal_repository.resolve(KIND, PurchaseChannel.BOT, Locale.RU, Locale.EN) is None


async def test_list_current_revisions_keeps_latest_per_key(
    legal_repository: LegalRepository,
) -> None:
    await _add(legal_repository, Locale.RU, None, "old")
    await _add(legal_repository, Locale.RU, None, "")
    await _add(legal_repository, Locale.RU, PurchaseChannel.BOT, "bot")

    current = await legal_repository.list_current_revisions()

    assert sorted(r.body for r in current) == ["", "bot"]


async def test_list_documents_creates_all_kinds_once(legal_repository: LegalRepository) -> None:
    await legal_repository.list_documents()
    documents = await legal_repository.list_documents()

    assert [d.kind for d in documents] == list(LegalDocumentKind)
    assert not any(d.show_in_bot or d.show_in_cabinet for d in documents)


async def test_concurrent_first_reads_create_documents_once(engine: AsyncEngine) -> None:
    # two real connections, both commit, so the cleanup is a try/finally
    session_a = AsyncSession(bind=engine, expire_on_commit=False)
    session_b = AsyncSession(bind=engine, expire_on_commit=False)
    try:
        first = await LegalRepository(session_a).list_documents()
        # waits on the first one's uncommitted rows, then must not hit the unique index
        second = asyncio.create_task(LegalRepository(session_b).list_documents())
        await asyncio.sleep(0.2)
        await session_a.commit()
        documents = await second
        await session_b.commit()

        assert [d.kind for d in documents] == list(LegalDocumentKind)
        assert [d.id for d in documents] == [d.id for d in first]
    finally:
        await session_a.close()
        await session_b.close()
        async with AsyncSession(bind=engine) as cleanup:
            await cleanup.execute(delete(LegalDocument))
            await cleanup.commit()
