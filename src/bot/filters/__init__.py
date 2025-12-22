from aiogram import Router

from .private import PrivateFilter

__all__ = [
    "SuperDevFilter",
    "setup_global_filters",
]


def setup_global_filters(router: Router) -> None:
    filters = [
        PrivateFilter(),  # global filter allows only private chats
    ]

    for filter in filters:
        router.message.filter(filter)
