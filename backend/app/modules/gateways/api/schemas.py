from typing import Literal

from pydantic import BaseModel, Field

from app.core.enums import PaymentGatewayType


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
    fields: list[GatewayFieldSpecResponse]


class GatewayCatalogResponse(BaseModel):
    entries: list[GatewayCatalogEntryResponse]
