from dataclasses import dataclass
from typing import Literal, Optional

import httpx
from loguru import logger

from app.modules.transactions.dto import TransactionDto
from app.modules.transactions.gateways.yookassa import YooKassaGateway
from app.modules.transactions.recurring_policy import RecurringReason


@dataclass(frozen=True)
class RecurringSubmission:
    outcome: Literal["accepted", "merchant", "configuration", "rejected", "ambiguous"]
    payment_id: Optional[str] = None
    reason: Optional[RecurringReason] = None


def _refusal(response: httpx.Response) -> RecurringSubmission:
    try:
        body = response.json()
    except ValueError:
        body = None
    if not isinstance(body, dict):
        return RecurringSubmission(
            "configuration", reason=RecurringReason.PROVIDER_CONFIGURATION_ERROR
        )
    # YooKassa's stable error code/parameter identify request failures. A generic
    # "method is not available" can be a shop/currency issue, not a revoked card.
    if body.get("code") == "invalid_request" and body.get("parameter") == "payment_method_id":
        description = body.get("description")
        if isinstance(description, str):
            description = description.casefold()
            if any(
                word in description
                for word in (
                    "revoked",
                    "does not exist",
                    "doesn't exist",
                    "not found",
                    "invalid payment_method_id",
                    "incorrect payment_method_id",
                )
            ):
                return RecurringSubmission(
                    "rejected", reason=RecurringReason.PAYMENT_METHOD_RESTRICTED
                )
            if "not available" in description:
                return RecurringSubmission("merchant", reason=RecurringReason.MERCHANT_UNAVAILABLE)
    return RecurringSubmission("configuration", reason=RecurringReason.PROVIDER_CONFIGURATION_ERROR)


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
        if not first_attempt:
            return RecurringSubmission("ambiguous", reason=RecurringReason.MERCHANT_UNAVAILABLE)
        if code in {401, 403}:
            return RecurringSubmission("merchant", reason=RecurringReason.MERCHANT_UNAVAILABLE)
        return _refusal(error.response)
    return RecurringSubmission("accepted", intent.provider_payment_id)
