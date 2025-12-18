from typing import Optional

from sqlalchemy import JSON, BigInteger, Boolean, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.enums import AccessMode, Currency
from src.infrastructure.database.models.dto import (
    ReferralSettingsDto,
    SystemNotificationDto,
    UserNotificationDto,
)

from .base import BaseSql


class Settings(BaseSql):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    rules_required: Mapped[bool] = mapped_column(Boolean, nullable=False)
    channel_required: Mapped[bool] = mapped_column(Boolean, nullable=False)

    rules_link: Mapped[str] = mapped_column(String, nullable=False)
    channel_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    channel_link: Mapped[str] = mapped_column(String, nullable=False)

    access_mode: Mapped[AccessMode] = mapped_column(
        Enum(
            AccessMode,
            name="access_mode",
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )
    purchases_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    registration_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False)

    default_currency: Mapped[Currency] = mapped_column(
        Enum(
            Currency,
            name="currency",
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )

    user_notifications: Mapped[UserNotificationDto] = mapped_column(
        JSON,
        default=lambda: UserNotificationDto().model_dump(),
        nullable=False,
    )
    system_notifications: Mapped[SystemNotificationDto] = mapped_column(
        JSON,
        default=lambda: SystemNotificationDto().model_dump(),
        nullable=False,
    )

    referral: Mapped[ReferralSettingsDto] = mapped_column(
        JSON,
        default=lambda: ReferralSettingsDto().model_dump(),
        nullable=False,
    )
