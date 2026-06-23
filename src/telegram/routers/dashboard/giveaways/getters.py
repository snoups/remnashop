from typing import Any

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject

from src.application.common import TranslatorRunner
from src.application.common.dao import GiveawayDao, PlanDao
from src.application.use_cases.giveaway.queries import generate_giveaway_conditions
from src.core.enums import GiveawayCampaignStatus, GiveawayEntrySource, PurchaseType


def _mask_phone(phone: str | None) -> str:
    if not phone:
        return "не указан"
    return f"{phone[:4]}****{phone[-3:]}"


def _entry_source_label(source: GiveawayEntrySource) -> str:
    if source == GiveawayEntrySource.MANUAL:
        return "добавлен вручную"
    return "покупка в боте"


@inject
async def campaigns_getter(
    dialog_manager: DialogManager,
    giveaway_dao: FromDishka[GiveawayDao],
    **kwargs: Any,
) -> dict[str, Any]:
    campaigns = await giveaway_dao.get_campaigns()
    items = [
        {"id": item.id, "name": item.name, "status": item.status}
        for item in campaigns
    ]
    return {"campaigns": items, "has_campaigns": bool(items)}


@inject
async def plans_getter(
    dialog_manager: DialogManager,
    plan_dao: FromDishka[PlanDao],
    i18n: FromDishka[TranslatorRunner],
    **kwargs: Any,
) -> dict[str, Any]:
    plans = [plan for plan in await plan_dao.get_all() if plan.is_active]
    items = [{"id": plan.id, "name": i18n.get(plan.name)} for plan in plans]
    dialog_manager.dialog_data["_giveaway_plans"] = {
        str(plan.id): {
            "name": i18n.get(plan.name),
            "durations": [duration.days for duration in plan.durations],
        }
        for plan in plans
        if plan.id is not None
    }
    return {"plans": items}


async def durations_getter(
    dialog_manager: DialogManager,
    **kwargs: Any,
) -> dict[str, Any]:
    plan_id = str(dialog_manager.dialog_data.get("eligible_plan_id"))
    plan = dialog_manager.dialog_data.get("_giveaway_plans", {}).get(plan_id, {})
    return {"durations": plan.get("durations", [])}


async def purchase_types_getter(
    dialog_manager: DialogManager,
    **kwargs: Any,
) -> dict[str, Any]:
    selected = set(dialog_manager.dialog_data.get("eligible_purchase_types", []))
    return {
        "purchase_types": [
            {"value": item, "selected": item.value in selected} for item in PurchaseType
        ],
        "has_purchase_types": bool(selected),
    }


async def configurator_getter(
    dialog_manager: DialogManager,
    **kwargs: Any,
) -> dict[str, Any]:
    data = dialog_manager.dialog_data
    return {
        "name": data.get("name", "—"),
        "starts_at": data.get("starts_at_display", "—"),
        "ends_at": data.get("ends_at_display", "—"),
        "winner_count": data.get("winner_count", "—"),
        "prize_amount": data.get("prize_amount", "—"),
        "plan_name": data.get("plan_name", "—"),
        "duration_days": data.get("eligible_duration_days", "—"),
        "purchase_types": ", ".join(data.get("eligible_purchase_types", [])),
        "rules_text": (
            "Заданы вручную" if data.get("rules_text") else "Автоматические условия"
        ),
        "is_active": data.get("is_active", False),
    }


@inject
async def campaign_getter(
    dialog_manager: DialogManager,
    giveaway_dao: FromDishka[GiveawayDao],
    plan_dao: FromDishka[PlanDao],
    i18n: FromDishka[TranslatorRunner],
    **kwargs: Any,
) -> dict[str, Any]:
    campaign_id = int(dialog_manager.dialog_data["campaign_id"])
    campaign = await giveaway_dao.get_campaign(campaign_id)
    if not campaign:
        return {}
    plan = await plan_dao.get_by_id(campaign.eligible_plan_id)
    entries = await giveaway_dao.get_entries(campaign_id)
    winners = await giveaway_dao.get_winners(campaign_id)
    return {
        "campaign_id": campaign_id,
        "name": campaign.name,
        "status": campaign.status,
        "starts_at": campaign.starts_at.strftime("%d.%m.%Y %H:%M UTC"),
        "ends_at": campaign.ends_at.strftime("%d.%m.%Y %H:%M UTC"),
        "winner_count": campaign.winner_count,
        "prize_amount": campaign.prize_amount,
        "plan_name": i18n.get(plan.name) if plan else str(campaign.eligible_plan_id),
        "duration_days": campaign.eligible_duration_days,
        "purchase_types": ", ".join(item.value for item in campaign.eligible_purchase_types),
        "rules_text": campaign.rules_text
        or generate_giveaway_conditions(
            campaign,
            i18n.get(plan.name) if plan else str(campaign.eligible_plan_id),
        ),
        "rules_mode": (
            "Заданы вручную" if campaign.rules_text else "Автоматические условия"
        ),
        "entries_count": len(entries),
        "winners_count": len(winners),
        "is_active": campaign.status == GiveawayCampaignStatus.ACTIVE,
        "is_draft": campaign.status == GiveawayCampaignStatus.DRAFT,
        "can_manage": campaign.status
        not in {GiveawayCampaignStatus.COMPLETED, GiveawayCampaignStatus.ARCHIVED},
        "can_add_entry": campaign.status
        in {GiveawayCampaignStatus.DRAFT, GiveawayCampaignStatus.ACTIVE},
        "can_select_winner": (
            campaign.status != GiveawayCampaignStatus.ARCHIVED
            and len(winners) < campaign.winner_count
        ),
        "participants_shortage": len(
            {
                (
                    "telegram",
                    entry.user_telegram_id,
                )
                if entry.user_telegram_id is not None
                else ("manual", entry.id)
                for entry in entries
            }
        )
        < campaign.winner_count,
    }


@inject
async def entries_getter(
    dialog_manager: DialogManager,
    giveaway_dao: FromDishka[GiveawayDao],
    **kwargs: Any,
) -> dict[str, Any]:
    entries = await giveaway_dao.get_entries(int(dialog_manager.dialog_data["campaign_id"]))
    lines = []
    for entry in entries:
        telegram_id = (
            str(entry.user_telegram_id)
            if entry.user_telegram_id is not None
            else "не указан"
        )
        username = f"@{entry.telegram_username}" if entry.telegram_username else "не указан"
        lines.append(
            "\n".join(
                [
                    f"Код: {entry.participant_code}",
                    f"Telegram ID: {telegram_id}",
                    f"Username: {username}",
                    f"Телефон: {_mask_phone(entry.phone)}",
                    f"Источник: {_entry_source_label(entry.entry_source)}",
                    f"Статус: {entry.status.value}",
                ]
            )
        )
    return {"entries_text": "\n\n".join(lines) if lines else "Участников пока нет."}


@inject
async def winners_getter(
    dialog_manager: DialogManager,
    giveaway_dao: FromDishka[GiveawayDao],
    **kwargs: Any,
) -> dict[str, Any]:
    campaign_id = int(dialog_manager.dialog_data["campaign_id"])
    winners = await giveaway_dao.get_winners(campaign_id)
    campaign = await giveaway_dao.get_campaign(campaign_id)
    lines = []
    for entry in winners:
        telegram_id = (
            str(entry.user_telegram_id)
            if entry.user_telegram_id is not None
            else "не указан"
        )
        username = f"@{entry.telegram_username}" if entry.telegram_username else "не указан"
        purchase_date = entry.created_at.strftime("%d.%m.%Y") if entry.created_at else "—"
        date_label = (
            "Дата добавления"
            if entry.entry_source == GiveawayEntrySource.MANUAL
            else "Дата покупки"
        )
        lines.append(
            "\n".join(
                [
                    f"#{entry.winner_rank} · {entry.participant_code}",
                    f"Telegram ID: {telegram_id}",
                    f"Username: {username}",
                    f"Телефон: {entry.phone or 'не указан'}",
                    f"Источник: {_entry_source_label(entry.entry_source)}",
                    f"Тариф: {entry.plan_name}, {entry.duration_days} дней",
                    f"{date_label}: {purchase_date}",
                    f"Сумма приза: {campaign.prize_amount if campaign else 0} ₽",
                ]
            )
        )
    return {"winners_text": "\n\n".join(lines) if lines else "Победители пока не выбраны."}


async def manual_entry_added_getter(
    dialog_manager: DialogManager,
    **kwargs: Any,
) -> dict[str, Any]:
    return {
        "phone": dialog_manager.dialog_data.get("manual_entry_phone", "—"),
        "participant_code": dialog_manager.dialog_data.get("manual_entry_code", "—"),
    }
