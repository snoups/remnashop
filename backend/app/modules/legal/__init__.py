from app.modules.legal.di import get_legal_providers
from app.modules.legal.dto import (
    AcceptLegalDocumentsDto,
    LegalRevisionDto,
    PendingLegalDocumentsDto,
)
from app.modules.legal.recorder import LegalAcceptanceRecorder
from app.modules.legal.usecases import (
    AcceptLegalDocumentsUseCase,
    GetPendingLegalDocumentsUseCase,
    ListVisibleLegalDocumentsUseCase,
)

__all__ = [
    "AcceptLegalDocumentsDto",
    "AcceptLegalDocumentsUseCase",
    "GetPendingLegalDocumentsUseCase",
    "LegalAcceptanceRecorder",
    "LegalRevisionDto",
    "ListVisibleLegalDocumentsUseCase",
    "PendingLegalDocumentsDto",
    "get_legal_providers",
]
