from dataclasses import dataclass
from datetime import datetime, timedelta
from math import ceil
from typing import Final, Optional

from src.application.dto import PromocodeDto
from src.core.enums import PromocodeRewardType
from src.core.utils.time import datetime_now

SUPPORTED_PROMOCODE_REWARD_TYPES: Final[tuple[PromocodeRewardType, ...]] = (
    PromocodeRewardType.PERSONAL_DISCOUNT,
    PromocodeRewardType.PURCHASE_DISCOUNT,
    PromocodeRewardType.DURATION,
    PromocodeRewardType.TRAFFIC,
)


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


def build_default_promocode() -> PromocodeDto:
    return PromocodeDto(
        code="",
        is_active=True,
        reward_type=PromocodeRewardType.PURCHASE_DISCOUNT,
        reward=10,
        lifetime=None,
        max_activations=None,
    )


def is_valid_promocode_reward(reward_type: PromocodeRewardType, reward: int) -> bool:
    if reward < 1:
        return False

    if reward_type in {
        PromocodeRewardType.PERSONAL_DISCOUNT,
        PromocodeRewardType.PURCHASE_DISCOUNT,
    }:
        return reward <= 100

    return True


def _normalize_created_at(value: Optional[datetime | str]) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value

    if not value:
        return None

    # В dialog_data timestamp может временно приехать строкой.
    # Для runtime-проверок промокода нормализуем его обратно в datetime.
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime_now().tzinfo)

    return parsed


def get_promocode_runtime_state(
    promocode: PromocodeDto,
    activation_count: int,
) -> PromocodeRuntimeState:
    now = datetime_now()
    created_at = _normalize_created_at(promocode.created_at)

    has_lifetime_limit = promocode.lifetime is not None and created_at is not None
    remaining_lifetime_days: Optional[int] = None
    is_expired = False

    if has_lifetime_limit and created_at is not None and promocode.lifetime is not None:
        expire_at = created_at + timedelta(days=promocode.lifetime)
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
