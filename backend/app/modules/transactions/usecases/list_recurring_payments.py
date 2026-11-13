from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission, PermissionPolicy
from app.core.usecase import UseCase
from app.modules.transactions.recurring_admin import (
    ListRecurringPaymentsDto,
    RecurringPaymentAdminPage,
)
from app.modules.transactions.recurring_admin_repository import RecurringPaymentAdminRepository


class ListRecurringPaymentsUseCase(UseCase[ListRecurringPaymentsDto, RecurringPaymentAdminPage]):
    required_permission = Permission.TRANSACTIONS_RECURRING_VIEW

    def __init__(self, repository: RecurringPaymentAdminRepository, uow: UnitOfWork) -> None:
        self._repository = repository
        self._uow = uow

    async def _execute(
        self, actor: Actor, data: ListRecurringPaymentsDto
    ) -> RecurringPaymentAdminPage:
        async with self._uow:
            items, total = await self._repository.list_page(
                data,
                actor_id=actor.id,
                show_staff=PermissionPolicy.has_permission(actor, Permission.ADMINS_MANAGE),
            )
            summary = await self._repository.summary()
        return RecurringPaymentAdminPage(
            items=items, total=total, page=data.page, page_size=data.page_size, summary=summary
        )
