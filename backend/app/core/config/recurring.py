from pydantic import Field

from app.core.config.base import BaseConfig


class RecurringConfig(BaseConfig, env_prefix="RECURRING_"):
    # Relative to the subscription's current expiry, including manual extensions.
    lead_minutes: int = Field(default=60, ge=0, le=1440)
    max_overdue_hours: int = Field(default=24, ge=1, le=168)
    retry_minutes: int = Field(default=5, ge=1, le=60)
    batch_size: int = Field(default=100, ge=1, le=1000)
