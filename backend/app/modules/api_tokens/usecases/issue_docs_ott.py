from typing import Final

from app.core.actor import Actor
from app.core.config import AppConfig
from app.core.security import create_docs_token
from app.core.security.permissions import Permission
from app.core.usecase import UseCase

_DOCS_OTT_TTL: Final[int] = 30


class IssueDocsOttUseCase(UseCase[None, str]):
    # the docs list every endpoint a token can be scoped to
    required_permission = Permission.API_TOKENS_MANAGE

    def __init__(self, config: AppConfig) -> None:
        self._config = config

    async def _execute(self, actor: Actor, data: None) -> str:
        return create_docs_token("ott", _DOCS_OTT_TTL, self._config.jwt_secret.get_secret_value())
