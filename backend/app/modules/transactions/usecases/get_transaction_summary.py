from decimal import Decimal

from app.core.actor import Actor
from app.core.constants import ZERO_AMOUNT
from app.core.db.uow import UnitOfWork
from app.core.enums import TransactionStatus
from app.core.security.permissions import Permission, PermissionPolicy
from app.core.usecase import UseCase
from app.modules.pricing import PricingRepository
from app.modules.transactions.dto import GetTransactionSummaryDto, TransactionSummaryDto
from app.modules.transactions.repository import TransactionRepository


class GetTransactionSummaryUseCase(UseCase[GetTransactionSummaryDto, TransactionSummaryDto]):
    required_permission = Permission.TRANSACTIONS_SUMMARY_VIEW

    def __init__(
        self,
        transaction_repository: TransactionRepository,
        pricing_repository: PricingRepository,
        uow: UnitOfWork,
    ) -> None:
        self._transaction_repository = transaction_repository
        self._pricing_repository = pricing_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: GetTransactionSummaryDto) -> TransactionSummaryDto:
        async with self._uow:
            rows = await self._transaction_repository.summarize(
                status=data.status,
                gateway_type=data.gateway_type,
                purchase_type=data.purchase_type,
                created_from=data.created_from,
                created_to=data.created_to,
                search=data.search,
                user_id=data.user_id,
                search_staff=PermissionPolicy.has_permission(actor, Permission.ADMINS_MANAGE),
            )
            rate_table = await self._pricing_repository.get_rate_table()

        report_currency = rate_table.anchor
        counts: dict[TransactionStatus, int] = {}
        amounts: dict[TransactionStatus, Decimal] = {}
        paid_base = ZERO_AMOUNT
        for order_status, count, amount, base_amount in rows:
            counts[order_status] = count
            amounts[order_status] = amount
            if order_status is TransactionStatus.PAID:
                paid_base = base_amount

        total_count = sum(counts.values())
        paid_count = counts.get(TransactionStatus.PAID, 0)
        revenue = amounts.get(TransactionStatus.PAID, ZERO_AMOUNT)
        return TransactionSummaryDto(
            report_currency=report_currency,
            total_count=total_count,
            pending_count=counts.get(TransactionStatus.PENDING, 0),
            paid_count=paid_count,
            conversion_rate=Decimal(paid_count) / total_count if total_count > 0 else ZERO_AMOUNT,
            revenue=revenue,
            average_check=revenue / paid_count if paid_count > 0 else None,
            average_discount=(paid_base - revenue) / paid_base if paid_base > 0 else None,
            discount_amount=paid_base - revenue,
            refunded_amount=amounts.get(TransactionStatus.REFUNDED, ZERO_AMOUNT),
        )
