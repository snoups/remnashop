from aiogram import Router

from app.telegram.filters.private import PrivateFilter

__all__ = [
    "setup_global_filters",
]


def setup_global_filters(router: Router) -> None:
    router.message.filter(PrivateFilter())
