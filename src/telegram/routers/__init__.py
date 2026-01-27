from aiogram import Router

from . import dashboard, extra, menu


def setup_routers(router: Router) -> None:
    # WARNING: The order of router registration matters!
    routers = [
        extra.payment.router,
        extra.notification.router,
        extra.test.router,
        extra.commands.router,
        extra.member.router,
        extra.goto.router,
        #
        menu.handlers.router,
        menu.dialog.router,
        #
        dashboard.dialog.router,
        dashboard.access.dialog.router,
        dashboard.remnawave.dialog.router,
        #
        dashboard.remnashop.dialog.router,
        # dashboard.remnashop.gateways.dialog.router,
        dashboard.remnashop.referral.dialog.router,
        dashboard.remnashop.notifications.dialog.router,
        dashboard.remnashop.plans.dialog.router,
        #
        dashboard.users.dialog.router,
        dashboard.users.user.dialog.router,
    ]

    router.include_routers(*routers)
