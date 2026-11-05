from datetime import datetime
from typing import Any, Final
from uuid import UUID

from sqlalchemy import ARRAY, DateTime, Enum, Integer, MetaData
from sqlalchemy import UUID as PG_UUID
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, registry

from app.core.enums import Locale, OAuthProvider, PaymentGatewayType, Role
from app.core.events import EventCategory

NAMING_CONVENTION: Final[dict[str, str]] = {
    "pk": "pk_%(table_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "uq": "ux_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "ix": "ix_%(column_0_label)s",
}

mapper_registry = registry(
    metadata=MetaData(naming_convention=NAMING_CONVENTION),
    type_annotation_map={
        int: Integer,
        dict[str, Any]: JSONB,
        UUID: PG_UUID,
        list[UUID]: ARRAY(PG_UUID),
        datetime: DateTime(timezone=True),
        Locale: Enum(Locale, name="locale"),
        Role: Enum(Role, name="user_role"),
        OAuthProvider: Enum(OAuthProvider, name="oauth_provider"),
        PaymentGatewayType: Enum(PaymentGatewayType, name="payment_gateway_type"),
        EventCategory: Enum(EventCategory, name="event_category"),
    },
)


class BaseSql(DeclarativeBase):
    registry = mapper_registry
