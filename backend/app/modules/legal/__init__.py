from app.modules.legal.di import get_legal_providers
from app.modules.legal.dto import (
    AcceptLegalDocumentsDto,
    CreateLegalAcceptanceDto,
    CreateLegalRevisionDto,
    LegalAcceptanceDto,
    LegalDocumentDto,
    LegalRevisionDto,
    PendingLegalDocumentsDto,
)
from app.modules.legal.pending import GATED_KINDS
from app.modules.legal.recorder import LegalAcceptanceRecorder
from app.modules.legal.repository import LegalRepository
from app.modules.legal.usecases import (
    AcceptLegalDocumentsUseCase,
    GetPendingLegalDocumentsUseCase,
    ListVisibleLegalDocumentsUseCase,
)
from app.modules.legal.visibility import visible_documents

__all__ = [
    "GATED_KINDS",
    "AcceptLegalDocumentsDto",
    "AcceptLegalDocumentsUseCase",
    "CreateLegalAcceptanceDto",
    "CreateLegalRevisionDto",
    "GetPendingLegalDocumentsUseCase",
    "LegalAcceptanceDto",
    "LegalAcceptanceRecorder",
    "LegalDocumentDto",
    "LegalRepository",
    "LegalRevisionDto",
    "ListVisibleLegalDocumentsUseCase",
    "PendingLegalDocumentsDto",
    "get_legal_providers",
    "visible_documents",
]
