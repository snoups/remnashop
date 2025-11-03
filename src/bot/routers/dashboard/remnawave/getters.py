from typing import Any

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from fluentogram import TranslatorRunner
from remnawave import RemnawaveSDK
from remnawave.models import (
    GetAllHostsResponseDto,
    GetAllInboundsResponseDto,
    GetAllNodesResponseDto,
    GetStatsResponseDto,
)

from src.core.i18n.translator import get_translated_kwargs
from src.core.utils.formatters import (
    format_country_code,
    format_percent,
    i18n_format_bytes_to_unit,
    i18n_format_seconds,
)


@inject
async def system_getter(
    dialog_manager: DialogManager,
    remnawave: FromDishka[RemnawaveSDK],
    **kwargs: Any,
) -> dict[str, Any]:
    response = await remnawave.system.get_stats()

    if not isinstance(response, GetStatsResponseDto):
        raise ValueError("Wrong response from Remnawave")

    return {
        "cpu_cores": response.cpu.physical_cores,
        "cpu_threads": response.cpu.cores,
        "ram_used": i18n_format_bytes_to_unit(response.memory.active),
        "ram_total": i18n_format_bytes_to_unit(response.memory.total),
        "ram_used_percent": format_percent(
            part=response.memory.active,
            whole=response.memory.total,
        ),
        "uptime": i18n_format_seconds(response.uptime),
    }


@inject
async def users_getter(
    dialog_manager: DialogManager,
    remnawave: FromDishka[RemnawaveSDK],
    **kwargs: Any,
) -> dict[str, Any]:
    response = await remnawave.system.get_stats()

    if not isinstance(response, GetStatsResponseDto):
        raise ValueError("Wrong response from Remnawave")

    return {
        "users_total": str(response.users.total_users),
        "users_active": str(response.users.status_counts.active),
        "users_disabled": str(response.users.status_counts.disabled),
        "users_limited": str(response.users.status_counts.limited),
        "users_expired": str(response.users.status_counts.expired),
        "online_last_day": str(response.online_stats.last_day),
        "online_last_week": str(response.online_stats.last_week),
        "online_never": str(response.online_stats.never_online),
        "online_now": str(response.online_stats.online_now),
    }


@inject
async def hosts_getter(
    dialog_manager: DialogManager,
    remnawave: FromDishka[RemnawaveSDK],
    i18n: FromDishka[TranslatorRunner],
    **kwargs: Any,
) -> dict[str, Any]:
    response = await remnawave.hosts.get_all_hosts()

    if not isinstance(response, GetAllHostsResponseDto):
        raise ValueError("Wrong response from Remnawave")

    hosts_text = "\n".join(
        i18n.get(
            "msg-remnawave-host-details",
            remark=host.remark,
            status="OFF" if host.is_disabled else "ON",
            address=host.address,
            port=str(host.port),
            inbound_uuid=str(host.inbound_uuid) if host.inbound_uuid else False,
        )
        for host in response
    )

    return {"hosts": hosts_text}


@inject
async def nodes_getter(
    dialog_manager: DialogManager,
    remnawave: FromDishka[RemnawaveSDK],
    i18n: FromDishka[TranslatorRunner],
    **kwargs: Any,
) -> dict[str, Any]:
    response = await remnawave.nodes.get_all_nodes()

    if not isinstance(response, GetAllNodesResponseDto):
        raise ValueError("Wrong response from Remnawave")

    nodes_text = []

    for node in response.root:
        kwargs_for_i18n = {
            "xray_uptime": i18n_format_seconds(node.xray_uptime),
            "traffic_used": i18n_format_bytes_to_unit(node.traffic_used_bytes),
            "traffic_limit": i18n_format_bytes_to_unit(node.traffic_limit_bytes, round_up=True),
        }

        translated_data = get_translated_kwargs(i18n, kwargs_for_i18n)

        nodes_text.append(
            i18n.get(
                "msg-remnawave-node-details",
                country=format_country_code(code=node.country_code),
                name=node.name,
                status="ON" if node.is_connected else "OFF",
                address=node.address,
                port=str(node.port) if node.port else False,
                xray_uptime=translated_data["xray_uptime"],
                users_online=str(node.users_online),
                traffic_used=translated_data["traffic_used"],
                traffic_limit=translated_data["traffic_limit"],
            )
        )

    return {"nodes": "\n".join(nodes_text)}


@inject
async def inbounds_getter(
    dialog_manager: DialogManager,
    remnawave: FromDishka[RemnawaveSDK],
    i18n: FromDishka[TranslatorRunner],
    **kwargs: Any,
) -> dict[str, Any]:
    response = await remnawave.inbounds.get_all_inbounds()

    if not isinstance(response, GetAllInboundsResponseDto):
        raise ValueError("Wrong response from Remnawave")

    inbounds_text = "\n".join(
        i18n.get(
            "msg-remnawave-inbound-details",
            inbound_id=str(inbound.uuid),
            tag=inbound.tag,
            type=inbound.type,
            port=str(int(inbound.port)),
            network=inbound.network or False,
            security=inbound.security or False,
        )
        for inbound in response.inbounds  # type: ignore[attr-defined]
    )

    return {"inbounds": inbounds_text}
