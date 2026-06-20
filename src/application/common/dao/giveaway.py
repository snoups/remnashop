from datetime import datetime
from typing import Optional, Protocol, runtime_checkable
from uuid import UUID

from src.application.dto import GiveawayCampaignDto, GiveawayEntryDto
from src.core.enums import GiveawayCampaignStatus, PurchaseType


@runtime_checkable
class GiveawayDao(Protocol):
    async def create_campaign(self, campaign: GiveawayCampaignDto) -> GiveawayCampaignDto: ...

    async def get_campaign(self, campaign_id: int) -> Optional[GiveawayCampaignDto]: ...

    async def get_campaigns(self) -> list[GiveawayCampaignDto]: ...

    async def get_matching_campaigns(
        self,
        now: datetime,
        plan_id: int,
        duration_days: int,
        purchase_type: PurchaseType,
    ) -> list[GiveawayCampaignDto]: ...

    async def set_campaign_status(
        self,
        campaign_id: int,
        status: GiveawayCampaignStatus,
        now: datetime,
    ) -> Optional[GiveawayCampaignDto]: ...

    async def archive_campaign(
        self,
        campaign_id: int,
        now: datetime,
    ) -> Optional[GiveawayCampaignDto]: ...

    async def delete_campaign(self, campaign_id: int) -> bool: ...

    async def create_entry(self, entry: GiveawayEntryDto) -> Optional[GiveawayEntryDto]: ...

    async def get_entry_by_payment(self, payment_id: UUID) -> Optional[GiveawayEntryDto]: ...

    async def get_entry(self, entry_id: int) -> Optional[GiveawayEntryDto]: ...

    async def update_phone(self, entry_id: int, phone: str) -> Optional[GiveawayEntryDto]: ...

    async def get_entries(self, campaign_id: int) -> list[GiveawayEntryDto]: ...

    async def get_winners(self, campaign_id: int) -> list[GiveawayEntryDto]: ...

    async def count_entries(self, campaign_id: int) -> int: ...

    async def select_winner(
        self,
        campaign_id: int,
        winner_rank: int,
        selected_at: datetime,
    ) -> Optional[GiveawayEntryDto]: ...
