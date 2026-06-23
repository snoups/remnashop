from src.application.common import Interactor
from src.application.common.dao import GiveawayDao, PlanDao
from src.application.common.policy import Permission
from src.application.dto import ClientGiveawayDto, GiveawayCampaignDto, UserDto
from src.core.enums import GiveawayCampaignStatus
from src.core.utils.time import datetime_now


def generate_giveaway_conditions(
    campaign: GiveawayCampaignDto,
    plan_name: str,
) -> str:
    return (
        f"Название: {campaign.name}\n\n"
        f"Сроки проведения: с {campaign.starts_at:%d.%m.%Y} "
        f"до {campaign.ends_at:%d.%m.%Y}.\n\n"
        f"Как участвовать: купите подписку «{plan_name}» "
        f"на {campaign.eligible_duration_days} дней в Telegram-боте. "
        "После успешной оплаты бот автоматически выдаст один уникальный "
        "номер участника на одну покупку.\n\n"
        f"Приз: {campaign.winner_count} победителей получат "
        f"по {campaign.prize_amount} ₽.\n\n"
        "После завершения акции победители случайно выбираются системой "
        "среди допущенных участников. Повторная обработка оплаты не выдаёт "
        "дополнительный код.\n\n"
        "Телефон оставляется по желанию. Организатор может связаться с "
        "победителем через Telegram или указанный телефон. При нарушении "
        "условий участник может быть исключён."
    )


class ListClientGiveaways(Interactor[None, list[ClientGiveawayDto]]):
    required_permission = Permission.PUBLIC

    def __init__(self, giveaway_dao: GiveawayDao, plan_dao: PlanDao) -> None:
        self.giveaway_dao = giveaway_dao
        self.plan_dao = plan_dao

    async def _execute(self, actor: UserDto, data: None) -> list[ClientGiveawayDto]:
        campaigns = await self.giveaway_dao.get_client_campaigns(
            datetime_now(),
            actor.telegram_id,
        )
        result: list[ClientGiveawayDto] = []
        for campaign in campaigns:
            if campaign.id is None:
                continue
            plan = await self.plan_dao.get_by_id(campaign.eligible_plan_id)
            entry = await self.giveaway_dao.get_entry_for_user(
                campaign.id,
                actor.telegram_id,
            )
            result.append(
                ClientGiveawayDto(
                    campaign=campaign,
                    plan_name=plan.name if plan else str(campaign.eligible_plan_id),
                    entry=entry,
                )
            )
        return result


class GetClientGiveawayDetails(Interactor[int, ClientGiveawayDto]):
    required_permission = Permission.PUBLIC

    def __init__(self, giveaway_dao: GiveawayDao, plan_dao: PlanDao) -> None:
        self.giveaway_dao = giveaway_dao
        self.plan_dao = plan_dao

    async def _execute(self, actor: UserDto, campaign_id: int) -> ClientGiveawayDto:
        campaign = await self.giveaway_dao.get_campaign(campaign_id)
        if not campaign:
            raise ValueError("Giveaway campaign not found")
        plan = await self.plan_dao.get_by_id(campaign.eligible_plan_id)
        entry = await self.giveaway_dao.get_entry_for_user(
            campaign_id,
            actor.telegram_id,
        )
        now = datetime_now()
        is_active = (
            campaign.status == GiveawayCampaignStatus.ACTIVE
            and campaign.starts_at <= now <= campaign.ends_at
        )
        is_completed_participant = (
            campaign.status == GiveawayCampaignStatus.COMPLETED and entry is not None
        )
        if not is_active and not is_completed_participant:
            raise PermissionError("Giveaway campaign is not available to this user")
        return ClientGiveawayDto(
            campaign=campaign,
            plan_name=plan.name if plan else str(campaign.eligible_plan_id),
            entry=entry,
        )


class GetClientGiveawayConditions(Interactor[int, str]):
    required_permission = Permission.PUBLIC

    def __init__(self, get_details: GetClientGiveawayDetails) -> None:
        self.get_details = get_details

    async def _execute(self, actor: UserDto, campaign_id: int) -> str:
        details = await self.get_details(actor, campaign_id)
        campaign = details.campaign
        if campaign.rules_text:
            return campaign.rules_text
        return generate_giveaway_conditions(campaign, details.plan_name)
