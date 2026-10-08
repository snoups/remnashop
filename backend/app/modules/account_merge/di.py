from dishka import Provider, Scope, provide_all

from app.modules.account_merge.repository import AccountMergeRepository
from app.modules.account_merge.usecases import GetMergePreviewUseCase, MergeAccountsUseCase


class AccountMergeProvider(Provider):
    scope = Scope.REQUEST

    repositories = provide_all(AccountMergeRepository)
    use_cases = provide_all(GetMergePreviewUseCase, MergeAccountsUseCase)


def get_account_merge_providers() -> list[Provider]:
    return [AccountMergeProvider()]
