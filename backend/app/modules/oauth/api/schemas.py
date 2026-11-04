from typing import Optional

from pydantic import BaseModel


class OAuthAuthorizeResponse(BaseModel):
    url: str


class OAuthCallbackRequest(BaseModel):
    code: str
    state: str


class OAuthIdentityResponse(BaseModel):
    provider: str
    external_login: Optional[str] = None


class OAuthIdentityListResponse(BaseModel):
    items: list[OAuthIdentityResponse]
    total: int
