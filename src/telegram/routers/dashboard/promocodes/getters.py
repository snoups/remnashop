from typing import Any

from adaptix import Retort
from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject

from src.application.common import TranslatorRunner
from src.application.common.dao import PromocodeDao
from src.application.common.uow import UnitOfWork
from src.application.dto import PromocodeDto
from src.application.use_cases.promocode.utils import (
    SUPPORTED_PROMOCODE_REWARD_TYPES,
    build_default_promocode,
    get_promocode_runtime_state,
)
from src.core.enums import PromocodeRewardType
from src.core.utils.i18n_helpers import i18n_format_days, i18n_format_traffic_limit

PROMOCODE_DIALOG_DATA_KEY = PromocodeDto.__name__


def _format_reward(i18n: TranslatorRunner, promocode: PromocodeDto) -> str:
    reward = promocode.reward or 0

    match promocode.reward_type:
        case PromocodeRewardType.PERSONAL_DISCOUNT | PromocodeRewardType.PURCHASE_DISCOUNT:
            return f"{reward}%"
        case PromocodeRewardType.DURATION:
            key, kwargs = i18n_format_days(reward)
            return i18n.get(key, **kwargs)
        case PromocodeRewardType.TRAFFIC:
            key, kwargs = i18n_format_traffic_limit(reward)
            return i18n.get(key, **kwargs)
        case _:
            return str(reward)


@inject
async def promocodes_getter(
    dialog_manager: DialogManager,
    promocode_dao: FromDishka[PromocodeDao],
    uow: FromDishka[UnitOfWork],
    **kwargs: Any,
) -> dict[str, Any]:
    async with uow:
        promocodes = await promocode_dao.get_all()
        activation_counts = await promocode_dao.get_activation_counts()
        has_updates = False

        # При открытии списка синхронизируем статусы, чтобы админ видел,
        # какие промокоды уже фактически истекли или исчерпали лимит.
        for promocode in promocodes:
            if promocode.id is None:
                continue

            runtime_state = get_promocode_runtime_state(
                promocode,
                activation_counts.get(promocode.id, 0),
            )
            if promocode.is_active and runtime_state.should_disable:
                promocode.is_active = False
                await promocode_dao.update(promocode.as_fully_changed())
                has_updates = True

        if has_updates:
            await uow.commit()

    return {
        "has_promocodes": bool(promocodes),
        "promocodes": [
            {
                "id": promocode.id,
                "code": promocode.code,
                "is_active": promocode.is_active,
            }
            for promocode in promocodes
            if promocode.id is not None
        ],
    }


@inject
async def configurator_getter(
    dialog_manager: DialogManager,
    i18n: FromDishka[TranslatorRunner],
    retort: FromDishka[Retort],
    **kwargs: Any,
) -> dict[str, Any]:
    raw_promocode = dialog_manager.dialog_data.get(PROMOCODE_DIALOG_DATA_KEY)

    if raw_promocode is None:
        promocode = build_default_promocode()
        dialog_manager.dialog_data[PROMOCODE_DIALOG_DATA_KEY] = retort.dump(promocode)
    else:
        promocode = retort.load(raw_promocode, PromocodeDto)

    if promocode.lifetime is None:
        lifetime_display = i18n.get("unlimited")
    else:
        lifetime_key, lifetime_kwargs = i18n_format_days(promocode.lifetime)
        lifetime_display = i18n.get(lifetime_key, **lifetime_kwargs)

    data = retort.dump(promocode)
    data.update(
        {
            "is_edit": dialog_manager.dialog_data.get("is_edit", False),
            "promocode_type": promocode.reward_type,
            "reward_display": _format_reward(i18n, promocode),
            "lifetime_display": lifetime_display,
            "max_activations_display": i18n.get("unlimited")
            if promocode.max_activations is None
            else str(promocode.max_activations),
        }
    )
    return data


async def type_getter(dialog_manager: DialogManager, **kwargs: Any) -> dict[str, Any]:
    return {"types": list(SUPPORTED_PROMOCODE_REWARD_TYPES)}
