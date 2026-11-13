from pydantic import Field

from app.core.config.base import BaseConfig


class RecurringConfig(BaseConfig, env_prefix="RECURRING_"):
    # Relative to the subscription's current expiry, including manual extensions.
    lead_minutes: int = Field(default=1440, ge=0, le=1440)
    max_overdue_hours: int = Field(default=96, ge=1, le=168)
    retry_minutes: int = Field(default=5, ge=1, le=60)
    batch_size: int = Field(default=1000, ge=1, le=10000)
    poll_batch_size: int = Field(default=1000, ge=1, le=10000)
    notice_lead_minutes: int = Field(default=2880, ge=0, le=10080)
    pending_timeout_hours: int = Field(default=24, ge=1, le=168)
    # A full debit/poll batch can need 40 minutes at the default worker concurrency.
    queue_lease_minutes: int = Field(default=60, ge=1, le=120)
