from dishka.integrations.taskiq import FromDishka, inject

from app.modules.oauth.usecases import CleanupOidcIdentitiesUseCase
from app.worker.broker import broker


@broker.task
@inject(patch_module=True)
async def cleanup_oidc_identities_task(use_case: FromDishka[CleanupOidcIdentitiesUseCase]) -> None:
    await use_case.system()
