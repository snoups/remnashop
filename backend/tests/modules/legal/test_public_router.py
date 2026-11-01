from typing import AsyncIterator, Optional

import httpx
import pytest
from dishka import AsyncContainer
from fastapi import FastAPI

from app.core.constants import API_V1
from app.core.enums import LegalDocumentKind, Locale, PurchaseChannel
from app.modules.legal.dto import CreateLegalRevisionDto
from app.modules.legal.repository import LegalRepository
from app.modules.translations.repository import TranslationRepository

pytestmark = pytest.mark.usefixtures("shown_documents")

URL = f"{API_V1}/legal/documents"


@pytest.fixture
async def client(
    test_container: AsyncContainer, api_app: FastAPI
) -> AsyncIterator[httpx.AsyncClient]:
    app = api_app
    app.state.dishka_container = test_container
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client


async def _put(
    repo: LegalRepository,
    body: str,
    locale: Locale = Locale.EN,
    channel: Optional[PurchaseChannel] = None,
) -> None:
    await repo.add_revision(
        CreateLegalRevisionDto(
            kind=LegalDocumentKind.OFFER,
            locale=locale,
            channel=channel,
            title="Offer",
            body=body,
            created_by=None,
        )
    )


async def test_public_documents_need_no_session(
    client: httpx.AsyncClient,
    legal_repository: LegalRepository,
    translation_repository: TranslationRepository,
) -> None:
    await translation_repository.add_active_locale(Locale.EN)
    await _put(legal_repository, "Terms")

    response = await client.get(URL, params={"locale": "en"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["kind"] == "OFFER"
    assert body["items"][0]["body"] == "Terms"
    assert body["items"][0]["revision_id"] > 0


async def test_unknown_locale_falls_back_to_default(
    client: httpx.AsyncClient,
    legal_repository: LegalRepository,
    translation_repository: TranslationRepository,
) -> None:
    await translation_repository.add_active_locale(Locale.EN)
    await _put(legal_repository, "Terms")

    for locale in ("zz", "ru"):
        response = await client.get(URL, params={"locale": locale})
        assert response.status_code == 200
        assert response.json()["items"][0]["body"] == "Terms"


async def test_hidden_in_cabinet_is_not_listed(
    client: httpx.AsyncClient,
    legal_repository: LegalRepository,
    translation_repository: TranslationRepository,
) -> None:
    await translation_repository.add_active_locale(Locale.EN)
    await _put(legal_repository, "Terms")
    await legal_repository.update_document(
        LegalDocumentKind.OFFER, show_in_bot=None, show_in_cabinet=False
    )

    response = await client.get(URL, params={"locale": "en"})

    assert response.json() == {"items": [], "total": 0}


async def test_cabinet_override_is_served(
    client: httpx.AsyncClient,
    legal_repository: LegalRepository,
    translation_repository: TranslationRepository,
) -> None:
    await translation_repository.add_active_locale(Locale.EN)
    await _put(legal_repository, "Common")
    await _put(legal_repository, "Cabinet only", channel=PurchaseChannel.CABINET)
    await _put(legal_repository, "Bot only", channel=PurchaseChannel.BOT)

    response = await client.get(URL, params={"locale": "en"})

    assert [item["body"] for item in response.json()["items"]] == ["Cabinet only"]
