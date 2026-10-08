from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, field_validator


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
    personal_discount: int
    purchase_discount: int
    loyalty_discount: int
    referral_code: Optional[str]
    points: Decimal
    bonus_days: int
    is_trial_available: bool
    created_at: Optional[datetime]
    deleted_at: Optional[datetime] = None

    @field_validator("role", "language", mode="before")
    @classmethod
    def _enum_as_name(cls, value: object) -> str:
        # Role's value is its rank; the API speaks its name
        return str(value)
