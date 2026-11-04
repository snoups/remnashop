from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, field_validator

from app.core.security.permissions import Permission, PermissionPolicy
from app.modules.users.dto import UserDto


# lives outside api/: users and account_merge both answer with it, and importing
# users.api from the package would pull in the routers
class UserResponse(BaseModel):
    id: int
    name: str
    role: str
    telegram_id: Optional[int]
    username: Optional[str]
    email: Optional[str]
    login: Optional[str]
    language: str
    is_blocked: bool
    is_bot_blocked: bool = False
    personal_discount: int
    purchase_discount: int
    loyalty_discount: int
    referral_code: Optional[str]
    points: Decimal
    bonus_days: int
    is_trial_available: bool
    created_at: Optional[datetime]
    deleted_at: Optional[datetime] = None
    email_undeliverable_at: Optional[datetime] = None

    @field_validator("role", "language", mode="before")
    @classmethod
    def _enum_as_name(cls, value: object) -> str:
        # Role's value is its rank; the API speaks its name
        return str(value)


# what every admin route answers about one user: the list row, its card, and each
# action on it, so a list can swap a row for the response
class UserListItemResponse(UserResponse):
    active_subscriptions: int
    limited_subscriptions: int
    expired_subscriptions: int


def effective_permission_names(user: UserDto) -> list[str]:
    return sorted(p.value for p in PermissionPolicy.effective_permissions(user))


class CurrentUserResponse(BaseModel):
    id: int
    login: Optional[str]
    name: str
    role: str
    effective_permissions: list[Permission]
    password_change_required: bool
    language: str
    email: Optional[str]
    telegram_id: Optional[int]
    username: Optional[str]
    created_at: Optional[datetime]
    points: Decimal
    bonus_days: int
    personal_discount: int
    purchase_discount: int
    loyalty_discount: int

    @field_validator("role", "language", mode="before")
    @classmethod
    def _enum_as_name(cls, value: object) -> str:
        # Role's value is its rank; the API speaks its name
        return str(value)


# /users/me and the cabinet's self-merge answer with the same body
def to_current_user_response(user: UserDto) -> CurrentUserResponse:
    return CurrentUserResponse.model_validate(
        {**dict(user), "effective_permissions": effective_permission_names(user)}
    )
