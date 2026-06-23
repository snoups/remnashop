from typing import Any

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject

from src.application.common import TranslatorRunner
from src.application.common.dao import GiveawayDao
from src.application.dto import UserDto
from src.application.use_cases.giveaway.queries import (
    GetClientGiveawayConditions,
    GetClientGiveawayDetails,
    ListClientGiveaways,
)
from src.core.enums import GiveawayCampaignStatus, GiveawayEntryStatus
from src.core.utils.time import datetime_now


def _mask_phone(phone: str | None) -> str:
    if not phone:
        return "не указан"
    return f"{phone[:4]}****{phone[-3:]}"


@inject
async def client_giveaways_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    list_giveaways: FromDishka[ListClientGiveaways],
    **kwargs: Any,
) -> dict[str, Any]:
    giveaways = await list_giveaways(user)
    items = [
        {
            "id": item.campaign.id,
            "name": item.campaign.name,
            "status": item.campaign.status,
            "is_participant": item.entry is not None,
        }
        for item in giveaways
    ]
    return {"giveaways": items, "has_giveaways": bool(items)}


@inject
async def client_giveaway_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    i18n: FromDishka[TranslatorRunner],
    get_details: FromDishka[GetClientGiveawayDetails],
    **kwargs: Any,
) -> dict[str, Any]:
    campaign_id = int(dialog_manager.dialog_data["campaign_id"])
    details = await get_details(user, campaign_id)
    campaign = details.campaign
    entry = details.entry
    is_winner = bool(entry and entry.status == GiveawayEntryStatus.WINNER)
    is_completed = campaign.status == GiveawayCampaignStatus.COMPLETED
    now = datetime_now()
    is_active = (
        campaign.status == GiveawayCampaignStatus.ACTIVE
        and campaign.starts_at <= now <= campaign.ends_at
    )

    if is_winner:
        status_text = i18n.get("msg-client-giveaway-status.winner")
    elif entry:
        status_text = i18n.get("msg-client-giveaway-status.participating")
    elif is_completed:
        status_text = i18n.get("msg-client-giveaway-status.completed")
    else:
        status_text = i18n.get("msg-client-giveaway-status.not-participating")

    dialog_manager.dialog_data["entry_id"] = entry.id if entry else None
    return {
        "campaign_id": campaign_id,
        "name": campaign.name,
        "winner_count": campaign.winner_count,
        "prize_amount": campaign.prize_amount,
        "starts_at": campaign.starts_at.strftime("%d.%m.%Y"),
        "ends_at": campaign.ends_at.strftime("%d.%m.%Y"),
        "plan_name": i18n.get(details.plan_name),
        "duration_days": campaign.eligible_duration_days,
        "status_text": status_text,
        "has_entry": entry is not None,
        "participant_code": entry.participant_code if entry else "—",
        "phone": _mask_phone(entry.phone if entry else None),
        "is_winner": is_winner,
        "winner_rank": entry.winner_rank if entry else 0,
        "is_completed": is_completed,
        "can_buy": is_active and entry is None,
        "can_edit_phone": entry is not None and not is_completed,
        "show_results": is_completed,
    }


@inject
async def client_giveaway_conditions_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    get_conditions: FromDishka[GetClientGiveawayConditions],
    **kwargs: Any,
) -> dict[str, Any]:
    campaign_id = int(dialog_manager.dialog_data["campaign_id"])
    return {"conditions": await get_conditions(user, campaign_id)}


@inject
async def client_giveaway_results_getter(
    dialog_manager: DialogManager,
    giveaway_dao: FromDishka[GiveawayDao],
    **kwargs: Any,
) -> dict[str, Any]:
    campaign_id = int(dialog_manager.dialog_data["campaign_id"])
    winners = await giveaway_dao.get_winners(campaign_id)
    lines = [f"#{winner.winner_rank} · {winner.participant_code}" for winner in winners]
    return {"results": "\n".join(lines) if lines else "Розыгрыш ещё не проведён."}
