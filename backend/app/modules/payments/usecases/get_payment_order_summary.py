from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Final, Optional

from app.core.db.uow import UnitOfWork
from app.core.enums import PaymentGatewayType, PaymentOrderStatus, PurchaseType
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.payments.dto import PaymentOrderSummaryDto
from app.modules.payments.repository import PaymentOrderRepository
from app.modules.pricing import PricingRepository, convert_for_report
from app.modules.users import UserDto

_ZERO: Final[Decimal] = Decimal(0)


@dataclass(frozen=True, kw_only=True)
class GetPaymentOrderSummaryInput:
    status: Optional[PaymentOrderStatus] = None
    gateway_type: Optional[PaymentGatewayType] = None
    purchase_type: Optional[PurchaseType] = None
    created_from: Optional[datetime] = None
    created_to: Optional[datetime] = None
    search: Optional[str] = None
    user_id: Optional[int] = None


class GetPaymentOrderSummaryUseCase(UseCase[GetPaymentOrderSummaryInput, PaymentOrderSummaryDto]):
    required_permission = Permission.PAYMENTS_SUMMARY_VIEW

    def __init__(
        self,
        payment_order_repository: PaymentOrderRepository,
        pricing_repository: PricingRepository,
        uow: UnitOfWork,
    ) -> None:
        self._payment_order_repository = payment_order_repository
        self._pricing_repository = pricing_repository
        self._uow = uow

    async def _execute(
        self, actor: UserDto, data: GetPaymentOrderSummaryInput
    ) -> PaymentOrderSummaryDto:
        async with self._uow:
            rows = await self._payment_order_repository.summarize(
                status=data.status,
                gateway_type=data.gateway_type,
                purchase_type=data.purchase_type,
                created_from=data.created_from,
                created_to=data.created_to,
                search=data.search,
                user_id=data.user_id,
            )
            rate_table = await self._pricing_repository.get_rate_table()

        report_currency = rate_table.anchor
        counts: dict[PaymentOrderStatus, int] = {}
        amounts: dict[PaymentOrderStatus, Decimal] = {}
        paid_base = _ZERO
        for order_status, currency, count, amount, base_amount in rows:
            counts[order_status] = counts.get(order_status, 0) + count
            amounts[order_status] = amounts.get(order_status, _ZERO) + convert_for_report(
                amount, currency, report_currency, rate_table
            )
            if order_status is PaymentOrderStatus.PAID:
                paid_base += convert_for_report(base_amount, currency, report_currency, rate_table)

        total_count = sum(counts.values())
        paid_count = counts.get(PaymentOrderStatus.PAID, 0)
        revenue = amounts.get(PaymentOrderStatus.PAID, _ZERO)
        return PaymentOrderSummaryDto(
            report_currency=report_currency,
            total_count=total_count,
            pending_count=counts.get(PaymentOrderStatus.PENDING, 0),
            paid_count=paid_count,
            conversion_rate=Decimal(paid_count) / total_count if total_count > 0 else _ZERO,
            revenue=revenue,
            average_check=revenue / paid_count if paid_count > 0 else None,
            average_discount=(paid_base - revenue) / paid_base if paid_base > 0 else None,
            discount_amount=paid_base - revenue,
            refunded_amount=amounts.get(PaymentOrderStatus.REFUNDED, _ZERO),
        )
