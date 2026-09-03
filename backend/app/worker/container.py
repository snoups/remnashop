from dishka import AsyncContainer, Provider, Scope, make_async_container

from app.core.config import AppConfig
from app.core.di.providers import get_core_providers
from app.modules.auth import SessionRepository
from app.modules.backups import BackupRepository
from app.modules.event_log import get_event_log_providers
from app.modules.oauth import OAuthIdentityRepository
from app.modules.payments import PaymentOrderRepository
from app.modules.plans import PlanRepository
from app.modules.referrals import get_referrals_providers
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
    # app.modules.users.get_users_providers() -- that provider also registers
    # admin usecases (e.g. UpdateAdminUseCase) that depend on SessionRevoker,
    # which only the api/telegram containers wire up.
    user_repository_provider = Provider(scope=Scope.REQUEST)
    user_repository_provider.provide(UserRepository)

    # PaymentOrderRepository is provided directly here, not via
    # app.modules.payments.get_payments_providers() -- that provider also
    # registers CreateCheckoutUseCase, which depends on GatewaysRepository and
    # the full plans/users usecase graph that only the api container wires up.
    # The prune task only needs the repository.
    payment_order_repository_provider = Provider(scope=Scope.REQUEST)
    payment_order_repository_provider.provide(PaymentOrderRepository)

    # SessionRepository is provided directly here, not via
    # app.modules.auth.get_auth_providers() -- that provider also registers
    # the full login usecase graph. The prune task only needs the
    # repository.
    session_repository_provider = Provider(scope=Scope.REQUEST)
    session_repository_provider.provide(SessionRepository)

    # OAuthIdentityRepository is provided directly here, not via
    # app.modules.oauth.get_oauth_providers() -- the OIDC-issuer cleanup task
    # only needs the repository, not the full OAuth usecase graph.
    oauth_identity_repository_provider = Provider(scope=Scope.REQUEST)
    oauth_identity_repository_provider.provide(OAuthIdentityRepository)

    # BackupRepository is provided directly here, not via
    # app.modules.backups.get_backups_providers() -- that provider also
    # registers CreateBackupRunUseCase (which needs a RunBackupDispatch and
    # the full request-scoped graph only api/telegram wire up). worker's two
    # backup tasks only need the repository.
    backup_repository_provider = Provider(scope=Scope.REQUEST)
    backup_repository_provider.provide(BackupRepository)

    # PlanRepository is provided directly here, not via
    # app.modules.plans.get_plans_providers() -- no worker task needs the
    # plans usecase graph. It's still required: SubscriptionsProvider now
    # includes GetAvailableTrialUseCase, which depends on PlanRepository,
    # and dishka validates every provide()-registered factory's full
    # dependency graph at container build time regardless of whether a
    # worker task actually calls that usecase.
    plan_repository_provider = Provider(scope=Scope.REQUEST)
    plan_repository_provider.provide(PlanRepository)

    context = {AppConfig: config}
    providers = [
        *get_core_providers(),
        *get_event_log_providers(),
        *get_referrals_providers(),
        *get_settings_providers(),
        *get_subscriptions_providers(),
        *get_translations_providers(),
        user_repository_provider,
        payment_order_repository_provider,
        session_repository_provider,
        oauth_identity_repository_provider,
        backup_repository_provider,
        plan_repository_provider,
    ]
    return make_async_container(*providers, context=context)
