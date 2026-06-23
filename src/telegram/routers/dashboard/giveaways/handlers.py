from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Optional

from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager, StartMode
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button, Select
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from loguru import logger

from src.application.common import Notifier
from src.application.common.dao import GiveawayDao
from src.application.dto import UserDto
from src.application.use_cases.giveaway.commands import (
    AddManualGiveawayEntry,
    AddManualGiveawayEntryDto,
    ArchiveGiveawayCampaign,
    CreateGiveawayCampaign,
    CreateGiveawayCampaignDto,
    DeleteGiveawayCampaign,
    SelectGiveawayWinner,
    SetGiveawayStatus,
    SetGiveawayStatusDto,
    UpdateGiveawayRules,
    UpdateGiveawayRulesDto,
)
from src.core.constants import USER_KEY
from src.core.enums import GiveawayCampaignStatus, PurchaseType
from src.telegram.states import DashboardGiveaways


def _parse_date(text: str, end_of_day: bool = False) -> Optional[datetime]:
    for fmt in ("%d.%m.%Y %H:%M", "%d.%m.%Y"):
        try:
            value = datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
            if fmt == "%d.%m.%Y" and end_of_day:
                value = value.replace(hour=23, minute=59, second=59)
            return value
        except ValueError:
            continue
    return None


async def on_create(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
) -> None:
    dialog_manager.dialog_data.clear()
    dialog_manager.dialog_data["eligible_purchase_types"] = [
        PurchaseType.NEW.value,
        PurchaseType.RENEW.value,
    ]
    await dialog_manager.switch_to(DashboardGiveaways.NAME)


@inject
async def on_name_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    notifier: FromDishka[Notifier],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    name = (message.text or "").strip()
    if not name or len(name) > 128:
        await notifier.notify_user(user, i18n_key="ntf-common.invalid-value")
        return
    dialog_manager.dialog_data["name"] = name
    await dialog_manager.switch_to(DashboardGiveaways.STARTS_AT)


@inject
async def on_start_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    notifier: FromDishka[Notifier],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    value = _parse_date((message.text or "").strip())
    if not value:
        await notifier.notify_user(user, i18n_key="ntf-common.invalid-value")
        return
    dialog_manager.dialog_data["starts_at_iso"] = value.isoformat()
    dialog_manager.dialog_data["starts_at_display"] = value.strftime("%d.%m.%Y %H:%M UTC")
    await dialog_manager.switch_to(DashboardGiveaways.ENDS_AT)


@inject
async def on_end_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    notifier: FromDishka[Notifier],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    value = _parse_date((message.text or "").strip(), end_of_day=True)
    starts_at = datetime.fromisoformat(dialog_manager.dialog_data["starts_at_iso"])
    if not value or value <= starts_at:
        await notifier.notify_user(user, i18n_key="ntf-common.invalid-value")
        return
    dialog_manager.dialog_data["ends_at_iso"] = value.isoformat()
    dialog_manager.dialog_data["ends_at_display"] = value.strftime("%d.%m.%Y %H:%M UTC")
    await dialog_manager.switch_to(DashboardGiveaways.WINNER_COUNT)


@inject
async def on_winner_count_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    notifier: FromDishka[Notifier],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    try:
        value = int((message.text or "").strip())
        if value < 1:
            raise ValueError
    except ValueError:
        await notifier.notify_user(user, i18n_key="ntf-common.invalid-value")
        return
    dialog_manager.dialog_data["winner_count"] = value
    await dialog_manager.switch_to(DashboardGiveaways.PRIZE_AMOUNT)


@inject
async def on_prize_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    notifier: FromDishka[Notifier],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    try:
        value = Decimal((message.text or "").strip().replace(",", "."))
        if value < 0:
            raise ValueError
    except (InvalidOperation, ValueError):
        await notifier.notify_user(user, i18n_key="ntf-common.invalid-value")
        return
    dialog_manager.dialog_data["prize_amount"] = str(value)
    await dialog_manager.switch_to(DashboardGiveaways.PLAN)


async def on_plan_select(
    callback: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    plan_id: int,
) -> None:
    plans = dialog_manager.dialog_data.get("_giveaway_plans", {})
    dialog_manager.dialog_data["eligible_plan_id"] = plan_id
    dialog_manager.dialog_data["plan_name"] = plans.get(str(plan_id), {}).get("name", str(plan_id))
    await dialog_manager.switch_to(DashboardGiveaways.DURATION)


async def on_duration_select(
    callback: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    duration_days: int,
) -> None:
    dialog_manager.dialog_data["eligible_duration_days"] = duration_days
    await dialog_manager.switch_to(DashboardGiveaways.PURCHASE_TYPES)


async def on_purchase_type_toggle(
    callback: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    purchase_type: PurchaseType,
) -> None:
    selected = set(dialog_manager.dialog_data.get("eligible_purchase_types", []))
    if purchase_type.value in selected:
        selected.remove(purchase_type.value)
    else:
        selected.add(purchase_type.value)
    dialog_manager.dialog_data["eligible_purchase_types"] = sorted(selected)


@inject
async def on_purchase_types_continue(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    notifier: FromDishka[Notifier],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    if not dialog_manager.dialog_data.get("eligible_purchase_types"):
        await notifier.notify_user(user, i18n_key="ntf-giveaway.purchase-type-required")
        return
    await dialog_manager.switch_to(DashboardGiveaways.RULES)


@inject
async def on_rules_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    notifier: FromDishka[Notifier],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    value = (message.text or "").strip()
    if len(value) > 4000:
        await notifier.notify_user(user, i18n_key="ntf-giveaway.rules-too-long")
        return
    dialog_manager.dialog_data["rules_text"] = None if value in {"", "-"} else value
    await dialog_manager.switch_to(DashboardGiveaways.ACTIVITY)


async def on_activity_select(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
) -> None:
    dialog_manager.dialog_data["is_active"] = widget.widget_id == "enable"
    await dialog_manager.switch_to(DashboardGiveaways.CONFIGURATOR)


@inject
async def on_confirm(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    create_campaign: FromDishka[CreateGiveawayCampaign],
    notifier: FromDishka[Notifier],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    data = dialog_manager.dialog_data
    try:
        campaign = await create_campaign(
            user,
            CreateGiveawayCampaignDto(
                name=data["name"],
                starts_at=datetime.fromisoformat(data["starts_at_iso"]),
                ends_at=datetime.fromisoformat(data["ends_at_iso"]),
                winner_count=int(data["winner_count"]),
                prize_amount=Decimal(data["prize_amount"]),
                eligible_plan_id=int(data["eligible_plan_id"]),
                eligible_duration_days=int(data["eligible_duration_days"]),
                eligible_purchase_types=[
                    PurchaseType(value) for value in data["eligible_purchase_types"]
                ],
                rules_text=data.get("rules_text"),
                is_active=bool(data["is_active"]),
            ),
        )
    except Exception:
        logger.exception(f"{user.log} Failed to create giveaway campaign")
        await notifier.notify_user(user, i18n_key="ntf-error.unknown")
        return
    await notifier.notify_user(user, i18n_key="ntf-giveaway.admin-created")
    dialog_manager.dialog_data.clear()
    dialog_manager.dialog_data["campaign_id"] = campaign.id
    await dialog_manager.switch_to(DashboardGiveaways.VIEW)


async def on_campaign_select(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
) -> None:
    dialog_manager.dialog_data["campaign_id"] = int(dialog_manager.item_id)  # type: ignore[attr-defined]
    await dialog_manager.switch_to(DashboardGiveaways.VIEW)


@inject
async def on_manual_entry_request(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    giveaway_dao: FromDishka[GiveawayDao],
    notifier: FromDishka[Notifier],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    campaign_id = int(dialog_manager.dialog_data["campaign_id"])
    campaign = await giveaway_dao.get_campaign(campaign_id)
    if not campaign or campaign.status not in {
        GiveawayCampaignStatus.DRAFT,
        GiveawayCampaignStatus.ACTIVE,
    }:
        await notifier.notify_user(
            user,
            i18n_key="ntf-giveaway.manual-entry-unavailable",
        )
        return
    logger.info(f"{user.log} Started manual entry creation for campaign='{campaign_id}'")
    await dialog_manager.switch_to(DashboardGiveaways.MANUAL_ENTRY_PHONE)


@inject
async def on_manual_entry_phone_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    add_manual_entry: FromDishka[AddManualGiveawayEntry],
    notifier: FromDishka[Notifier],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    phone = (message.text or "").strip()
    if not phone.isdigit() or not 10 <= len(phone) <= 15:
        await notifier.notify_user(
            user,
            i18n_key="ntf-giveaway.manual-phone-invalid",
        )
        return

    campaign_id = int(dialog_manager.dialog_data["campaign_id"])
    try:
        entry = await add_manual_entry(
            user,
            AddManualGiveawayEntryDto(
                campaign_id=campaign_id,
                phone=phone,
            ),
        )
    except ValueError as error:
        logger.warning(
            f"{user.log} Manual giveaway entry rejected for campaign='{campaign_id}': {error}"
        )
        await notifier.notify_user(
            user,
            i18n_key="ntf-giveaway.manual-entry-unavailable",
        )
        await dialog_manager.switch_to(DashboardGiveaways.VIEW)
        return
    except Exception:
        logger.exception(
            f"{user.log} Failed to add manual giveaway entry campaign='{campaign_id}'"
        )
        await notifier.notify_user(user, i18n_key="ntf-error.unknown")
        return

    dialog_manager.dialog_data["manual_entry_phone"] = phone
    dialog_manager.dialog_data["manual_entry_code"] = entry.participant_code
    await dialog_manager.switch_to(DashboardGiveaways.MANUAL_ENTRY_ADDED)


@inject
async def on_toggle_status(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    set_status: FromDishka[SetGiveawayStatus],
    notifier: FromDishka[Notifier],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    new_status = (
        GiveawayCampaignStatus.DRAFT
        if widget.widget_id == "disable"
        else GiveawayCampaignStatus.ACTIVE
    )
    await set_status(
        user,
        SetGiveawayStatusDto(
            campaign_id=int(dialog_manager.dialog_data["campaign_id"]),
            status=new_status,
        ),
    )
    await notifier.notify_user(user, i18n_key="ntf-giveaway.status-updated")


@inject
async def on_complete(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    set_status: FromDishka[SetGiveawayStatus],
    notifier: FromDishka[Notifier],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    await set_status(
        user,
        SetGiveawayStatusDto(
            campaign_id=int(dialog_manager.dialog_data["campaign_id"]),
            status=GiveawayCampaignStatus.COMPLETED,
        ),
    )
    await notifier.notify_user(user, i18n_key="ntf-giveaway.completed")


@inject
async def on_select_winner(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    select_winner: FromDishka[SelectGiveawayWinner],
    giveaway_dao: FromDishka[GiveawayDao],
    notifier: FromDishka[Notifier],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    campaign_id = int(dialog_manager.dialog_data["campaign_id"])
    try:
        winner = await select_winner(user, campaign_id)
        campaign = await giveaway_dao.get_campaign(campaign_id)
        await notifier.notify_user(
            user,
            payload=None,
            i18n_key="ntf-giveaway.winner-selected",
        )
        logger.info(
            f"{user.log} Winner rank='{winner.winner_rank}' selected "
            f"for campaign='{campaign_id}', prize='{campaign.prize_amount if campaign else 0}'"
        )
        await dialog_manager.switch_to(DashboardGiveaways.WINNERS)
    except ValueError as error:
        logger.warning(f"{user.log} Giveaway winner selection rejected: {error}")
        await notifier.notify_user(user, i18n_key="ntf-giveaway.winner-unavailable")


async def on_archive_request(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
) -> None:
    await dialog_manager.switch_to(DashboardGiveaways.ARCHIVE_CONFIRM)


@inject
async def on_archive_confirm(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    archive_campaign: FromDishka[ArchiveGiveawayCampaign],
    notifier: FromDishka[Notifier],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    await archive_campaign(user, int(dialog_manager.dialog_data["campaign_id"]))
    await notifier.notify_user(user, i18n_key="ntf-giveaway.archived")
    await dialog_manager.start(DashboardGiveaways.LIST, mode=StartMode.RESET_STACK)


async def on_delete_request(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
) -> None:
    await dialog_manager.switch_to(DashboardGiveaways.DELETE_CONFIRM)


async def on_rules_edit_request(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
) -> None:
    await dialog_manager.switch_to(DashboardGiveaways.RULES_EDIT)


@inject
async def on_rules_edit_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    update_rules: FromDishka[UpdateGiveawayRules],
    notifier: FromDishka[Notifier],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    value = (message.text or "").strip()
    if len(value) > 4000:
        await notifier.notify_user(user, i18n_key="ntf-giveaway.rules-too-long")
        return
    await update_rules(
        user,
        UpdateGiveawayRulesDto(
            campaign_id=int(dialog_manager.dialog_data["campaign_id"]),
            rules_text=None if value in {"", "-"} else value,
        ),
    )
    await notifier.notify_user(user, i18n_key="ntf-giveaway.rules-updated")
    await dialog_manager.switch_to(DashboardGiveaways.VIEW)


@inject
async def on_delete_confirm(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    delete_campaign: FromDishka[DeleteGiveawayCampaign],
    notifier: FromDishka[Notifier],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    await delete_campaign(user, int(dialog_manager.dialog_data["campaign_id"]))
    await notifier.notify_user(user, i18n_key="ntf-giveaway.deleted")
    await dialog_manager.start(DashboardGiveaways.LIST, mode=StartMode.RESET_STACK)
