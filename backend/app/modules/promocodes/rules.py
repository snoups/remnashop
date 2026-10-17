from datetime import datetime

from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError, ValidationError
from app.modules.promocodes.dto import PromocodeDto


def assert_usable(promo: PromocodeDto, now: datetime) -> None:
    # checked on the code as typed and again on the locked row at claim time
    if not promo.is_active:
        raise NotFoundError(
            f"Promocode '{promo.code}' not found", code=ErrorCode.PROMOCODE_NOT_FOUND
        )
    if promo.expires_at is not None and now > promo.expires_at:
        raise ValidationError(
            f"Promocode '{promo.code}' has expired", code=ErrorCode.PROMOCODE_EXPIRED
        )
