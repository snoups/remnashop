import pytest

from app.core.enums import LegalDocumentKind
from app.modules.legal.repository import LegalRepository


@pytest.fixture
async def shown_documents(legal_repository: LegalRepository) -> None:
    """Documents start hidden; these tests exercise the visible ones."""
    for kind in LegalDocumentKind:
        await legal_repository.update_document(kind, show_in_bot=True, show_in_cabinet=True)
