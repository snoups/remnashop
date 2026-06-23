from aiogram_dialog import Dialog, StartMode, Window
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import (
    Button,
    Column,
    ListGroup,
    Row,
    Select,
    Start,
    SwitchTo,
)
from aiogram_dialog.widgets.text import Format
from magic_filter import F

from src.core.enums import BannerName, PurchaseType
from src.telegram.keyboards import main_menu_button
from src.telegram.states import Dashboard, DashboardGiveaways
from src.telegram.widgets import Banner, I18nFormat, IgnoreUpdate

from .getters import (
    campaign_getter,
    campaigns_getter,
    configurator_getter,
    durations_getter,
    entries_getter,
    manual_entry_added_getter,
    plans_getter,
    purchase_types_getter,
    winners_getter,
)
from .handlers import (
    on_activity_select,
    on_archive_confirm,
    on_archive_request,
    on_campaign_select,
    on_complete,
    on_confirm,
    on_create,
    on_delete_confirm,
    on_delete_request,
    on_duration_select,
    on_end_input,
    on_manual_entry_phone_input,
    on_manual_entry_request,
    on_name_input,
    on_plan_select,
    on_prize_input,
    on_purchase_type_toggle,
    on_purchase_types_continue,
    on_rules_edit_input,
    on_rules_edit_request,
    on_rules_input,
    on_select_winner,
    on_start_input,
    on_toggle_status,
    on_winner_count_input,
)

main = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-giveaways-main"),
    Row(
        SwitchTo(
            text=I18nFormat("btn-giveaway.list"),
            id="list",
            state=DashboardGiveaways.LIST,
        ),
        Button(
            text=I18nFormat("btn-giveaway.create"),
            id="create",
            on_click=on_create,
        ),
    ),
    Row(
        Start(
            text=I18nFormat("btn-back.general"),
            id="back",
            state=Dashboard.MAIN,
            mode=StartMode.RESET_STACK,
        ),
        *main_menu_button,
    ),
    IgnoreUpdate(),
    state=DashboardGiveaways.MAIN,
)

campaigns = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-giveaways-list"),
    ListGroup(
        Button(
            text=Format("{item[name]} · {item[status]}"),
            id="campaign",
            on_click=on_campaign_select,
        ),
        id="campaigns",
        item_id_getter=lambda item: item["id"],
        items="campaigns",
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back.general"),
            id="back",
            state=DashboardGiveaways.MAIN,
        )
    ),
    IgnoreUpdate(),
    getter=campaigns_getter,
    state=DashboardGiveaways.LIST,
)

name = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-giveaway-name"),
    MessageInput(func=on_name_input),
    IgnoreUpdate(),
    state=DashboardGiveaways.NAME,
)

starts_at = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-giveaway-start"),
    MessageInput(func=on_start_input),
    IgnoreUpdate(),
    state=DashboardGiveaways.STARTS_AT,
)

ends_at = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-giveaway-end"),
    MessageInput(func=on_end_input),
    IgnoreUpdate(),
    state=DashboardGiveaways.ENDS_AT,
)

winner_count = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-giveaway-winner-count"),
    MessageInput(func=on_winner_count_input),
    IgnoreUpdate(),
    state=DashboardGiveaways.WINNER_COUNT,
)

prize_amount = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-giveaway-prize"),
    MessageInput(func=on_prize_input),
    IgnoreUpdate(),
    state=DashboardGiveaways.PRIZE_AMOUNT,
)

plan = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-giveaway-plan"),
    Column(
        Select(
            text=Format("{item[name]}"),
            id="plan",
            item_id_getter=lambda item: item["id"],
            items="plans",
            type_factory=int,
            on_click=on_plan_select,
        )
    ),
    IgnoreUpdate(),
    getter=plans_getter,
    state=DashboardGiveaways.PLAN,
)

duration = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-giveaway-duration"),
    Column(
        Select(
            text=Format("{item} дней"),
            id="duration",
            item_id_getter=lambda item: item,
            items="durations",
            type_factory=int,
            on_click=on_duration_select,
        )
    ),
    IgnoreUpdate(),
    getter=durations_getter,
    state=DashboardGiveaways.DURATION,
)

purchase_types = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-giveaway-purchase-types"),
    Column(
        Select(
            text=I18nFormat(
                "btn-giveaway.purchase-type",
                selected=F["item"]["selected"],
                purchase_type=F["item"]["value"],
            ),
            id="purchase_type",
            item_id_getter=lambda item: item["value"].value,
            items="purchase_types",
            type_factory=PurchaseType,
            on_click=on_purchase_type_toggle,
        )
    ),
    Button(
        text=I18nFormat("btn-giveaway.continue"),
        id="continue",
        on_click=on_purchase_types_continue,
    ),
    IgnoreUpdate(),
    getter=purchase_types_getter,
    state=DashboardGiveaways.PURCHASE_TYPES,
)

activity = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-giveaway-activity"),
    Row(
        Button(
            text=I18nFormat("btn-giveaway.enable"),
            id="enable",
            on_click=on_activity_select,
        ),
        Button(
            text=I18nFormat("btn-giveaway.keep-disabled"),
            id="keep_disabled",
            on_click=on_activity_select,
        ),
    ),
    IgnoreUpdate(),
    state=DashboardGiveaways.ACTIVITY,
)

rules = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-giveaway-rules"),
    MessageInput(func=on_rules_input),
    IgnoreUpdate(),
    state=DashboardGiveaways.RULES,
)

configurator = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-giveaway-configurator"),
    Row(
        Button(
            text=I18nFormat("btn-giveaway.confirm"),
            id="confirm",
            on_click=on_confirm,
        )
    ),
    IgnoreUpdate(),
    getter=configurator_getter,
    state=DashboardGiveaways.CONFIGURATOR,
)

view = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-giveaway-view"),
    I18nFormat("msg-giveaway-participants-shortage", when=F["participants_shortage"]),
    Row(
        SwitchTo(
            text=I18nFormat("btn-giveaway.entries"),
            id="entries",
            state=DashboardGiveaways.ENTRIES,
        ),
        SwitchTo(
            text=I18nFormat("btn-giveaway.winners"),
            id="winners",
            state=DashboardGiveaways.WINNERS,
        ),
    ),
    Row(
        Button(
            text=I18nFormat("btn-giveaway.select-winner"),
            id="select_winner",
            on_click=on_select_winner,
            when=F["can_select_winner"],
        )
    ),
    Row(
        Button(
            text=I18nFormat("btn-giveaway.add-participant"),
            id="add_participant",
            on_click=on_manual_entry_request,
            when=F["can_add_entry"],
        )
    ),
    Row(
        Button(
            text=I18nFormat("btn-giveaway.disable"),
            id="disable",
            on_click=on_toggle_status,
            when=F["is_active"] & F["can_manage"],
        ),
        Button(
            text=I18nFormat("btn-giveaway.enable"),
            id="enable",
            on_click=on_toggle_status,
            when=F["is_draft"] & F["can_manage"],
        ),
    ),
    Row(
        Button(
            text=I18nFormat("btn-giveaway.complete"),
            id="complete",
            on_click=on_complete,
            when=F["can_manage"],
        ),
        Button(
            text=I18nFormat("btn-giveaway.archive"),
            id="archive",
            on_click=on_archive_request,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-giveaway.rules"),
            id="rules",
            state=DashboardGiveaways.RULES_VIEW,
        ),
    ),
    Row(
        Button(
            text=I18nFormat("btn-giveaway.delete"),
            id="delete",
            on_click=on_delete_request,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back.general"),
            id="back",
            state=DashboardGiveaways.LIST,
        )
    ),
    IgnoreUpdate(),
    getter=campaign_getter,
    state=DashboardGiveaways.VIEW,
)

entries = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-giveaway-entries"),
    Format("{entries_text}"),
    SwitchTo(
        text=I18nFormat("btn-back.general"),
        id="back",
        state=DashboardGiveaways.VIEW,
    ),
    IgnoreUpdate(),
    getter=entries_getter,
    state=DashboardGiveaways.ENTRIES,
)

winners = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-giveaway-winners"),
    Format("{winners_text}"),
    Row(
        Button(
            text=I18nFormat("btn-giveaway.select-next-winner"),
            id="select_next",
            on_click=on_select_winner,
        )
    ),
    SwitchTo(
        text=I18nFormat("btn-back.general"),
        id="back",
        state=DashboardGiveaways.VIEW,
    ),
    IgnoreUpdate(),
    getter=winners_getter,
    state=DashboardGiveaways.WINNERS,
)

archive_confirm = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-giveaway-archive-confirm"),
    Row(
        Button(
            text=I18nFormat("btn-giveaway.archive-confirm"),
            id="archive_confirm",
            on_click=on_archive_confirm,
        ),
        SwitchTo(
            text=I18nFormat("btn-giveaway.cancel"),
            id="cancel",
            state=DashboardGiveaways.VIEW,
        ),
    ),
    IgnoreUpdate(),
    state=DashboardGiveaways.ARCHIVE_CONFIRM,
)

delete_confirm = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-giveaway-delete-confirm"),
    Row(
        Button(
            text=I18nFormat("btn-giveaway.delete-confirm"),
            id="delete_confirm",
            on_click=on_delete_confirm,
        ),
        SwitchTo(
            text=I18nFormat("btn-giveaway.cancel"),
            id="cancel",
            state=DashboardGiveaways.VIEW,
        ),
    ),
    IgnoreUpdate(),
    state=DashboardGiveaways.DELETE_CONFIRM,
)

rules_edit = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-giveaway-rules-edit"),
    MessageInput(func=on_rules_edit_input),
    SwitchTo(
        text=I18nFormat("btn-giveaway.cancel"),
        id="cancel",
        state=DashboardGiveaways.VIEW,
    ),
    IgnoreUpdate(),
    getter=campaign_getter,
    state=DashboardGiveaways.RULES_EDIT,
)

rules_view = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-giveaway-rules-view"),
    Format("{rules_text}"),
    Row(
        Button(
            text=I18nFormat("btn-giveaway.rules-edit"),
            id="edit",
            on_click=on_rules_edit_request,
        ),
        SwitchTo(
            text=I18nFormat("btn-back.general"),
            id="back",
            state=DashboardGiveaways.VIEW,
        ),
    ),
    IgnoreUpdate(),
    getter=campaign_getter,
    state=DashboardGiveaways.RULES_VIEW,
)

manual_entry_phone = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-giveaway-manual-entry-phone"),
    MessageInput(func=on_manual_entry_phone_input),
    SwitchTo(
        text=I18nFormat("btn-giveaway.cancel"),
        id="cancel",
        state=DashboardGiveaways.VIEW,
    ),
    IgnoreUpdate(),
    state=DashboardGiveaways.MANUAL_ENTRY_PHONE,
)

manual_entry_added = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-giveaway-manual-entry-added"),
    SwitchTo(
        text=I18nFormat("btn-back.general"),
        id="back",
        state=DashboardGiveaways.VIEW,
    ),
    IgnoreUpdate(),
    getter=manual_entry_added_getter,
    state=DashboardGiveaways.MANUAL_ENTRY_ADDED,
)

router = Dialog(
    main,
    campaigns,
    name,
    starts_at,
    ends_at,
    winner_count,
    prize_amount,
    plan,
    duration,
    purchase_types,
    rules,
    activity,
    configurator,
    view,
    entries,
    winners,
    archive_confirm,
    delete_confirm,
    rules_view,
    rules_edit,
    manual_entry_phone,
    manual_entry_added,
)
