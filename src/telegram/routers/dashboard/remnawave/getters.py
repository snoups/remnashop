from typing import Any, Optional

from aiogram_dialog import DialogManager
from aiogram_dialog.widgets.common import ManagedScroll
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from loguru import logger
from remnapy import RemnawaveSDK

from src.application.common import TranslatorRunner
from src.core.utils.converters import country_code_to_flag, percent
from src.core.utils.i18n_helpers import i18n_format_bytes_to_unit, i18n_format_seconds


@inject
async def system_getter(
    dialog_manager: DialogManager,
    remnawave_sdk: FromDishka[RemnawaveSDK],
    **kwargs: Any,
) -> dict[str, Any]:
    stats = await remnawave_sdk.system.get_stats()
    metadata = await remnawave_sdk.system.get_metadata()
    logger.success(stats)
    return {
        "version": metadata.version,
        "cpu_cores": stats.cpu.cores,
        "ram_used": i18n_format_bytes_to_unit(stats.memory.used),
        "ram_total": i18n_format_bytes_to_unit(stats.memory.total),
        "ram_used_percent": percent(
            part=stats.memory.used or 0,
            whole=stats.memory.total,
        ),
        "uptime": i18n_format_seconds(stats.uptime),
    }


@inject
async def users_getter(
    dialog_manager: DialogManager,
    remnawave_sdk: FromDishka[RemnawaveSDK],
    **kwargs: Any,
) -> dict[str, Any]:
    result = await remnawave_sdk.system.get_stats()

    return {
        "users_total": result.users.total_users,
        "users_active": result.users.status_counts.get("ACTIVE"),
        "users_disabled": result.users.status_counts.get("DISABLED"),
        "users_limited": result.users.status_counts.get("LIMITED"),
        "users_expired": result.users.status_counts.get("EXPIRED"),
        "online_last_day": result.online_stats.last_day,
        "online_last_week": result.online_stats.last_week,
        "online_never": result.online_stats.never_online,
        "online_now": result.online_stats.online_now,
    }


@inject
async def hosts_getter(
    dialog_manager: DialogManager,
    remnawave_sdk: FromDishka[RemnawaveSDK],
    i18n: FromDishka[TranslatorRunner],
    **kwargs: Any,
) -> dict[str, Any]:
    widget: Optional[ManagedScroll] = dialog_manager.find("scroll_hosts")

    if not widget:
        raise ValueError()

    current_page = await widget.get_page()
    result = await remnawave_sdk.hosts.get_all_hosts()
    hosts = []

    for host in result:
        hosts.append(
            i18n.get(
                "msg-remnawave-host-details",
                remark=host.remark,
                is_disabled=host.is_disabled,
                address=host.address,
                port=host.port,
                inbound_uuid=host.inbound_uuid,
            )
        )

    return {
        "pages": len(hosts),
        "current_page": current_page + 1,
        "host": hosts[current_page],
    }


@inject
async def nodes_getter(
    dialog_manager: DialogManager,
    remnawave_sdk: FromDishka[RemnawaveSDK],
    i18n: FromDishka[TranslatorRunner],
    **kwargs: Any,
) -> dict[str, Any]:
    widget: Optional[ManagedScroll] = dialog_manager.find("scroll_nodes")

    if not widget:
        raise ValueError()

    current_page = await widget.get_page()
    result = await remnawave_sdk.nodes.get_all_nodes()
    nodes = []

    for node in result:
        nodes.append(
            i18n.get(
                "msg-remnawave-node-details",
                country=country_code_to_flag(code=node.country_code),
                name=node.name,
                is_connected=node.is_connected,
                address=node.address,
                port=node.port,
                xray_uptime=i18n_format_seconds(node.xray_uptime),
                users_online=node.users_online,
                traffic_used=i18n_format_bytes_to_unit(node.traffic_used_bytes),
                traffic_limit=i18n_format_bytes_to_unit(
                    node.traffic_limit_bytes or None, round_up=True
                ),
            )
        )

    return {
        "pages": len(nodes),
        "current_page": current_page + 1,
        "node": nodes[current_page],
    }


@inject
async def inbounds_getter(
    dialog_manager: DialogManager,
    remnawave_sdk: FromDishka[RemnawaveSDK],
    i18n: FromDishka[TranslatorRunner],
    **kwargs: Any,
) -> dict[str, Any]:
    widget: Optional[ManagedScroll] = dialog_manager.find("scroll_inbounds")

    if not widget:
        raise ValueError()

    current_page = await widget.get_page()
    result = await remnawave_sdk.inbounds.get_all_inbounds()
    inbounds = []

    for inbound in result.inbounds:
        inbounds.append(
            i18n.get(
                "msg-remnawave-inbound-details",
                inbound_id=inbound.uuid,
                tag=inbound.tag,
                type=inbound.type,
                port=inbound.port,
                network=inbound.network,
                security=inbound.security,
            )
        )

    return {
        "pages": len(inbounds),
        "current_page": current_page + 1,
        "inbound": inbounds[current_page],
    }
