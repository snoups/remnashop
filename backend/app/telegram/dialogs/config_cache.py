import asyncio
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.enums import DialogWindowKind
from app.modules.dialogs import DialogButtonDto, DialogRepository, DialogWindowDto


class DialogConfigCache:
    def __init__(self, session_maker: async_sessionmaker[AsyncSession]) -> None:
        self._session_maker = session_maker
        self._windows: dict[str, DialogWindowDto] = {}
        self._custom_slots: dict[str, int] = {}
        self._keys_by_slot: dict[int, str] = {}
        self._loaded = asyncio.Event()

    async def reload(self) -> None:
        async with self._session_maker() as session:
            windows = await DialogRepository(session).list_all()
        self._windows = {window.key: window for window in windows}
        self._custom_slots = {
            window.key: window.slot
            for window in windows
            if window.kind == DialogWindowKind.CUSTOM and window.slot is not None
        }
        self._keys_by_slot = {slot: key for key, slot in self._custom_slots.items()}
        self._loaded.set()

    async def _ensure_loaded(self) -> None:
        if not self._loaded.is_set():
            await self.reload()

    async def get_window(self, key: str) -> DialogWindowDto:
        await self._ensure_loaded()
        return self._windows[key]

    async def get_button(self, window_key: str, button_id: int) -> Optional[DialogButtonDto]:
        await self._ensure_loaded()
        window = self._windows.get(window_key)
        if window is None:
            return None
        for button in window.buttons:
            if button.id == button_id:
                return button
        return None

    async def custom_window_slot(self, window_key: str) -> Optional[int]:
        await self._ensure_loaded()
        return self._custom_slots.get(window_key)

    async def key_for_slot(self, slot: int) -> Optional[str]:
        await self._ensure_loaded()
        return self._keys_by_slot.get(slot)
