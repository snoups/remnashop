from dataclasses import dataclass
from typing import Literal, Optional

import httpx
from loguru import logger

from app.modules.transactions.dto import TransactionDto
from app.modules.transactions.gateways.yookassa import YooKassaGateway


@dataclass(frozen=True)
class RecurringSubmission:
    outcome: Literal["accepted", "merchant", "rejected", "ambiguous", "superseded"]
    payment_id: Optional[str] = None


async def submit_recurring(
    gateway: YooKassaGateway,
    order: TransactionDto,
    payment_method: str,
    *,
    first_attempt: bool,
) -> RecurringSubmission:
    try:
        intent = await gateway.create_recurring_payment(order, payment_method)
    except httpx.HTTPStatusError as error:
        code = error.response.status_code
        logger.warning(f"YooKassa order '{order.id}' rejected with HTTP {code}")
        if code not in {400, 401, 403, 404}:
            raise
        # A refusal now cannot establish the outcome of an earlier lost response.
        if not first_attempt:
            return RecurringSubmission("ambiguous")
        return RecurringSubmission("merchant" if code in {401, 403} else "rejected")
    return RecurringSubmission("accepted", intent.provider_payment_id)
