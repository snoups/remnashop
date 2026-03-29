from typing import Any

from adaptix import Retort
from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject

from src.application.common import TranslatorRunner
from src.application.common.dao import PromocodeDao
from src.application.common.uow import UnitOfWork
from src.application.dto import PromocodeDto
from src.application.use_cases.promocode.utils import get_promocode_runtime_state
from src.core.enums import PromocodeRewardType


def _build_default_promocode() -> PromocodeDto:
    return PromocodeDto(
        code="",
        is_active=True,
        reward_type=PromocodeRewardType.PURCHASE_DISCOUNT,
        reward=10,
        lifetime=None,
        max_activations=None,
    )


def _format_reward(promocode: PromocodeDto) -> str:
    reward = promocode.reward or 0

    match promocode.reward_type:
        case PromocodeRewardType.PERSONAL_DISCOUNT | PromocodeRewardType.PURCHASE_DISCOUNT:
            return f"{reward}%"
        case PromocodeRewardType.DURATION:
            return f"{reward} дн."
        case PromocodeRewardType.TRAFFIC:
            return f"{reward} ГБ"
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
    raw_promocode = dialog_manager.dialog_data.get(PromocodeDto.__name__)

    if raw_promocode is None:
        promocode = _build_default_promocode()
        dialog_manager.dialog_data[PromocodeDto.__name__] = retort.dump(promocode)
    else:
        promocode = retort.load(raw_promocode, PromocodeDto)

    data = retort.dump(promocode)
    data.update(
        {
            "is_edit": dialog_manager.dialog_data.get("is_edit", False),
            "promocode_type": promocode.reward_type,
            "reward_display": _format_reward(promocode),
            "lifetime_display": i18n.get("unlimited")
            if promocode.lifetime is None
            else f"{promocode.lifetime} дн.",
            "max_activations_display": i18n.get("unlimited")
            if promocode.max_activations is None
            else str(promocode.max_activations),
        }
    )
    return data


async def type_getter(dialog_manager: DialogManager, **kwargs: Any) -> dict[str, Any]:
    return {
        "types": [
            PromocodeRewardType.PERSONAL_DISCOUNT,
            PromocodeRewardType.PURCHASE_DISCOUNT,
            PromocodeRewardType.DURATION,
            PromocodeRewardType.TRAFFIC,
        ]
    }
