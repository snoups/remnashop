from dataclasses import dataclass
from datetime import timedelta
from math import ceil
from typing import Optional

from src.application.dto import PromocodeDto
from src.core.utils.time import datetime_now


@dataclass(frozen=True)
class PromocodeRuntimeState:
    is_expired: bool
    is_limit_reached: bool
    has_lifetime_limit: bool
    has_activation_limit: bool
    remaining_lifetime_days: Optional[int]
    remaining_activations: Optional[int]

    @property
    def should_disable(self) -> bool:
        return self.is_expired or self.is_limit_reached


def get_promocode_runtime_state(
    promocode: PromocodeDto,
    activation_count: int,
) -> PromocodeRuntimeState:
    now = datetime_now()

    has_lifetime_limit = promocode.lifetime is not None and promocode.created_at is not None
    remaining_lifetime_days: Optional[int] = None
    is_expired = False

    if has_lifetime_limit and promocode.created_at is not None and promocode.lifetime is not None:
        expire_at = promocode.created_at + timedelta(days=promocode.lifetime)
        lifetime_left = expire_at - now
        is_expired = lifetime_left.total_seconds() <= 0

        if not is_expired:
            remaining_lifetime_days = max(1, ceil(lifetime_left.total_seconds() / 86400))

    has_activation_limit = promocode.max_activations is not None
    remaining_activations: Optional[int] = None
    is_limit_reached = False

    if has_activation_limit and promocode.max_activations is not None:
        remaining_activations = max(promocode.max_activations - activation_count, 0)
        is_limit_reached = remaining_activations == 0

    return PromocodeRuntimeState(
        is_expired=is_expired,
        is_limit_reached=is_limit_reached,
        has_lifetime_limit=has_lifetime_limit,
        has_activation_limit=has_activation_limit,
        remaining_lifetime_days=remaining_lifetime_days,
        remaining_activations=remaining_activations,
    )
