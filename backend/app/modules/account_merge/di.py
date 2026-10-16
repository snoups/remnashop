from dishka import Provider, Scope, provide, provide_all

from app.modules.account_merge.repository import AccountMergeRepository
from app.modules.account_merge.usecases import (
    CustomerAccountMerger,
    GetMergePreviewUseCase,
    MergeAccountsUseCase,
)


class AccountMergeProvider(Provider):
    scope = Scope.REQUEST

    account_merge_repository = provide(AccountMergeRepository)
    use_cases = provide_all(GetMergePreviewUseCase, MergeAccountsUseCase)
    customer_merger = provide(CustomerAccountMerger)


def get_account_merge_providers() -> list[Provider]:
    return [AccountMergeProvider()]
