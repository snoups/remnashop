from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.core.enums import PaymentGatewayType, PaymentOrderStatus


class GatewayTestPaymentResponse(BaseModel):
    order_id: int
    confirmation_url: Optional[str]


class GatewayTestPaymentStatusResponse(BaseModel):
    status: PaymentOrderStatus


class GatewayResponse(BaseModel):
    type: PaymentGatewayType
    order_index: int
    is_active: bool
    is_configured: bool


class UpdateGatewaySettingsRequest(BaseModel):
    values: dict[str, str] = Field(min_length=1)


class ReorderGatewaysRequest(BaseModel):
    types: list[PaymentGatewayType]


class GatewayFieldSpecResponse(BaseModel):
    key: str
    kind: Literal["text", "secret", "number"]
    required: bool


class GatewayCatalogEntryResponse(BaseModel):
    type: PaymentGatewayType
    webhook_url: Optional[str]
    fields: list[GatewayFieldSpecResponse]


class GatewayCatalogResponse(BaseModel):
    entries: list[GatewayCatalogEntryResponse]
