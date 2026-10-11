from app.modules.cabinet_auth.deeplink_store import DeeplinkStore
from app.modules.cabinet_auth.dto import TelegramProfileDto


class ConfirmDeeplinkUseCase:
    def __init__(self, store: DeeplinkStore) -> None:
        self._store = store

    async def execute(self, token: str, profile: TelegramProfileDto) -> bool:
        return await self._store.confirm(token, profile)
