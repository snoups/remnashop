from dishka import Provider, Scope, provide, provide_all

from app.modules.legal.recorder import LegalAcceptanceRecorder
from app.modules.legal.repository import LegalRepository
from app.modules.legal.usecases import (
    AcceptLegalDocumentsUseCase,
    GetPendingLegalDocumentsUseCase,
    ListLegalDocumentsUseCase,
    ListUserLegalAcceptancesUseCase,
    ListVisibleLegalDocumentsUseCase,
    RemoveLegalTextUseCase,
    SetLegalTextUseCase,
    UpdateLegalDocumentUseCase,
)


class LegalProvider(Provider):
    scope = Scope.REQUEST

    legal_repository = provide(LegalRepository)
    legal_acceptance_recorder = provide(LegalAcceptanceRecorder)
    use_cases = provide_all(
        AcceptLegalDocumentsUseCase,
        GetPendingLegalDocumentsUseCase,
        ListLegalDocumentsUseCase,
        ListUserLegalAcceptancesUseCase,
        ListVisibleLegalDocumentsUseCase,
        UpdateLegalDocumentUseCase,
        SetLegalTextUseCase,
        RemoveLegalTextUseCase,
    )


def get_legal_providers() -> list[Provider]:
    return [LegalProvider()]
