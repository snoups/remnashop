from pydantic import BaseModel, ConfigDict, Field

from app.modules.connect_guide.catalog import ConnectCatalog, ConnectPlatform


class ConnectGuideRequest(BaseModel):
    enabled: bool
    catalog: ConnectCatalog


class ConnectGuideResponse(BaseModel):
    enabled: bool
    catalog: ConnectCatalog
    is_default: bool


class PublicConnectGuideResponse(BaseModel):
    # empty while the guide is switched off: the cabinet falls back to its plain link page
    platforms: list[ConnectPlatform]


class ConnectHandoffVerifyRequest(BaseModel):
    # SHA-256 of the subscription link, never the link itself: the request may be logged on the way
    model_config = ConfigDict(extra="forbid")

    digest: str = Field(min_length=43, max_length=43)
    signature: str = Field(min_length=43, max_length=43)


class ConnectHandoffVerifyResponse(BaseModel):
    valid: bool
