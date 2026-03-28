from datetime import datetime
from typing import Any, Optional

from sqlalchemy import BigInteger, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.core.enums import PromocodeRewardType

from .base import BaseSql
from .timestamp import NOW_FUNC, TimestampMixin


class Promocode(BaseSql, TimestampMixin):
    __tablename__ = "promocodes"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(unique=True)
    is_active: Mapped[bool]

    reward_type: Mapped[PromocodeRewardType]
    reward: Mapped[Optional[int]]
    plan: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    lifetime: Mapped[Optional[int]]
    max_activations: Mapped[Optional[int]]


class PromocodeActivation(BaseSql):
    __tablename__ = "promocode_activations"

    id: Mapped[int] = mapped_column(primary_key=True)
    promocode_id: Mapped[int] = mapped_column(ForeignKey("promocodes.id"))
    user_telegram_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    activated_at: Mapped[datetime] = mapped_column(server_default=NOW_FUNC, nullable=False)
