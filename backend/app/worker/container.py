from dishka import AsyncContainer, Provider, Scope, make_async_container

from app.core.config import AppConfig
from app.core.di.providers import get_core_providers
from app.modules.event_log import get_event_log_providers
from app.modules.plans import get_plans_providers
from app.modules.settings import get_settings_providers
from app.modules.subscriptions import get_subscriptions_providers
from app.modules.translations import get_translations_providers
from app.modules.users import UserRepository


def create_worker_container(config: AppConfig) -> AsyncContainer:
    # Kept in sync by hand with docker-entrypoint.sh's `taskiq worker ...` task
    # module list -- a new worker-task module needs both its task module added
    # there AND its providers added here. Dishka doesn't catch a forgotten
    # provider at container build time for FromDishka-injected task params
    # (only for provide()-registered classes); it only fails every time that
    # task actually runs. See tests/worker/test_container.py.
    #
    # UserRepository is provided directly here, not via
    # app.modules.users.get_user_providers() -- that provider also registers
    # admin usecases (e.g. UpdateAdminUseCase) that depend on SessionRevoker,
    # which only the api/telegram containers wire up.
    user_repository_provider = Provider(scope=Scope.REQUEST)
    user_repository_provider.provide(UserRepository)

    context = {AppConfig: config}
    providers = [
        *get_core_providers(),
        *get_event_log_providers(),
        *get_plans_providers(),
        *get_settings_providers(),
        *get_subscriptions_providers(),
        *get_translations_providers(),
        user_repository_provider,
    ]
    return make_async_container(*providers, context=context)
