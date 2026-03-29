import re

from adaptix import Retort
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager, ShowMode, StartMode
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button, Select
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from loguru import logger

from src.application.common import Notifier
from src.application.common.dao import PromocodeDao
from src.application.common.uow import UnitOfWork
from src.application.dto import PromocodeDto, UserDto
from src.application.use_cases.promocode.commands.commit import CommitPromocode
from src.application.use_cases.promocode.commands.delete import DeletePromocode
from src.application.use_cases.promocode.utils import (
    build_default_promocode,
    get_promocode_runtime_state,
    is_valid_promocode_reward,
)
from src.core.constants import USER_KEY
from src.core.enums import PromocodeRewardType
from src.core.exceptions import PromocodeCodeAlreadyExistsError
from src.core.utils.time import datetime_now
from src.telegram.states import DashboardPromocodes
from src.telegram.utils import is_double_click

PROMOCODE_CODE_RE = re.compile(r"^[A-Z0-9_-]{3,32}$")
PROMOCODE_DIALOG_DATA_KEY = PromocodeDto.__name__


def _load_promocode(dialog_manager: DialogManager, retort: Retort) -> PromocodeDto:
    return retort.load(dialog_manager.dialog_data[PROMOCODE_DIALOG_DATA_KEY], PromocodeDto)


def _store_promocode(
    dialog_manager: DialogManager,
    retort: Retort,
    promocode: PromocodeDto,
) -> None:
    dialog_manager.dialog_data[PROMOCODE_DIALOG_DATA_KEY] = retort.dump(promocode)


@inject
async def on_promocode_create(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    retort: FromDishka[Retort],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    promocode = build_default_promocode()

    _store_promocode(dialog_manager, retort, promocode)
    dialog_manager.dialog_data["is_edit"] = False

    logger.info(f"{user.log} Started promocode creation")
    await dialog_manager.switch_to(DashboardPromocodes.CONFIGURATOR)


@inject
async def on_promocode_select(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    retort: FromDishka[Retort],
    promocode_dao: FromDishka[PromocodeDao],
    uow: FromDishka[UnitOfWork],
) -> None:
    promocode_id = int(dialog_manager.item_id)  # type: ignore[attr-defined]
    user: UserDto = dialog_manager.middleware_data[USER_KEY]

    async with uow:
        promocode = await promocode_dao.get_by_id(promocode_id)

        if not promocode:
            raise ValueError(f"Attempted to select non-existent promocode '{promocode_id}'")

        if promocode.id is not None:
            activations = await promocode_dao.count_activations(promocode.id)
            runtime_state = get_promocode_runtime_state(promocode, activations)

            if promocode.is_active and runtime_state.should_disable:
                promocode.is_active = False
                promocode = await promocode_dao.update(promocode.as_fully_changed()) or promocode
                await uow.commit()

    _store_promocode(dialog_manager, retort, promocode)
    dialog_manager.dialog_data["is_edit"] = True

    logger.info(f"{user.log} Selected promocode '{promocode.code}'")
    await dialog_manager.switch_to(DashboardPromocodes.CONFIGURATOR)


@inject
async def on_active_toggle(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    retort: FromDishka[Retort],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    promocode = _load_promocode(dialog_manager, retort)

    if not promocode.is_active:
        runtime_state = get_promocode_runtime_state(promocode, 0)
        if runtime_state.is_expired and promocode.lifetime is not None:
            promocode.created_at = datetime_now()

    promocode.is_active = not promocode.is_active
    _store_promocode(dialog_manager, retort, promocode)

    logger.info(f"{user.log} Toggled promocode active status to '{promocode.is_active}'")


@inject
async def on_code_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    retort: FromDishka[Retort],
    notifier: FromDishka[Notifier],
) -> None:
    dialog_manager.show_mode = ShowMode.EDIT
    user: UserDto = dialog_manager.middleware_data[USER_KEY]

    if not message.text:
        await notifier.notify_user(user, i18n_key="ntf-common.invalid-value")
        return

    code = message.text.strip().upper()
    if not PROMOCODE_CODE_RE.fullmatch(code):
        await notifier.notify_user(user, i18n_key="ntf-common.invalid-value")
        return

    promocode = _load_promocode(dialog_manager, retort)
    promocode.code = code
    _store_promocode(dialog_manager, retort, promocode)

    logger.info(f"{user.log} Updated promocode code to '{code}'")
    await dialog_manager.switch_to(DashboardPromocodes.CONFIGURATOR)


@inject
async def on_type_select(
    callback: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    selected_type: PromocodeRewardType,
    retort: FromDishka[Retort],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    promocode = _load_promocode(dialog_manager, retort)

    promocode.reward_type = selected_type
    _store_promocode(dialog_manager, retort, promocode)

    logger.info(f"{user.log} Updated promocode reward type to '{selected_type.name}'")
    await dialog_manager.switch_to(DashboardPromocodes.CONFIGURATOR)


@inject
async def on_reward_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    retort: FromDishka[Retort],
    notifier: FromDishka[Notifier],
) -> None:
    dialog_manager.show_mode = ShowMode.EDIT
    user: UserDto = dialog_manager.middleware_data[USER_KEY]

    if not message.text:
        await notifier.notify_user(user, i18n_key="ntf-common.invalid-value")
        return

    try:
        reward = int(message.text.strip())
    except ValueError:
        await notifier.notify_user(user, i18n_key="ntf-common.invalid-value")
        return

    promocode = _load_promocode(dialog_manager, retort)
    if not is_valid_promocode_reward(promocode.reward_type, reward):
        await notifier.notify_user(user, i18n_key="ntf-common.invalid-value")
        return

    promocode.reward = reward
    _store_promocode(dialog_manager, retort, promocode)

    logger.info(f"{user.log} Updated promocode reward to '{reward}'")
    await dialog_manager.switch_to(DashboardPromocodes.CONFIGURATOR)


@inject
async def on_lifetime_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    retort: FromDishka[Retort],
    notifier: FromDishka[Notifier],
) -> None:
    dialog_manager.show_mode = ShowMode.EDIT
    user: UserDto = dialog_manager.middleware_data[USER_KEY]

    if not message.text:
        await notifier.notify_user(user, i18n_key="ntf-common.invalid-value")
        return

    try:
        lifetime = int(message.text.strip())
    except ValueError:
        await notifier.notify_user(user, i18n_key="ntf-common.invalid-value")
        return

    if lifetime < 0:
        await notifier.notify_user(user, i18n_key="ntf-common.invalid-value")
        return

    promocode = _load_promocode(dialog_manager, retort)
    promocode.lifetime = None if lifetime == 0 else lifetime
    _store_promocode(dialog_manager, retort, promocode)

    logger.info(f"{user.log} Updated promocode lifetime to '{promocode.lifetime}'")
    await dialog_manager.switch_to(DashboardPromocodes.CONFIGURATOR)


@inject
async def on_max_activations_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    retort: FromDishka[Retort],
    notifier: FromDishka[Notifier],
) -> None:
    dialog_manager.show_mode = ShowMode.EDIT
    user: UserDto = dialog_manager.middleware_data[USER_KEY]

    if not message.text:
        await notifier.notify_user(user, i18n_key="ntf-common.invalid-value")
        return

    try:
        max_activations = int(message.text.strip())
    except ValueError:
        await notifier.notify_user(user, i18n_key="ntf-common.invalid-value")
        return

    if max_activations < 0:
        await notifier.notify_user(user, i18n_key="ntf-common.invalid-value")
        return

    promocode = _load_promocode(dialog_manager, retort)
    promocode.max_activations = None if max_activations == 0 else max_activations
    _store_promocode(dialog_manager, retort, promocode)

    logger.info(
        f"{user.log} Updated promocode max activations to '{promocode.max_activations}'"
    )
    await dialog_manager.switch_to(DashboardPromocodes.CONFIGURATOR)


@inject
async def on_promocode_confirm(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    retort: FromDishka[Retort],
    notifier: FromDishka[Notifier],
    commit_promocode: FromDishka[CommitPromocode],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    promocode = _load_promocode(dialog_manager, retort)

    try:
        result = await commit_promocode(user, promocode)
    except PromocodeCodeAlreadyExistsError:
        await notifier.notify_user(user, i18n_key="ntf-promocode.code-already-exists")
        return
    except ValueError:
        await notifier.notify_user(user, i18n_key="ntf-common.invalid-value")
        return

    i18n_key = "ntf-promocode.created" if result.is_created else "ntf-promocode.updated"

    await notifier.notify_user(user, i18n_key=i18n_key)
    await dialog_manager.reset_stack()
    await dialog_manager.start(state=DashboardPromocodes.MAIN)


@inject
async def on_promocode_delete(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    retort: FromDishka[Retort],
    notifier: FromDishka[Notifier],
    delete_promocode: FromDishka[DeletePromocode],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    promocode = _load_promocode(dialog_manager, retort)

    if promocode.id is None:
        await notifier.notify_user(user, i18n_key="ntf-common.invalid-value")
        return

    if is_double_click(dialog_manager, key=f"delete_confirm_{promocode.id}", cooldown=10):
        await delete_promocode(user, promocode.id)
        await notifier.notify_user(user, i18n_key="ntf-promocode.deleted")
        await dialog_manager.start(state=DashboardPromocodes.MAIN, mode=StartMode.RESET_STACK)
        return

    await notifier.notify_user(user, i18n_key="ntf-common.double-click-confirm")
    logger.debug(
        f"{user.log} Clicked delete for promocode ID '{promocode.id}' (awaiting confirmation)"
    )
