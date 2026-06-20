import secrets
import string
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from loguru import logger

from src.application.common import Interactor
from src.application.common.dao import GiveawayDao
from src.application.common.policy import Permission
from src.application.common.uow import UnitOfWork
from src.application.dto import (
    GiveawayCampaignDto,
    GiveawayEntryDto,
    TransactionDto,
    UserDto,
)
from src.core.enums import GiveawayCampaignStatus, PurchaseType
from src.core.utils.time import datetime_now


@dataclass(frozen=True)
class CreateGiveawayCampaignDto:
    name: str
    starts_at: datetime
    ends_at: datetime
    winner_count: int
    prize_amount: Decimal
    eligible_plan_id: int
    eligible_duration_days: int
    eligible_purchase_types: list[PurchaseType]
    is_active: bool


class CreateGiveawayCampaign(Interactor[CreateGiveawayCampaignDto, GiveawayCampaignDto]):
    required_permission = Permission.REMNASHOP_GIVEAWAY_EDITOR

    def __init__(self, uow: UnitOfWork, giveaway_dao: GiveawayDao) -> None:
        self.uow = uow
        self.giveaway_dao = giveaway_dao

    async def _execute(
        self,
        actor: UserDto,
        data: CreateGiveawayCampaignDto,
    ) -> GiveawayCampaignDto:
        if not data.name.strip() or len(data.name.strip()) > 128:
            raise ValueError("Invalid giveaway name")
        if data.ends_at <= data.starts_at:
            raise ValueError("Giveaway end must be after start")
        if data.winner_count < 1 or data.prize_amount < 0:
            raise ValueError("Invalid giveaway prize settings")
        if not data.eligible_purchase_types:
            raise ValueError("At least one purchase type is required")

        async with self.uow:
            campaign = await self.giveaway_dao.create_campaign(
                GiveawayCampaignDto(
                    name=data.name.strip(),
                    status=(
                        GiveawayCampaignStatus.ACTIVE
                        if data.is_active
                        else GiveawayCampaignStatus.DRAFT
                    ),
                    starts_at=data.starts_at,
                    ends_at=data.ends_at,
                    winner_count=data.winner_count,
                    prize_amount=data.prize_amount,
                    eligible_plan_id=data.eligible_plan_id,
                    eligible_duration_days=data.eligible_duration_days,
                    eligible_purchase_types=data.eligible_purchase_types,
                    code_prefix="VAY",
                )
            )
            await self.uow.commit()
        logger.info(f"{actor.log} Created giveaway campaign id='{campaign.id}'")
        return campaign


@dataclass(frozen=True)
class SetGiveawayStatusDto:
    campaign_id: int
    status: GiveawayCampaignStatus


class SetGiveawayStatus(Interactor[SetGiveawayStatusDto, GiveawayCampaignDto]):
    required_permission = Permission.REMNASHOP_GIVEAWAY_EDITOR

    def __init__(self, uow: UnitOfWork, giveaway_dao: GiveawayDao) -> None:
        self.uow = uow
        self.giveaway_dao = giveaway_dao

    async def _execute(self, actor: UserDto, data: SetGiveawayStatusDto) -> GiveawayCampaignDto:
        async with self.uow:
            campaign = await self.giveaway_dao.set_campaign_status(
                data.campaign_id,
                data.status,
                datetime_now(),
            )
            if not campaign:
                raise ValueError("Giveaway campaign not found")
            await self.uow.commit()
        logger.info(
            f"{actor.log} Set giveaway campaign '{data.campaign_id}' status='{data.status}'"
        )
        return campaign


class ArchiveGiveawayCampaign(Interactor[int, GiveawayCampaignDto]):
    required_permission = Permission.REMNASHOP_GIVEAWAY_EDITOR

    def __init__(self, uow: UnitOfWork, giveaway_dao: GiveawayDao) -> None:
        self.uow = uow
        self.giveaway_dao = giveaway_dao

    async def _execute(self, actor: UserDto, campaign_id: int) -> GiveawayCampaignDto:
        async with self.uow:
            campaign = await self.giveaway_dao.archive_campaign(campaign_id, datetime_now())
            if not campaign:
                raise ValueError("Giveaway campaign not found")
            await self.uow.commit()
        logger.warning(f"{actor.log} Archived giveaway campaign '{campaign_id}'")
        return campaign


class DeleteGiveawayCampaign(Interactor[int, None]):
    required_permission = Permission.REMNASHOP_GIVEAWAY_EDITOR

    def __init__(self, uow: UnitOfWork, giveaway_dao: GiveawayDao) -> None:
        self.uow = uow
        self.giveaway_dao = giveaway_dao

    async def _execute(self, actor: UserDto, campaign_id: int) -> None:
        async with self.uow:
            deleted = await self.giveaway_dao.delete_campaign(campaign_id)
            if not deleted:
                raise ValueError("Giveaway campaign not found")
            await self.uow.commit()
        logger.warning(f"{actor.log} Deleted giveaway campaign '{campaign_id}'")


@dataclass(frozen=True)
class RegisterGiveawayEntryDto:
    user: UserDto
    transaction: TransactionDto


class RegisterGiveawayEntry(
    Interactor[RegisterGiveawayEntryDto, list[GiveawayEntryDto]]
):
    required_permission = None
    _ALPHABET = string.ascii_uppercase + string.digits

    def __init__(self, uow: UnitOfWork, giveaway_dao: GiveawayDao) -> None:
        self.uow = uow
        self.giveaway_dao = giveaway_dao

    async def _execute(
        self,
        actor: UserDto,
        data: RegisterGiveawayEntryDto,
    ) -> list[GiveawayEntryDto]:
        transaction = data.transaction
        existing = await self.giveaway_dao.get_entry_by_payment(transaction.payment_id)
        if existing:
            logger.info(
                f"Giveaway entry already exists for payment '{transaction.payment_id}'"
            )
            return [existing]

        now = datetime_now()
        campaigns = await self.giveaway_dao.get_matching_campaigns(
            now=now,
            plan_id=transaction.plan_snapshot.id,
            duration_days=transaction.plan_snapshot.duration,
            purchase_type=transaction.purchase_type,
        )
        created: list[GiveawayEntryDto] = []
        for campaign in campaigns:
            if campaign.id is None:
                continue
            for _ in range(10):
                code = self._generate_code(campaign.code_prefix)
                async with self.uow:
                    entry = await self.giveaway_dao.create_entry(
                        GiveawayEntryDto(
                            campaign_id=campaign.id,
                            user_telegram_id=data.user.telegram_id,
                            telegram_username=data.user.username,
                            participant_code=code,
                            transaction_payment_id=transaction.payment_id,
                            plan_id=transaction.plan_snapshot.id,
                            plan_name=transaction.plan_snapshot.name,
                            duration_days=transaction.plan_snapshot.duration,
                            purchase_type=transaction.purchase_type,
                        )
                    )
                    if entry:
                        await self.uow.commit()
                        created.append(entry)
                        logger.info(
                            f"Registered giveaway entry id='{entry.id}' "
                            f"campaign='{campaign.id}' payment='{transaction.payment_id}'"
                        )
                        return created
                    await self.uow.rollback()

                existing = await self.giveaway_dao.get_entry_by_payment(transaction.payment_id)
                if existing:
                    return [existing]
            else:
                logger.error(
                    f"Failed to generate unique giveaway code for campaign '{campaign.id}'"
                )
        return created

    def _generate_code(self, prefix: str) -> str:
        left = "".join(secrets.choice(self._ALPHABET) for _ in range(4))
        right = "".join(secrets.choice(self._ALPHABET) for _ in range(4))
        return f"{prefix}-{left}-{right}"


@dataclass(frozen=True)
class SaveGiveawayPhoneDto:
    entry_id: int
    user_telegram_id: int
    phone: str


class SaveGiveawayPhone(Interactor[SaveGiveawayPhoneDto, GiveawayEntryDto]):
    required_permission = Permission.PUBLIC

    def __init__(self, uow: UnitOfWork, giveaway_dao: GiveawayDao) -> None:
        self.uow = uow
        self.giveaway_dao = giveaway_dao

    async def _execute(self, actor: UserDto, data: SaveGiveawayPhoneDto) -> GiveawayEntryDto:
        if not data.phone.isdigit() or not 10 <= len(data.phone) <= 15:
            raise ValueError("Invalid phone")
        entry = await self.giveaway_dao.get_entry(data.entry_id)
        if not entry or entry.user_telegram_id != data.user_telegram_id:
            raise PermissionError("Giveaway entry does not belong to user")
        async with self.uow:
            updated = await self.giveaway_dao.update_phone(data.entry_id, data.phone)
            if not updated:
                raise ValueError("Giveaway entry not found")
            await self.uow.commit()
        masked = f"{data.phone[:4]}****{data.phone[-3:]}"
        logger.info(f"Saved masked giveaway phone '{masked}' for entry '{data.entry_id}'")
        return updated


class SelectGiveawayWinner(Interactor[int, GiveawayEntryDto]):
    required_permission = Permission.REMNASHOP_GIVEAWAY_EDITOR

    def __init__(self, uow: UnitOfWork, giveaway_dao: GiveawayDao) -> None:
        self.uow = uow
        self.giveaway_dao = giveaway_dao

    async def _execute(self, actor: UserDto, campaign_id: int) -> GiveawayEntryDto:
        async with self.uow:
            campaign = await self.giveaway_dao.get_campaign(campaign_id)
            if not campaign:
                raise ValueError("Giveaway campaign not found")
            winners = await self.giveaway_dao.get_winners(campaign_id)
            if len(winners) >= campaign.winner_count:
                raise ValueError("All giveaway winners already selected")
            winner = await self.giveaway_dao.select_winner(
                campaign_id,
                len(winners) + 1,
                datetime_now(),
            )
            if not winner:
                raise ValueError("No eligible giveaway participants")
            await self.uow.commit()
        logger.info(
            f"{actor.log} Selected giveaway winner entry='{winner.id}' "
            f"campaign='{campaign_id}' rank='{winner.winner_rank}'"
        )
        return winner
