from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import ARRAY, DateTime, Enum, Integer
from sqlalchemy import UUID as PG_UUID
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, registry

from app.core.enums import Locale, OAuthProvider, PaymentGatewayType, Role
from app.core.events import EventCategory

mapper_registry = registry(
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
    }
)


class BaseSql(DeclarativeBase):
    registry = mapper_registry
