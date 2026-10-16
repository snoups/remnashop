from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.settings import SettingsRepository
from app.modules.subscriptions import PurchaseRollbackService
from app.modules.transactions.dto import RefundPreviewDto
from app.modules.transactions.repository import TransactionRepository
from app.modules.transactions.usecases._refund import refund_refusal, rollback_input
from app.modules.users import UserRepository


class PreviewRefundUseCase(UseCase[int, RefundPreviewDto]):
    required_permission = Permission.TRANSACTIONS_REFUND_PREVIEW

    def __init__(
        self,
        transaction_repository: TransactionRepository,
        user_repository: UserRepository,
        settings_repository: SettingsRepository,
        purchase_rollback_service: PurchaseRollbackService,
        uow: UnitOfWork,
    ) -> None:
        self._transaction_repository = transaction_repository
        self._user_repository = user_repository
        self._settings_repository = settings_repository
        self._purchase_rollback_service = purchase_rollback_service
        self._uow = uow

    async def _execute(self, actor: Actor, data: int) -> RefundPreviewDto:
        async with self._uow:
            order = await self._transaction_repository.get_by_id(data)
            payer = await self._user_repository.find_by_id(order.user_id)
            bot_settings = await self._settings_repository.get_bot_settings()
            reason = refund_refusal(order, payer, bot_settings.token is not None)
            if reason is not None:
                return RefundPreviewDto(refundable=False, reason=reason, rollback=None)
            rollback = await rollback_input(self._transaction_repository, order)

        preview = await self._purchase_rollback_service.preview(rollback)
        return RefundPreviewDto(refundable=True, reason=None, rollback=preview)
