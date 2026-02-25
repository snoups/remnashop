from dishka import Provider, Scope, provide_all

from src.application.use_cases.access import ACCESS_USE_CASES
from src.application.use_cases.broadcast import BROADCAST_USE_CASES
from src.application.use_cases.logs import LOGS_USE_CASES
from src.application.use_cases.menu import MENU_USE_CASES
from src.application.use_cases.menu_editor import MENU_EDITOR_USE_CASES
from src.application.use_cases.payment_gateway import GATEWAYS_USE_CASES
from src.application.use_cases.plan import PLAN_USE_CASES
from src.application.use_cases.redirect import REDIRECT_USE_CASES
from src.application.use_cases.referral import REFERRAL_USE_CASES
from src.application.use_cases.remnawave import REMNAWAVE_USE_CASES
from src.application.use_cases.settings import SETTINGS_USE_CASES
from src.application.use_cases.subscription import SUBSCRIPTION_USE_CASES
from src.application.use_cases.user import USER_USE_CASES


class UseCasesProvider(Provider):
    scope = Scope.REQUEST

    use_cases = provide_all(
        *ACCESS_USE_CASES,
        *BROADCAST_USE_CASES,
        *LOGS_USE_CASES,
        *MENU_USE_CASES,
        *MENU_EDITOR_USE_CASES,
        *GATEWAYS_USE_CASES,
        *PLAN_USE_CASES,
        *REDIRECT_USE_CASES,
        *REFERRAL_USE_CASES,
        *REMNAWAVE_USE_CASES,
        *SETTINGS_USE_CASES,
        *SUBSCRIPTION_USE_CASES,
        *USER_USE_CASES,
    )
