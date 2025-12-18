from typing import Any, Optional

from aiogram_dialog import DialogManager
from aiogram_dialog.widgets.common import ManagedScroll
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from fluentogram import TranslatorRunner
from remnapy import RemnawaveSDK

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
    result = await remnawave.system.get_stats()

    return {
        "version": "",  # TODO: Добавить версию панели
        "cpu_cores": result.cpu.physical_cores,
        "cpu_threads": result.cpu.cores,
        "ram_used": i18n_format_bytes_to_unit(result.memory.active),
        "ram_total": i18n_format_bytes_to_unit(result.memory.total),
        "ram_used_percent": format_percent(
            part=result.memory.active,
            whole=result.memory.total,
        ),
        "uptime": i18n_format_seconds(result.uptime),
    }


@inject
async def users_getter(
    dialog_manager: DialogManager,
    remnawave: FromDishka[RemnawaveSDK],
    **kwargs: Any,
) -> dict[str, Any]:
    result = await remnawave.system.get_stats()

    return {
        "users_total": str(result.users.total_users),
        "users_active": str(result.users.status_counts.get("ACTIVE")),
        "users_disabled": str(result.users.status_counts.get("DISABLED")),
        "users_limited": str(result.users.status_counts.get("LIMITED")),
        "users_expired": str(result.users.status_counts.get("EXPIRED")),
        "online_last_day": str(result.online_stats.last_day),
        "online_last_week": str(result.online_stats.last_week),
        "online_never": str(result.online_stats.never_online),
        "online_now": str(result.online_stats.online_now),
    }


@inject
async def hosts_getter(
    dialog_manager: DialogManager,
    remnawave: FromDishka[RemnawaveSDK],
    i18n: FromDishka[TranslatorRunner],
    **kwargs: Any,
) -> dict[str, Any]:
    widget: Optional[ManagedScroll] = dialog_manager.find("scroll_hosts")

    if not widget:
        raise ValueError()

    current_page = await widget.get_page()
    result = await remnawave.hosts.get_all_hosts()
    hosts = []

    for host in result:
        hosts.append(
            i18n.get(
                "msg-remnawave-host-details",
                remark=host.remark,
                status="OFF" if host.is_disabled else "ON",
                address=host.address,
                port=str(host.port),
                inbound_uuid=str(host.inbound_uuid) if host.inbound_uuid else False,
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
    remnawave: FromDishka[RemnawaveSDK],
    i18n: FromDishka[TranslatorRunner],
    **kwargs: Any,
) -> dict[str, Any]:
    widget: Optional[ManagedScroll] = dialog_manager.find("scroll_nodes")

    if not widget:
        raise ValueError()

    current_page = await widget.get_page()
    result = await remnawave.nodes.get_all_nodes()
    nodes = []

    for node in result:
        kwargs_for_i18n = {
            "xray_uptime": i18n_format_seconds(node.xray_uptime),
            "traffic_used": i18n_format_bytes_to_unit(node.traffic_used_bytes),
            "traffic_limit": i18n_format_bytes_to_unit(
                node.traffic_limit_bytes or -1, round_up=True
            ),
        }

        translated_data = get_translated_kwargs(i18n, kwargs_for_i18n)

        nodes.append(
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

    return {
        "pages": len(nodes),
        "current_page": current_page + 1,
        "node": nodes[current_page],
    }


@inject
async def inbounds_getter(
    dialog_manager: DialogManager,
    remnawave: FromDishka[RemnawaveSDK],
    i18n: FromDishka[TranslatorRunner],
    **kwargs: Any,
) -> dict[str, Any]:
    widget: Optional[ManagedScroll] = dialog_manager.find("scroll_inbounds")

    if not widget:
        raise ValueError()

    current_page = await widget.get_page()
    result = await remnawave.inbounds.get_all_inbounds()
    inbounds = []

    for inbound in result.inbounds:  # type: ignore[attr-defined]
        inbounds.append(
            i18n.get(
                "msg-remnawave-inbound-details",
                inbound_id=str(inbound.uuid),
                tag=inbound.tag,
                type=inbound.type,
                port=str(int(inbound.port)) if inbound.port else False,
                network=inbound.network or False,
                security=inbound.security or False,
            )
        )

    return {
        "pages": len(inbounds),
        "current_page": current_page + 1,
        "inbound": inbounds[current_page],
    }
