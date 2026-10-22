from app.modules.legal.usecases.accept_legal_documents import AcceptLegalDocumentsUseCase
from app.modules.legal.usecases.get_pending_legal_documents import (
    GetPendingLegalDocumentsUseCase,
)
from app.modules.legal.usecases.list_legal_documents import ListLegalDocumentsUseCase
from app.modules.legal.usecases.list_user_legal_acceptances import (
    ListUserLegalAcceptancesUseCase,
)
from app.modules.legal.usecases.list_visible_legal_documents import (
    ListVisibleLegalDocumentsUseCase,
)
from app.modules.legal.usecases.remove_legal_text import RemoveLegalTextUseCase
from app.modules.legal.usecases.set_legal_text import SetLegalTextUseCase
from app.modules.legal.usecases.update_legal_document import UpdateLegalDocumentUseCase

__all__ = [
    "AcceptLegalDocumentsUseCase",
    "GetPendingLegalDocumentsUseCase",
    "ListLegalDocumentsUseCase",
    "ListUserLegalAcceptancesUseCase",
    "ListVisibleLegalDocumentsUseCase",
    "RemoveLegalTextUseCase",
    "SetLegalTextUseCase",
    "UpdateLegalDocumentUseCase",
]
